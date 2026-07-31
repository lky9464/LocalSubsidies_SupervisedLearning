# 버전 이력

현재 버전: **v0.7.0**  
저장소: [LocalSubsidies_SupervisedLearning](https://github.com/lky9464/LocalSubsidies_SupervisedLearning)  
릴리스: [Releases](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases)

새 버전을 낼 때 이 문서 상단에 항목을 추가하고, GitHub Release/태그와 맞춥니다.

---

## v0.7.0 — 엔티티 무중복 Valid 튜닝 · v3 · CLI 튜닝 독립

- **Valid 분할:** `nested_group_random` · Train 안 엔티티 K-fold · `top1_lift_std` · fold 무결성 감사
- **`*_v3` 등록:** 5 family · `model_params` · `algorithm_registry` · `05_train_*_v3.py` (v2 이력 보존)
- **튜닝 설정 분리:** [`configs/tune.yaml`](../configs/tune.yaml) · `load_tune_config()` · 웹 `default.yaml`과 `tune` 블록 분리
- **산출 이력:** `outputs/reports/tuning/vN/` (v2 git 복원 · v3 nested_group_random) · `comparison/`은 07·08 전용
- **일괄 실행:** [`tune_batch/run_tune_batch.py`](../tune_batch/run_tune_batch.py) · 5종 · `data_run_id`
- **문서:** README Owner CLI 튜닝(v4 예시) · [`model_tuning.md`](model_tuning.md) §3.1
- **오프라인 full sync:** `update-to-v0.7.0.zip` · `web-out.zip` · deps 변경 없음 ([`offline_update.md`](offline_update.md))

[Release v0.7.0](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.7.0)

---

## v0.6.2 — 행 PK 결측 제외 (학습·평가·추론)

- **03 전처리**: `CRTR_YM` · `PFM_BIZ_ID` · `INST_ID` 중 null인 행 집계 후 제외 · `preprocess_meta.json`에 `pk_drop` 기록
- **04~07·train·tune**: `align_labeled_to_split_masks()` — `labeled.csv`(원본)와 `split_masks` 길이 정렬
- **11 추론**: merge 직후 동일 PK 기준 제외 · 전량 제외 시 명확한 오류
- **공통**: `drop_rows_missing_group_keys()` · `DEFAULT_ROW_PK_COLUMNS` (`group_audit.py`) · 단위 테스트 보강
- **deps/UI 변경 없음** — `update-to-v0.6.2.zip` full sync만

[Release v0.6.2](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.6.2)

---

## v0.6.1 — 사업·기관 무중복 분할 (`group_random`)

- **분할 모드 `group_random`**: `PFM_BIZ_ID+INST_ID` 엔티티 단위 Train/Test — 교집합 0 · `group_random_split_masks()` · `03` 연동
- **04 그룹 감사**: `group_audit.py` · `leakage_audit` 그룹중복 시트·콘솔 · `PASS_그룹중복_낮음` 판정
- **웹 UI**: 학습 실행 분할 3종(기간 / 행 random / **사업단위 랜덤**) · API `split_summary` · `web/out` 갱신
- **baseline 유지**: `random` 기본값·v0.6.0 튜닝 Run과 **Test 지표 직접 비교 금지** (무결 vs baseline)
- **미완**: 웹 `group_random` Run **05~10 중단** — 다른 PC에서 동일 Run 이어 실행 ([`SESSION_HANDOFF.md`](SESSION_HANDOFF.md))

[Release v0.6.1](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.6.1)

---

## v0.6.0 — GBM·Stacked·EasyEnsemble v2 튜닝·등록

- **Validation 튜닝 (`12`)**: `gradient_boosting` · `stacked_ensemble` · `easy_ensemble` — `tune.grids` · `--run-id` Run-scoped `03` 산출물
- **v2 등록**: `model_params` · `algorithm_registry` · `05_train_*_v2.py` ×3 · `DEFAULT_ALGO_IDS` 갱신
- **튜닝 모듈**: `tune.py` family 화이트리스트 해제 · trial `elapsed_sec` 기록
- **Test**: 5 family 모두 v2 채택(새 raw · `run_20260728_200201`) · 주·보 4×4 조합 비교는 **다음 세션**

[Release v0.6.0](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.6.0)

---

## v0.5.2 — Run 격리·재실행 초기화·오프라인 full sync

- **Run 산출물 격리**: `runs/{run_id}/interim|processed|algorithms|reports/` · 재실행 시 클릭 단계~10 이력·파일 초기화 · 취소 시 미실행으로 되돌림
- **레거시 정리**: `CleanupLegacy.bat` (raw 유지 · 선택 실행)
- **오프라인 full sync**: `update-to-vX.Y.Z.zip` · `UpdateOffline.bat` 더블클릭 자동 탐색 · v0.3.0+ → 최신 · baseline wheels · 현장 오류 대처(구버전 bat · `.venv` 경로 · `web\out`) ([`offline_update.md`](offline_update.md) §5)
- **추론**: Run 경로 조회 수정 · ops 큐 Excel/CSV 자동 저장 · 결과 화면 수동보내기 제거

[Release v0.5.2](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.5.2)

---

## v0.5.1 — 01~04 완료 후 알고리즘 저장·05~10 진행

- **설정 잠금 분리**: 01 merge 이후 Train/Test 분할만 잠금 · 05~10 시작 전까지 학습 알고리즘 저장·수정 허용
- **학습 실행 UI**: 01~04 완료 시 알고리즘 패널 자동 펼침 · 안내 문구 · Job 실행 중에만 상단 취소 배너
- **회귀 테스트**: `tests/test_pipeline_config.py` — prep 완료 후 algo commit PUT 허용 검증
- **오프라인 업데이트**: `app_code` · `UpdateOffline.bat` / `update-v0.5.1.zip` · yaml·raw·whl 재설치 불필요 ([`offline_update.md`](offline_update.md))

[Release v0.5.1](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.5.1)

---

## v0.5.0 — 학습 UI 2섹션·모델 비교·Job 취소

- **학습 실행 UI**: 데이터 가공(01~04) / 학습·평가(05~10) 2섹션 · raw·분할·알고리즘 분리 저장 · 「데이터 등록」 메뉴 제거(학습·추론 화면 내장)
- **Job 취소**: 파이프라인 잠금 시 `/api/jobs/cancel` + abandon 연동 · 05~10 구간 취소 UI · ops 단계 `failed(사용자 취소)` 기록
- **모델 비교·평가**: Run별 `eval_summary.json` 스냅샷 · legacy algo_id alias · `model_ranking` top-k 컬럼 · 방사형 차트 PR-AUC+상위1% 3종 기본·전 모델 표시
- **08 순위 정책**: 상위1% 리프트 → PR-AUC · [`ranking_methodology.md`](ranking_methodology.md)
- **오프라인**: 배치 ASCII · UTF-8 설정/API · raw `encoding_candidates` — PC 코드페이지와 무관 ([`offline_setup.md`](offline_setup.md) §0)

[Release v0.5.0](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.5.0)

---

## v0.4.0 — 하이퍼파라미터 튜닝·알고리즘 v2 추가

- **`12_tune_hyperparams.py`**: Validation 격자 탐색(28 trial) · `top1_lift` + 정밀도 가드로 best 선정 · RF·CatBoost v1 튜닝 리포트(JSON/Excel)
- **튜닝 채택 → v2 등록**: `random_forest_v2`, `catboost_v2` (`algorithm_registry`, `05_train_*_v2.py`, `model_params`)
- **`{family}_vN` 버전 체계**: algo_id 레지스트리 · 학습 옵션 UI 종류→버전 2단 선택 · `run_config.algorithms` + `LSL_RUN_ID`로 06~10 평가·순위 연동
- **튜닝 분할**: `nested_random`(Test 고정 후 Train 안 Valid) · `split.mode=random` · [`hyperparam_methodology.md`](hyperparam_methodology.md) 원리·알고리즘별 설명 보강
- **추론 결과**: Run별 `inference_algorithms` 저장 · v2 추론 시 주·보·파일 목록이 실제 선택 모델과 일치
- **설정 메뉴**: 버전 정보(`/version/`) · [`local_web_flow.md`](local_web_flow.md) 학습·데이터 옵션 흐름 정리

[Release v0.4.0](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.4.0)

---

## v0.3.0 — Next.js + FastAPI 로컬 UI

- Streamlit UI 제거 → **Next.js + FastAPI** 웹 UI (`RunWebNext.bat` → `http://127.0.0.1:8600`)
- 백그라운드 Job, 운영 DB(`ops.sqlite`), Run 이력·추론 결과 조회
- 오프라인 Release 자산: `wheels` · `web-out` · Python 3.12 · VC++ 설치 파일
- 일반 사용자용 오프라인 설치·사용 문서 정리 (`docs/offline_setup.md`)

[Release v0.3.0](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.3.0)

---

## v0.2.0 — Streamlit 로컬 UI + 오프라인 wheels

- **Streamlit** 기반 로컬 웹 UI (`127.0.0.1`) 추가
- 백그라운드 Job, 운영 큐(ops queue), 추론 결과 화면
- Windows x64 + Python 3.12용 **오프라인 wheels** 배포 (`SetupOffline.bat`)

[Release v0.2.0](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.2.0)

---

## v0.1.0 — CLI 전용 파이프라인

- 지도학습 CLI 파이프라인 (`scripts/01`~`11`) 최초 구성
- 알고리즘 5종 학습·평가·리포트 (CatBoost, Stacked Ensemble, EasyEnsemble, Gradient Boosting, RandomForest)
- 데이터·모델은 `{data_root}`에만 보관하는 구조 확립

[Tag v0.1.0](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.1.0)
