# 로컬 웹 UI (Next.js + FastAPI)

로컬 전용 UI: **`RunWebNext.bat`** → `http://127.0.0.1:8600`

## 원칙

- **127.0.0.1** 만 바인딩 (`0.0.0.0` 금지)
- raw·모델·행단위 점수는 `{data_root}` 파일
- 운영 DB는 `{data_root}/ops/ops.sqlite` — **런/순위/타겟 포착·점검 우선순위 조회·메타만**, raw 미포함
- 데이터 등록: CSV는 `raw`/`raw_inference`에 누적, **선택(selected)된 파일만** 학습·추론에 사용 (Job 시작 시 run_config에 동결)
- 파이프라인은 **백그라운드 Job** (`Popen`) — 메뉴 이동해도 계속 실행
- GitHub·Agent로 민감데이터 유출 금지

## 아키텍처

```
브라우저 → FastAPI (127.0.0.1:8600)
            ├─ /api/*     BFF (OpsRepository, JobManager, run_config)
            └─ /*         Next.js 정적 export (web/out/)
```

Python 파이프라인(`scripts/01~11`)은 변경 없음.

## 실행

### 더블클릭 (권장)

1. (최초 1회, Node 있는 PC) **`scripts/build_web.bat`** → `web/out/` 생성  
   - 오프라인 배포 시: Release에 포함된 `web/out`을 쓰거나, 빌드 결과를 USB로 복사  
2. **`RunWebNext.bat`** 더블클릭 → 브라우저에서 **`http://127.0.0.1:8600`** 접속  
3. 콘솔 창을 닫지 마세요 (서버 종료)

> **`web/out/index.html`을 탐색기에서 직접 열지 마세요.** (`file://` — 메뉴·API 모두 깨짐)

### 개발

```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH = (Get-Location)
python -m uvicorn api.main:app --host 127.0.0.1 --port 8600
```

UI 소스 수정 후: `scripts\build_web.bat` → `RestartWeb.bat` (또는 창 유지 중이면 재기동).

별도 터미널: `cd web && npm run dev` (프록시 없이 API 직접 호출 시 CORS 허용됨)

## 화면

| 메뉴 | 기능 |
|------|------|
| 대시보드 | Run 카드 · 모델 순위 · Test 4×4 · 추론 4×4 |
| Run ID 발급 | 작업자/작업내용/비고 |
| 데이터 등록 | train/inference raw 업로드·선택삭제·초기화 |
| ▼ 모델 학습 및 평가 | 학습 실행 / 모델 비교·평가 / 타겟 포착 분포 |
| ▼ 추론 | 추론 실행 / 결과 확인 |
| Run 이력 · PC · 가이드 · 설정 | 조회·사양·문서·data_root |

상단 **Job 배너**, 헤더 **현재 Run** 선택.

## API 문서

서버 기동 후 `http://127.0.0.1:8600/api/docs`

## Agent

Cursor Agent는 raw/DB 행을 읽거나 학습 스크립트를 실행하지 않습니다.
