# 하이퍼파라미터 튜닝 — 원리·방식·알고리즘별 설명

본 문서는 **하이퍼파라미터 튜닝을 처음 접하는 분**도 원리를 이해할 수 있도록 작성했습니다.  
실행 절차·기준선·반영 체크리스트는 [`model_tuning.md`](model_tuning.md), 운영·4×4 기준은 [`operations_criteria.md`](operations_criteria.md)를 참고하세요.

전제: 알고리즘 ID = `{family}_v{N}` ([`algo_id_migration.md`](algo_id_migration.md)). 채택 결과는 해당 family의 **새 버전(v2+)** 으로 추가하고 v1은 유지합니다.

> **수치 반영:** RF·CatBoost Validation best는 `random_forest_v2` / `catboost_v2`로 **등록됨** (§5.1).  
> Test 확정(`05`~`10`)·주·보 갱신은 사용자 로컬에서 진행합니다.

---

## 0. 이 문서에서 다루는 것

| 주제 | 위치 |
|------|------|
| 하이퍼파라미터가 무엇인지 | §1 |
| Train / Valid / Test를 왜 나누는지 | §1.3 |
| `12_tune_hyperparams.py`가 28회 돌리는 방식 | §2 |
| best 선정·엑셀 행 순서 | §2.4 |
| 5종 알고리즘·파라미터 뜻 | §3 |
| 향후 격자 확대 제안 | §4 |
| v2 채택 절차 | §5 |
| **권장 튜닝 로드맵 (단계별)** | **§8** |
| **`tune.method` Grid \| Optuna 설계 (미구현)** | **§9** |

---

## 1. 기초 개념

### 1.1 학습 파라미터 vs 하이퍼파라미터

| 구분 | 누가 정하나 | 예 |
|------|-------------|-----|
| **학습 파라미터** | 모델이 **데이터를 보며 스스로** 학습 | 결정트리의 분기 기준, CatBoost leaf 가중치 |
| **하이퍼파라미터** | 사람(또는 튜닝 스크립트)이 **학습 전에** 정함 | 트리 개수, 깊이, learning rate |

하이퍼파라미터 튜닝 = “모델 구조·학습 강도를 **몇 가지 후보 조합**으로 바꿔 가며, **어느 조합이 우리 업무에 가장 맞는지** 고르는 작업”입니다.

### 1.2 왜 튜닝하나

같은 데이터·같은 알고리즘이라도 하이퍼파라미터에 따라:

- 상위 1% 점검 큐에 타겟이 **더 많이 모이는지**(리프트)
- 정밀도가 **너무 떨어져 과탐이 늘지 않는지**
- 학습 시간·RAM이 **PC에서 감당 가능한지**

가 달라집니다. 기본값(v0.3.0 baseline)은 출발점이고, **Validation에서 더 나은 조합**을 찾아 반영하는 것이 목표입니다.

### 1.3 Train · Validation · Test — 역할 구분

```text
풀 202401~202512
├─ ~70% Train ──┬─ ~80% fit   (튜닝 시 “학습”에 사용)
│               └─ ~20% Valid (튜닝 시 “모의고사” — best 선택)
└─ ~30% Test    (최종 1회만 — 07→08→10)
```

| 구간 | 이 프로젝트에서 하는 일 |
|------|-------------------------|
| **fit** | 후보별 모델 **학습** |
| **Valid** | 후보별 **점수·리프트 계산** → best 선정 (`scripts/12`) |
| **Test** | 채택 후 **최종 성능·4×4·주·보** 확정 (`07`~`10`) |

**Valid로 best를 고르고, Test로 “정말 괜찮은지” 1번만 확인**합니다. Test로 반복 튜닝하면 Test에 맞춰져 **과적합(낙관적 평가)** 이 됩니다.

튜닝 분할 설정: `tune.split_mode=nested_random` — 03의 `train_mask` **안에서만** fit/valid를 80/20으로 나눕니다.

### 1.4 과적합·과소적합 (직관)

