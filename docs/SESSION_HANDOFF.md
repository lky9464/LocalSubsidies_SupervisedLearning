# 세션 인수인계 (2026-07-28)

## 프로젝트
지방보조금 부정수급 위험도 지도학습 + **로컬 Next.js + FastAPI UI** + 운영 SQLite(raw 제외) + 백그라운드 Job.

- 원격: https://github.com/lky9464/LocalSubsidies_SupervisedLearning  
- **GitHub 최신 태그/Release:** **v0.5.2**  
  - Run 산출물 격리 · 재실행 초기화 · CleanupLegacy  
  - 오프라인 full sync (`update-to-v0.5.2.zip` · `UpdateOffline.bat` 더블클릭)  
  - 추론 Run 경로 수정 · ops 큐 자동 저장  
- 실행: `RunWebNext.bat` → `http://127.0.0.1:8600`

## v0.5.2 요약

### Run 격리
```text
{data_root}/raw/                    # 공유
{data_root}/raw_inference/          # 공유
{data_root}/runs/{run_id}/interim|processed|algorithms|reports/
{data_root}/ops/ops.sqlite          # 공유
```

### 재실행 초기화
클릭 단계~10 연쇄 초기화 · Job 취소 시 미실행으로 삭제 · `CleanupLegacy.bat`은 선택(raw 유지)

### 오프라인 업데이트
1. `update-to-v0.5.2.zip` + `wheels-win-amd64-py312.zip`을 프로젝트 루트에 복사  
2. `UpdateOffline.bat` 더블클릭  
3. (필요 시) `SetupOffline.bat` → `RunWebNext.bat restart`

상세: `docs/offline_update.md` · `docs/VERSION_HISTORY.md`

## Agent 경계
data_root / ops.sqlite / raw 내용 읽기·학습 스크립트·웹 서버 기동(데이터 유발) 금지.  
상세: `docs/AGENT_BOUNDARY.md` · `.cursor/rules/no-sensitive-data.mdc`
