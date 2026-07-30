# 세션 인수인계 (2026-07-30)

## 프로젝트
지방보조금 부정수급 위험도 지도학습 + **로컬 Next.js + FastAPI UI** + 운영 SQLite(raw 제외) + 백그라운드 Job.

- 원격: https://github.com/lky9464/LocalSubsidies_SupervisedLearning  
- **GitHub 최신 태그/Release:** **v0.6.2**  
- **이전 Release:** **v0.6.1** — `group_random` 분할 · 04 그룹 감사 · UI  
- 실행: `RunWebNext.bat` → `http://127.0.0.1:8600`

---

## v0.6.2 완료 요약 — 행 PK 결측 제외

**배경:** 새 raw에서 `PFM_BIZ_ID`/`INST_ID` 결측 시 04 그룹 감사(`bincount`) 실패. PK 3종(`CRTR_YM`, `PFM_BIZ_ID`, `INST_ID`) 중 하나라도 null이면 사용 불가로 통일.

| 구간 | 처리 |
|------|------|
| **03 preprocess** | merge 후 PK null 행 제외 · `pk_drop` 메타 저장 |
| **04~07, train, tune** | `align_labeled_to_split_masks()` — `labeled.csv`와 `split_masks` 길이 맞춤 |
| **11 inference** | merge 후 동일 PK 기준 제외 · 전량 제외 시 `RuntimeError` |

**검증:** 웹에서 01~10 전수 테스트 완료 · 11 추론 PK 제외 반영.

### 코드 변경 (v0.6.2)

| 영역 | 파일 |
|------|------|
| PK 유틸 | `src/features/group_audit.py` — `drop_rows_missing_group_keys`, `align_labeled_to_split_masks` |
| 전처리 | `scripts/03_preprocess.py` |
| 누수·평가 | `scripts/04_leakage_audit.py`, `06_*`, `07_*` |
| 학습·튜닝 | `src/models/train_runner.py`, `src/models/tune.py` |
| 추론 | `scripts/11_score_inference.py` |
| 테스트 | `tests/test_group_split.py` |

---

## v0.6.1 참고 — `group_random`

- Train/Test **동일 `PFM_BIZ_ID+INST_ID` 엔티티 교집합 0** · 04 `PASS_그룹중복_낮음`
- baseline `random` Run과 **Test 지표 직접 비교 금지**
- 상세: [`VERSION_HISTORY.md`](VERSION_HISTORY.md) v0.6.1 섹션

---

## 오프라인 업데이트

1. Release **`update-to-v0.6.2.zip`** 을 프로젝트 루트에 복사 (**zip 풀지 않음**)  
2. `UpdateOffline.bat` → `SetupOffline.bat` → `RunWebNext.bat`  
3. deps 변경 없음 — wheels는 v0.5.2+ 기존 설치 유지

상세: [`offline_update.md`](offline_update.md) · [Release v0.5.2](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.5.2)

## Agent 경계
data_root / ops.sqlite / raw 내용 읽기·학습 스크립트·웹 서버 기동(데이터 유발) 금지.  
상세: `docs/AGENT_BOUNDARY.md` · `.cursor/rules/no-sensitive-data.mdc`
