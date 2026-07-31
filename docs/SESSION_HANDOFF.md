# 세션 인수인계 (2026-07-31 · v0.7.0 Release)

## 프로젝트
지방보조금 부정수급 위험도 지도학습 + **로컬 Next.js + FastAPI UI** + 운영 SQLite(raw 제외) + 백그라운드 Job.

- 원격: https://github.com/lky9464/LocalSubsidies_SupervisedLearning  
- **GitHub 최신 태그/Release:** **v0.7.0**  
- 실행: `RunWebNext.bat` → `http://127.0.0.1:8600`

---

## v0.7.0 Release 요약 (2026-07-31)

**목표:** v2 튜닝(`nested_random` Valid) 지표 낙관 가능성 → **엔티티 무중복 Valid 재튜닝 → `{family}_v3` 등록** (v2 이력 보존).

### 코드·설정 (v0.7.0 태그)

| 영역 | 내용 |
|------|------|
| Valid K-fold | `src/features/preprocess.py` — `group_fold_masks_within_mask`, `group_split_masks_within_mask` |
| 12 튜닝 | `src/models/tune.py` — `nested_group_random`, fold 평균·`top1_lift_std`, `load_tune_config()`, `tuning/{tag}/` |
| 튜닝 설정 | **`configs/tune.yaml`** · `tune_local.yaml.example` · `load_tune_config()` |
| 웹·학습 설정 | **`configs/default.yaml`** — `model_params.*_v3`, registry v3, **`tune` 블록 제거** |
| v3 학습 | `scripts/05_train_*_v3.py` × 5 · `src/models/registry.py` |
| 일괄 튜닝 | **`tune_batch/run_tune_batch.py`** — 5종 · `data_run_id` · 로그 `tune_batch/logs/` |
| 버그 수정 | `src/evaluate/eval_snapshot.py` — Run 격리 후 전역 eval fallback (compare 빈칸 회귀) |
| 테스트 | `test_tune_group_split`, `test_tune_config`, `test_tune_preprocess_guard`, `test_eval_snapshot` |
| 문서 | README Owner CLI 튜닝(v4 예시) · `model_tuning.md` §3.1 · `VERSION_HISTORY` v0.7.0 |

### 튜닝·리포트 폴더

| 경로 | 역할 |
|------|------|
| `configs/tune.yaml` | 12·tune_batch (`output_tag`, `data_run_id`, grids) |
| `outputs/reports/tuning/v2/` | v2 이력 (nested_random · git v0.6.2 복원) |
| `outputs/reports/tuning/v3/` | v3 이력 (nested_group_random · Run `run_20260730_172901`) |
| `outputs/reports/comparison/` | 04·06·07·08 모델 비교 전용 |

**튜닝 독립성:** 웹 API 미연동 · `require_preprocess_split_mode: group_random` · [`model_tuning.md`](model_tuning.md) §3.1

---

## v0.7.0 튜닝 Run (로컬 · 완료)

| 항목 | 값 |
|------|-----|
| **run_id** | `run_20260730_172901` |
| 분할 | **group_random** · 풀 202401~202512 |
| 01~04 | 완료 · 04 `group_verdict` 낮음 |
| **12 (5종)** | 완료 · 정밀도 가드 전원 pass |

### Validation best (`top1_lift` · Valid만)

| algo | best | Primary/Aux 후보 |
|------|-----:|------------------|
| catboost_v1 | **71.23** | Primary |
| random_forest_v1 | 64.49 | Aux (정밀도 0.79) |
| stacked_ensemble_v1 | 63.49 | 참고 (meta CV 이슈 v0.7.1) |
| gradient_boosting_v1 | 61.31 | — |
| easy_ensemble_v1 | 20.52 | 부적합 |

### v3 등록 (튜닝 best → `model_params`)

| family | algo_id | trial |
|--------|---------|------:|
| catboost | `catboost_v3` | #25 |
| random_forest | `random_forest_v3` | #26 |
| gradient_boosting | `gradient_boosting_v3` | #18 |
| stacked_ensemble | `stacked_ensemble_v3` | #9 |
| easy_ensemble | `easy_ensemble_v3` | #2 |

---

## 다음 세션 (우선순위)

1. **`run_20260730_172901`에서 05→10** — `run_config.algorithms`에 v3 5종 추가 후 학습·Test  
   ```powershell
   $env:LSL_RUN_ID = "run_20260730_172901"
   python scripts/05_train.py --algo random_forest_v3 --algo catboost_v3 ...
   python scripts/06_feature_importance.py
   python scripts/07_evaluate.py
   python scripts/08_update_ranking.py
   python scripts/09_report.py
   python scripts/10_ops_queue.py
   ```
2. v1 / v2 / **v3** Test 비교 (v2 random Run과 **직접 비교 금지**)
3. Test 확정 후 `ops_queue` → CB v3 primary / RF v3 aux 검토
4. (연기) Stacked meta CV 엔티티 무중복 — **v0.7.1**
5. (v4 튜닝) `output_tag: v4` · `tune.grids` baseline `*_v3` — README Owner CLI 절

---

## 설정 구분

| 파일 | 역할 |
|------|------|
| `configs/default.yaml` | 웹·03~11 · registry · `model_params` |
| `configs/tune.yaml` | 12·tune_batch 전용 |
| `configs/local.yaml` | `data_root` (Git 제외) |
| `runs/{run_id}/run_config.yaml` | Run별 split·`algorithms` (05~10) |

---

## v0.6.2 이하

[`VERSION_HISTORY.md`](VERSION_HISTORY.md)

---

## Agent 경계
data_root / ops.sqlite / raw 내용 읽기·학습 스크립트·웹 서버 기동(데이터 유발) 금지.  
상세: `docs/AGENT_BOUNDARY.md` · `.cursor/rules/no-sensitive-data.mdc`
