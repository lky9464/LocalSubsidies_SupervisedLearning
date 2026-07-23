# 모델 순위·주·보 선정 (08)

Test **1회**(`07_evaluate`) 결과로 Run에 포함된 알고리즘의 **순위**와 **primary/aux/reference** 역할을 산출하는 규칙입니다.  
튜닝(`12`)의 Validation 기준과 **분리**됩니다.

관련: [`operations_criteria.md`](operations_criteria.md) · [`model_tuning.md`](model_tuning.md) · [`metrics_guide.md`](metrics_guide.md) · `configs/default.yaml` → `ranking`

---

## 1. 목적·전제

| 전제 | 순위 정책 |
|------|-----------|
| 타겟 **불균형**이 지속 | **F1·ROC-AUC는 순위에 사용하지 않음** (표·레이더 참고만) |
| 점검 자원 제한 · **상위 1%**(주A) 위주 실무 | **상위1% 리프트** 중심, **PR-AUC**는 리프트가 근접할 때만 |
| 주·보는 **4×4**로 실제 점검 | 08 = **초안** · `ranking_confidence: low` 이면 **Test 4×4(B)** 로 최종 확정 |

---

## 2. 입력·출력

| 항목 | 내용 |
|------|------|
| **입력** | `{data_root}/algorithms/eval_summary.json` (07) |
| **대상 algo** | `run_config.algorithms` (`LSL_RUN_ID` Job 시 Run별) |
| **출력** | `algorithms/operations/model_ranking.json` + `ops.sqlite` `model_ranking` |
| **메타** | `ranking_confidence` (`high` / `low`), `ranking_note` |

---

## 3. 정렬 (순위 번호)

두 모델 `a`, `b` 비교:

### 3.1 1차 — 상위1% 리프트

\[
\Delta_{\text{lift}} = \frac{|L_a - L_b|}{\max(L_b,\,10^{-6})}
\]

- **`Δ_lift ≥ 3%`** (기본 `ranking.lift_tie_relative_pct`) → **리프트 높은 쪽** 승 (PR-AUC 무시)
- **`Δ_lift < 3%`** → **근접** → 3.2

### 3.2 2차 — PR-AUC (근접 시만)

- **`Δ_pr = |P_a - P_b| ≥ 0.005`** (기본 `ranking.pr_auc_tie_absolute`) → PR-AUC 높은 쪽 승
- **`Δ_pr < 0.005`** → **동순** (같은 `rank`, 다음 순위 건너뜀: 1, 1, 3 …)

### 3.3 미사용

- F1, ROC-AUC, 상위1% 양성비중·양성포착(순위용), 상위5% 지표

> 같은 Test에서 **리프트·양성비중·양성포착** 순위는 동일합니다. 순위 키는 **리프트** 하나만 사용합니다.

---

## 4. 역할 (primary / aux / reference / excluded)

정렬 후 **별도** 부여:

| 역할 | 규칙 |
|------|------|
| **primary** | 정렬 상위부터 **primary PR-AUC 가드** 통과한 **첫** algo |
| **aux** | primary 다음 algo (가드 없음) |
| **reference** | 정렬 **3번째** |
| **excluded** | 나머지 |

### 4.1 primary PR-AUC 가드 (풀 내 상대 하한)

후보 풀의 PR-AUC 최고값 `P_max`에 대해:

\[
P_{\text{candidate}} \ge P_{\max} - \max(0.01,\; 0.03 \times P_{\max})
\]

(`ranking.primary_pr_auc_abs_gap`, `primary_pr_auc_rel_gap_pct`)

- **의미:** 리프트 1위여도 PR-AUC가 풀 대비 **현저히 낮으면 주모델 불가**
- **전원 미통과:** 정렬 1위를 primary **초안**으로 두고 `ranking_confidence: low`

---

## 5. ranking_confidence

| 값 | 조건 (요약) | 조치 |
|----|-------------|------|
| **high** | 1·2위 리프트·PR-AUC로 구분 · 가드 정상 | 08 주·보 **초안** → 4×4 확인 후 `ops_queue` 반영 |
| **low** | 1·2위 **동순** · 가드로 primary 이동 · 전원 가드 실패 | **Test 4×4 (B) 실제 타겟**으로 주·보 **확정** |

### 5.1 4×4 확정 시 비교 (주·보 2조합)

애매할 때 **(1) A주·B보** vs **(2) B주·A보** 각각 4×4 **(B) 실제 타겟** 확인:

1. **주A×보A** (우선순위 1)
2. **주A×보B~보D** (우선 2~4)
3. **주A 행 합**

→ 더 나은 조합으로 `ops_queue.primary_algo` / `aux_algo` 설정 후 `10` 실행.

---

## 6. 설정 (`configs/default.yaml`)

```yaml
ranking:
  lift_tie_relative_pct: 3.0
  pr_auc_tie_absolute: 0.005
  primary_pr_auc_abs_gap: 0.01
  primary_pr_auc_rel_gap_pct: 3.0
```

---

## 7. 실행

```text
07_evaluate  →  eval_summary.json
08_update_ranking  →  model_ranking.json (+ confidence)
10_ops_queue  →  4×4 (주·보는 ranking 또는 ops_queue 설정)
```

웹 **모델 비교·평가**: Run DB ranking + `ranking_note` 표시.

---

## 8. 예시 (가상)

| | 리프트 | PR-AUC |
|--|--------|--------|
| RF v2 | **8.4** | 0.967 |
| CB v2 | 8.1 (Δ≈3.6%) | **0.969** |

- **정렬:** RF 1위 (리프트 Δ≥3%)
- **primary:** RF (가드 통과 시)
- CB v2가 PR-AUC만 앞서도 **리프트 차이가 크면** RF가 1위 유지

리프트 **Δ<3%** 이고 PR-AUC **Δ<0.005** → **동순 · low** → 4×4 확정.

---

## 9. 튜닝(12)과의 차이

| | 12 튜닝 | 08 순위 |
|--|---------|---------|
| 데이터 | Validation (Train 내부) | **Test** 1회 |
| 1순위 | top1 lift (+ 정밀도 **가드**) | top1 lift → PR-AUC |
| F1·ROC | 미사용 | 미사용 |

Test로 반복 튜닝하지 않습니다.
