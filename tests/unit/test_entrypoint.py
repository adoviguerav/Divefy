"""Unit — punto de entrada `python -m divefy`.

Regresión del crash del 2026-09-23: ejecutar `python -m divefy.chat` cargaba el
módulo dos veces (`__main__` + `divefy.chat`), con dos cerrojos, y torch (MPS)
cascaba al cargar el reranker desde dos hilos. Ahora el único entrypoint es
`divefy.__main__`, y `divefy.chat` no se ejecuta nunca como script.
"""

import subprocess
import sys


def test_python_m_divefy_arranca_y_parsea_argumentos():
    # --help sale antes de tocar red o modelos: prueba que el entrypoint importa
    # y que los flags existen, sin cargar nada.
    out = subprocess.run(
        [sys.executable, "-m", "divefy", "--help"], capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    assert "--port" in out.stdout and "--no-browser" in out.stdout


def test_chat_no_es_ejecutable_como_script():
    import divefy.chat as chat

    assert not hasattr(chat, "main"), (
        "chat.py es librería: el arranque vive en divefy/__main__.py (ver docstring)"
    )
