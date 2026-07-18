# 세션 인수인계 (2026-07-18 웹 UI 2차 대개선)

## 프로젝트
지방보조금 부정수급 위험도 지도학습 + **로컬 Streamlit(M3 톤)** + **운영 SQLite**(raw 제외) + **백그라운드 Job**.

원격: https://github.com/lky9464/LocalSubsidies_SupervisedLearning

## 완료 (2차)
- 스크립트 재번호: 08 ranking → 09 report → 10 ops → 11 inference
- 교차 컬럼: `primary_only_high` (구 `rf_only_high` 읽기 호환)
- JobManager (`src/pipeline/jobs.py`) + `_job_worker.py`
- run_config: 분할 time/random, 알고≥2, 누수 재개(03부터)
- 메뉴 IA 분리, M3 CSS, 타이틀「지방보조금 부정수급 위험도 측정」
- 모델비교 Plotly, 점검큐 툴팁, PC사양, Run이력, 사용자 가이드 PDF

## 사용자 실행
```powershell
.\RunWeb.bat
```
http://127.0.0.1:8501

## Agent 경계
data_root / ops.sqlite / streamlit·파이프라인 스크립트 실행 금지.
