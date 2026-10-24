"""Wrap web/app.html into docs/index.html as a full HTML document for GitHub Pages.

Run: python web/build_pages.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "app.html"
OUT = ROOT / "docs" / "index.html"

CSP = (
    "default-src 'none'; "
    "script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src data:; "
    "connect-src 'none'; form-action 'none'; base-uri 'none'"
)

HEAD = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="description" content="Heuristic estimate of how many entries share your NFL Classic DFS lineup, and the tie-split payout impact. Runs in your browser.">
<style>
:root {{ padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }}
body {{ margin: 0; }}
img {{ max-width: 100%; }}
[hidden] {{ display: none !important; }}
</style>
"""


def build() -> Path:
    app = SRC.read_text(encoding="utf-8")
    marker = "<style>"
    cut = app.index(marker)
    head_part = app[:cut]  # <title>, viewport-fit meta, fonts link
    body_part = app[cut:]
    style_end = body_part.index("</style>") + len("</style>")
    doc = HEAD + head_part + body_part[:style_end] + "\n</head>\n<body>\n" + body_part[style_end:].lstrip("\n") + "</body>\n</html>\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    out = build()
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size:,} bytes)")
