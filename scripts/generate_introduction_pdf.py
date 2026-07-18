"""docs/project_introduction.md → docs/project_introduction.pdf (fpdf2)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_user_guide_pdf import build_pdf  # noqa: E402


def main() -> None:
    md = ROOT / "docs" / "project_introduction.md"
    out = ROOT / "docs" / "project_introduction.pdf"
    path = build_pdf(md, out)
    print(f"[intro] wrote {path}")


if __name__ == "__main__":
    main()
