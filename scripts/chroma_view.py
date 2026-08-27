"""Visor HTML de una colección Chroma local — workaround a `chroma browse`, que hoy
solo funciona contra Cloud (--path usa un lector desfasado; --local pide /search,
501 en servidor local). Uso: uv run python scripts/chroma_view.py <colección>"""

import html
import subprocess
import sys
import tempfile
from pathlib import Path

import chromadb

DOC_PREVIEW = 400  # chars de document en la celda; el resto no aporta en un vistazo


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "combined-512-hype-bgem3"
    collection = chromadb.PersistentClient(path="data/chroma").get_collection(name)
    result = collection.get(include=["documents", "metadatas"])

    meta_keys = sorted({k for m in result["metadatas"] for k in m})
    header = "".join(f"<th>{k}</th>" for k in ["id", "document"] + meta_keys)
    rows = []
    for id_, doc, meta in zip(result["ids"], result["documents"], result["metadatas"]):
        cells = [html.escape(id_), html.escape((doc or "")[:DOC_PREVIEW])]
        cells += [html.escape(str(meta[k])) if k in meta else "" for k in meta_keys]
        rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")

    page = f"""<!doctype html><meta charset="utf-8"><title>{name}</title>
<style>body{{font:13px monospace;margin:1rem}}table{{border-collapse:collapse}}
td,th{{border:1px solid #ccc;padding:4px 6px;vertical-align:top;max-width:38rem}}
th{{position:sticky;top:0;background:#eee}}input{{width:30rem;margin-bottom:.5rem;padding:4px}}</style>
<h2>{name} — {len(rows)} filas</h2>
<input placeholder="filtrar (id, texto, metadata)..." oninput="
  const q=this.value.toLowerCase();
  document.querySelectorAll('tbody tr').forEach(tr=>
    tr.style.display=tr.textContent.toLowerCase().includes(q)?'':'none')">
<table><thead><tr>{header}</tr></thead><tbody>{"".join(rows)}</tbody></table>"""

    out = Path(tempfile.gettempdir()) / f"chroma-{name}.html"
    out.write_text(page, encoding="utf-8")
    print(f"{len(rows)} filas -> {out}")
    subprocess.run(["open", str(out)])


if __name__ == "__main__":
    main()
