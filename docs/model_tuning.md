# 지도학습 모델 고도화 가이드

UI(v0.3.0) 이후 **하이퍼파라미터·주·보 재선정·피처** 실험을 위한 운영 문서입니다.  
학습·튜닝 실행은 **사용자 로컬**에서만 합니다 (Cursor Agent는 `scripts/01`~`12` 및 data_root를 실행·읽지 않음).

관련: [`operations_criteria.md`](operations_criteria.md) · [`pipeline.md`](pipeline.md) · [`VERSION_HISTORY.md`](VERSION_HISTORY.md)

---

## 1. 기준선 고정 (v0.3.0 Baseline)

튜닝·피처 실험 전에 아래를 **동결**한다. 바꾸면 비교가 무의미해진다.

| 항목 | 고정값 (기준선) |
|------|-----------------|
| 버전·하이퍼 기본 | v0.3.0 기본값 → `configs/default.yaml` `model_params` (동일 수치로 이전) |
| Train | `202401` ~ `202506` |
| Test | `202507` ~ `202512` |
| Validation (튜닝 전용) | `202504` ~ `202506` (Train 끝부분, **Test와 분리**) |
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

---

## 4. RF·CatBoost 소규모 탐색 (로컬)

```text
python scripts/12_tune_hyperparams.py
python scripts/12_tune_hyperparams.py --algo random_forest_v1
python scripts/12_tune_hyperparams.py --algo catboost_v1
```

- 탐색 격자: `configs/default.yaml` → `tune.grids`
- 대상 알고리즘 기본: `tune.algorithms` = `random_forest_v1`, `catboost_v1`
- 산출(집계만): `outputs/reports/comparison/hyperparam_tune_*.json` / `.xlsx`  
  및 추천값 `hyperparam_tune_best.yaml`

### 4.1 반영 절차

1. `12` 실행 → best 후보 확인 (Validation 지표)
2. 채택 시 `model_params`에 수동 반영 (또는 best yaml 내용 병합)
3. `05` (해당 algo) → `06` → `07` → `08` → `10`
4. 기준선과 PR-AUC·상위 1%/5% 리프트·4×4 주A/주B 비교
5. 주·보 변경 시 `ops_queue` + `operations_criteria.md` §2.1 갱신
6. [`VERSION_HISTORY.md`](VERSION_HISTORY.md) 기록

EasyEnsemble / Stacked / HGB는 전면 격자 탐색하지 않고, 주·보 확정 후 필요 시만 재평가한다.

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
| 튜닝 도구·`model_params` 분리·문서 (기본 수치 동일) | Unreleased → 향후 **v0.4.0** ([`VERSION_HISTORY.md`](VERSION_HISTORY.md)) |
| 탐색 결과로 기본 하이퍼·주보·품질이 바뀐 배포 | 다음 MINOR 또는 PATCH (변경 폭에 따름) |
| 기본값 버그성 수정만 | PATCH |
