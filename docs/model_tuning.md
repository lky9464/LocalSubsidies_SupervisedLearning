# 지도학습 모델 고도화 가이드

UI(v0.3.0) 이후 **하이퍼파라미터·주·보 재선정·피처** 실험을 위한 운영 문서입니다.  
학습·튜닝 실행은 **사용자 로컬**에서만 합니다 (Cursor Agent는 `scripts/01`~`12` 및 data_root를 실행·읽지 않음).

관련: [`hyperparam_methodology.md`](hyperparam_methodology.md) · [`ranking_methodology.md`](ranking_methodology.md) (Test **08 순위**) · [`operations_criteria.md`](operations_criteria.md) · [`pipeline.md`](pipeline.md) · [`VERSION_HISTORY.md`](VERSION_HISTORY.md)

---

## 1. 기준선 고정 (v0.3.0 Baseline)

튜닝·피처 실험 전에 아래를 **동결**한다. 바꾸면 비교가 무의미해진다.

| 항목 | 고정값 (기준선) |
|------|-----------------|
| 버전·하이퍼 기본 | v0.3.0 기본값 → `configs/default.yaml` `model_params` (동일 수치로 이전) |
| Train | 풀 `202401`~`202512` 중 **사업·기관 무중복 ~70%** (`split.mode=group_random`, `test_size=0.3`) |
| Test | 동일 풀 **~30%** — Train과 `PFM_BIZ_ID+INST_ID` 교집합 0 (최종 평가만, 튜닝 금지) |
| Validation (튜닝) | **Train 안** 엔티티 단위 K-fold (`tune.split_mode=nested_group_random`, `n_folds=3`) |
| 타겟 | `TAET_YN` ([`label_definition.md`](label_definition.md)) |
| 누수 제외 | `exclude_features` + `04_leakage_audit` PASS 필수 |
| 주·보 스냅샷 | RF / CatBoost ([`operations_criteria.md`](operations_criteria.md) §2.1) |

**기준선 보관 (사용자 로컬):** 동일 구간으로 돌린 `07`/`08`/`10` 집계 리포트·순위 JSON을  
`outputs/reports/comparison/` 등에 날짜를 붙여 복사해 둔다. (행단위 점수·raw는 repo에 넣지 않음.)

---

## 2. 최적화 목표

| 순위 | 지표 | 용도 |
|------|------|------|
| 1 | Validation **상위 1%·5% 리프트** (및 양성 포착비율) | 점검 큐·4×4와 정합 |
| 2 | **PR-AUC** | 불균형 순위 능력 |
| 가드 | **정밀도** 급락 시 후보 탈락 | 과탐 폭증 방지 |

ROC-AUC만 올리는 튜닝은 하지 않는다.  
**Test로 반복 튜닝하지 않는다.** 후보 선택은 Validation, 최종 확정만 Test 1회 (`07`→`08`→`10`).

---

## 3. 하이퍼파라미터 설정

기본값: [`configs/default.yaml`](../configs/default.yaml) → `model_params.{algo}`  
생성: [`src/models/factory.py`](../src/models/factory.py) (`build_model(..., params=...)`)  
Run 오버라이드: `{data_root}/runs/{run_id}/run_config.yaml` 의 `model_params` (shallow merge)

현재 기본값은 v0.3.0 `factory` 하드코딩과 **동일한 수치**이다.

> **원리·용어·5종 알고리즘별 파라미터 뜻·28회 격자 탐색 방식**은  
> [`hyperparam_methodology.md`](hyperparam_methodology.md) §1~§3을 참고하세요.

---

## 3.1 튜닝 vs 웹 서비스 (독립 실행)

**`12` / `tune_batch`는 웹 API·FastAPI·Streamlit과 연결되지 않습니다.** 설정·산출물만 아래 파일을 사용합니다.

| 구분 | 튜닝 (Owner CLI) | 웹·05~11 |
|------|------------------|----------|
| 설정 | `configs/tune.yaml` (+ `tune_local.yaml`) | `default.yaml` + `run_config.yaml` |
| 로드 | `load_tune_config()` | `load_config()` + `load_run_config()` |
| 산출 | `outputs/reports/tuning/{output_tag}/` | `comparison/` · Run `algorithms/` |
| Run ID | `data_run_id` / `--run-id` / `LSL_RUN_ID` | 웹 Job · run_config |

