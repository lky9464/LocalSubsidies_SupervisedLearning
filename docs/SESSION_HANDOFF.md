# 세션 인수인계 (2026-07-29)

## 프로젝트
지방보조금 부정수급 위험도 지도학습 + **로컬 Next.js + FastAPI UI** + 운영 SQLite(raw 제외) + 백그라운드 Job.

- 원격: https://github.com/lky9464/LocalSubsidies_SupervisedLearning  
- **GitHub 최신 태그/Release:** **v0.6.1** (이 세션 커밋·릴리스 대상)  
- **이전 Release:** **v0.6.0** — GBM·Stacked·EasyEnsemble v2 튜닝·등록 · `run_20260728_200201` (random baseline)  
- 실행: `RunWebNext.bat` → `http://127.0.0.1:8600`

---

## v0.6.1 완료 요약 — `group_random` (사업·기관 무중복 분할)

**목표:** Train/Test가 **동일 `PFM_BIZ_ID+INST_ID` 엔티티를 공유하지 않는** 분할 모드를 추가하고, UI·04 그룹 감사까지 연동. baseline `random`은 v0.6.0과 동일하게 유지.

| Phase | 내용 | 상태 |
|------|------|------|
| 1 | `group_random_split_masks()` · `group_audit.py` · 합성 테스트 6건 | ✅ |
| 2 | `03_preprocess` · `default.yaml` · `run_config` · CMD 실데이터 01~04 | ✅ |
| 3 | 웹 분할 UI 3종 · API · `web/out` 빌드 · 문서 | ✅ |
| 4 | 웹 UI `group_random` → 01~04 일괄 · 04 PASS 확인 | ✅ |
| 5 | **05~10 학습·평가** (웹 Job) | ⏸ **중단 — 다른 PC에서 이어감** |

### 검증 결과 (group_random · 04 PASS)

| 항목 | 값 |
|------|-----|
| 분할 | `group_random` · `PFM_BIZ_ID+INST_ID` · pool 202401~202512 · test_size 0.3 |
| Train / Test 행 | 608,754 / 262,792 |
| 피처 누수 | PASS · 의심 0 |
| 그룹중복 | **PASS_그룹중복_낮음** · worst ratio **0** |
| Test 양성 엔티티 | 219 (Train 양성 510과 합 729 — 완전 분할) |
| Train/Test 엔티티 교집합 (`PFM_BIZ_ID+INST_ID`) | **0%** |

**참고:** `PFM_BIZ_ID` 단독 키는 복합 분할 특성상 미세 비율(~2.8e-05)만 보일 수 있음. **판정·분할 기준은 복합 키.**

**random baseline과 비교:** Test 지표·리프트를 **직접 숫자 비교하지 말 것**. group_random은 일반화·무결 평가용.

### 코드·문서 변경 (v0.6.1)

| 영역 | 파일 |
|------|------|
| 코어 분할 | `src/features/preprocess.py` — `group_random_split_masks()` |
| 그룹 감사 | `src/features/group_audit.py` · `scripts/04_leakage_audit.py` |
| 파이프라인 | `scripts/03_preprocess.py` · `configs/default.yaml` · `src/pipeline/run_config.py` |
| UI/API | `web/app/pipeline/page.tsx` · `api/routers/pipeline.py` · `web/out/` |
| 테스트 | `tests/test_group_split.py` |
| 문서 | `docs/pipeline.md` · `docs/user_guide.md` · `docs/leakage_checklist.md` |

### Phase 2 CMD 검증 Run (참고)

- **Run ID:** `run_20260729_142002` — `run_config` 수동 `group_random` · 01~04 PASS (UI 적용 전)

### 웹 UI group_random Run (05~10 이어갈 Run)

- **01~04:** 웹 「사업단위 랜덤(무중복)」 저장 → **01~04 일괄** 완료 · `leakage_audit.xlsx` 검토 **정상**
- **05~10:** 웹 Job **실행 중 중단** — 현재 PC에서 **「전체 작업 취소」** 권장 (미완료 algo·단계는 Run 격리 규칙상 05부터 리셋 후 재실행)
- **Run ID:** 학습 실행 화면 **「실행할 Run」** / Job 배너 `run=...` 에서 확인 (CMD 검증 Run과 **다를 수 있음**)

