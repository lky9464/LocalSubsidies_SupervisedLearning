# 파이프라인·산출물 요약

작성 기준: 2026-07-17  
실행 주체: **사용자 로컬 Python** (Cursor Agent는 스크립트 실행·민감데이터 읽기 금지)

## 1. 스크립트 순서 (01~09)

| # | 스크립트 | 역할 | 주요 산출 |
|---|----------|------|-----------|
| 01 | `01_merge_raw.py` | raw CSV 통합 | `{data_root}/interim/` |
| 02 | `02_fix_target.py` | `TAET_YN` 수정 | `{data_root}/interim/labeled.csv` |
| 03 | `03_preprocess.py` | Feature·분할·전처리 fit | `{data_root}/processed/` |
| 04 | `04_leakage_audit.py` | 누수 점검 (학습 전) | `outputs/reports/comparison/leakage_audit*` |
| 05 | `05_train.py` (+ `05_train_*.py`) | 5종 모델 학습 | `{data_root}/algorithms/{algo}/model.joblib` |
| 06 | `06_feature_importance.py` | Feature TOP10 | `feature_top10.json`, `outputs/reports/**/feature_importance_top10*.xlsx` |
| 07 | `07_evaluate.py` | Test 평가·행단위 점수 | `{algo}_test_scores.csv`, `{algo}_test_scores_top.xlsx`, `eval_*.json` |
| 08 | `08_report.py` | 집계 Excel/PDF | `outputs/reports/comparison/`, `outputs/reports/{algo}/` |
| 09 | `09_score_inference.py` | 라벨 미지 추론 (선택) | `{data_root}/algorithms/{algo}/scores/inference_scores.csv` |

의존: **`06` → `07`** (TOP10이 점수 컬럼에 필요). `01`~`08` 순차 1회면 Test 점수 파일이 완성된다.

## 2. 시계열 분할·타겟

| 항목 | 값 |
|------|-----|
| Train | `CRTR_YM` 202401 ~ 202506 |
| Test | `CRTR_YM` 202507 ~ 202512 |
| 타겟 | `TAET_YN` (`any_of_y`: ISDP/ISRC/PMBZ 중 1개 이상 Y) |

상세: `docs/label_definition.md`

## 3. 운영 모델 순위 (요약)

1. **RandomForest** — 주 운영  
2. **CatBoost** — 보조·교차  
3. **Stacked Ensemble** — 참고  

상세·S/A/B/C 컷오프: `docs/operations_criteria.md`

## 4. Test 점수 파일 (로컬 전용, GitHub 금지)

경로: `{data_root}/algorithms/{algo}/scores/`

| 파일 | 내용 |
|------|------|
| `{algo}_test_scores.csv` | Test 전체 행 |
| `{algo}_test_scores_top.xlsx` | 시트 `상위1%`, `상위5%` (위험도점수 내림차순) |

### 컬럼 순서 (두 파일 동일)

1. 키: `CRTR_YM`, `PFM_BIZ_ID`, `INST_ID`  
2. 명칭·금액: 수행사업명칭, 기관명, 사업비보조금금액, 사업비자부담금액  
3. `위험도점수(risk_score)`  
4. `양성확률(positive_probability)`  
5. `예측라벨(predicted_label)` (0/1)  
6. `실제라벨(actual_label)` (0/1, Test만)  
7. `기여도TOP01_…` ~ `기여도TOP10_…` (해당 알고리즘 Feature TOP10의 **행별 값**)

추론(`09`)에는 실제라벨이 없으며, TOP10 열은 `06` 산출물을 사용한다.

## 5. GitHub에 올리는 것 / 올리지 않는 것

| 허용 | 금지 |
|------|------|
| `src/`, `scripts/`, `configs/default.yaml`, `configs/local.yaml.example` | `configs/local.yaml` |
| `docs/`, `README.md`, `TLS4902R_Layout.csv` | `{data_root}` 전체 (raw/interim/processed/algorithms) |
| `outputs/reports/` 집계 Excel·PDF·json | 행단위 `*_test_scores*`, 모델 `.joblib` |
| `.cursor/rules/`, `.gitignore`, `.cursorignore` | `.venv/`, raw CSV |

## 6. 관련 문서

| 문서 | 내용 |
|------|------|
| `docs/AGENT_BOUNDARY.md` | Agent vs 로컬 실행 경계 |
| `docs/metrics_guide.md` | 지표 비전문가 해설 |
| `docs/operations_criteria.md` | 모델 순위·점검 등급 |
| `docs/leakage_checklist.md` | 누수 점검 |
| `docs/label_definition.md` | 타겟 정의 |
