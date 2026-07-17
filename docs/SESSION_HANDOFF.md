# 세션 인수인계 (2026-07-17)

다른 PC·다음 세션에서 **「오늘까지 뭐 했는지 / 다음에 뭘 하면 되는지」** 를 바로 이어가기 위한 메모입니다.

## 프로젝트 한 줄

지방보조금 부정수급 **위험도 점수(0~1000)** 지도학습 파이프라인.  
데이터·모델·행단위 점수는 repo 밖 `{data_root}` (예: `LocalSubsidies_ML_Data`), 코드·집계 리포트만 GitHub.

원격: https://github.com/lky9464/LocalSubsidies_SupervisedLearning

## 완료된 것 (2026-07-17까지)

### 파이프라인
| # | 스크립트 | 상태 |
|---|----------|------|
| 01~05 | merge → label → preprocess → leakage → train | 구현·로컬 실행 완료(사용자 PC) |
| 06 | feature importance → `feature_top10.json` + Excel | 순서상 evaluate **앞**으로 배치 |
| 07 | evaluate → `{algo}_test_scores.csv` + `{algo}_test_scores_top.xlsx` | 14열 부가 + 실제라벨 + 상위1%/5% |
| 08 | 집계 Excel/PDF | 구현됨 |
| 09 | 추론 골격 | 있음 (2026 추론은 사용자 요청으로 보류) |

### 점수 파일 규약 (`07`)
- 경로: `{data_root}/algorithms/{algo}/scores/`
- 파일명: `{algo}_test_scores.csv`, `{algo}_test_scores_top.xlsx`
- 컬럼 순서: 키·명칭/금액 → 위험도점수 → 양성확률 → 예측라벨 → **실제라벨** → 기여도TOP10(맨 뒤)

### 운영 모델 (문서화됨)
1. RandomForest (주)  
2. CatBoost (보조)  
3. Stacked (참고)  
EasyEnsemble 운영 제외. 상세: `docs/operations_criteria.md`

### Git / 문서
- 초기 커밋·푸시 완료, README 유의사항·알고리즘 5종 도식 반영
- `.gitignore`에서 `src/models/`가 무시되지 않도록 `/models/`로 수정함
- `docs/pipeline.md` 신설

### Owner 검증 PC 사양 (참고)
Ryzen 3 3200G / 약 14GB RAM / Vega 8 / Win11 — README 유의사항 표와 동일.

## 의도적으로 안 한 것
- 2026.01~06 추론(`09`) 실데이터 적용
- RF 점수 S/A/B/C 등급·점검 큐 스크립트 (다음 추천 작업)
- EasyEnsemble/GB를 기본 algorithms에서 제거하는 정리

## 다음 세션 추천 (우선순위)
1. **RF(+CatBoost) 점검 큐**: S/A/B/C 등급 컬럼 + (선택) 교차 플래그  
2. Test 상위1%/5% 업무 검토(로컬만, Agent에 행 출력 금지)  
3. 컷오프를 “점수 절대값”으로 `operations_criteria`에 숫자 고정  
4. (여유 시) RF 하이퍼파라미터·운영용 임계값 튜닝  
5. 2026 추론은 사용자가 다시 요청할 때

## 다른 PC에서 이어갈 때
1. `git clone` 또는 `git pull`  
2. `configs/local.yaml`은 **새로** 만들고 `data_root`만 해당 PC 경로로 (커밋 금지)  
3. raw/모델/점수는 USB·별도 복사로 옮기거나 그 PC에서 파이프라인 재실행  
4. Agent에게: 「`docs/SESSION_HANDOFF.md` 기준으로 이어서」라고 요청

## Agent 경계 (잊지 말 것)
- `data_root`·행단위 점수·학습 스크립트 실행 금지  
- Rule: `.cursor/rules/no-sensitive-data.mdc`
