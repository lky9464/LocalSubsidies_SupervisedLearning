"""알고리즘 family + version (algo_id = {family}_v{N}) 레지스트리."""

from __future__ import annotations

import re
from typing import Any

# family → 표시명 (새 패키지 도입 시 여기에 family 추가 후 v1부터)
FAMILY_LABELS: dict[str, str] = {
    "catboost": "CatBoost",
    "stacked_ensemble": "Stacked Ensemble",
    "easy_ensemble": "EasyEnsemble",
    "gradient_boosting": "Gradient Boosting",
    "random_forest": "RandomForest",
}

# 기본 등록 algo_id (configs.algorithm_registry / algorithms 와 동기)
DEFAULT_ALGO_IDS: list[str] = [
    "catboost_v1",
    "catboost_v2",
    "stacked_ensemble_v1",
    "easy_ensemble_v1",
    "gradient_boosting_v1",
    "random_forest_v1",
    "random_forest_v2",
]

_ALGO_ID_RE = re.compile(r"^([a-z][a-z0-9_]*)_v(\d+)$", re.IGNORECASE)


def normalize_algo_id(name: str) -> str:
    """구 ID(family만) → {family}_v1. 이미 versioned 이면 소문자 유지."""
    raw = (name or "").strip().lower()
    if not raw:
        raise ValueError("빈 알고리즘 ID")
    if _ALGO_ID_RE.match(raw):
        return raw
    if raw in FAMILY_LABELS:
        return f"{raw}_v1"
    raise ValueError(
        f"알 수 없는 알고리즘 ID: {name}. "
        f"형식={{family}}_v{{N}} 또는 구 family명. families={list(FAMILY_LABELS)}"
    )


def parse_algo_id(name: str) -> tuple[str, str]:
    """algo_id → (family, version_tag) 예: ('catboost', 'v1')."""
    algo_id = normalize_algo_id(name)
    m = _ALGO_ID_RE.match(algo_id)
    if not m:
        raise ValueError(f"algo_id 파싱 실패: {name}")
    family, num = m.group(1).lower(), m.group(2)
    if family not in FAMILY_LABELS:
        raise ValueError(f"미등록 family: {family}")
    return family, f"v{num}"


def family_of(name: str) -> str:
    return parse_algo_id(name)[0]


def version_of(name: str) -> str:
    return parse_algo_id(name)[1]


def algo_display_label(name: str, cfg: dict[str, Any] | None = None) -> str:
    """예: CatBoost (v1). 레지스트리 label 우선."""
    algo_id = normalize_algo_id(name)
    family, ver = parse_algo_id(algo_id)
    label = FAMILY_LABELS.get(family, family)
    if cfg:
        reg = (cfg.get("algorithm_registry") or {}).get(family) or {}
        if isinstance(reg, dict) and reg.get("label"):
            label = str(reg["label"])
        versions = reg.get("versions") if isinstance(reg, dict) else None
        if isinstance(versions, dict):
            meta = versions.get(ver) or {}
            if isinstance(meta, dict) and meta.get("label"):
                return str(meta["label"])
    return f"{label} ({ver})"


def default_algo_labels() -> dict[str, str]:
    return {aid: algo_display_label(aid) for aid in DEFAULT_ALGO_IDS}


def list_algo_ids(cfg: dict[str, Any] | None = None) -> list[str]:
    """등록된 algo_id 목록.

    우선순위: algorithm_registry 전체 → algorithms 리스트 → DEFAULT_ALGO_IDS.
    (UI·학습이 v2 등 레지스트리 버전을 빠짐없이 인식하도록 registry를 우선)
    """
    if cfg:
        reg = cfg.get("algorithm_registry") or {}
        out: list[str] = []
        for family, meta in reg.items():
            versions = (meta or {}).get("versions") or {}
            for ver, vmeta in versions.items():
                if isinstance(vmeta, dict) and vmeta.get("algo_id"):
                    out.append(normalize_algo_id(str(vmeta["algo_id"])))
                else:
                    out.append(normalize_algo_id(f"{family}_{ver}"))
        if out:
            return out
        listed = cfg.get("algorithms")
        if listed:
            return [normalize_algo_id(a) for a in listed]
    return list(DEFAULT_ALGO_IDS)


def default_train_algo_ids(cfg: dict[str, Any] | None = None) -> list[str]:
    """신규 Run 기본 학습 대상 (configs.algorithms, 없으면 v1만)."""
    if cfg:
        listed = cfg.get("algorithms")
        if listed:
            return [normalize_algo_id(a) for a in listed]
    return [a for a in DEFAULT_ALGO_IDS if a.endswith("_v1")]


def registry_payload(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """프론트 2단 UI용: [{family, label, versions: [{version, algo_id, label}]}]."""
    cfg = cfg or {}
    reg = cfg.get("algorithm_registry") or {}
    if not reg:
        # 기본 구성
        by_family: dict[str, list[str]] = {}
        for aid in list_algo_ids(cfg):
            fam, ver = parse_algo_id(aid)
            by_family.setdefault(fam, []).append(aid)
        payload = []
        for fam, aids in by_family.items():
            payload.append(
                {
                    "family": fam,
                    "label": FAMILY_LABELS.get(fam, fam),
                    "versions": [
                        {
                            "version": parse_algo_id(a)[1],
                            "algo_id": a,
                            "label": algo_display_label(a, cfg),
                        }
                        for a in sorted(aids, key=lambda x: parse_algo_id(x)[1])
                    ],
                }
            )
        return payload

    payload = []
    for family, meta in reg.items():
        meta = meta or {}
        versions_out = []
        for ver, vmeta in (meta.get("versions") or {}).items():
            vmeta = vmeta or {}
            aid = normalize_algo_id(str(vmeta.get("algo_id") or f"{family}_{ver}"))
            versions_out.append(
                {
                    "version": ver if str(ver).startswith("v") else f"v{ver}",
                    "algo_id": aid,
                    "label": str(vmeta.get("label") or algo_display_label(aid, cfg)),
                    "script": vmeta.get("script"),
                }
            )
        versions_out.sort(key=lambda x: x["version"])
        payload.append(
            {
                "family": family,
                "label": str(meta.get("label") or FAMILY_LABELS.get(family, family)),
                "versions": versions_out,
            }
        )
    return payload


def build_algo_labels_map(cfg: dict[str, Any] | None = None) -> dict[str, str]:
    labels = default_algo_labels()
    for aid in list_algo_ids(cfg):
        labels[aid] = algo_display_label(aid, cfg)
    # 구 ID 호환 라벨
    for fam in FAMILY_LABELS:
        labels[fam] = algo_display_label(f"{fam}_v1", cfg)
    return labels