| 상태 | 증상 | 하이퍼파라미터 쪽 힌트 |
|------|------|------------------------|
| **과소적합** | Train·Valid 모두 성능 낮음 | 모델을 조금 **복잡하게** (트리 깊이↑, 트리 수↑ 등) |
| **과적합** | Train은 좋은데 Valid/Test가 나쁨 | **단순하게** (깊이↓, min_samples_leaf↑, learning rate↓+iterations 조정) |

Valid는 Train의 일부이므로 완벽한 “미래 예측”은 아니지만, **같은 시기 데이터 안에서** 후보 간 상대 비교에는 적합합니다.

### 1.5 탐색 방법 종류 (본 프로젝트는 어디에 해당?)

| 방법 | 설명 | 본 프로젝트 |
|------|------|-------------|
| **수동** | 사람이 값 하나 바꿔 재학습 | 반영 단계에서 `model_params` 수동 병합 |
| **격자 탐색 (Grid Search)** | 정해진 후보 목록의 **모든 조합** 시도 | **`12` 현재 기본** (`tune.grids`, §2) |
| **무작위 탐색** | 범위에서 무작위 샘플 | 미구현 · §9에서 Optuna RandomSampler 대안 |
| **Optuna TPE** | 이전 trial로 유망 구역 집중 샘플 | **§9 설계안** (Stacked·넓은 범위용) |

RAM·시간(약 16GB, `n_jobs=2`)을 고려해 **축 3개 × 값 3개 = 27조합 + 기준선 1** 수준의 **소규모 전수 격자**를 택했습니다.

---

## 2. `scripts/12_tune_hyperparams.py` 동작 원리

코드: [`src/models/tune.py`](../src/models/tune.py) · 설정: [`configs/default.yaml`](../configs/default.yaml) → `tune`

### 2.1 전체 흐름

```text
1) labeled.csv + preprocess_bundle + split_masks 로드
2) Train 마스크 안에서 fit / valid 분리 (nested_random)
3) model_params = 기준선(base_params) 확정
4) tune.grids 로 후보 조합(delta) 생성
5) 각 trial: params = base_params + delta → 학습(fit) → Valid 예측 → 지표 계산
6) rank_candidates: 정밀도 가드 → top1_lift → top5_lift → PR-AUC 순 정렬
7) hyperparam_tune_{algo}.json / .xlsx / hyperparam_tune_best.yaml 저장
```

대상 알고리즘(기본): `random_forest_v1`, `catboost_v1` (`tune.algorithms`).  
EasyEnsemble / Stacked / HistGB는 `12` **자동 격자 대상 아님** (§3·§4 참고).

### 2.2 28회(trial)는 어떻게 만들어지나

RF·CatBoost 모두 `tune.grids`에 **파라미터 3개 × 각 3값** 이 있으면:

```text
1회 (trial 1)  : delta = {}  → 변경 없음, 현재 model_params = 기준선(baseline)
2~28회         : 3 × 3 × 3 = 27가지 조합 (itertools.product 전수 조합)
────────────────
합계 28회
```

격자 전개 코드:

```python
# 의사코드
for delta in [{}] + all_combinations(tune.grids):
    params = {**base_params, **delta}  # grids에 없는 키는 base 유지
    train → evaluate on Valid
```

**고정되는 것:** `class_weight`, CatBoost `auto_class_weights`, 피처·전처리·seed·fit/valid 행  
**바뀌는 것:** `grids`에 적힌 3개 축만 trial마다 교체

### 2.3 현재 격자 (`default.yaml`)

**random_forest_v1**

| 파라미터 | 탐색 값 | v1 기본 (기준선) |
|----------|---------|------------------|
| `n_estimators` | 150, 200, 300 | 200 |
| `max_depth` | 16, 20, 24 | 20 |
| `min_samples_leaf` | 3, 5, 8 | 5 |

고정: `class_weight=balanced`

**catboost_v1**

| 파라미터 | 탐색 값 | v1 기본 |
|----------|---------|---------|
| `iterations` | 300, 400, 500 | 400 |
| `depth` | 5, 6, 7 | 6 |
| `learning_rate` | 0.03, 0.05, 0.08 | 0.05 |

