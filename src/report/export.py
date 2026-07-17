"""집계-only Excel/PDF 산출 (raw 행 미포함)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def export_metrics_excel(
    path: Path,
    model_metrics: dict[str, dict[str, Any]],
    lift_by_model: dict[str, dict[str, Any]] | None = None,
    bin_tables: dict[str, list[dict[str, Any]]] | None = None,
) -> None:
    """모델별 지표 비교표를 Excel로 저장."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for algo, m in model_metrics.items():
        row = {"알고리즘(algorithm)": algo}
        row.update(m)
        rows.append(row)
    df = pd.DataFrame(rows)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="모델비교(model_comparison)", index=False)
        if lift_by_model:
            lift_rows = []
            for algo, lift in lift_by_model.items():
                r = {"알고리즘(algorithm)": algo}
                r.update(lift)
                lift_rows.append(r)
            pd.DataFrame(lift_rows).to_excel(
                writer, sheet_name="상위K퍼센트(lift)", index=False
            )
        if bin_tables:
            for algo, table in bin_tables.items():
                sheet = f"점수구간_{algo}"[:31]
                pd.DataFrame(table).to_excel(writer, sheet_name=sheet, index=False)
    print(f"[report] Excel 저장: {path}")


def export_summary_pdf(
    path: Path,
    title: str,
    paragraphs: list[str],
    metrics_table: list[dict[str, Any]] | None = None,
) -> None:
    """간단한 요약 PDF (비전문가용 문구 포함)."""
    from fpdf import FPDF

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    # 기본 폰트는 한글 미지원 → 영문/숫자 요약 + 안내
    # 한글 PDF는 시스템 폰트 등록이 필요하므로, 우선 안내 문장을 병기
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, title)
    pdf.ln(4)
    pdf.set_font("Helvetica", size=10)
    note = (
        "Note: Korean narrative is in docs/metrics_guide.md. "
        "This PDF summarizes aggregate metrics only (no raw rows)."
    )
    pdf.multi_cell(0, 6, note)
    pdf.ln(3)
    for p in paragraphs:
        # 한글이 깨질 수 있어 ASCII 안전 변환 시도
        safe = p.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 5, safe)
        pdf.ln(2)

    if metrics_table:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "Model metrics (aggregate)", ln=True)
        pdf.set_font("Helvetica", size=9)
        for row in metrics_table:
            line = ", ".join(f"{k}={v}" for k, v in row.items())
            safe = line.encode("latin-1", errors="replace").decode("latin-1")
            pdf.multi_cell(0, 5, safe)
            pdf.ln(1)

    pdf.output(str(path))
    print(f"[report] PDF 저장: {path}")
    print(
        "[report] 한글 본문은 docs/metrics_guide.md 및 Excel을 참고하세요. "
        "PDF는 기본 폰트 제약으로 영문 요약 중심입니다."
    )
