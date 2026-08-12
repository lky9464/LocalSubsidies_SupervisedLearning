"""모델 비교 — Test 점수 분포 API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from api.services.model_insights import role_algos_from_ranking
from src.io.config import resolve_algo_score_csv
from src.models.registry import resolve_algo_label
from src.scoring.score_distribution import get_or_build_score_distribution_payload


def _role_panel_unavailable(role: str, algo: str | None, label: str | None, reason: str) -> dict[str, Any]:
    return {
        "role": role,
        "algo": algo,
        "label": label,
        "available": False,
        "reason": reason,
        "pk": None,
        "entity": None,
    }


def _build_one_role_panel(
    cfg: dict[str, Any],
    *,
    role: str,
    key: str,
    algo: str | None,
    label: str | None,
    run_id: str | None,
    encoding: str,
) -> tuple[str, dict[str, Any]]:
    if not algo:
        reason = (
            "참조 모델 없음 (2개 모델 학습)"
            if key == "reference"
            else "해당 역할 모델 없음"
        )
        return key, _role_panel_unavailable(role, None, label, reason)

    path = resolve_algo_score_csv(cfg, algo, "test", run_id=run_id)
    dist = get_or_build_score_distribution_payload(path, cfg, encoding=encoding)
    if dist is None:
        return key, _role_panel_unavailable(
            role,
            algo,
            label,
            "07 평가 미실행 또는 Test 점수 CSV 없음",
        )
    return key, {
        "role": role,
        "algo": algo,
        "label": label or algo,
        "available": True,
        "reason": "",
        **dist,
    }


def build_score_distribution_panels(
    cfg: dict[str, Any],
    ranking: list[dict],
    *,
    run_id: str | None,
    labels_map: dict[str, str],
) -> dict[str, Any]:
    roles = role_algos_from_ranking(ranking)
    encoding = str(cfg.get("encoding") or "EUC-KR")

    role_meta = {
        "primary": ("primary", "주"),
        "aux": ("aux", "보"),
        "reference": ("reference", "참"),
    }
    jobs: list[tuple[str, str, str | None, str | None]] = []
    for key, (role, _ko) in role_meta.items():
        algo = roles.get(key)
        label = resolve_algo_label(algo, labels_map) if algo else None
        jobs.append((key, role, algo, label))

    out: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = [
            pool.submit(
                _build_one_role_panel,
                cfg,
                role=role,
                key=key,
                algo=algo,
                label=label,
                run_id=run_id,
                encoding=encoding,
            )
            for key, role, algo, label in jobs
        ]
        for fut in as_completed(futs):
            key, panel = fut.result()
            out[key] = panel
    return {k: out[k] for k in role_meta if k in out}