고정: `auto_class_weights=Balanced`

### 2.4 best 선정·엑셀 행 순서

| 단계 | 내용 |
|------|------|
| **정밀도 가드** | Valid 정밀도 < `baseline_precision × tune.min_precision_ratio`(기본 0.85) → `precision_guard_pass = F` |
| **1순위** | `top1_lift` (상위 1% 리프트) — 주A 점검 큐와 정합 |
| **2순위** | `top5_lift` (상위 5% 리프트) — 주B 구간 |
| **3순위** | `PR-AUC` (불균형 순위 능력) |

엑셀 **위→아래**: 가드 통과(T) 후보를 위 지표 순으로 정렬 → **1행 = best** → 가드 탈락(F)은 맨 아래.  
**trial 번호 ≠ 행 순서** (1행이 trial 1 baseline일 필요 없음).

산출물: `outputs/reports/comparison/hyperparam_tune_*.json` / `.xlsx`, 추천값 `hyperparam_tune_best.yaml`  
지표 해설: [`metrics_guide.md`](metrics_guide.md)

---

## 3. 알고리즘별 상세 (5종)

아래는 **이 프로젝트에서 쓰는 구현**(`src/models/factory.py`) 기준입니다.  
`*_v1`은 동일 family 내 **버전 ID**일 뿐, v1끼리도 `model_params`로 수치를 다르게 둘 수 있습니다.

---

### 3.1 Random Forest (`random_forest_v1`)

**한 줄:** 여러 **결정트리**를 각각 다른 데이터/특성 샘플로 학습시키고, **다수결(또는 확률 평균)** 로 예측하는 앙상블.

**왜 쓰나:** 해석·안정성·범주형+수치형 혼합에 강하고, 본 프로젝트 **주 모델(primary)** 후보로 07·08 순위가 높았음 ([`operations_criteria.md`](operations_criteria.md) §2.1).

| 하이퍼파라미터 | 의미 | 값을 올리면 | 값을 내리면 |
|----------------|------|-------------|-------------|
| **`n_estimators`** | 트리 **개수** | 일반적으로 분산↓·안정↑, **학습·예측 시간↑** | 빠르지만 불안정할 수 있음 |
| **`max_depth`** | 트리 **최대 깊이** | 복잡한 규칙·Train 적합↑, **과적합·RAM↑** 위험 | 단순한 규칙, 과소적합 위험 |
| **`min_samples_leaf`** | leaf(말단)에 필요한 **최소 샘플 수** | 규칙 단순화·과적합 완화 | 더 잘게 쪼개어 Train에 맞춤 |
| **`class_weight=balanced`** (고정) | 소수 클래스(타겟 Y)에 **가중치** | 불균형(양성 ~0.27%)에서 Y를 덜 놓치도록 유도 | — |
| **`n_jobs=2`** (환경) | 병렬 트리 학습 | CPU/RAM 사용 | 16GB PC 보호 |

**튜닝 직관 (RF):**

- 리프트만 올리고 싶다 → `max_depth`·`n_estimators`를 올리는 조합을 탐색 (가드로 정밀도 하한 유지)
- Valid는 좋은데 Test가 나쁘다 → `max_depth` 낮추기, `min_samples_leaf` 올리기 검토
- `12` 격자는 **깊이·트리 수·leaf** 세 축만 바꾸고, 불균형 처리(`class_weight`)는 고정

---

### 3.2 CatBoost (`catboost_v1`)

**한 줄:** **부스팅** 계열. 이전 트리의 오류를 다음 트리가 보완하며 순차 학습. **범주형 변수**를 네이티브하게 잘 다룸.

**왜 쓰나:** 재현율·상위 K% 리프트가 좋아 **보조 모델(aux)** 에 적합했던 스냅샷 ([`operations_criteria.md`](operations_criteria.md) §3.2).

