# 세션 인수인계 (2026-07-19)

## 프로젝트
지방보조금 부정수급 위험도 지도학습 + **로컬 Next.js + FastAPI UI** + 운영 SQLite(raw 제외) + 백그라운드 Job.

- 원격: https://github.com/lky9464/LocalSubsidies_SupervisedLearning  
- 태그/Release: **v0.3.0** (소스·wheels·web-out 정합)  
- 실행: `RunWebNext.bat` → `http://127.0.0.1:8600`

## 오늘 완료한 작업

### 안정성·버그
- 런처 PIPE 교착 수정 (`_next_web_launcher.py` stdout 상속) · cp949 유니코드 크래시 수정
- 데이터 등록 무한 로딩/`ChunkLoadError` — 서버 행 + 메타 UI 경량화
- 대시보드: `01`만 한 Run에 전역 추론 결과 오표시 → **해당 Run에 inference step 성공 시에만** 표시
- 추론 실행: 현재 Run 미학습 모델 선택 불가 · 주/보(평가 1·2위) 기본 체크 · 미학습 안내 팝업
- 표시 소수점 3자리(화면만) · 추론/대시보드 4×4 우선순위 적색 히트맵 · 「주」행 강조
- 모델별 지표비교(구 방사형) 명칭·범례색(RF/EasyEnsemble 구분)

### Streamlit 제거·경량화
- `app/`·`RunWeb.bat`·streamlit/plotly 제거
- helpers → `src/scoring/inference_helpers.py`
- requirements / lock 재생성 · SetupOffline fastapi 검증

### Release·문서·배포
- Release **v0.3.0**: `wheels-win-amd64-py312.zip`, `web-out.zip`
- README를 **오프라인 일반 사용자** 중심으로 재작성 (소스 ZIP + wheels + web-out 경로, 일상 사용 표)
- `docs/offline_setup.md` · SetupOffline `web/out` 누락 WARN
- main 푸시 · `v0.3.0` 태그 = 최신 문서 커밋과 동일

## 사용자 실행
```powershell
.\RunWebNext.bat
```
오프라인: Release Source zip + wheels → `vendor\wheels\` + web-out → `web\out\` → SetupOffline → RunWebNext

## Agent 경계
data_root / ops.sqlite / 웹 서버·파이프라인 스크립트 실행 금지.  
상세: `docs/AGENT_BOUNDARY.md`
