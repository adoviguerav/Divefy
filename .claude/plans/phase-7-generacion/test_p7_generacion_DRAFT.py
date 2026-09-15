"""Acceptance tests for Fase 7 — generation, guardrail and LLM evaluator.

Scope (one class per acceptance criterion):
  1. TestLlmInterface        — single `generate(model, system, user)` seam; `answer()`
                               builds the complete state (pregunta, chunks, respuesta)
                               with a fake backend, no network.
  2. TestAbstencion          — empty support => response is EXACTLY the public
                               abstention template constant.
  4. TestGuardrail           — deterministic number check over 10 synthetic responses
                               (5 good / 5 altered) + observable retry-once policy.
  5. TestConstantesCheatsheet — schema of data/guardrail/constantes.jsonl.
  6. TestLlmEvaluator        — `run()` yields per-question verdicts + aggregates with
                               fake generator and fake judge; run_id includes the model.
  7. TestPromptVersioning    — result row records prompt_version (generation + judge)
                               traceable to real files under prompts/.

Criteria 3, 8 and 9 are inspection-only (procedural step formatting, judge
calibration, real model rows in results/) and are NOT tested here.

Criteria 6-7 are marked `slow` (the shared fixture runs the full eval set
through real local retrieval) and run only with the slow marker (/verify gate).

These tests are written BEFORE the implementation. On first run they must fail
RED with ImportError/AttributeError raised INSIDE the tests/fixtures — hence
every `divefy.*` import lives inside a test function or fixture, never at
module level. Tests never write to data/, results/ or data/chroma/.
"""

import dataclasses
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = ROOT / "data" / "chroma"
COLLECTION = "combined-512-contextual-bgem3"
COLLECTION_MARKER = CHROMA_DIR / f"{COLLECTION}.complete"
CONSTANTES_PATH = ROOT / "data" / "guardrail" / "constantes.jsonl"
GOLDEN_PATH = ROOT / "data" / "eval" / "golden.jsonl"
PROMPTS_DIR = ROOT / "prompts"

# Fresh plain-Spanish questions written for these tests — never from the golden dataset.
Q_AIRE = "¿Qué hago si el aire de mi botella se está agotando durante la inmersión?"
Q_ASCENSO = "¿A qué velocidad debo subir hacia la superficie para hacerlo con seguridad?"
Q_SIN_SOPORTE = "¿Qué marca de neopreno me recomiendas comprar para bucear en aguas frías?"

VERDICTS = {"aprobado", "suspenso", "abstención", "abstencion"}

CONSTANTES_HINT = "create the constants cheat-sheet (data/guardrail/constantes.jsonl)"


def _require(path, hint):
    if not Path(path).exists():
        pytest.skip(f"missing {path} — {hint}")


def _fake_generate(replies):
    """Return (fake, calls). Replies are consumed in order; the last one repeats."""
    calls = []

    def fake(model, system, user):
        calls.append({"model": model, "system": system, "user": user})
        return replies[min(len(calls) - 1, len(replies) - 1)]

    return fake, calls


def _patch_generate(monkeypatch, replies):
    import divefy.llm as llm

    fake, calls = _fake_generate(replies)
    monkeypatch.setattr(llm, "generate", fake)
    return calls


@pytest.fixture(scope="module")
def store_ready():
    _require(CHROMA_DIR, "run p4 indexing first")
    _require(COLLECTION_MARKER, f"index the {COLLECTION} collection (p4) first")


@pytest.fixture(scope="module")
def retrieval_config(store_ready):
    from divefy.config import RetrievalConfig

    return RetrievalConfig(
        corpus="combined",
        extras="contextual",
        embedding="bgem3",
        search="hibrida",
        k=5,
        cap=512,
    )


# ---------------------------------------------------------------------------
# Criterion 1 — one signature for all models; answer() builds the full state
# ---------------------------------------------------------------------------