| 하이퍼파라미터 | 의미 | 값을 올리면 | 값을 내리면 |
|----------------|------|-------------|-------------|
| **`iterations`** | 부스팅 **라운드(트리) 수** | 학습 더 진행·복잡도↑, **과적합·시간↑** | 빠르지만 underfit 가능 |
| **`depth`** | 각 트리 **깊이** | 상호작용·복잡 규칙↑ | 단순·빠름 |
| **`learning_rate`** | 한 라운드당 **보정 강도** | 보통 **iterations와 Trade-off** (높으면 빠르게 수렴하지만 거칠 수 있음) | 더 세밀하지만 iterations 많이 필요 |
| **`auto_class_weights=Balanced`** (고정) | 클래스 불균형 자동 가중 | Y(양성) 학습 강조 | — |

**튜닝 직관 (CatBoost):**

- `learning_rate` ↑ + `iterations` ↓ vs `learning_rate` ↓ + `iterations` ↑ 는 비슷해 보여도 Valid 리프트가 다를 수 있음 → 격자로 비교
- `depth` 7·`iterations` 500은 RAM/시간 부담 — Owner PC에서는 §4 권장 범위 내에서 확장
- v1 `12`에는 **early stopping 미적용**; Valid loss 보고 iterations를 자르는 방식은 v2 검토 항목

---

### 3.3 Histogram Gradient Boosting (`gradient_boosting_v1`)

**한 줄:** scikit-learn **HistGradientBoostingClassifier**. 연속형을 **구간(bin)** 으로 나눠 빠르게 부스팅. CatBoost와 비슷한 “트리 부스팅” 계열이지만 **범주형 전용 처리는 전처리(ordinal 등)** 에 의존.

| 하이퍼파라미터 | 의미 | 튜닝 시 참고 |
|----------------|------|--------------|
| **`max_iter`** | 부스팅 반복 횟수 | CatBoost `iterations`에 해당 |
| **`max_depth`** | 트리 깊이 | CatBoost `depth`에 해당 |
| **`learning_rate`** | 학습률 | iterations와 Trade-off |
| **`max_bins`** | 연속형 **구간 수** | ↑ = 세밀하지만 **메모리↑** (기본 128) |
| **`class_weight=balanced`** | 불균형 가중 | RF와 동일 목적 |

**본 프로젝트:** `12` **자동 격자 미포함**. 주·보(RF/CatBoost) 확정 후 필요 시 **수동·소규모** 재평가 ([`model_tuning.md`](model_tuning.md) §4).

---

### 3.4 Stacked Ensemble (`stacked_ensemble_v1`)

**한 줄:** **RF + HistGB** 두 모델을 **베이스**로 학습하고, 그 예측을 입력으로 **로지스틱 회귀(meta)** 가 최종 분류. `StackingClassifier`, 내부 **교차검증(cv)** 로 meta 학습.

```text
입력 X
  ├─ RF  ──→ 예측 p1 ─┐
  └─ HGB ──→ 예측 p2 ─┼─→ LogisticRegression(meta) ─→ 최종
                      (cv=3 fold)
```

| 하이퍼파라미터 | 의미 |
|----------------|------|
| **`rf_n_estimators` / `rf_max_depth` / `rf_min_samples_leaf`** | 베이스 RF 쪽 (§3.1과 동일 개념, 이름 접두 `rf_`) |
| **`hgb_max_iter` / `hgb_max_depth` / `hgb_learning_rate` / `hgb_max_bins`** | 베이스 HGB 쪽 (§3.3) |
| **`meta_max_iter`** | 최종 로지스틱 반복 상한 |
| **`cv`** | meta 학습용 **내부 CV fold 수** (기본 3). ↑면 시간↑ |

**튜닝 직관:** 베이스 2개 + meta + CV라 **한 trial 비용이 큼**. `12` 일괄 격자 대상 아님. 순위·4×4는 **참고 모델**로 두고, 시간 여유 있을 때 RF/HGB 축을 **각각 소규모**로 조정하는 방식이 현실적 (§4.4).

---

