"""Unit — the results table is built from results/ rows and written into the README block."""

import json

import pytest

from divefy.config import RECETA_GANADORA, RetrievalConfig
from divefy.evals import results_table as rt


def _retrieval_row(config: RetrievalConfig, hit: float) -> dict:
    return {
        "config": {**{d: getattr(config, d) for d in rt.DIMENSIONS},
                   "collection": config.collection, "run_id": config.run_id},
        "resumen": {"hit_rate": hit, "recall": 0.6, "mrr": 0.8, "tokens_recuperados_media": 3000.0},
        "detalle": [],
    }


def _generation_row(config: RetrievalConfig, model: str, rate: float) -> dict:
    return {
        "config": {"run_id": f"{config.run_id}-{model}", "model": model,
                   "prompt_version_generacion": "generation_v2", "prompt_version_juez": "judge_v3"},
        "resumen": {"n": 84, "aprobado": round(rate * 84), "suspenso": 0, "abstenciones": 1,
                    "tasa_aprobado": rate, "score_medio": 0.8},
        "detalle": [],
    }


@pytest.fixture
def results(tmp_path):
    base = RECETA_GANADORA
    k3 = RetrievalConfig(base.corpus, base.extras, base.embedding, base.search, 3, rerank=True)
    for row in (_retrieval_row(base, 0.9881), _retrieval_row(k3, 0.869),
                _generation_row(base, "sonnet5", 0.8333)):
        (tmp_path / f"{row['config']['run_id']}.json").write_text(json.dumps(row))
    return tmp_path


def test_sweep_marks_base_and_computes_delta(results):
    retrieval, generation = rt.load(results)
    rows = rt.sweep(retrieval)
    by_k = {r["value"]: r for r in rows if r["dimension"] == "k"}
    assert by_k[10]["is_base"] and by_k[10]["delta_hit"] == 0.0
    assert not by_k[3]["is_base"] and by_k[3]["delta_hit"] == round(0.869 - 0.9881, 4)
    assert sum(r["is_base"] for r in rows) == len(rt.DIMENSIONS), "the base shows once per setting"
    assert [m["model"] for m in rt.models_on_base(generation)] == ["sonnet5"]


def test_main_rewrites_only_the_readme_block(results, tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(f"intro\n\n{rt.START}\nold table\n{rt.END}\n\nfooter\n")
    table = rt.main(results, readme)
    text = readme.read_text()
    assert text.startswith("intro\n\n") and text.endswith("\n\nfooter\n"), "text outside the block is untouched"
    assert "old table" not in text and table in text
    assert "**10** (best)" in text and "| sonnet5 | 83.3% (70/84)" in text


def test_missing_markers_fail_loudly(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("no markers here\n")
    with pytest.raises(ValueError):
        rt.update_readme("table", readme)
