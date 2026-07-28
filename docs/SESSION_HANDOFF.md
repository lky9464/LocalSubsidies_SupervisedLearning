# 세션 인수인계 (2026-07-29)

## 프로젝트
지방보조금 부정수급 위험도 지도학습 + **로컬 Next.js + FastAPI UI** + 운영 SQLite(raw 제외) + 백그라운드 Job.

- 원격: https://github.com/lky9464/LocalSubsidies_SupervisedLearning  
- **GitHub 최신 태그/Release:** **v0.6.0**  
  - GBM · Stacked · EasyEnsemble Validation 튜닝 → v2 등록  
  - 5 family Test v2 채택 (`run_20260728_200201`)  
  - `tune.py` 3종 family 허용 · `12 --run-id`  
- 실행: `RunWebNext.bat` → `http://127.0.0.1:8600`

---

## v0.6.0 완료 요약

**목표:** v2가 없던 3종(`gradient_boosting`, `stacked_ensemble`, `easy_ensemble`) Validation 튜닝 → v2 등록 → 동 family v1과 Test 비교.  
RF/CatBoost v2는 재튜닝 없이 새 raw로 Test만 재확정.

| 단계 | 내용 | 상태 |
|------|------|------|
| 0 | `tune.py` · `tune.grids` · `12 --run-id` | ✅ |
| 1 | raw·Run · `01`~`04` | ✅ |
| 2 | `12` 튜닝 3종 | ✅ |
| 3 | v2 registry · model_params · `05_train_*_v2.py` | ✅ |
| 4 | `05`~`10` (10 algo) · data_root 이동 | ✅ |
| 5 | Test v1 vs v2 채택 · v0.6.0 Release | ✅ |

**Run ID:** `run_20260728_200201` · random·0.3 · 현행 raw · `{data_root}` 새 부모 경로 반영 완료

### Validation 튜닝 (`12`)

| algo_id | v1 baseline top1_lift | best top1_lift | v2 |
|---------|----------------------:|---------------:|----|
| `gradient_boosting_v1` | 86.67 | **91.09** | `gradient_boosting_v2` |
| `stacked_ensemble_v1` | 90.36 | **92.32** | `stacked_ensemble_v2` |
| `easy_ensemble_v1` | 23.33 | **24.06** | `easy_ensemble_v2` |

산출: `outputs/reports/comparison/hyperparam_tune_*.json|xlsx` · `hyperparam_tune_best.yaml`

### Test v1 vs v2 (5 family 모두 v2 채택)

| family | top1_lift v1→v2 | PR-AUC | 비고 |
|--------|------------------:|-------:|------|
| CatBoost | 88.09 → **94.10** | 0.698 → **0.860** | v2 채택 |
| RandomForest | 93.16 → **93.74** | ≈ | v2 채택 |
| Stacked | 91.74 → **93.51** | ↑ | v2 채택 |
| Gradient Boosting | 89.39 → **90.80** | 0.753 → 0.745 (소폭↓) | v2 채택 (리프트↑) |
| EasyEnsemble | 21.79 → **22.38** | ≈ | v2 채택 (절대값仍 낮음) |

### 웹 「모델 비교·평가」 (`08` · confidence **low**)

| 순위 | 알고리즘 | 역할 | PR-AUC | 상위1% 리프트 |
|------|----------|------|-------:|-------------:|
| 1 | RandomForest (v1) | **primary** | 0.884 | 93.156 |
| 1 | RandomForest (v2) | reference | 0.884 | 93.744 |
| 1 | Stacked Ensemble (v2) | **aux** | 0.884 | 93.509 |
| 4 | CatBoost (v2) | excluded | 0.860 | 94.098 |

안내: *「1·2위 리프트·PR-AUC 모두 근접 — Test 4×4로 주·보 확정 권장」*

→ **주·보는 단순 리프트 정렬이 아니라 `08` + (권장) 4×4** 기준.

### 코드 변경 (v0.6.0)

- `src/models/tune.py` — 3종 family 허용 · trial `elapsed_sec`
- `configs/default.yaml` — `tune.grids` · `model_params` v2 ×3 · `algorithm_registry` v2 ×3
- `src/models/registry.py` — `DEFAULT_ALGO_IDS` v2 ×3
- `scripts/12_tune_hyperparams.py` — `--run-id`
- `scripts/05_train_{gradient_boosting,stacked_ensemble,easy_ensemble}_v2.py`

---

## 다음 세션 (미완 · 사용자 보류)

**Test 4×4 주·보 조합 대조** — 여러 primary/aux 후보를 바꿔가며 비교 후 확정.

| 항목 | 현재 | 다음 작업 |
|------|------|-----------|
| `ops_queue.primary_algo` | `random_forest_v1` | 4×4 결과 반영 |
| `ops_queue.aux_algo` | `catboost_v1` | 4×4 결과 반영 (후보: `stacked_ensemble_v2`, `random_forest_v2`, `catboost_v2` 등) |
| `operations_criteria.md` §2.1 | v0.5.x 기준 | 주·보 확정 후 갱신 |
| `10` 재실행 | — | ops_queue 확정 후 |

**4×4 확인:** 웹 「모델 비교·평가」→ Test 4×4 또는 「타겟 포착 분포」.  
대안 조합은 `ops_queue` 편집 + (필요 시) `model_ranking.json` 역할 조정 → **`10`만** 재실행.

**같은 Run에서 이어가기:** `run_20260728_200201` · `{data_root}` 유지 · `04` PASS 상태면 `10`만 반복 가능.

---

## v0.5.2 이후 인프라 (참고)

### Run 격리
```text
{data_root}/raw/                    # 공유
{data_root}/raw_inference/          # 공유
{data_root}/runs/{run_id}/interim|processed|algorithms|reports/
{data_root}/ops/ops.sqlite          # 공유
```

### 오프라인 업데이트
1. Release **`update-to-v0.6.0.zip`** (+ deps 변경 시 wheels)을 프로젝트 루트에 복사 (**zip 풀지 않음**)  
2. `UpdateOffline.bat` → `SetupOffline.bat` → `RunWebNext.bat`  
3. 현장 이슈: [`offline_update.md`](offline_update.md) §5 · [Release v0.6.0](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.6.0)

상세: `docs/VERSION_HISTORY.md` · README §B-2

## Agent 경계
data_root / ops.sqlite / raw 내용 읽기·학습 스크립트·웹 서버 기동(데이터 유발) 금지.  
상세: `docs/AGENT_BOUNDARY.md` · `.cursor/rules/no-sensitive-data.mdc`