### 3.5 EasyEnsemble (`easy_ensemble_v1`)

**한 줄:** **불균형 전용** 앙상블. 다수(정상) 클래스를 **여러 번 다운샘플링**해 여러 분류기를 학습하고, 그 예측을 **평균**.

| 하이퍼파라미터 | 의미 |
|----------------|------|
| **`n_estimators`** | 다운샘플링 **서브셋·분류기 개수** (기본 8). ↑면 다양성↑ but **시간↑** |

**튜닝 직관:** 과거 Test 스냅샷에서 순위가 낮았음 → **대규모 격자보다 기준선 재평가 우선**. `n_estimators` 5~15 정도만 보더라도 trial당 비용이 RF/CatBoost보다 부담될 수 있음.

---

### 3.6 알고리즘·튜닝 지원 요약

| algo_id | 학습 방식 | `12` 자동 격자 | 주요 튜닝 축 |
|---------|-----------|----------------|--------------|
| `random_forest_v1` | Bagging (다수 트리) | **예** (28 trial) | n_estimators, max_depth, min_samples_leaf |
| `catboost_v1` | Boosting | **예** (28 trial) | iterations, depth, learning_rate |
| `gradient_boosting_v1` | Hist Boosting | 아니오 | max_iter, max_depth, learning_rate, max_bins |
| `stacked_ensemble_v1` | Stacking (RF+HGB→LR) | 아니오 | rf_*, hgb_*, cv, meta_max_iter |
| `easy_ensemble_v1` | 불균형 앙상블 | 아니오 | n_estimators |

---

## 4. Family별 권장 탐색축 (다음 실험 후보)

현재 v1 기본값은 [`configs/default.yaml`](../configs/default.yaml) `model_params`와 동일합니다.  
`12`의 **현재 격자**는 §2.3이고, 아래는 **격자를 넓힐 때** 참고할 범위입니다.

### 4.1 random_forest (`random_forest_v1` → 채택 시 `random_forest_v2`)

| 파라미터 | v1 기본 | 탐색 제안 |
|----------|---------|-----------|
| `n_estimators` | 200 | 150 ~ 400 |
| `max_depth` | 20 | 12 ~ 28 (너무 깊으면 과적합·RAM) |
| `min_samples_leaf` | 5 | 2 ~ 10 |

유지: `class_weight=balanced`, `n_jobs=2`.

### 4.2 catboost (`catboost_v1` → `catboost_v2`)

| 파라미터 | v1 기본 | 탐색 제안 |
|----------|---------|-----------|
| `iterations` | 400 | 300 ~ 800 |
| `depth` | 6 | 4 ~ 8 |
| `learning_rate` | 0.05 | 0.02 ~ 0.1 |

권장: Validation 기준 early stopping 검토(구현 시 v2에서). `auto_class_weights=Balanced` 유지.

### 4.3 gradient_boosting (`gradient_boosting_v1`)

| 파라미터 | v1 기본 | 탐색 제안 |
|----------|---------|-----------|
| `max_iter` | 300 | 200 ~ 500 |
| `max_depth` | 6 | 3 ~ 8 |
| `learning_rate` | 0.05 | 0.03 ~ 0.1 |
| `max_bins` | 128 | 64 ~ 255 (메모리 주의) |

### 4.4 stacked_ensemble (`stacked_ensemble_v1`)

| 파라미터 | v1 기본 | 탐색 제안 |
|----------|---------|-----------|
| `rf_n_estimators` / `rf_max_depth` | 100 / 16 | RF와 유사 소규모 |
| `hgb_max_iter` / `hgb_max_depth` / `hgb_learning_rate` | 150 / 5 / 0.05 | HGB와 유사 |
| `cv` | 3 | 3 유지 권장 (시간) |

학습 시간이 길어 주·보 확정 후·시간 여유 있을 때만 본격 탐색.

### 4.5 easy_ensemble (`easy_ensemble_v1`)

| 파라미터 | v1 기본 | 탐색 제안 |
|----------|---------|-----------|
| `n_estimators` | 8 | 5 ~ 15 |