**공유(의도적):** `configs/local.yaml`의 `data_root`, `default.yaml`의 `model_params`(baseline)·`exclude_features`·타겟 정의.

**선행 01~04:** 웹 없이 CLI만 가능. `{data_root}/runs/{run_id}/run_config.yaml` 예시는 [`configs/tune_run.yaml.example`](../configs/tune_run.yaml.example).  
`12` 시작 시 `require_preprocess_split_mode`(기본 `group_random`)로 **03 산출물**만 검증 — 웹 `run_config`는 읽지 않음.

```text
# tune.yaml data_run_id 만 맞추면 12 단독 실행 가능
python scripts/12_tune_hyperparams.py
python tune_batch/run_tune_batch.py
```

---

## 4. 5종 격자 탐색 (로컬)

```text
python scripts/12_tune_hyperparams.py --run-id {group_random Run ID}
python scripts/12_tune_hyperparams.py --run-id {run} --algo random_forest_v1
python scripts/12_tune_hyperparams.py --run-id {run} --algo stacked_ensemble_v1
```

- 탐색 격자: `configs/tune.yaml` → `tune.grids`
- 대상 알고리즘 기본: `tune.algorithms` = v1 **5종**
- 분할: **03의 Train 마스크 안에서** 엔티티 단위 K-fold (`nested_group_random`, `n_folds=3`)  
  같은 `PFM_BIZ_ID+INST_ID`가 fit과 Valid에 동시에 들어가지 않음
- 산출(집계만): `outputs/reports/tuning/{output_tag}/hyperparam_tune_*.{json,xlsx}`  
  (`분할무결성(folds)` 시트) 및 `hyperparam_tune_best.yaml` · `tune_manifest.yaml`
- 일괄 실행: `python tune_batch/run_tune_batch.py --run-id {run}`

> **전제:** `12`는 반드시 **`split.mode=group_random`으로 돌린 Run**에서 실행하세요.  
> 03이 `random`이면 `train_mask` 자체가 Test와 엔티티를 공유해, Valid만 그룹 분할해도 지표가 왜곡됩니다.

> `split.mode`/`tune` 변경 후 **`03_preprocess`를 다시 실행**해야 `split_masks`가 맞습니다.  
> 이전 `nested_random` 결과는 비교용으로 이름을 바꿔 보관하는 것을 권장합니다.

**실행 시간:** 후보 수 × `n_folds` 만큼 학습합니다(기본 3배). Stacked는 trial마다 내부 CV까지 돌아
가장 오래 걸리므로 `--algo`로 분리 실행하는 편이 안전합니다.

### 4.1 반영 절차

1. `12` 실행 → best 후보 확인 (Validation 지표 · fold 평균)
2. 채택 시 `model_params.{algo}_v3` + `algorithm_registry` + `05_train_*_v3.py`  
   **기존 v1·v2 수치는 덮어쓰지 않는다** (과거 Run 재현성)
3. 학습 옵션에서 **v3** 선택 → `05` → `06` → `07` → `08` → `10` (Test 1회)
4. 동일 Run 안에서 v1 / v2 / v3의 PR-AUC·상위 1%/5% 리프트·4×4 주A/주B 비교
5. 주·보 변경 시 `ops_queue` + `operations_criteria.md` §2.1 갱신
6. [`VERSION_HISTORY.md`](VERSION_HISTORY.md) 기록

**현재 (v0.7.0):** 5 family를 `nested_group_random`으로 재튜닝해 **v3** 등록 예정.  
v2는 `nested_random`(엔티티 공유 Valid) + `random` Test에서 선정된 값이라 **이력용으로만 보존**합니다.

> **v2 숫자와 직접 비교 금지:** v2의 Test 리프트는 Train/Test가 엔티티를 공유하던 Run
> (`run_20260728_200201`)에서 측정됐습니다. v3가 낮게 나오는 것은 성능 저하가 아니라
> 이전 값이 낙관적이었다는 뜻입니다. 비교는 **동일 group_random Run 안에서만** 하세요.

