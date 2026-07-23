# 버전 이력

현재 버전: **v0.5.0**  
저장소: [LocalSubsidies_SupervisedLearning](https://github.com/lky9464/LocalSubsidies_SupervisedLearning)  
릴리스: [Releases](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases)

새 버전을 낼 때 이 문서 상단에 항목을 추가하고, GitHub Release/태그와 맞춥니다.

---

## Unreleased (작업 중)

_(다음 릴리스 예정 항목)_

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