class TestLlmInterface:
    def test_answer_builds_complete_state_with_fake_backend(
        self, monkeypatch, retrieval_config
    ):
        """El test central: con un muñeco en lugar del LLM, answer() debe llamar al
        modelo UNA vez, pasarle la pregunta dentro del prompt, y devolver el paquete
        completo — pregunta, trozos del corpus con sus fuentes, y la respuesta tal
        cual la dio el modelo, sin retocar."""
        _require(CONSTANTES_PATH, CONSTANTES_HINT)

        model = "fake-model"
        # Reply carries no digits so the guardrail has nothing to verify.
        reply = "Avisa a tu compañero, comparte aire si hace falta y asciende con calma."
        calls = _patch_generate(monkeypatch, [reply])

        from divefy.pipeline import p7_generate

        result = p7_generate.answer(retrieval_config, model, Q_AIRE)

        assert len(calls) == 1, "one question without bad numbers => exactly one LLM call"
        assert calls[0]["model"] == model, "the model config must reach the llm seam untouched"
        assert isinstance(calls[0]["system"], str) and calls[0]["system"], "system prompt empty"
        assert isinstance(calls[0]["user"], str) and calls[0]["user"], "user prompt empty"
        assert Q_AIRE in (calls[0]["system"] + calls[0]["user"]), (
            "the question must appear in the prompt sent to the model"
        )

        assert result.pregunta == Q_AIRE
        assert result.respuesta == reply, "respuesta must be the backend reply verbatim"
        assert result.abstencion is False, "grounded reply without numbers must not abstain"

        assert len(result.chunks) > 0, "answer() must carry the retrieved chunks in its state"
        for chunk in result.chunks:
            assert chunk["id"], "each chunk needs its retrieval id"
            assert chunk["texto"], "each chunk needs its text"
            metadata = chunk["metadata"]
            assert isinstance(metadata, dict) and metadata, "chunk metadata missing"
            assert metadata.get("corpus") in {"apuntes", "manual"}, (
                f"chunk metadata must come from the store row, got corpus={metadata.get('corpus')!r}"
            )

    def test_answer_is_frozen(self, monkeypatch, retrieval_config):
        """Nadie puede modificar el estado a posteriori: intentar mutar el Answer
        tiene que fallar. Protege contra el bug de 'otro código me cambió el objeto
        por debajo sin que yo lo viera'."""
        _require(CONSTANTES_PATH, CONSTANTES_HINT)

        _patch_generate(monkeypatch, ["Respuesta sin cifras."])

        from divefy.pipeline import p7_generate

        result = p7_generate.answer(retrieval_config, "fake-model", Q_AIRE)
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.respuesta = "mutado"


# ---------------------------------------------------------------------------
# Criterion 2 — no support => EXACTLY the public abstention template
# ---------------------------------------------------------------------------


class TestAbstencion:
    def test_forced_no_support_yields_exact_template(self, monkeypatch, retrieval_config):
        """Pregunta fuera del corpus (marcas de neopreno) => la respuesta debe ser LA
        PLANTILLA de abstención, letra por letra, y el flag abstencion levantado. Ni
        una palabra de cosecha propia cuando no hay soporte."""
        _require(CONSTANTES_PATH, CONSTANTES_HINT)

        from divefy.pipeline import p7_generate
        from divefy.pipeline.p7_generate import ABSTENTION_TEMPLATE

        assert isinstance(ABSTENTION_TEMPLATE, str) and ABSTENTION_TEMPLATE.strip(), (
            "ABSTENTION_TEMPLATE must be a non-empty public string constant"
        )

        # Forced no-support: the fake backend signals it cannot ground an answer.
        _patch_generate(monkeypatch, [ABSTENTION_TEMPLATE])

        result = p7_generate.answer(retrieval_config, "fake-model", Q_SIN_SOPORTE)

        assert result.respuesta == ABSTENTION_TEMPLATE, (
            "no-support response must be EXACTLY the template — no wrapping, no edits"
        )
        assert result.abstencion is True, "abstencion flag must be set on template responses"


