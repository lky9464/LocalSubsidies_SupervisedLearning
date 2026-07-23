# 파이프라인 실행 순서

로컬 전용. Cursor Agent는 아래 스크립트를 실행하지 않습니다.

| 번호 | 스크립트 | 역할 | 주요 산출 |
|------|----------|------|-----------|
| 01 | `01_merge_raw.py` | 원본 CSV 통합 | `{data_root}/interim/merged.csv` |
| 02 | `02_fix_target.py` | 타겟 `TAET_YN` 수정 | `interim/labeled.csv` |
| 03 | `03_preprocess.py` | 분할(time/random)+전처리 | `processed/` |
| 04 | `04_leakage_audit.py` | 누수 점검 | `outputs/reports/comparison/leakage_audit*` |
| 05 | `05_train.py` / `05_train_{family}_v1.py` | 학습 (`--algo` = algo_id) | `algorithms/{algo_id}/model.joblib` |
| 06 | `06_feature_importance.py` | Feature TOP10 | `feature_top10.json` + Excel |
| 07 | `07_evaluate.py` | 평가·점수 파일 | `scores/test/{algo}_test_scores*` |
| 08 | `08_update_ranking.py` | 모델 순위·역할 | `model_ranking.json` (+ `ranking_confidence`) + SQLite · [`ranking_methodology.md`](ranking_methodology.md) |
| 09 | `09_report.py` | 집계 리포트 | `outputs/reports/` |
| 10 | `10_ops_queue.py` | 타겟 포착 분포 (Test 주/보 A~D · 4×4) | `algorithms/operations/ops_queue_test.*` |
| 11 | `11_score_inference.py` | 라벨 미지 추론 · 점검 우선순위표 | `scores/inference/{algo}_inference_scores*` · `ops_queue_inference.*` |
| 12 | `12_tune_hyperparams.py` | Validation 하이퍼 탐색 (RF·CatBoost, Test 미사용) | `outputs/reports/comparison/hyperparam_tune_*` |

웹 UI **학습 파이프라인**은 01~10만 포함합니다. 추론(11)은 **추론** 메뉴입니다.  
튜닝(12)은 CLI 전용이며, 반영 후 다시 `05`~`10`으로 Test 확정합니다. 상세: [`model_tuning.md`](model_tuning.md).

백그라운드 Job: `scripts/_job_worker.py` + `src/pipeline/jobs.py`  
run별 옵션: `{data_root}/runs/{run_id}/run_config.yaml` (`algorithms` = algo_id 리스트, `model_params` 오버라이드 가능)  
기본 하이퍼: `configs/default.yaml` → `model_params.{algo_id}`  
알고리즘 ID: `{family}_v{N}` (예: `random_forest_v1`). 레지스트리: `algorithm_registry`.  
로컬 폴더 rename: [`algo_id_migration.md`](algo_id_migration.md)

같은 Run에서 파이프라인을 다시 실행하면 `interim` / `processed` / `algorithms` 등 **작업용 산출은 덮어쓰기**됩니다. Run당 화면·파일 기준 결과는 **가장 최근 성공 실행**입니다.