---

## 다음 PC에서 이어가기 (05~10)

### 1. 코드 동기화

```text
git pull
git checkout v0.6.1
UpdateOffline.bat   ← update-to-v0.6.1.zip 을 프로젝트 루트에 둔 뒤 (오프라인이면 Release Assets)
SetupOffline.bat → RunWebNext.bat
```

`configs/local.yaml` · `{data_root}` · raw는 **그대로** 유지.

### 2. 중단한 Run 확인

1. **RunWebNext.bat** 기동  
2. **학습 실행** → **동일 Run ID** 선택  
3. **단계별 상태:** `merge`~`leakage` **[OK]** · `train` 이후 **미완/실행 중/취소** 확인  
4. 05~10 Job이 **아직 돌고 있으면** 「전체 작업 취소」

### 3. 05~10 재개

| 조건 | 조치 |
|------|------|
| 04까지 OK · 05만 일부/취소 | **알고리즘 저장** 확인 → **05~10 일괄** (또는 05부터) 재실행 |
| split/algorithms 변경 필요 | 취소 → 옵션 저장 → **03+** 또는 **05+** 규칙에 맞게 재실행 ([`local_web_flow.md`](local_web_flow.md) §9) |
| 새 무결 Run으로 처음부터 | 새 Run · `group_random` 저장 → 01~04 → 05~10 |

**알고리즘:** v0.6.0과 동일 10종(v1+v2) 기본. `random` baseline Run(`run_20260728_200201`)과 **성능 숫자 비교 금지**.

### 4. 완료 후 (미착수 · v0.6.2+ 후보)

| 항목 | 비고 |
|------|------|
| Test 4×4 · `ops_queue` 주·보 | v0.6.0 HANDOFF 항목 — **group_random Run 기준**으로 재판단 권장 |
| `model_tuning.md` | baseline vs integrity Run 가이드 (Phase 5) |
| `12` 튜닝 Valid | `nested_group_random` — Train 내부 Valid도 엔티티 무중복 (미구현) |
| 04 요약 | `split_mode` 한 줄 표기 (선택) |

---

## v0.6.0 완료 요약 (참고 · random baseline)

**Run ID:** `run_20260728_200201` · random · test_size 0.3 · 5 family Test **v2 채택**

| family | top1_lift v1→v2 | 비고 |
|--------|------------------:|------|
| CatBoost | 88.09 → **94.10** | v2 채택 |
| RandomForest | 93.16 → **93.74** | v2 채택 |
| Stacked | 91.74 → **93.51** | v2 채택 |
| Gradient Boosting | 89.39 → **90.80** | v2 채택 |
| EasyEnsemble | 21.79 → **22.38** | v2 채택 |

Test 4×4 주·보 조합 대조 · `ops_queue` 갱신은 **group_random Run 05~10 완료 후** 진행 권장.

---

## v0.5.2 이후 인프라 (참고)

### Run 격리
```text
{data_root}/raw/                    # 공유
{data_root}/raw_inference/          # 공유
{data_root}/runs/{run_id}/interim|processed|algorithms|reports/
{data_root}/ops/ops.sqlite          # 공유
{data_root}/runs/{run_id}/logs/{job_id}.log   # 웹 Job 통합 로그 (03·04 확인)
```

### 오프라인 업데이트
1. Release **`update-to-v0.6.1.zip`** (+ deps 변경 시 wheels)을 프로젝트 루트에 복사 (**zip 풀지 않음**)  
2. `UpdateOffline.bat` → `SetupOffline.bat` → `RunWebNext.bat`  
3. 현장 이슈: [`offline_update.md`](offline_update.md) §5 · [Release v0.5.2](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.5.2)

상세: `docs/VERSION_HISTORY.md` · README §B-2

## Agent 경계
data_root / ops.sqlite / raw 내용 읽기·학습 스크립트·웹 서버 기동(데이터 유발) 금지.  
상세: `docs/AGENT_BOUNDARY.md` · `.cursor/rules/no-sensitive-data.mdc`
