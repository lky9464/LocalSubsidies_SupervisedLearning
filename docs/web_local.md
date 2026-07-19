# 로컬 웹 UI (Streamlit)

## 원칙

- **127.0.0.1** 만 바인딩 (`0.0.0.0` 금지)
- raw·모델·행단위 점수는 `{data_root}` 파일
- 운영 DB는 `{data_root}/ops/ops.sqlite` — **런/순위/타겟 포착·점검 우선순위 조회·메타만**, raw 미포함
- 파이프라인은 **백그라운드 Job** (`Popen`) — 메뉴 이동해도 계속 실행
- GitHub·Agent로 민감데이터 유출 금지

## 실행

### 더블클릭 (권장)

프로젝트 루트의 **`RunWeb.bat`** 을 더블클릭하세요.  
검은 콘솔 창이 열린 채로 유지되어야 하며, **서버가 준비된 뒤** 브라우저가 자동으로 열립니다.  
기본 포트는 `8501`이며, 점유 시 `8502`~`8510` 중 빈 포트를 씁니다.

### 코드 수정 후 재시작 (개발)

| 방법 | 설명 |
|------|------|
| **`RestartWeb.bat`** | 기존 Streamlit 종료 → 새로 기동 (권장) |
| `RunWeb.bat restart` | 동일 (콘솔에서) |
| `.\scripts\run_web.ps1 -Restart` | PowerShell |

이미 실행 중일 때 **`RunWeb.bat`만** 누르면 브라우저만 열립니다(빠른 경로).  
Agent가 `app/` 등을 수정하면 Cursor hook이 작업 종료 시 **`RestartWeb.bat`** 을 자동 실행할 수 있습니다 (`.cursor/hooks.json`).

### 터미널

```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
.\scripts\run_web.ps1
```

## 화면 (타이틀: 지방보조금 부정수급 위험도 측정)

| 메뉴 | 기능 |
|------|------|
| 대시보드 | Run 카드로 현재 Run 선택 · 모델 평가 + 추론 4×4 |
| 데이터 등록 | 학습 raw + 추론 raw, 추가확인·선택삭제·초기화 |
| ▼ 모델 학습 및 평가 | 하위: 학습 파이프라인 / 모델 비교·평가 / 타겟 포착 분포 |
| ▼ 추론 | 하위: 추론 실행 / 결과 확인 (점검 우선순위표) |
| Run 이력 | 조회 전용 (현재 Run은 대시보드 카드에서 선택) |
| 내 PC 사양 체크 | psutil 쾌적/보통/부족 |
| 사용자 가이드 | md + PDF 다운로드 |
| 설정 | data_root·ops.sqlite 경로 |

상단 **전역 배너**에 실행 중 Job·진행률이 표시됩니다.

## 타겟 포착 · 점검 우선순위 규칙 (요약)

- 주/보 각각 상위 1%·5%·10% 구간 → 주A~주D / 보A~보D  
- 우선순위 1~16: **주등급 우선**, 보조는 같은 주등급 안에서만 순서  
- **타겟 포착 분포**(Test): 전체 4×4 + 실제 타겟 분포 / **점검 우선순위표**(추론): 전체 4×4만  
- 상세: `docs/operations_criteria.md` §5

## Agent

Cursor Agent는 웹 앱을 통해 raw/DB 행을 읽거나 학습을 대행하지 않습니다.
