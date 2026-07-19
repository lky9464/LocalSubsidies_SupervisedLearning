# 세션 인수인계

## 프로젝트
지방보조금 부정수급 위험도 지도학습 + **로컬 Next.js + FastAPI UI** + **운영 SQLite**(raw 제외) + **백그라운드 Job**.

원격: https://github.com/lky9464/LocalSubsidies_SupervisedLearning

## 현재 UI
- `RunWebNext.bat` → `http://127.0.0.1:8600`
- API: `api/` · 정적 UI: `web/out/` (소스 `web/`, 빌드 `scripts/build_web.bat`)
- Streamlit(`app/`, `RunWeb.bat`)은 제거됨

## 사용자 실행
```powershell
.\RunWebNext.bat
```

## Agent 경계
data_root / ops.sqlite / 웹 서버·파이프라인 스크립트 실행 금지.  
상세: `docs/AGENT_BOUNDARY.md`