# ---------------------------------------------------------------------------
# Criterion 4 — guardrail catches altered numbers; retry-once then abstain
# ---------------------------------------------------------------------------

SYNTH_CONSTANTES = [
    {"numero": "18", "unidad": "m/min", "concepto": "velocidad máxima de ascenso",
     "fuente": "PADI", "section_id": "apuntes-owd#ascenso"},
    {"numero": "3", "unidad": "min", "concepto": "duración de la parada de seguridad",
     "fuente": "PADI", "section_id": "apuntes-owd#parada"},
    {"numero": "5", "unidad": "m", "concepto": "profundidad de la parada de seguridad",
     "fuente": "PADI", "section_id": "apuntes-owd#parada"},
    {"numero": "18", "unidad": "m", "concepto": "profundidad máxima Open Water",
     "fuente": "PADI", "section_id": "apuntes-owd#limites"},
    {"numero": "12", "unidad": "h", "concepto": "espera antes de volar tras una inmersión",
     "fuente": "PADI", "section_id": "apuntes-owd#volar"},
    {"numero": "18", "unidad": "h", "concepto": "espera antes de volar tras inmersiones repetitivas",
     "fuente": "PADI", "section_id": "apuntes-owd#volar"},
]

GOOD_RESPONSES = [
    "La velocidad máxima de ascenso es de 18 m/min.",
    "Haz una parada de seguridad de 3 min a 5 m de profundidad.",
    "La profundidad máxima en el curso Open Water es de 18 m.",
    "Espera 12 h antes de volar tras una única inmersión.",
    "Tras inmersiones repetitivas espera 18 h antes de volar.",
]

BAD_RESPONSES = [
    "La velocidad máxima de ascenso es de 25 m/min.",
    "Haz una parada de seguridad de 8 min a 5 m de profundidad.",
    "La profundidad máxima en el curso Open Water es de 30 m.",
    "Espera 6 h antes de volar tras una única inmersión.",
    "Tras inmersiones repetitivas espera 24 h antes de volar.",
]


class TestGuardrail:
    @pytest.mark.parametrize("respuesta", GOOD_RESPONSES, ids=lambda r: r[:30])
    def test_correct_numbers_pass(self, respuesta):
        """Cinco frases con los números PADI correctos => el guardarraíl dice 'ok' a
        todas. Vigila que el portero no sea un paranoico que bloquee lo correcto."""
        from divefy.pipeline.p7_guardrail import verify

        verdict = verify(respuesta, SYNTH_CONSTANTES)
        assert verdict == "ok", f"correct figure wrongly rejected: {respuesta!r} -> {verdict!r}"

    @pytest.mark.parametrize("respuesta", BAD_RESPONSES, ids=lambda r: r[:30])
    def test_altered_numbers_are_caught(self, respuesta):
        """Las mismas frases con los números manipulados (25 m/min, 30 m...) =>
        ninguna pasa como 'ok'. EL test de seguridad del producto: cifra inventada,
        cifra pillada."""
        from divefy.pipeline.p7_guardrail import verify

        verdict = verify(respuesta, SYNTH_CONSTANTES)
        assert verdict in {"reintento", "abstener_cifra"}, (
            f"altered figure slipped through the guardrail: {respuesta!r} -> {verdict!r}"
        )
        assert verdict != "ok", f"altered figure marked ok: {respuesta!r}"

    def test_retry_once_then_abstain_when_bad_number_repeats(
        self, monkeypatch, retrieval_config
    ):
        """El muñeco insiste en el número falso también a la segunda => exactamente
        2 intentos (ni cero ni bucle infinito), el número falso jamás sale, y la
        respuesta acaba en abstención."""
        _require(CONSTANTES_PATH, CONSTANTES_HINT)

        # The fake generator repeats the same altered figure on the retry.
        calls = _patch_generate(
            monkeypatch, ["La velocidad máxima de ascenso es de 25 m/min."]
        )

        from divefy.pipeline import p7_generate

        result = p7_generate.answer(retrieval_config, "fake-model", Q_ASCENSO)

        assert len(calls) == 2, (
            f"bad verdict must trigger exactly ONE retry (2 calls total), got {len(calls)}"
        )
        assert "25" not in result.respuesta, (
            "an unverified figure must NEVER be emitted"
        )
        assert result.abstencion is True, (
            "second failed verification must turn the figure into abstention"
        )

    def test_retry_recovers_when_second_answer_is_correct(
        self, monkeypatch, retrieval_config
    ):
        """El muñeco se corrige a la segunda (18 m/min) => esa respuesta buena es la
        que sale y NO hay abstención. Distingue 'reintenta de verdad' de 'se rinde a
        la primera', que pasaría el test anterior igual."""
        _require(CONSTANTES_PATH, CONSTANTES_HINT)

        good = "La velocidad máxima de ascenso es de 18 m/min."
        calls = _patch_generate(
            monkeypatch, ["La velocidad máxima de ascenso es de 25 m/min.", good]
        )

        from divefy.pipeline import p7_generate

        result = p7_generate.answer(retrieval_config, "fake-model", Q_ASCENSO)

        assert len(calls) == 2, "one bad verdict => one retry"
        assert result.respuesta == good, "the verified retry answer must be the one emitted"
        assert result.abstencion is False
        assert "25" not in result.respuesta, "the rejected figure must not leak into the answer"


