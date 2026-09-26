"""Phase 9: the results table, generated from `results/` into the README (never by hand).

Two views: (1) retrieval, changing one setting at a time from the best configuration,
with the hit_rate difference; (2) generation, the models measured on that configuration.
The table lives in README.md between two marker comments; this script rewrites only
that block.

    uv run python -m divefy.evals.results_table
"""

import json
import re
from pathlib import Path

from divefy.config import RECETA_GANADORA, RetrievalConfig

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results"
README = REPO_ROOT / "README.md"
START, END = "<!-- results-table:start -->", "<!-- results-table:end -->"
DIMENSIONS = ("corpus", "cap", "extras", "embedding", "search", "k", "rerank")


def load(results_dir: Path = RESULTS_DIR) -> tuple[dict[str, dict], dict[str, dict]]:
    """(retrieval, generation) rows by run_id; a row with `model` is a generation row."""
    retrieval, generation = {}, {}
    for path in sorted(results_dir.glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        config = row.get("config", {})
        if "run_id" not in config:
            continue
        (generation if "model" in config else retrieval)[config["run_id"]] = row
    return retrieval, generation


def _run_id(base: RetrievalConfig, **change) -> str:
    values = {d: getattr(base, d) for d in DIMENSIONS}
    values.update(change)
    return RetrievalConfig(**values).run_id


def sweep(retrieval: dict[str, dict], base: RetrievalConfig = RECETA_GANADORA) -> list[dict]:
    """One row per measured arm: one setting changed from `base`, plus hit_rate delta."""
    base_row = retrieval.get(base.run_id)
    base_hit = base_row["resumen"]["hit_rate"] if base_row else None
    rows = []
    for dim in DIMENSIONS:
        # Rows older than phase 6 carry no `rerank` key: they ran without it.
        values = sorted({r["config"].get(dim, False) for r in retrieval.values()}, key=str)
        for value in values:
            row = retrieval.get(_run_id(base, **{dim: value}))
            if row is None:
                continue
            s = row["resumen"]
            rows.append({
                "dimension": dim, "value": value, "is_base": value == getattr(base, dim),
                "hit_rate": s["hit_rate"], "recall": s["recall"], "mrr": s["mrr"],
                "tokens": s["tokens_recuperados_media"],
                "delta_hit": None if base_hit is None else round(s["hit_rate"] - base_hit, 4),
            })
    return rows


def models_on_base(generation: dict[str, dict], base: RetrievalConfig = RECETA_GANADORA) -> list[dict]:
    rows = []
    for row in generation.values():
        c, s = row["config"], row["resumen"]
        if c["run_id"] != f"{base.run_id}-{c['model']}":
            continue
        rows.append({
            "model": c["model"], "pass_rate": s["tasa_aprobado"], "mean_score": s["score_medio"],
            "abstentions": s["abstenciones"], "n": s["n"],
            "prompt": c.get("prompt_version_generacion"), "judge": c.get("prompt_version_juez"),
        })
    return sorted(rows, key=lambda r: -r["pass_rate"])


def render(sweep_rows: list[dict], model_rows: list[dict], base: RetrievalConfig = RECETA_GANADORA) -> str:
    out = [f"Best configuration: `{base.run_id}`. 84 exam questions; one question is about 1.2 points.", "",
           "Retrieval, changing one setting at a time from the best configuration:", "",
           "| setting | value | hit_rate | vs best | recall | MRR | tokens |",
           "|---|---|---|---|---|---|---|"]
    for r in sweep_rows:
        value = f"**{r['value']}** (best)" if r["is_base"] else str(r["value"])
        delta = "" if r["delta_hit"] is None else f"{r['delta_hit']:+.4f}"
        out.append(f"| {r['dimension']} | {value} | {r['hit_rate']:.4f} | {delta} | "
                   f"{r['recall']:.4f} | {r['mrr']:.4f} | {r['tokens']:.0f} |")
    out += ["", "Generation, each model on the best configuration:", "",
            "| model | passed | mean score | abstentions | prompt | judge |",
            "|---|---|---|---|---|---|"]
    for m in model_rows:
        out.append(f"| {m['model']} | {m['pass_rate']:.1%} ({round(m['pass_rate'] * m['n'])}/{m['n']}) | "
                   f"{m['mean_score']:.3f} | {m['abstentions']} | {m['prompt']} | {m['judge']} |")
    return "\n".join(out)


def update_readme(table: str, readme: Path = README) -> None:
    """Replace the block between the markers; fail loudly if the markers are missing."""
    text = readme.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise ValueError(f"{readme} has no {START} / {END} markers")
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        lambda _: f"{START}\n{table}\n{END}",
        text, count=1, flags=re.DOTALL,
    )
    readme.write_text(new, encoding="utf-8")


def main(results_dir: Path = RESULTS_DIR, readme: Path = README) -> str:
    retrieval, generation = load(results_dir)
    table = render(sweep(retrieval), models_on_base(generation))
    update_readme(table, readme)
    print(table)
    return table


if __name__ == "__main__":
    main()
