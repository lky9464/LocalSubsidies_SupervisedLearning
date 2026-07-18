"""docs/user_guide.md → docs/user_guide.pdf (fpdf2)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build_pdf(md_path: Path | None = None, out_path: Path | None = None) -> Path:
    from fpdf import FPDF

    md_path = md_path or (ROOT / "docs" / "user_guide.md")
    out_path = out_path or (ROOT / "docs" / "user_guide.pdf")
    text = md_path.read_text(encoding="utf-8")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    font_path = Path("C:/Windows/Fonts/malgun.ttf")
    if font_path.exists():
        pdf.add_font("Malgun", "", str(font_path))
        pdf.set_font("Malgun", size=11)
        use_kr = True
    else:
        pdf.set_font("Helvetica", size=11)
        use_kr = False

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            pdf.ln(3)
            continue
        if line.startswith("|") or set(line) <= set("-|: "):
            # 표는 단순 텍스트로 (셀 폭 문제 회피)
            plain = " / ".join(
                p.strip() for p in line.strip("|").split("|") if p.strip() and set(p.strip()) != {"-"}
            )
            if not plain or set(plain.replace("/", "").replace(" ", "")) <= {"-"}:
                continue
            pdf.set_font_size(9)
            _safe_cell(pdf, plain, use_kr)
            pdf.set_font_size(11)
            continue
        if line.startswith("# "):
            pdf.set_font_size(16)
            _safe_cell(pdf, _strip_md(line[2:]), use_kr)
            pdf.set_font_size(11)
            pdf.ln(2)
        elif line.startswith("## "):
            pdf.set_font_size(13)
            _safe_cell(pdf, _strip_md(line[3:]), use_kr)
            pdf.set_font_size(11)
            pdf.ln(1)
        else:
            _safe_cell(pdf, _strip_md(line), use_kr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def _safe_cell(pdf, text: str, use_kr: bool) -> None:
    if not use_kr:
        text = text.encode("latin-1", errors="replace").decode("latin-1")
    try:
        pdf.multi_cell(0, 6, text)
    except Exception:
        pdf.ln(6)


def _strip_md(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    return s


def main() -> None:
    out = build_pdf()
    print(f"[guide] wrote {out}")


if __name__ == "__main__":
    main()
