# 운영 기준 확정서 (모델 선정·점검 기준)

작성 기준일: 2026-07-17  
평가 구간(Test): `CRTR_YM` 2025.07 ~ 2025.12  
학습 구간(Train): 2024.01 ~ 2025.06  
타겟: `TAET_YN` (ISDP_RGSTR_YN / ISRC_DSCL_YN / PMBZ_CFMTN_YN 중 1개 이상 Y)

### 관련 파이프라인 순서 (scripts)

`01_merge` → `02_label` → `03_preprocess` → `04_leakage_audit` → `05_train` → `06_feature_importance` → `07_evaluate` → `08_ranking` → `09_report` → `10_ops_queue` → (`11_inference` 별도)

---

## 1. 목적

지방보조금 부정수급 **위험도 점수(0~1000)** 를 실무 점검에 적용하기 위한  
**주·보 모델 선정 방법**, **점검 컷오프(4×4) 규칙**, 및 **현재 평가 스냅샷**을 정리한다.

> **주·보 알고리즘은 고정이 아닙니다.**  
> 5종 학습 → 평가(07) → 순위(08) → `ops_queue.primary_algo` / `aux_algo` 설정으로 결정하며,  
> 데이터·타겟·재학습에 따라 **RandomForest·CatBoost 등 어떤 조합이든** 바뀔 수 있다.

---

## 2. 주·보 모델 선정 (원칙)

| 단계 | 내용 |
|------|------|
| 1 | 5종 알고리즘 학습(05) · 평가(07) |
| 2 | `08_update_ranking.py` — PR-AUC·리프트·F1 등으로 **순위** 산출 |
| 3 | 웹 **모델 비교·평가** · 대시보드에서 순위·4×4 확인 |
| 4 | `configs/default.yaml` → `ops_queue.primary_algo`(주), `aux_algo`(보) 반영 |
| 5 | `10_ops_queue` · 추론 — 위 설정의 **주·보 점수**로 4×4·우선순위표 생성 |

**역할 정의**

| 역할 | 의미 |
|------|------|
| **주 모델** | 점검 우선순위·타겟 포착의 **1차 기준** (주A~주D) |
| **보조 모델** | **교차 확인** · 동일 주등급 내 **정렬** (보A~보D) |
| **참고** | 순위 3위 이하 등 — 분쟁·재검토·리포트 비교 (단독 4×4 기준 아님) |

주·보는 **서로 다른 알고리즘 2개**를 쓰는 것을 권장(과적합·편향 분산).  
PC·시간 제약 시 **주·보에 해당하는 2종만** 학습·추론해도 된다.

---

## 2.1 현재 평가 스냅샷 (2026-07-17 기준 · 변경 가능)

아래는 **당시 Test 구간·데이터**로 07·08을 돌린 **결과 기록**이다.  
재학습·데이터 변경 후 순위가 바뀌면 **설정과 본 절을 갱신**한다.

| 순위 | 알고리즘 | 당시 운영 역할 | 비고 |
|------|----------|----------------|------|
| **1위** | **RandomForest** | **주 모델** (`primary_algo`) | 점수·4×4의 1차 기준 |
| **2위** | **CatBoost** | **보조 모델** (`aux_algo`) | 교차 확인·동등급 정렬 |
| **3위** | **Stacked Ensemble** | 참고 | 비교·리포트 |

**당시 운영 후보에서 제외(참고)**  
- EasyEnsemble: Test 성능(PR-AUC·리프트·정밀도)이 크게 낮음  
- Gradient Boosting: 3위(Stacked) 대비 우선순위 낮음 — 재평가 가능

**설정 기본값** (`configs/default.yaml`):  
`primary_algo: random_forest`, `aux_algo: catboost` — **초기값·스냅샷 반영**이며 영구 고정 아님.

---

## 3. 선정 사유 (2026-07-17 스냅샷 요약)

### 3.1 당시 1위 — RandomForest (주 후보)
- ROC-AUC·PR-AUC·F1·상위 1%/5% 리프트가 전반적으로 균형  
- 고득점 구간의 실제 양성 비율이 높아 “고위험 우선 점검”에 적합  
- 정밀도·재현율 균형이 CatBoost/Stacked보다 실무(과탐 부담)에 유리  