# ---------------------------------------------------------------------------
# Criterion 5 — constants cheat-sheet schema (real versioned file)
# ---------------------------------------------------------------------------


class TestConstantesCheatsheet:
    REQUIRED_FIELDS = ("numero", "unidad", "concepto", "fuente", "section_id")

    def test_cheatsheet_schema(self):
        """La chuleta real de números de seguridad no está rota: cada fila con sus 5
        campos rellenos y fuente PADI o Navy. No juzga si los números son verdad
        (eso es la auditoría de Adolfo); juzga que el fichero tiene la forma de la
        que depende el guardarraíl."""
        _require(
            CONSTANTES_PATH,
            "version the constants cheat-sheet at data/guardrail/constantes.jsonl",
        )

        rows = [
            json.loads(line)
            for line in CONSTANTES_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rows, "constantes.jsonl exists but is empty"

        for i, row in enumerate(rows):
            for field in self.REQUIRED_FIELDS:
                assert field in row, f"row {i} missing field {field!r}: {row}"
                assert str(row[field]).strip(), f"row {i} has empty {field!r}: {row}"
            assert row["fuente"] in {"PADI", "Navy"}, (
                f"row {i}: fuente must be 'PADI' or 'Navy', got {row['fuente']!r}"
            )


# ---------------------------------------------------------------------------
# Criteria 6 & 7 — llm_evaluator.run() with fake generator + fake judge
# ---------------------------------------------------------------------------

EVAL_MODEL = "fake-model"


@pytest.fixture(scope="module")
def eval_result(retrieval_config):
    """One evaluator run shared by criteria 6 and 7 (it iterates the eval questions)."""
    _require(GOLDEN_PATH, "the golden dataset is required to run the evaluator")
    _require(CONSTANTES_PATH, CONSTANTES_HINT)

    mp = pytest.MonkeyPatch()
    calls = {"generate": 0, "grade": 0}
    try:
        import divefy.llm as llm
        import divefy.evals.judge as judge

        def fake_generate(model, system, user):
            calls["generate"] += 1
            return "Respuesta simulada del examen, sin cifras."

        def fake_grade(*args, **kwargs):
            calls["grade"] += 1
            return "aprobado"

        mp.setattr(llm, "generate", fake_generate)
        mp.setattr(judge, "grade", fake_grade)

        from divefy.evals import llm_evaluator

        result = llm_evaluator.run(retrieval_config, EVAL_MODEL)
    finally:
        mp.undo()
    return result, calls


def _find_run_id(result):
    if "run_id" in result:
        return result["run_id"]
    config = result.get("config", {})
    assert "run_id" in config, f"no run_id found at top level nor in config: {sorted(result)}"
    return config["run_id"]


class TestLlmEvaluator:
    @pytest.mark.slow
    def test_result_has_config_resumen_detalle(self, eval_result):
        """Una pasada del examen (con muñecos de modelo Y de juez) produce la fila
        entera: config, resumen y detalle. Los contadores verifican de paso que
        ninguna llamada se escapó hacia una API real."""
        result, calls = eval_result
        assert set(result) >= {"config", "resumen", "detalle"}, (
            f"run() must return config/resumen/detalle, got {sorted(result)}"
        )
        assert calls["generate"] > 0, "the fake generator was never called — network seam leak?"
        assert calls["grade"] > 0, "the fake judge was never called — network seam leak?"

    @pytest.mark.slow
    def test_every_question_gets_a_verdict(self, eval_result):
        """Ninguna pregunta del examen se pierde por el camino: cada una tiene su
        veredicto y es uno de los tres válidos (aprobado/suspenso/abstención)."""
        result, _ = eval_result
        detalle = result["detalle"]
        assert len(detalle) > 0, "detalle must carry one row per eval question"
        for i, row in enumerate(detalle):
            assert "veredicto" in row, f"detalle row {i} has no 'veredicto': {sorted(row)}"
            assert row["veredicto"] in VERDICTS, (
                f"detalle row {i}: verdict {row['veredicto']!r} not in {sorted(VERDICTS)}"
            )

    @pytest.mark.slow
    def test_resumen_aggregates_match_detalle(self, eval_result):
        """Cuenta los 'aprobado' del detalle a mano y exige que el agregado del
        resumen diga lo mismo. Pilla el bug clásico de resumen descuadrado con su
        detalle."""
        result, _ = eval_result
        detalle = result["detalle"]
        resumen = result["resumen"]
        n_aprobado = sum(1 for row in detalle if row["veredicto"] == "aprobado")
        assert resumen.get("aprobado") == n_aprobado, (
            f"resumen['aprobado']={resumen.get('aprobado')!r} but detalle counts {n_aprobado}"
        )

    @pytest.mark.slow
    def test_run_id_includes_the_model(self, eval_result):
        """El identificador de la fila lleva el nombre del modelo: la pasada de
        Sonnet y la de Qwen jamás pueden pisarse en results/."""
        result, _ = eval_result
        run_id = _find_run_id(result)
        assert EVAL_MODEL in str(run_id), (
            f"run_id {run_id!r} must include the model so rows are distinguishable"
        )


class TestPromptVersioning:
    @pytest.mark.slow
    def test_prompt_versions_come_from_prompt_filenames(self, eval_result):
        """La fila registra qué versión de prompt se usó (generación Y juez), leída
        del nombre del fichero de prompts/. Si cambias el prompt entre dos pasadas,
        las filas lo delatan sin abrir el código."""
        _require(PROMPTS_DIR, "create the prompts/ directory with versioned prompt files")

        result, _ = eval_result
        config = result["config"]
        prompt_keys = sorted(k for k in config if "prompt" in k.lower())
        assert len(prompt_keys) >= 2, (
            "the result row must register prompt_version for BOTH generation and judge, "
            f"found prompt-ish keys: {prompt_keys} in {sorted(config)}"
        )

        prompt_files = [p for p in PROMPTS_DIR.iterdir() if p.is_file()]
        assert prompt_files, "prompts/ exists but holds no prompt files"
        valid_names = {p.name for p in prompt_files} | {p.stem for p in prompt_files}
        for key in prompt_keys:
            value = str(config[key])
            assert value in valid_names, (
                f"{key}={value!r} does not match any file in prompts/ — the version must be "
                f"read from the prompt filename, not a loose constant (files: {sorted(valid_names)})"
            )
