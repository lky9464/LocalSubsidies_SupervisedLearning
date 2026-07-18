"""
[로컬 전용] 집계 Excel/PDF
→ outputs/reports/{algo}/  (알고리즘별)
→ outputs/reports/comparison/  (5종 비교, 공통 1벌)

선행: 07_evaluate.py
raw 행·개별 점수는 포함하지 않음.
Cursor Agent는 이 스크립트를 실행하지 마세요.

"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.io.config import (  # noqa: E402
    ensure_algo_dirs,
    load_config,
    resolve_algo_report_dir,
    resolve_data_path,
    resolve_repo_path,
)
from src.report.export import export_metrics_excel, export_summary_pdf  # noqa: E402


def main() -> None:
    print_banner()
    cfg = load_config()
    algorithms = cfg.get("algorithms", [])
    ensure_algo_dirs(cfg, algorithms)
    algo_root = resolve_data_path(cfg, "algorithms")
    comparison_dir = resolve_repo_path(cfg, "reports_comparison")
    comparison_dir.mkdir(parents=True, exist_ok=True)

    summary_path = algo_root / "eval_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"{summary_path} 없음. 먼저 07_evaluate.py를 실행하세요.")


    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)

    metrics = summary.get("metrics", {})
    lift = summary.get("lift", {})
    bins = summary.get("bins", {})

    # 1) 5종 비교 — 공통 폴더 1벌
    xlsx = comparison_dir / "model_evaluation_comparison.xlsx"
    export_metrics_excel(xlsx, metrics, lift_by_model=lift, bin_tables=bins)

    table = []
    for algo, m in metrics.items():
        table.append(
            {
                "algorithm": algo,
                "Accuracy": m.get("정확도(Accuracy)"),
                "Precision": m.get("정밀도(Precision)"),
                "Recall": m.get("재현율(Recall)"),
                "F1": m.get("F1점수(F1)"),
                "ROC_AUC": m.get("ROC_AUC(ROC_AUC)"),
            }
        )

    split = cfg.get("split", {})
    paragraphs = [
        f"Train period: {split.get('train_start')}-{split.get('train_end')}",
        f"Test period: {split.get('test_start')}-{split.get('test_end')}",
        "Risk score range: 0-1000 (higher = higher fraud risk).",
        "Reports contain aggregate statistics only. No raw PII rows.",
        "See docs/metrics_guide.md for Korean explanations of metrics.",
        "Per-algorithm reports: outputs/reports/{algorithm}/",
    ]
    pdf = comparison_dir / "model_evaluation_summary.pdf"
    export_summary_pdf(
        pdf,
        title="Local Subsidies Fraud Risk - Model Comparison",
        paragraphs=paragraphs,
        metrics_table=table,
    )

    # 2) 알고리즘별 폴더 — 해당 모델 집계만
    for algo in algorithms:
        if algo not in metrics:
            continue
        algo_report = resolve_algo_report_dir(cfg, algo)
        algo_report.mkdir(parents=True, exist_ok=True)
        export_metrics_excel(
            algo_report / "evaluation.xlsx",
            {algo: metrics[algo]},
            lift_by_model={algo: lift.get(algo, {})},
            bin_tables={algo: bins.get(algo, [])},
        )
        export_summary_pdf(
            algo_report / "evaluation_summary.pdf",
            title=f"Local Subsidies Fraud Risk - {algo}",
            paragraphs=paragraphs + [f"Algorithm: {algo}"],
            metrics_table=[
                {
                    "algorithm": algo,
                    "Accuracy": metrics[algo].get("정확도(Accuracy)"),
                    "Precision": metrics[algo].get("정밀도(Precision)"),
                    "Recall": metrics[algo].get("재현율(Recall)"),
                    "F1": metrics[algo].get("F1점수(F1)"),
                    "ROC_AUC": metrics[algo].get("ROC_AUC(ROC_AUC)"),
                }
            ],
        )
        print(f"[report] 알고리즘별 리포트: {algo_report}")

    print(f"[report] 공통 비교 리포트: {comparison_dir}")


if __name__ == "__main__":
    main()
