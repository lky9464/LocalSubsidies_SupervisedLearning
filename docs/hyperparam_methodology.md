# 하이퍼파라미터 고도화 방법론 (제안만 · 수치 미적용)

본 문서는 **수정 방안·방법론**만 제시합니다.  
`configs/default.yaml`의 `model_params` 수치 변경·`*_v2` 스크립트 추가는 **로컬 실험·승인 후** 별도 작업으로 수행합니다.

전제: 알고리즘 ID = `{family}_v{N}` ([`algo_id_migration.md`](algo_id_migration.md)). 채택 결과는 해당 family의 **새 버전(v2+)** 으로 추가하고 v1은 유지합니다.

관련: [`model_tuning.md`](model_tuning.md) · [`operations_criteria.md`](operations_criteria.md)

---

## 1. 공통 원칙

| 항목 | 고정 |
|------|------|
| 1순위 지표 | Validation 상위 **1%·5% 리프트** (및 양성 포착비율) |
| 2순위 | **PR-AUC** |
| 가드 | 기준선 대비 정밀도 비율 (`tune.min_precision_ratio`, 기본 0.85) 미달 시 탈락 |
| 탐색 구간 | Train 내부 Validation (`split.valid_start`~`valid_end`)만 |
| 확정 | 기존 Test 구간으로 **07→08→10 1회** (Test로 반복 튜닝 금지) |
| 환경 | `memory.n_jobs: 2`, 16GB RAM 친화 — 깊이·트리 수 과도한 확대 지양 |
| 도구 | `python scripts/12_tune_hyperparams.py --algo {algo_id}` |
| 튜닝 분할 | `tune.split_mode`: `random`(풀 기간 랜덤) 또는 `time`(Train 내 valid 월) |

현재 default: `tune.split_mode=random`, `pool_start=202401`, `pool_end=202512`, `valid_size=0.2`  
(본 학습/평가의 `split.mode=time` Train/Test와는 독립)

---

## 2. Family별 권장 탐색축

현재 v1 기본값은 기존 factory 수치와 동일합니다. 아래는 **다음에 바꿀 후보 축**입니다.

### 2.1 random_forest (`random_forest_v1` → 채택 시 `random_forest_v2`)

| 파라미터 | v1 기본 | 탐색 제안 |
|----------|---------|-----------|
| `n_estimators` | 200 | 150 ~ 400 |
| `max_depth` | 20 | 12 ~ 28 (너무 깊으면 과적합·RAM) |
| `min_samples_leaf` | 5 | 2 ~ 10 |

유지: `class_weight=balanced`, `n_jobs=2`.

### 2.2 catboost (`catboost_v1` → `catboost_v2`)

| 파라미터 | v1 기본 | 탐색 제안 |
|----------|---------|-----------|
| `iterations` | 400 | 300 ~ 800 |
| `depth` | 6 | 4 ~ 8 |
| `learning_rate` | 0.05 | 0.02 ~ 0.1 |

권장: Validation 기준 early stopping 검토(구현 시 v2에서). `auto_class_weights=Balanced` 유지.

### 2.3 gradient_boosting (`gradient_boosting_v1`)

| 파라미터 | v1 기본 | 탐색 제안 |
|----------|---------|-----------|
| `max_iter` | 300 | 200 ~ 500 |
| `max_depth` | 6 | 3 ~ 8 |
| `learning_rate` | 0.05 | 0.03 ~ 0.1 |
| `max_bins` | 128 | 64 ~ 255 (메모리 주의) |

### 2.4 stacked_ensemble (`stacked_ensemble_v1`)

| 파라미터 | v1 기본 | 탐색 제안 |
|----------|---------|-----------|
| `rf_n_estimators` / `rf_max_depth` | 100 / 16 | RF와 유사 소규모 |
| `hgb_max_iter` / `hgb_max_depth` / `hgb_learning_rate` | 150 / 5 / 0.05 | HGB와 유사 |
| `cv` | 3 | 3 유지 권장 (시간) |

학습 시간이 길어 주·보 확정 후·시간 여유 있을 때만 본격 탐색.

### 2.5 easy_ensemble (`easy_ensemble_v1`)

| 파라미터 | v1 기본 | 탐색 제안 |
|----------|---------|-----------|
| `n_estimators` | 8 | 5 ~ 15 |

불균형 대응용. 과거 스냅샷에서 순위가 낮았으므로 **기준선 재평가 우선**, 대규모 격자는 후순위.

---

## 3. 채택 후 버전 업 절차 (구현은 별도)

1. Validation에서 best 후보 확정 (`hyperparam_tune_*.json` 집계만 참고)
2. `model_params.{family}_v2` 추가 + `algorithm_registry.{family}.versions.v2`
3. `scripts/05_train_{family}_v2.py` 추가 (v1 스크립트 유지)
4. `05`~`10`으로 Test 확정 · 주·보·`operations_criteria` 갱신
5. [`VERSION_HISTORY.md`](VERSION_HISTORY.md) 기록

**이 문서 작성 시점에 v2 수치·스크립트는 만들지 않습니다.**
