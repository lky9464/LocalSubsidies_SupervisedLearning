"""cleanup_legacy_artifacts reports 보존 규칙."""

from __future__ import annotations

from pathlib import Path

from scripts.cleanup_legacy_artifacts import _clear_reports_dir


def test_clear_reports_preserves_tuning(tmp_path: Path) -> None:
    reports = tmp_path / "outputs" / "reports"
    reports.mkdir(parents=True)
    (reports / "random_forest_v1").mkdir()
    (reports / "random_forest_v1" / "x.xlsx").write_text("x", encoding="utf-8")
    tuning = reports / "tuning" / "v2"
    tuning.mkdir(parents=True)
    (tuning / "hyperparam_tune_best.yaml").write_text("k: v", encoding="utf-8")

    removed, kept = _clear_reports_dir(reports)

    assert removed == 1
    assert kept == ["tuning"]
    assert not (reports / "random_forest_v1").exists()
    assert (tuning / "hyperparam_tune_best.yaml").exists()
    assert (reports / "comparison").is_dir()


def test_clear_reports_can_wipe_tuning(tmp_path: Path) -> None:
    reports = tmp_path / "outputs" / "reports"
    tuning = reports / "tuning" / "v3"
    tuning.mkdir(parents=True)
    (tuning / "manifest.yaml").write_text("v3", encoding="utf-8")

    removed, kept = _clear_reports_dir(reports, preserve_subdirs=frozenset())

    assert removed == 1
    assert kept == []
    assert not (reports / "tuning").exists()
