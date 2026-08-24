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
            "corpus": self.corpus,
            "section_ids": self.section_ids,
            "titulo": self.titulo,
            "tipo": self.tipo,
            "texto": self.texto,
            "fichero": self.fichero,
            "capitulo": self.capitulo,
            "pagina": self.pagina,
            "pagina_fin": self.pagina_fin,
        }


def _clave_frontera(r: Record) -> tuple:
    """Frontera de documento que el splitter nunca puede cruzar: mismo fichero en
    apuntes, mismo capítulo en el manual."""
    return (r.corpus, r.fichero if r.corpus == "apuntes" else r.capitulo)


def trocear_registros(registros: list[Record], tope: int, contar: Callable[[str], int]) -> list[Chunk]:
    """Prosa: por cada frontera de documento, une el texto de sus secciones y deja
    que RecursiveCharacterTextSplitter empaquete libremente hasta el tope (junta
    secciones pequeñas, parte las que no caben). Cada trozo resultante se atribuye a
    las secciones de origen con las que solapa, por posición de caracteres. Punteros
    de tabla: pasan sin tocar, ya son un trozo por tabla (Fase 1)."""
    prosa = [r for r in registros if r.tipo == "prosa"]
    punteros = [r for r in registros if r.tipo == "puntero_tabla"]

    splitter = RecursiveCharacterTextSplitter(chunk_size=tope, chunk_overlap=0, length_function=contar)

    chunks: list[Chunk] = []
    for _clave, grupo_iter in groupby(prosa, key=_clave_frontera):
        grupo = list(grupo_iter)
        texto_completo = "\n\n".join(r.texto for r in grupo)

        rangos = []  # (inicio, fin, registro) — posición de cada sección en texto_completo
        cursor = 0
        for i, r in enumerate(grupo):
            if i > 0:
                cursor += 2  # el "\n\n" del join
            rangos.append((cursor, cursor + len(r.texto), r))
            cursor += len(r.texto)

        cursor_busqueda = 0
        for parte in splitter.split_text(texto_completo):
            pos = texto_completo.find(parte, cursor_busqueda)
            fin = pos + len(parte)
            cursor_busqueda = fin  # avanza más allá de este trozo: sin solape (chunk_overlap=0),
            # evita reencontrar una ocurrencia anterior si el texto repite una frase
            solapan = [r for inicio_r, fin_r, r in rangos if inicio_r < fin and fin_r > pos]
            chunks.append(Chunk(texto=parte, origen=solapan))

    for r in punteros:
        chunks.append(Chunk(texto=r.texto, origen=[r]))

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
