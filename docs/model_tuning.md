# 지도학습 모델 고도화 가이드

UI(v0.3.0) 이후 **하이퍼파라미터·주·보 재선정·피처** 실험을 위한 운영 문서입니다.  
학습·튜닝 실행은 **사용자 로컬**에서만 합니다 (Cursor Agent는 `scripts/01`~`12` 및 data_root를 실행·읽지 않음).

관련: [`hyperparam_methodology.md`](hyperparam_methodology.md) (튜닝 **원리·알고리즘별 파라미터 설명**) · [`operations_criteria.md`](operations_criteria.md) · [`pipeline.md`](pipeline.md) · [`VERSION_HISTORY.md`](VERSION_HISTORY.md)

---

## 1. 기준선 고정 (v0.3.0 Baseline)

튜닝·피처 실험 전에 아래를 **동결**한다. 바꾸면 비교가 무의미해진다.

| 항목 | 고정값 (기준선) |
|------|-----------------|
| 버전·하이퍼 기본 | v0.3.0 기본값 → `configs/default.yaml` `model_params` (동일 수치로 이전) |
| Train | 풀 `202401`~`202512` 중 random **~70%** (`split.mode=random`, `test_size=0.3`) |
| Test | 동일 풀 random **~30%** (최종 평가만, 튜닝 금지) |
| Validation (튜닝) | **Train 안** random ~20% (`tune.split_mode=nested_random`) |
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

## 4. RF·CatBoost 소규모 탐색 (로컬)

```text
python scripts/12_tune_hyperparams.py
python scripts/12_tune_hyperparams.py --algo random_forest_v1
python scripts/12_tune_hyperparams.py --algo catboost_v1
```

- 탐색 격자: `configs/default.yaml` → `tune.grids`
- 대상 알고리즘 기본: `tune.algorithms` = `random_forest_v1`, `catboost_v1`
- 분할: **03의 Train 마스크 안에서만** Valid (`nested_random`). Test와 겹치지 않음
- 산출(집계만): `outputs/reports/comparison/hyperparam_tune_*.json` / `.xlsx`  
  및 추천값 `hyperparam_tune_best.yaml`

> `split.mode`/`tune` 변경 후 **`03_preprocess`를 다시 실행**해야 `split_masks`가 맞습니다.  
> 이어서 `12`를 RF·CatBoost 각각(또는 일괄) 재실행하세요. 이전 pool_random 결과는 비교용으로 이름을 바꿔 보관하는 것을 권장합니다.

### 4.1 반영 절차

1. `12` 실행 → best 후보 확인 (Validation 지표)
2. 채택 시 `model_params.{algo}_v2` + `algorithm_registry` + `05_train_*_v2.py` (v1 유지)
3. 학습 옵션에서 **v2** 선택 → `05` → `06` → `07` → `08` → `10` (Test 1회)
4. 기준선(v1)과 PR-AUC·상위 1%/5% 리프트·4×4 주A/주B 비교
5. 주·보 변경 시 `ops_queue` + `operations_criteria.md` §2.1 갱신
6. [`VERSION_HISTORY.md`](VERSION_HISTORY.md) 기록

**현재:** `random_forest_v2` · `catboost_v2` 등록 완료. Test 확정 대기.

EasyEnsemble / Stacked / HGB는 전면 격자 탐색하지 않고, 주·보 확정 후 필요 시만 재평가한다.

> **단계별 로드맵**(RF/CB v2 STOP → HistGB → Optuna) 및 **`tune.method` 설계**는  
> [`hyperparam_methodology.md`](hyperparam_methodology.md) **§8·§9** 참고.

### 4.2 Phase 2 — HistGB·Stacked·EasyEnsemble (요약)

| algo_id | 권장 |
|---------|------|
| `gradient_boosting_v1` | `12` grid 확장 · 15~27 trial |
| `stacked_ensemble_v1` | grid 전수 금지 · Phase 3 Optuna 또는 1축씩 |
| `easy_ensemble_v1` | `n_estimators` 짧은 grid 또는 07·08만 |

상세: [`hyperparam_methodology.md`](hyperparam_methodology.md) §8.2.

---

## 5. 주·보 재선정 체크리스트

- [ ] 기준선 대비 Validation 개선이 Test에서도 유지되는가
- [ ] 4×4 주A·주B 실제 타겟 포착이 악화되지 않았는가
- [ ] 정밀도 급락(과탐) 없는가
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
| 탐색 결과로 기본 하이퍼·주보·품질이 바뀐 배포 | 다음 MINOR 또는 PATCH (변경 폭에 따름) |
| 기본값 버그성 수정만 | PATCH |