불균형 대응용. 과거 스냅샷에서 순위가 낮았으므로 **기준선 재평가 우선**, 대규모 격자는 후순위.

---

## 5. 채택 후 버전 업 절차

1. Validation에서 best 후보 확정 (`hyperparam_tune_*.json` 집계만 참고)
2. `model_params.{family}_v2` 추가 + `algorithm_registry.{family}.versions.v2`
3. `scripts/05_train_{family}_v2.py` 추가 (v1 스크립트 유지)
4. `05`~`10`으로 Test 확정 · 주·보·`operations_criteria` 갱신
5. [`VERSION_HISTORY.md`](VERSION_HISTORY.md) 기록

### 5.1 적용 현황 (Validation 채택 · Test 확정 전)

| algo_id | 채택 하이퍼 (요약) | 상태 |
|---------|-------------------|------|
| `random_forest_v2` | `n_estimators=200`, `max_depth=24`, `min_samples_leaf=8` | **등록됨** · Test `05`~`10` 대기 |
| `catboost_v2` | `iterations=500`, `depth=7`, `learning_rate=0.08` | **등록됨** · Test `05`~`10` 대기 |

v1은 기준선으로 유지. `ops_queue` 주·보는 Test 확정 전까지 `*_v1` 유지.

---

## 8. 권장 튜닝 로드맵 (단계별)

RF·CatBoost v2 등록 이후 **어디까지 튜닝하고, 언제 Optuna를 도입할지**에 대한 합의안입니다.  
실행·Test 확정은 사용자 로컬 ([`model_tuning.md`](model_tuning.md) §4).

### 8.1 Phase 1 — 주·보 v2에서 멈춤 (지금)

| 항목 | 내용 |
|------|------|
| 대상 | `random_forest_v2`, `catboost_v2` (Validation best → registry 등록 완료) |
| 다음 | 웹 **학습 옵션 v2** 선택 → `05`~`10` **Test 1회** |
| 판단 | baseline(v1) 대비 top1/top5 리프트·4×4·정밀도 **유지 또는 개선** |
| 멈춤 | Test 통과 시 **v2에서 RF/CB 튜닝 종료** · `ops_queue` 갱신 검토 |
| Optuna | **당장 불필요** — v1 grid 28회로 이미 소규모 공간 전수 탐색함 |

### 8.2 Phase 2 — 나머지 3종 (우선순위·방식 분리)

주·보(RF/CatBoost) 확정 후 **참고·순위 3~5위** 모델을 가볍게 다룹니다.  
**5종 모두 RF/CB와 동일 28회 grid**는 비권장 (특히 Stacked).

| algo_id | 우선순위 | 권장 방식 | trial 규모 |
|---------|----------|-----------|------------|
| `gradient_boosting_v1` | **중** | `12` grid 확장 또는 수동 1축 | 축 3~4개 · **15~27회** |
| `stacked_ensemble_v1` | **낮~중** | **grid 전수 금지** · 1축씩 또는 §9 Optuna | trial당 RF+HGB+meta+CV → **비용 큼** |
| `easy_ensemble_v1` | **낮** | `n_estimators`만 · 짧은 grid | **5~10회** · 순위 낮으면 07·08 재평가만 |

**HistGB(`gradient_boosting_v1`) 예시 grid (Phase 2):**

```yaml
# tune.grids 확장 후보 (구현·실험은 별도)
gradient_boosting_v1:
  max_iter: [200, 300, 400]
  max_depth: [4, 6, 8]
  learning_rate: [0.03, 0.05, 0.08]
  # max_bins: [128]  # 1차는 고정 권장 (RAM)
```

**Stacked / EasyEnsemble:** 급하지 않으면 **baseline `07`·`08` 재실행**으로 순위만 확인한 뒤, 본격 튜닝은 Phase 3 이후.

### 8.3 Phase 3 — 탐색 엔진 업그레이드 (Optuna)

**시점:** Stacked 본격 튜닝 · HistGB v2 · RF/CatBoost **v3(범위 확대)** 직전.