### 3.2 당시 2위 — CatBoost (보 후보)
- 재현율·상위 K% 리프트가 우수 — **미탐 줄이는 교차 확인**에 적합  
- 정밀도는 RF보다 낮아, 단독 주 모델보다 **보조**가 적절  

### 3.3 당시 3위 — Stacked Ensemble (참고)
- 순위 능력(ROC/PR-AUC, 상위 K% 리프트)은 상위권  
- 0.5 기준 분류 시 정밀도·F1이 낮아 **단독 주·보 비권장**  
- 주·보 모델과 점수 분포·고위험 교집합 **비교용**  

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
| **주 점수** | **`ops_queue.primary_algo`** 모델 점수 (4×4 주등급) |
| **보조 점수** | **`ops_queue.aux_algo`** 모델 점수 (동등급 내 정렬) |
| 참고 | 순위 3위 이하 모델 점수 — 비교·재검토 시 |

동일 건에 여러 알고리즘 점수를 둘 경우 컬럼 예 (`{algo}` = 알고리즘 폴더명):
- `위험도점수_{algo}(risk_score_{algo})`  
- ops 큐 조인 시: `위험도점수_주모델(risk_score_primary)`, `위험도점수_보조모델(risk_score_aux)`

`algorithms/{algo}/scores/test/{algo}_test_scores.csv` (로컬 전용)에는 추가로 다음이 포함된다.
수행사업명칭, 기관명, 사업비보조금금액, 사업비자부담금액, 예측/실제라벨, 해당 알고리즘 기여도 TOP10 Feature 값(10열, 맨 뒤).  
상위 1%/5%는 `scores/test/{algo}_test_scores_top.xlsx`에 동일 컬럼 순서로 저장된다.

---

## 5. 타겟 포착 분포 · 점검 우선순위표 (주·보 = ops_queue 설정)

동일 주·보 상위% 구간 규칙을 쓰되 용도를 나눈다.  
**주·보에 쓰는 알고리즘**은 `configs/default.yaml`의 `ops_queue.primary_algo` / `aux_algo` (웹 대시보드·모델 비교에서 확인).

| 구분 | 웹 메뉴 | 목적 |
|------|---------|------|
| Test(평가) | **타겟 포착 분포** | 이미 타겟이 있는 평가 데이터에서 포착 품질 확인 |
| 추론 | **추론 → 결과 확인** (점검 우선순위표) | 타겟 미지 데이터에서 점검 대상 선정 |

Test 집계(양성 비율 약 0.27%) 및 상위 K% 리프트·점수구간 결과를 바탕으로 한 **초기 권고**이다.  
현장 인력·점검 가능 건수에 맞춰 조정한다.

### 5.1 우선 권고안 (실무 기본) — 코드 고정

스크립트: `scripts/10_ops_queue.py`  
설정: `configs/default.yaml` → `ops_queue` (`a_top_pct: 1`, `b_top_pct: 5`, `c_top_pct: 10`)

주·보조 각각에 **동일 상위% 구간(A~D)** 을 두고, **주등급이 우선**·보조는 동등급 내 정렬만 담당합니다.  
절대 점수 컷(예: ≥900)은 사용하지 않습니다.

| 구간 | 기준 (점수 상위 백분위) | 주모델 라벨 | 보조모델 라벨 |
|------|-------------------------|-------------|---------------|
| **A** | 상위 **1%** 이내 | 주A | 보A |
| **B** | 상위 1% 초과 ~ **5%** 이내 | 주B | 보B |
| **C** | 상위 5% 초과 ~ **10%** 이내 | 주C | 보C |
| **D** | 상위 **10%** 초과 | 주D | 보D |

구간은 **상호 배타**입니다.

### 5.2 4×4 우선순위 (1~16)

`우선순위 = 주등급순위×4 + 보등급순위 + 1` (작을수록 우선).

| 우선순위 | 조합 | 권고 |
|----------|------|------|
| 1 | 주A×보A | 최우선 점검 |
| 2 | 주A×보B | 주A 내 차순위 |
| … | … | … |
| 4 | 주A×보D | 주A이지만 보조는 낮음 |
| 5~8 | 주B×보A~보D | 주B 구간 |
| 9~12 | 주C×보A~보D | 주C 구간 |
| 13~16 | 주D×보A~보D | 후순위(보조만 높아도 주D면 후순위) |

