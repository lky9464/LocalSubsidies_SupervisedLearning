"""위험도 점수 0~1000 변환."""

from __future__ import annotations

import numpy as np


def probability_to_score(
    proba: np.ndarray,
    min_score: int = 0,
    max_score: int = 1000,
) -> np.ndarray:
    """양성 확률을 위험도 점수로 단조 변환 (높을수록 위험↑)."""
    p = np.asarray(proba, dtype=float)
    p = np.clip(p, 0.0, 1.0)
    score = np.rint(p * (max_score - min_score) + min_score).astype(int)
    return np.clip(score, min_score, max_score)