| 도입 | 이유 |
|------|------|
| **Optuna TPE** | 연속 범위·다축·Stacked처럼 grid 폭발 시 **적은 trial로 유망 구역** 탐색 |
| **CatBoost pruning** | `iterations` full run이 병목 → Valid early stopping으로 **wall-clock 단축** |
| **grid 유지** | v1/v2 소규모 3×3×3 · 재현·감사용 baseline 비교 |

**하지 않을 것:** Test로 반복 튜닝 · `top1_lift`·정밀도 가드 정책 변경.

### 8.4 로드맵 한눈에

```text
[Phase 1] RF/CB v2 Test 확정 → 주·보 갱신 → v2 튜닝 STOP
    ↓
[Phase 2] HistGB 소규모 grid · Stacked/EE는 07·08 또는 극소 trial
    ↓
[Phase 3] tune.method=optuna 구현 → Stacked / 넓은 범위 / v3
    ↓
[항상] Valid 선택 · Test 1회 확정 · hyperparam_tune_* 집계 저장
```

---

## 9. 향후 `tune.method` 설계 (Grid | Optuna) — **미구현**

§8 Phase 3용 **코드·설정 설계안**입니다. 아직 `src/models/tune.py`에 반영하지 않았습니다.

### 9.1 목표

- **`grid`** (현행): `tune.grids` 전수 조합 + baseline 1회
- **`optuna`**: TPE sampler + (CatBoost) trial pruning
- **공통 유지:** `nested_random` Valid · `score_candidate` · `rank_candidates` · JSON/XLSX 산출 형식

### 9.2 설정 (`configs/default.yaml` 예시)

```yaml
tune:
  method: grid          # grid | optuna  (기본 grid — 현행 유지)
  # --- optuna 전용 (method=optuna 일 때) ---
  n_trials: 25          # grid 28 대비 비슷~적은 trial
  optuna_sampler: tpe   # tpe | random
  optuna_seed: 42
  catboost_pruning: true
  catboost_early_stopping_rounds: 50
  # 연속/넓은 범위 (grid 대신 search_space)
  search_space:
    random_forest_v1:
      n_estimators: { type: int, low: 150, high: 400, step: 25 }
      max_depth: { type: int, low: 12, high: 28 }
      min_samples_leaf: { type: int, low: 2, high: 10 }
    catboost_v1:
      iterations: { type: int, low: 300, high: 800, step: 50 }
      depth: { type: int, low: 4, high: 8 }
      learning_rate: { type: float, low: 0.02, high: 0.1, log: true }
    gradient_boosting_v1:
      max_iter: { type: int, low: 200, high: 500, step: 50 }
      max_depth: { type: int, low: 3, high: 8 }
      learning_rate: { type: float, low: 0.03, high: 0.1, log: true }
    stacked_ensemble_v1:
      rf_n_estimators: { type: int, low: 80, high: 200, step: 20 }
      hgb_max_iter: { type: int, low: 100, high: 250, step: 50 }
      # meta·cv는 1차 고정 권장
```

주석 placeholder는 [`configs/default.yaml`](../configs/default.yaml) `tune:` 블록에도 동일 요지로 적어 두었습니다.

### 9.3 `tune.py` 구조 (구현 시)

```text
tune_one_algorithm(algo, cfg)
  ├─ load data / fit-valid split          # 기존과 동일
  ├─ method = cfg["tune"].get("method", "grid")
  │
  ├─ if method == "grid":
  │     combos = [{}] + expand_param_grid(grids[algo])
  │     for delta in combos: run_trial(delta)
  │
  └─ if method == "optuna":
        def objective(trial):
            params = suggest_params(trial, search_space[algo], base_params)
            row = run_trial(params_delta=params)   # score_candidate 동일
            if catboost and pruning:
                raise optuna.TrialPruned() if should_prune(...)
            return row["top1_lift"]   # maximize
        study = optuna.create_study(direction="maximize", sampler=TPESampler(...))
        study.optimize(objective, n_trials=n_trials)
        rows = [trial.user_attrs["full_row"] for trial in study.trials]
  │
  └─ ranked = rank_candidates(rows, ...)    # 정밀도 가드 · 정렬 — 기존 동일
  └─ _save_tune_report(...)
```

