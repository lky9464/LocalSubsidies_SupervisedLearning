"""모델 평가지표 (집계만)."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
) -> dict[str, Any]:
    """분류 지표 딕셔너리. 키는 한글(영어) 형태."""
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    specificity = tn / (tn + fp) if (tn + fp) else 0.0

    out: dict[str, Any] = {
        "정확도(Accuracy)": float(accuracy_score(y_true, y_pred)),
        "정밀도(Precision)": float(precision_score(y_true, y_pred, zero_division=0)),
        "재현율(Recall)": float(recall_score(y_true, y_pred, zero_division=0)),
        "F1점수(F1)": float(f1_score(y_true, y_pred, zero_division=0)),
        "특이도(Specificity)": float(specificity),
        "혼동행렬_TN(TrueNegative)": int(tn),
        "혼동행렬_FP(FalsePositive)": int(fp),
        "혼동행렬_FN(FalseNegative)": int(fn),
        "혼동행렬_TP(TruePositive)": int(tp),
    }
    # 양성 클래스가 한 쪽만 있으면 AUC 계산 불가
    if len(np.unique(y_true)) > 1:
        out["ROC_AUC(ROC_AUC)"] = float(roc_auc_score(y_true, y_proba))
        out["PR_AUC(AveragePrecision)"] = float(average_precision_score(y_true, y_proba))
    else:
        out["ROC_AUC(ROC_AUC)"] = None
        out["PR_AUC(AveragePrecision)"] = None
    return out


def top_k_lift(
    y_true: np.ndarray,
    scores: np.ndarray,
    percents: list[float | int],
) -> dict[str, Any]:
    """상위 K% 위험군에서의 양성 비율·리프트."""
    y_true = np.asarray(y_true)
    scores = np.asarray(scores)
    n = len(y_true)
    base = float(y_true.mean()) if n else 0.0
    order = np.argsort(-scores)
    result: dict[str, Any] = {"전체양성비율(base_positive_rate)": base}
    for pct in percents:
        k = max(1, int(np.ceil(n * float(pct) / 100.0)))
        idx = order[:k]
        rate = float(y_true[idx].mean()) if k else 0.0
        lift = rate / base if base > 0 else None
        pos_in_top = float(y_true[idx].sum()) if k else 0.0
        total_pos = float(y_true.sum()) if n else 0.0
        recall_at = (pos_in_top / total_pos) if total_pos > 0 else None
        result[f"상위{pct}%건수(top_{pct}pct_count)"] = k
        # 상위 K% 안에서의 양성 비중 (= precision@topK)
        result[f"상위{pct}%양성비율(top_{pct}pct_positive_rate)"] = rate
        result[f"상위{pct}%리프트(top_{pct}pct_lift)"] = lift
        # 전체 양성 중 상위 K%에 포함된 비중 (= recall@topK)
        result[f"상위{pct}%양성포착비율(top_{pct}pct_recall)"] = recall_at
    return result


def score_bin_target_rate(
    y_true: np.ndarray,
    scores: np.ndarray,
    n_bins: int = 10,
    min_cell_count: int = 5,
) -> list[dict[str, Any]]:
    """점수 구간별 타겟율 (작은 셀 마스킹)."""
    y_true = np.asarray(y_true)
    scores = np.asarray(scores)
    bins = np.linspace(0, 1000, n_bins + 1)
    rows: list[dict[str, Any]] = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        if i == n_bins - 1:
            mask = (scores >= lo) & (scores <= hi)
        else:
            mask = (scores >= lo) & (scores < hi)
        cnt = int(mask.sum())
        pos = int(y_true[mask].sum()) if cnt else 0
        rate = pos / cnt if cnt else None
        if cnt < min_cell_count:
            rows.append(
                {
                    "점수구간(score_bin)": f"{int(lo)}-{int(hi)}",
                    "건수(count)": cnt,
                    "양성공(positive_count)": None,
                    "양성비율(positive_rate)": None,
                    "마스킹여부(masked)": True,
                }
            )
        else:
            rows.append(
                {
                    "점수구간(score_bin)": f"{int(lo)}-{int(hi)}",
                    "건수(count)": cnt,
                    "양성공(positive_count)": pos,
                    "양성비율(positive_rate)": rate,
                    "마스킹여부(masked)": False,
                }
            )
    return rows
