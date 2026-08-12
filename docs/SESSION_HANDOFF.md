# 세션 인수인계 (2026-08-13)

## 프로젝트
지방보조금 부정수급 위험도 지도학습 + **로컬 Next.js + FastAPI UI** + 운영 SQLite(raw 제외) + 백그라운드 Job.

- 원격: https://github.com/lky9464/LocalSubsidies_SupervisedLearning  
- **GitHub 최신 태그/Release:** **v1.0.0**  
- 실행: `RunWebNext.bat` → `http://127.0.0.1:8600` (**코드 반영 후 재시작 필수**)

---

## v1.0.0 요약

### 추론 → 결과 확인
- 타겟 포착(`/ops`)과 동일 패턴: **주/보 · 주/참 · 보/참** · **PK(A-1) · 엔티티(B-1)** (실제 타겟 A-2/B-2 숨김)
- 산출: `ops_queue_inference_pk.*` · `ops_queue_inference_entity.*` + `inference_queue_*` DB
- 추론 실행: **08 주·보·참만** 선택 · 「알고리즘별 점수」UI 제거

### 모델 비교·평가 (이전 세션 포함)
- 점수 분포: slim/캐시 · 막대 색=타겟 **비중** · SHAP TOP10별 점수분포 UI/API 삭제
- 타겟 포착: 케이스 지연 로드

### 정리
- 데드 코드·구 `ops_queue_inference.*` 문서명 정리 · FeatureDistribution 컴포넌트 제거

상세: [`VERSION_HISTORY.md`](VERSION_HISTORY.md)

---

## 설정 구분

| 파일 | 역할 |
|------|------|
| `configs/default.yaml` | 웹·03~11 · registry · `model_params` |
| `configs/tune.yaml` | 12·tune_batch 전용 |
| `configs/local.yaml` | `data_root` (Git 제외) |
| `runs/{run_id}/run_config.yaml` | Run별 split·`algorithms` |

---

## Agent 경계
data_root / ops.sqlite / raw 내용 읽기·학습 스크립트·웹 서버 기동(데이터 유발) 금지.  
상세: `docs/AGENT_BOUNDARY.md` · `.cursor/rules/no-sensitive-data.mdc`