**중요:** Optuna `objective` 반환값은 `top1_lift`지만, **최종 best는 `rank_candidates`**(top1 → top5 → PR-AUC + precision_guard)로 통일합니다.

### 9.4 CatBoost pruning (Optuna 연동)

```python
# 의사코드 — Valid 구간 eval_set
model.fit(
    X_tr, y_fit,
    eval_set=(X_va, y_val),
    early_stopping_rounds=50,
    verbose=False,
)
# 중간 AUC/Logloss를 trial.report(step, value) → trial.should_prune()
```

- RF는 epoch 개념이 약해 **1차는 pruning 생략** (trial 수·`n_estimators` 상한으로 조절)
- pruning 후에도 **최종 지표는 Valid top1_lift**로 `score_candidate` 재계산

### 9.5 산출물·재현성

| 항목 | grid | optuna |
|------|------|--------|
| `hyperparam_tune_{algo}.json` | 유지 | `method`, `n_trials`, `sampler` 메타 추가 |
| `hyperparam_tune_{algo}.xlsx` | 유지 | trial 번호 = Optuna trial number |
| `hyperparam_tune_best.yaml` | 유지 | 동일 |
| 재현 | `grids` + seed | `optuna_seed` + `n_trials` + study 직렬화(선택) |

### 9.6 의존성 (오프라인)

- PyPI: `optuna` (Release wheels zip에 **추가 필요**)
- Agent는 `12` 미실행 — 사용자 로컬에서 `pip install optuna` 또는 offline wheels 반영 후 검증

### 9.7 method 선택 가이드

| 상황 | 권장 `method` |
|------|----------------|
| v1/v2 · 3×3×3 소규모 | **`grid`** (현행) |
| HistGB Phase 2 · 15~27칸 | `grid` 또는 `optuna` + `n_trials=20` |
| Stacked · §4 넓은 범위 · v3 | **`optuna`** + CatBoost pruning |
| 감사·baseline 재현 | **`grid`** 결과와 병행 보관 |

---

## 6. 공통 원칙 (한눈에)

| 항목 | 고정 |
|------|------|
| 1순위 지표 | Validation 상위 **1%·5% 리프트** (및 양성 포착비율) |
| 2순위 | **PR-AUC** |
| 가드 | 기준선 대비 정밀도 비율 (`tune.min_precision_ratio`, 기본 0.85) 미달 시 탈락 |
| 탐색 구간 | **Train 내부 Validation만** (`tune.split_mode=nested_random`) — Test 미사용 |
| 확정 | 기존 Test 구간으로 **07→08→10 1회** (Test로 반복 튜닝 금지) |
| 환경 | `memory.n_jobs: 2`, 16GB RAM 친화 — 깊이·트리 수 과도한 확대 지양 |
| 도구 | `python scripts/12_tune_hyperparams.py --algo {algo_id}` |
| 튜닝 분할 | `nested_random`(권장): 03 `train_mask` 안 80/20 · `time`: Train 내 valid 월 · `pool_random`: 레거시 |

---

## 7. 더 읽을 문서

| 문서 | 내용 |
|------|------|
| [`model_tuning.md`](model_tuning.md) | 기준선·실행 명령·반영 체크리스트 |
| [`metrics_guide.md`](metrics_guide.md) | PR-AUC·리프트·정밀도 해설 |
| [`operations_criteria.md`](operations_criteria.md) | 4×4·주A/주B·튜닝 목표와의 연결 |
| [`pipeline.md`](pipeline.md) | 03·05·07·12 스크립트 순서 |
| **본 문서 §8** | RF/CB v2 STOP → 3종 → Optuna **단계별 로드맵** |
| **본 문서 §9** | `tune.method: grid \| optuna` **설계안 (미구현)** |
