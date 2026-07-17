# 운영 기준 확정서 (모델 선정·점검 기준)

작성 기준일: 2026-07-17  
평가 구간(Test): `CRTR_YM` 2025.07 ~ 2025.12  
학습 구간(Train): 2024.01 ~ 2025.06  
타겟: `TAET_YN` (ISDP_RGSTR_YN / ISRC_DSCL_YN / PMBZ_CFMTN_YN 중 1개 이상 Y)

### 관련 파이프라인 순서 (scripts)

`01_merge` → `02_label` → `03_preprocess` → `04_leakage_audit` → `05_train` → `06_feature_importance` → `07_evaluate` → `08_report` → (`09_score_inference`)

---

## 1. 목적

지방보조금 부정수급 **위험도 점수(0~1000)** 를 실무 점검에 적용하기 위한  
**주 운영 모델·보조 모델·참고 모델**과 **점검 컷오프 기준**을 확정한다.

---

## 2. 모델 순위 (확정)

| 순위 | 알고리즘 | 운영 역할 | 비고 |
|------|----------|-----------|------|
| **1위** | **RandomForest** | **주 운영 모델** | 점수 부여·점검 우선순위·보고의 기본 |
| **2위** | **CatBoost** | **보조·교차검증 모델** | 주 모델 고위험 건과의 교차 확인 |
| **3위** | **Stacked Ensemble** | **참고·예비 모델** | 단독 운영보다 비교·리포트용 |

**운영 후보에서 제외(현 시점)**  
- EasyEnsemble: Test 성능(PR-AUC·리프트·정밀도)이 크게 낮아 운영 순위에서 제외  
- Gradient Boosting: 3위(Stacked) 대비 우선순위 낮음. 필요 시 재평가 가능

---

## 3. 선정 사유 (요약)

### 3.1 주 운영 — RandomForest
- ROC-AUC·PR-AUC·F1·상위 1%/5% 리프트가 전반적으로 가장 균형 있음  
- 고득점(900~1000) 구간의 실제 양성 비율이 높아, “고위험 우선 점검”에 적합  
- 정밀도·재현율 균형이 CatBoost/Stacked보다 실무(과탐 부담)에 유리  

### 3.2 보조 — CatBoost
- 재현율·상위 K% 리프트가 우수하여 **놓치는 위험(미탐)을 줄이는 교차 확인**에 적합  
- 정밀도는 RF보다 낮아, 단독 주 모델보다는 보조 역할이 적절  

### 3.3 참고 — Stacked Ensemble
- 순위 능력(ROC/PR-AUC, 상위 K% 리프트)은 상위권  
- 0.5 기준 분류 시 정밀도·F1이 크게 낮아 **단독 운영은 비권장**  
- RF/CatBoost와 점수 분포·고위험 교집합을 비교하는 **참고 모델**로 활용  

### 3.4 누수 점검 결과
- `scripts/04_leakage_audit.py` 결과: **PASS**  
- **실행 위치:** `03_preprocess` 직후 · `05_train` 이전 (권장 순서). 이번 프로젝트에서는 학습 이후에도 동일 점검 수행·PASS 확인  
- 타겟·라벨소스 3종·사후성 제외 컬럼이 Feature에 잔존하지 않음  
- 단변량 ROC-AUC ≥ 0.9 인 “타겟 복제형” 피처 없음  
- → 고생능은 **직접 누수보다 신호 결합**으로 해석  

상세: `outputs/reports/comparison/leakage_audit.xlsx`

---

## 4. 위험도 점수 운영 규칙

| 항목 | 내용 |
|------|------|
| 점수 범위 | 0 ~ 1000 (높을수록 위험↑) |
| 산출 | 양성(부정수급 위험) 확률 × 1000 (반올림) |
| **공식 점수** | **RandomForest 점수**를 업무 기본값으로 사용 |
| 보조 점수 | CatBoost(필수 교차 시), Stacked(선택 참고) |

동일 건에 대해 RF·CatBoost 점수를 함께 둘 경우 컬럼 예:
- `위험도점수_RF(risk_score_rf)`
- `위험도점수_CatBoost(risk_score_catboost)`
- (선택) `위험도점수_Stacked(risk_score_stacked)`

`algorithms/{algo}/scores/{algo}_test_scores.csv` (로컬 전용)에는 추가로 다음이 포함된다.  
수행사업명칭, 기관명, 사업비보조금금액, 사업비자부담금액, 예측/실제라벨, 해당 알고리즘 기여도 TOP10 Feature 값(10열, 맨 뒤).  
상위 1%/5%는 `{algo}_test_scores_top.xlsx`에 동일 컬럼 순서로 저장된다.

