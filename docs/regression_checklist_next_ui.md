# Phase 7 — Next.js UI 회귀 체크리스트

수동 테스트 (로컬 `RunWebNext.bat` + `web/out` 빌드 후)  
주소: **`http://127.0.0.1:8600`** (`web/out/index.html` 직접 열기 금지)

## 실행 전

1. `RestartWeb.bat` (또는 `RunWebNext.bat`)
2. 브라우저 **Ctrl+F5**
3. (선택) 자동 스모크: `.venv\Scripts\python.exe scripts\smoke_web_ui.py`

---

## 글로벌
- [x] 헤더 Run 선택 ↔ 대시보드 카드 동기화
- [x] Job 배너 폴링 · 취소 · 완료/실패 메시지

## 화면별
- [x] 대시보드: Run 카드, 순위, Test 4×4, 추론 4×4, 빈상태  
  → Run DB 순위 없으면 「순위 없음」(이전 eval_summary 전역 폴백 제거)
- [x] Run 발급: Dialog 필수값, DB 저장, 현재 Run 전환, 목록
- [x] 데이터 등록: 메타 표 표시 (Playwright: train 8건 표출)  
  → Radix Checkbox 제거 · API abort/12초 타임아웃 · 응답 컬럼 슬림화
- [x] 학습 실행: 옵션/단계/상태표 로드 (client exception 수정)  
  → 배열 안전 처리 · ErrorBoundary · Dialog 비모달
- [x] 모델 비교: empty=true 시 빈상태 (Run별 순위만)
- [x] 타겟 포착: 로딩/빈상태 분기 수정 (DualMatrices null 안전)
- [x] 추론 실행/결과: API prereq·results·ops-queue 응답 OK
- [x] Run 이력, PC 사양, 가이드, 설정: 정적 페이지·API OK

## Streamlit 레거시
- [x] `app/` · `RunWeb.bat` · streamlit/plotly 의존성 제거 (helpers → `src/scoring/inference_helpers.py`)

---


## Agent 일괄 점검 (2026-07-19)

`scripts/smoke_web_ui.py` 결과: **PASS**

| 구분 | 결과 |
|------|------|
| 정적 페이지 12개 | 모두 200 + HTML chunk |
| `/api/data/raw` | items=8 |
| `/api/data/raw-inference` | items=2 |
| dashboard | ranking_empty=True (01만 진행 Run — 정상) |
| models | empty=True (정상) |
| config/steps/leakage/ops/history/inference | OK |

### 이번 라운드에서 고친 것
1. 학습 실행 **client-side exception** — Radix Dialog/Checkbox 제거, 단순 모달·native input로 교체  
2. Dialog 전역 구현을 Radix 없이 경량화 (정적 export 호환)  
3. 타겟 포착 — DualMatrices null 안전  
4. 대시보드/모델 — Run별 순위 없을 때 전역 eval_summary 오표시 제거  
5. Run 목록 sessionStorage 캐시 · 내비 시 쿼리 취소  

### Playwright 재확인 (학습 실행)
- 직접 `/pipeline/` 로드: **에러 없음**, 옵션/단계 UI 표시  
- 사이드바 내비 진입: 동일 확인 권장 (Ctrl+F5 후)

### 사용자 확인 권장 (Job·업로드는 Agent가 실행하지 않음)
- [x] 학습 실행 화면 진입 후 멈추지 않음
- [ ] 데이터 등록 메타 표 표시
- [ ] Job 시작 후 다른 메뉴 이동
- [ ] merge만 한 Run → 대시보드 「순위 없음」