산출(로컬 전용): `{data_root}/algorithms/operations/ops_queue_test.csv`  
및 `ops_queue_test.xlsx` (시트 `전체` / `우선순위요약` / `4x4전체` / `4x4실제양성` / `주A` / `주B` / `주C`).

**Test vs 추론 화면**

| 구분 | 메뉴명 | 4×4 표시 |
|------|--------|----------|
| Test(평가) | 타겟 포착 분포 | 전체 + 실제 타겟 분포 (나란히) |
| 추론 | 점검 우선순위표 | 전체 매트릭스만 |

Stacked 등 **참고 모델**은 분쟁·재검토 시에만 사용 (단독 4×4·선정 기준 비포함).

### 5.3 수치 참고 (Test, 2026-07-17 스냅샷 · 주=RF / 보=CatBoost 당시)

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

**주 모델(`primary_algo`)** TOP 요지(2026-07-17 RF 기준 예): 지자체·부서·시도 코드, 상근직원수·회원수·설립년수, 대표자 연령/세대, 사업비 규모 등.

상세 TOP10:  
`outputs/reports/comparison/feature_importance_top10_all.xlsx`  
`outputs/reports/{primary_algo}/feature_importance_top10.xlsx` (주 모델 폴더)

주의: 중요도는 **상관·기여도**이지, 곧바로 “원인=부정수급”을 의미하지 않는다. 점검 단서로 사용한다.

---

## 7. 2026년 데이터 적용 절차

대상: **2026.01 ~ 2026.06** (라벨 미지 가능)

1. CSV를 `{data_root}/raw_inference/` 에 배치 (스키마·EUC-KR 동일)  
2. 로컬 실행 ( **`primary_algo` / `aux_algo` 각각** — 설정값 확인):
   ```text
   python scripts/11_score_inference.py --algo random_forest
   python scripts/11_score_inference.py --algo catboost
   ```
   (예시는 당시 스냅샷. 실제 `--algo`는 설정·순위에 맞게 바꿉니다.)
3. 점수 파일은 Test와 동일 양식·명명 규칙으로 저장 (로컬 전용, GitHub 금지)  
   - `scores/inference/{algo}_inference_scores.csv`  
   - `scores/inference/{algo}_inference_scores_top.xlsx` (시트: 상위1% / 상위5%)  
   - 컬럼: 키 + 명칭/금액 → 위험도점수 → 양성확률 → 예측라벨 → 실제라벨(비움) → 기여도 TOP10  
4. **점검 우선순위표** = **주 모델 상위% 구간 우선** + **보조 모델** 동등급 내 정렬 (`10` / 추론 결과)  


---

## 8. 변경·재평가 조건

다음이 발생하면 **순위·`primary_algo`/`aux_algo`·본 문서 스냅샷**을 재검토한다.

- 타겟(`TAET_YN`) 정의 규칙 변경  
- Feature 추가·삭제 또는 점수 시점 가용 컬럼 정책 변경  
- 2026 현장 적발/환수 결과와 점수 등급의 정합이 지속 불량  
- 재학습 후 Test 지표에서 **1~3위·주·보 후보**가 바뀌는 경우  
- raw 기간·건수·양성 비율이 크게 변한 경우  

---

## 9. 관련 산출물

| 구분 | 경로 |
|------|------|
| 모델 성능 비교 | `outputs/reports/comparison/model_evaluation_comparison.xlsx` |
| 누수 감사 | `outputs/reports/comparison/leakage_audit.xlsx` |
| Feature TOP10 | `outputs/reports/comparison/feature_importance_top10_all.xlsx` |
| 타겟 포착 분포 (Test, 로컬) | `{data_root}/algorithms/operations/ops_queue_test.*` |
| 점검 우선순위표 (추론, 로컬) | `{data_root}/algorithms/operations/ops_queue_inference.*` |
| 지표 해설 | `docs/metrics_guide.md` |
| 타겟 정의 | `docs/label_definition.md` |
| Agent/데이터 경계 | `docs/AGENT_BOUNDARY.md` |