---

## 5. 점검 컷오프 권고 (주 모델 = RandomForest)

Test 집계(양성 비율 약 0.27%) 및 상위 K% 리프트·점수구간 결과를 바탕으로 한 **초기 권고**이다.  
현장 인력·점검 가능 건수에 맞춰 조정한다.

### 5.1 우선 권고안 (실무 기본)

| 등급 | 기준 (RF) | 의미 | 대응 |
|------|-----------|------|------|
| **S (최우선)** | 점수 **900 ~ 1000** | 고위험 집중 구간 | 즉시/우선 점검 |
| **A (우선)** | 상위 **약 1%** 또는 점수 높은 순 점검 큐 | 리프트 매우 높음 | 계획 점검 |
| **B (관심)** | 상위 **약 5%** | 확대 모니터링 | 샘플·테마 점검 |
| **C (일반)** | 그 외 | 통상 관리 | 정기 모니터링 |

### 5.2 교차검증 규칙 (보조 모델)

주 모델(RF)이 S/A 등급인 건에 대해:

1. **CatBoost 점수도 함께 확인**  
2. 권고 판정 예:
   - RF·CatBoost **모두 고위험** → 점검 우선순위 상향  
   - RF만 고위험·CatBoost는 중저위험 → 사유 확인 후 점검(과탐 가능성 고려)  
3. Stacked는 **분쟁·재검토 시 참고**로만 사용 (단독 컷오프 비권장)

### 5.3 수치 참고 (Test, 이전 평가 요약)

| 지표 | RF | CatBoost | Stacked |
|------|-----|----------|---------|
| ROC-AUC | 0.985 | 0.976 | 0.978 |
| PR-AUC | 0.742 | 0.667 | 0.707 |
| 상위 1% 리프트 | 약 92 | 약 92 | 약 90 |
| 상위 5% 리프트 | 약 19 | 약 19 | 약 19 |

※ Accuracy만으로 모델을 고르지 말 것. 불균형 데이터이므로 PR-AUC·리프트·정밀도/재현율을 본다.  
해설: `docs/metrics_guide.md`

---

## 6. Feature 해석 (운영 참고)

주 모델(RF) TOP 요지: **지자체·부서·시도 코드**, **상근직원수·회원수·설립년수**, **대표자 연령/세대**, **사업비 규모** 등이 중요.

상세 TOP10:  
`outputs/reports/comparison/feature_importance_top10_all.xlsx`  
`outputs/reports/random_forest/feature_importance_top10.xlsx`

주의: 중요도는 **상관·기여도**이지, 곧바로 “원인=부정수급”을 의미하지 않는다. 점검 단서로 사용한다.

---

## 7. 2026년 데이터 적용 절차

대상: **2026.01 ~ 2026.06** (라벨 미지 가능)

1. CSV를 `{data_root}/raw_inference/` 에 배치 (스키마·EUC-KR 동일)  
2. 로컬 실행:
   ```text
   python scripts/09_score_inference.py --algo random_forest
   python scripts/09_score_inference.py --algo catboost
   python scripts/09_score_inference.py --algo stacked_ensemble
   ```
3. 점수 파일은 `{data_root}/algorithms/{algo}/scores/` (로컬 전용, GitHub 금지)  
4. **업무 배포·점검 큐는 RF 점수 기준** + 필요 시 CatBoost 교차  

---

## 8. 변경·재평가 조건

다음이 발생하면 본 문서를 개정하고 순위를 재검토한다.

- 타겟(`TAET_YN`) 정의 규칙 변경  
- Feature 추가·삭제 또는 점수 시점 가용 컬럼 정책 변경  
- 2026 현장 적발/환수 결과와 점수 등급의 정합이 지속 불량  
- 재학습 후 Test 지표에서 1~3위 순위가 바뀌는 경우  

---

## 9. 관련 산출물

| 구분 | 경로 |
|------|------|
| 모델 성능 비교 | `outputs/reports/comparison/model_evaluation_comparison.xlsx` |
| 누수 감사 | `outputs/reports/comparison/leakage_audit.xlsx` |
| Feature TOP10 | `outputs/reports/comparison/feature_importance_top10_all.xlsx` |
| 지표 해설 | `docs/metrics_guide.md` |
| 타겟 정의 | `docs/label_definition.md` |
| Agent/데이터 경계 | `docs/AGENT_BOUNDARY.md` |
