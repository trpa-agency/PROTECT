"""Markdown document -> styled HTML (TRPA house style) -> PDF through headless Edge.

    python scripts/md2html.py docs/SCORING_RUBRICS.md outputs/PROTECT_SCORING_RUBRICS_v0.4.pdf
    python scripts/md2html.py docs/X.md outputs/X.html      # HTML only

Uses the `markdown` package (tables, fenced code) and msedge --headless --print-to-pdf.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import markdown

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CSS = """
body{font-family:Calibri,'Open Sans',Arial,sans-serif;font-size:10.5pt;color:#003B71;line-height:1.4;max-width:7.2in;margin:0 auto;padding:0.2in 0;}
h1{font-size:20pt;color:#003B71;border-bottom:3px solid #0072CE;padding-bottom:4pt;margin:0 0 10pt;}
h2{font-size:15pt;color:#003B71;margin:18pt 0 6pt;border-bottom:1px solid #B4CBE8;padding-bottom:2pt;page-break-after:avoid;}
h3{font-size:12pt;color:#0072CE;margin:12pt 0 4pt;page-break-after:avoid;}
p{margin:0 0 7pt;} li{margin:0 0 3pt;} code{font-family:Consolas,monospace;font-size:9.5pt;background:#eef1f5;padding:0 3px;border-radius:2px;}
pre{background:#eef1f5;padding:6pt;font-size:9pt;overflow-x:auto;}
table{border-collapse:collapse;width:100%;font-size:9pt;margin:6pt 0 10pt;page-break-inside:auto;}
th{background:#003B71;color:#fff;text-align:left;padding:3pt 5pt;font-weight:600;}
td{border-bottom:1px solid #DDDDDD;padding:3pt 5pt;vertical-align:top;}
tr{page-break-inside:avoid;}
hr{border:0;border-top:1px solid #DDDDDD;margin:14pt 0;}
strong{color:#003B71;}
@page{size:letter;margin:0.7in 0.6in;}
"""


def to_html(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"])
    title = md_path.stem.replace("_", " ")
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>"


def main() -> None:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    html = to_html(src)
    if out.suffix.lower() == ".html":
        out.write_text(html, encoding="utf-8")
        print(f"-> {out}")
        return
    tmp = out.with_suffix(".html")
    tmp.write_text(html, encoding="utf-8")
    cmd = [EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out.resolve()}", tmp.resolve().as_uri()]
    subprocess.run(cmd, check=True, timeout=180)
    tmp.unlink(missing_ok=True)
    print(f"-> {out} ({out.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