> **단계별 로드맵**(RF/CB v2 STOP → HistGB → Optuna) 및 **`tune.method` 설계**는  
> [`hyperparam_methodology.md`](hyperparam_methodology.md) **§8·§9** 참고.

### 4.2 알려진 한계 — Stacked 내부 CV

`stacked_ensemble`은 `StackingClassifier(cv=3)`을 쓰며, 이 CV는 **행 단위**입니다.
메타 학습기가 보는 out-of-fold 예측이 같은 엔티티의 다른 달에서 나오므로,
**모델 내부에 별도의 엔티티 누수**가 남아 있습니다. `tune.split_mode`를 바꿔도 해소되지 않으며,
`GroupKFold` 주입이 필요합니다 (v0.7.1 검토 항목).

Stacked의 Test 지표는 이 한계를 감안해 해석하세요.

상세 로드맵: [`hyperparam_methodology.md`](hyperparam_methodology.md) §8.2.

### 4.3 v4 튜닝 예시 (웹 최소 · CLI)

README **「Owner — CLI 전용 하이퍼파라미터 튜닝」** 과 동일합니다. 요약:

| 단계 | 경로 A (03 재사용) | 경로 B (01~04 CLI) |
|------|-------------------|-------------------|
| Run | `data_run_id` 기존 유지 | `tune_run.yaml.example` → `run_config.yaml` |
| yaml | `output_tag: v4`, `algorithms`/`grids` → `*_v3` | 동일 + `data_run_id` 신규 |
| 실행 | `python tune_batch/run_tune_batch.py` | 01~04 후 배치 |
| 산출 | `tuning/v4/` | `tuning/v4/` |
| 채택 | `{family}_v4` 등록 → 05~10 Test 1회 | 동일 |

v4부터 `tune.grids` 키와 `tune.algorithms`는 **v3 algo_id**(`random_forest_v3` 등)를 baseline으로 두는 것을 권장합니다 (`default.yaml` `model_params.*_v3`).

---

## 5. 주·보 재선정 체크리스트

Test **08** 순위 규칙: [`ranking_methodology.md`](ranking_methodology.md)

- [ ] 08 `ranking_confidence` 확인 (`low` → Test **4×4**로 주·보 확정)
- [ ] 상위1% 리프트·PR-AUC 표와 4×4 **주A·우선 1~4** (B) 실제 타겟 일치 여부
- [ ] 정밀도 급락(과탐) 없는가 (F1·ROC는 참고)
- [ ] 학습 시간·RAM이 Owner PC(약 14GB)에서 수용 가능한가
- [ ] `ops_queue.primary_algo` / `aux_algo` 갱신
- [ ] `operations_criteria.md` 스냅샷·일자 갱신

---

## 6. 다음 단계 — 피처·전처리 (파라미터 안정화 후)

한 축씩만 바꾼다. 변경마다 `04` 재통과 후 `05`~`10`.

| 축 | 내용 |
|----|------|
| Feature 제외 | TOP10·도메인 판단으로 `exclude_features` / run `exclude_features_extra` |
| Feature 파생 | 파생 추가 시 누수·점수 시점 가용성 검토 |
| 불균형 | `class_weight` / CatBoost `auto_class_weights` 유지 vs 샘플링 (동시 변경 금지) |
| 범주 | `categorical_candidates` 정리 (`memory.sklearn_encoding: ordinal` 유지) |

새 알고리즘 추가는 이 단계 이후에만 검토한다.

---

## 7. 버전

| 상황 | 버전 |
|------|------|
| 튜닝 도구·`model_params` 분리·RF/CB v2 채택 | **v0.4.0** ([`VERSION_HISTORY.md`](VERSION_HISTORY.md)) |
| 엔티티 무중복 Valid(`nested_group_random`)·5종 v3 재튜닝 | **v0.7.0** |
| 탐색 결과로 기본 하이퍼·주보·품질이 바뀐 배포 | 다음 MINOR 또는 PATCH (변경 폭에 따름) |
| 기본값 버그성 수정만 | PATCH |
