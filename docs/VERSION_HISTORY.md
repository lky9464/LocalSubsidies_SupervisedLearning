# 버전 이력

현재 버전: **v0.3.0**  
저장소: [LocalSubsidies_SupervisedLearning](https://github.com/lky9464/LocalSubsidies_SupervisedLearning)  
릴리스: [Releases](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases)

새 버전을 낼 때 이 문서 상단에 항목을 추가하고, GitHub Release/태그와 맞춥니다.

---

## Unreleased (작업 중 · 아직 v0.4.0 아님)

알고리즘 `{family}_vN` 버전 관리·튜닝 도구·학습 옵션 2단 UI 등이 main에 반영 중이며,  
하이퍼파라미터 채택·나머지 알고리즘 튜닝·Release 태그 전까지 **공식 버전은 v0.3.0** 을 유지한다.

주요 진행 (요약):
- algo_id `*_v1`, `algorithm_registry`, `05_train_*_v1.py`, `12_tune_hyperparams.py`
- 학습 옵션 UI 종류→버전 2단 선택
- [`algo_id_migration.md`](algo_id_migration.md) · [`hyperparam_methodology.md`](hyperparam_methodology.md) · [`model_tuning.md`](model_tuning.md)

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
