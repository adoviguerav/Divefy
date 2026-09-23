"""Config de experimento: una config = una fila de la tabla. Nombre canónico corpus-tope-extras-embedding."""

from dataclasses import dataclass

from divefy.pipeline.p4_vectorstore import canonical_name

CORPUS_VALUES = ("apuntes", "manual", "combined")
EXTRAS_VALUES = ("base", "contextual", "hype")
EMBEDDING_VALUES = ("bgem3", "qwen06b", "qwen8b", "openai3large")
SEARCH_VALUES = ("densa", "hibrida")
K_VALUES = (3, 5, 10)


@dataclass(frozen=True)
class RetrievalConfig:
    """Una config de retrieval = un brazo del grid. `cap` no se valida (decisión
    de Adolfo, Notas del plan de Fase 5): la validez real de un cap la impone el
    marcador `.complete` de su colección en runtime, no el dataclass."""

    corpus: str
    extras: str
    embedding: str
    search: str
    k: int
    cap: int = 512
    rerank: bool = False

    def __post_init__(self):
        for campo, valor, permitidos in (
            ("corpus", self.corpus, CORPUS_VALUES),
            ("extras", self.extras, EXTRAS_VALUES),
            ("embedding", self.embedding, EMBEDDING_VALUES),
            ("search", self.search, SEARCH_VALUES),
            ("k", self.k, K_VALUES),
        ):
            if valor not in permitidos:
                raise ValueError(f"{campo}={valor!r} no está en {permitidos}")

    @property
    def collection(self) -> str:
        return canonical_name(self.corpus, self.cap, self.extras, self.embedding)

    @property
    def run_id(self) -> str:
        base = f"{self.collection}-{self.search}-k{self.k}"
        return f"{base}-rerank" if self.rerank else base


# Receta ganadora medida en Fase 5/6 (EXPERIMENTOS.md): hit_rate 0.9881, MRR 0.815
# — la que usa el chat (Fase 8) por defecto.
RECETA_GANADORA = RetrievalConfig(
    corpus="combined", extras="contextual", embedding="qwen8b",
    search="hibrida", k=10, cap=512, rerank=True,
)
