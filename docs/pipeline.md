# 파이프라인 실행 순서

로컬 전용. Cursor Agent는 아래 스크립트를 실행하지 않습니다.

| 번호 | 스크립트 | 역할 | 주요 산출 |
|------|----------|------|-----------|
| 01 | `01_merge_raw.py` | 원본 CSV 통합 | `{data_root}/interim/merged.csv` |
| 02 | `02_fix_target.py` | 타겟 `TAET_YN` 수정 | `interim/labeled.csv` |
| 03 | `03_preprocess.py` | 분할(time/random)+전처리 | `processed/` |
| 04 | `04_leakage_audit.py` | 누수 점검 | `outputs/reports/comparison/leakage_audit*` |
| 05 | `05_train.py` | 학습 (`--algo` 복수) | `algorithms/{algo}/model.joblib` |
| 06 | `06_feature_importance.py` | Feature TOP10 | `feature_top10.json` + Excel |
| 07 | `07_evaluate.py` | 평가·점수 파일 | `scores/test/{algo}_test_scores*` |
| 08 | `08_update_ranking.py` | 모델 1~5위 | `model_ranking.json` + SQLite |
| 09 | `09_report.py` | 집계 리포트 | `outputs/reports/` |
| 10 | `10_ops_queue.py` | 타겟 포착 분포 (Test 주/보 A~D · 4×4) | `algorithms/operations/ops_queue_test.*` |
| 11 | `11_score_inference.py` | 라벨 미지 추론 · 점검 우선순위표 | `scores/inference/{algo}_inference_scores*` · `ops_queue_inference.*` |

웹 UI **학습 파이프라인**은 01~10만 포함합니다. 추론(11)은 **추론** 메뉴입니다.

백그라운드 Job: `scripts/_job_worker.py` + `src/pipeline/jobs.py`  
run별 옵션: `{data_root}/runs/{run_id}/run_config.yaml`
