"""Fase 2 — Chunking estructural: granularidad subsección, tope parametrizado (tokenizador BGE-M3), splitter recursivo interno."""

import json
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Callable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from divefy.pipeline.p1_ingest import Record


@dataclass(frozen=True)
class Chunk:
    """Un trozo indexable: su texto y las secciones de origen (Fase 1) con las que
    solapa — más de una si el splitter empaquetó varias juntas. El resto de metadatos
    (corpus, título, página...) no se copian: se leen de `origen` bajo demanda, para no
    repetir los mismos campos que ya declara `Record`."""

    texto: str
    origen: list[Record]
    id: str = ""  # calculado en trocear_registros — de contenido, no de posición
    n_tokens: int = 0  # tokens BGE-M3 de `texto` — la vara única del grid (docs/modelo-datos.md)

    @property
    def corpus(self) -> str:
        return self.origen[0].corpus

    @property
    def titulo(self) -> str:
        return self.origen[0].titulo

    @property
    def tipo(self) -> str:
        return self.origen[0].tipo

    @property
    def fichero(self) -> str | None:
        return self.origen[0].fichero

    @property
    def capitulo(self) -> int | None:
        return self.origen[0].capitulo

    @property
    def pagina(self) -> int | None:
        return self.origen[0].pagina

    @property
    def pagina_fin(self) -> int | None:
        return self.origen[-1].pagina

    @property
    def section_ids(self) -> list[str]:
        return [r.section_id for r in self.origen]

    def to_dict(self) -> dict:
        """Forma plana para chunks.jsonl — el contrato de fichero no cambia,
        solo cómo vive en memoria."""
        return {
            "id": self.id,
            "corpus": self.corpus,
            "section_ids": self.section_ids,
            "titulo": self.titulo,
            "tipo": self.tipo,
            "texto": self.texto,
            "fichero": self.fichero,
            "capitulo": self.capitulo,
            "pagina": self.pagina,
            "pagina_fin": self.pagina_fin,
            "n_tokens": self.n_tokens,
        }


UMBRAL_MINUSCULA = 50  # tokens BGE-M3: por debajo, la sección se funde con una vecina (PRD Fase 2)


def _clave_frontera(r: Record) -> tuple:
    """Frontera de documento que una fusión nunca puede cruzar: mismo fichero en
    apuntes, mismo capítulo en el manual."""
    return (r.corpus, r.fichero if r.corpus == "apuntes" else r.capitulo)


def _texto_fundido(fundido: list[Record]) -> str:
    return "\n\n".join(r.texto for r in fundido)


def fundir_minusculas(
    registros: list[Record], contar: Callable[[str], int], umbral: int = UMBRAL_MINUSCULA
) -> list[list[Record]]:
    """Agrupa por frontera de documento (fichero/capítulo — ya vienen contiguos en
    corpus.jsonl) y, dentro de cada grupo, funde cada sección bajo el umbral con la
    anterior ya aceptada. Si la(s) primera(s) del grupo siguen bajo el umbral al no
    tener anterior, se funden hacia la que sigue."""
    resultado: list[list[Record]] = []
    for _clave, grupo in groupby(registros, key=_clave_frontera):
        fundidos: list[list[Record]] = []
        for r in grupo:
            if fundidos and contar(r.texto) < umbral:
                fundidos[-1].append(r)
            else:
                fundidos.append([r])

        while len(fundidos) > 1 and contar(_texto_fundido(fundidos[0])) < umbral:
            fundidos[1] = fundidos[0] + fundidos[1]
            fundidos.pop(0)

        resultado.extend(fundidos)
    return resultado


def trocear_registros(registros: list[Record], tope: int, contar: Callable[[str], int]) -> list[Chunk]:
    """Prosa: cada sección es su propio trozo, salvo que sea minúscula (funde con una
    vecina, ver `fundir_minusculas`) o se pase del tope (se parte con el splitter
    recursivo de LangChain — los trozos resultantes heredan las secciones de origen).
    Punteros de tabla: pasan sin tocar, ya son un trozo por tabla (Fase 1)."""
    prosa = [r for r in registros if r.tipo == "prosa"]
    punteros = [r for r in registros if r.tipo == "puntero_tabla"]

    splitter = RecursiveCharacterTextSplitter(chunk_size=tope, chunk_overlap=0, length_function=contar)

    chunks: list[Chunk] = []
    for fundido in fundir_minusculas(prosa, contar):
        texto = _texto_fundido(fundido)
        partes = splitter.split_text(texto) if contar(texto) > tope else [texto]
        base_id = "|".join(r.section_id for r in fundido)
        for i, parte in enumerate(partes):
            id_parte = base_id if len(partes) == 1 else f"{base_id}#{i}"
            chunks.append(Chunk(texto=parte, origen=fundido, id=id_parte, n_tokens=contar(parte)))

    for r in punteros:
        chunks.append(Chunk(texto=r.texto, origen=[r], id=r.section_id, n_tokens=contar(r.texto)))

    return chunks


def cargar_tokenizer_bge_m3():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained("BAAI/bge-m3")


def cargar_corpus(processed_dir: Path) -> list[Record]:
    registros = []
    with (processed_dir / "corpus.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                registros.append(Record(**json.loads(line)))
    return registros


def escribir_chunks(chunks: list[Chunk], processed_dir: Path) -> None:
    ids = [c.id for c in chunks]
    if len(ids) != len(set(ids)):
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"ids de chunk repetidos (no debería pasar nunca): {repetidos}")

    processed_dir.mkdir(parents=True, exist_ok=True)
    with (processed_dir / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")

    review_dir = processed_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    grupos: dict[str, list[Chunk]] = {}
    for c in chunks:
        clave = f"cap-{c.capitulo:02d}" if c.corpus == "manual" else "apuntes"
        grupos.setdefault(clave, []).append(c)

    for clave, cs in grupos.items():
        lineas = ["<!-- DERIVADO — no consumir -->", ""]
        for c in cs:
            lineas.append(f"## {c.titulo}  `{','.join(c.section_ids)}`")
            lineas.append("")
            lineas.append(c.texto)
            lineas.append("")
        (review_dir / f"chunks-{clave}.md").write_text("\n".join(lineas), encoding="utf-8")


def main(tope: int = 512) -> None:
    processed_dir = Path("data/processed")
    registros = cargar_corpus(processed_dir)
    tokenizer = cargar_tokenizer_bge_m3()
    chunks = trocear_registros(registros, tope, lambda t: len(tokenizer.tokenize(t)))
    escribir_chunks(chunks, processed_dir)


if __name__ == "__main__":
    main()
