"""`python -m divefy` — arranca la API local del chat, precarga los modelos y abre el
navegador. Único punto de entrada del proyecto: los módulos de librería (`chat`,
`api`, `pipeline/*`) no se ejecutan nunca como `__main__`.
"""

import argparse
import threading
import webbrowser

from divefy import chat
from divefy.api import make_server
from divefy.config import RECETA_GANADORA


def _precarga() -> None:
    try:
        chat.warm_up(chat.DEFAULT_MODEL, RECETA_GANADORA)
        print("Modelos cargados. Listo para preguntar.", flush=True)
    except Exception as e:  # visible en la terminal; un hilo no debe morir en silencio
        print(f"Precarga fallida: {type(e).__name__}: {e}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(prog="divefy", description="Divefy — chat web local")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = make_server(port=args.port)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Divefy en {url}  (Ctrl+C para parar) — precargando modelos…", flush=True)

    threading.Thread(target=_precarga, name="precarga", daemon=True).start()
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
