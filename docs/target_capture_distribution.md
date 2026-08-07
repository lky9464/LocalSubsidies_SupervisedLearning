# 타겟 포착 분포 — 확장 설계 (Phase 0)

**상태:** 초안 (구현 전 설계 고정)  
**작성:** 2026-08-07  
**관련:** [`operations_criteria.md`](operations_criteria.md) §5 · [`ranking_methodology.md`](ranking_methodology.md) · [`local_web_flow.md`](local_web_flow.md) · `scripts/10_ops_queue.py`

---

## 1. 목적

웹 **「타겟 포착 분포」** (`/ops/`) 화면과 `10_ops_queue` 산출물을 확장하여:

1. **PK(행)** 단위뿐 아니라 **엔티티(`PFM_BIZ_ID` + `INST_ID`)** 단위 포착 품질을 함께 본다.
2. **주/보** 외 **주/참·보/참** 모델 쌍별 4×4·점수 분포를 제공한다.
3. UI는 정보 과밀을 줄이고(접기·미리보기 제거), 선정된 **주·보·참 알고리즘 명칭**을 명시한다.

Test(평가) 전용 기능이다. **추론(11)·점검 우선순위표**는 본 설계 범위 밖(별도 요구 시 확장).

---

## 2. 범위

### 2.1 이번 작업에 포함

| 영역 | 내용 |
|------|------|
| `src/scoring/ops_queue.py` | 3케이스 pair queue · 엔티티 집계 · 동적 축 라벨 |
| `scripts/10_ops_queue.py` | PK/엔티티 파일·Excel·DB 적재 |
| `src/ops_db/` | 엔티티 행·케이스별 집계 스키마 |
| `GET /api/runs/{run_id}/ops-queue` | `roles` + `cases[]` 응답 |
| `web/app/ops/page.tsx` | UI 전면 (아래 §7) |
| 단위 테스트 | synthetic DataFrame (민감 데이터 미사용) |
| 문서 | 본 문서 확정 후 `operations_criteria.md` §5·`user_guide.md` 등 동기화 |

### 2.2 이번 작업에 **미포함** (후속 Phase 6)

| 영역 | 내용 |
|------|------|
| **대시보드** · **Run 이력** | 주/보 **엔티티** 2매트릭스(B-1/B-2) 추가 — **ops 1차 요구 완료 후 맨 마지막** |
| `11_score_inference.py` | `ops_queue_inference_entity` 등 추론용 엔티티 큐 |
| 주/참·보/참 | 대시보드·이력에는 **표시하지 않음** (ops 전용) |

### 2.3 확정된 UI·데이터 결정 (2026-08-07)

| # | 항목 | 결정 |
|---|------|------|
| 1 | reference 없을 때 | 케이스 **영역 유지**, 내용 **「해당 없음」** + `reason` (모델 비교 SHAP 참조 패널과 동일) |
| 2 | summary 테이블 | **케이스별 16행 × 3블록** (단일 테이블 + case 컬럼 아님) |
| 3 | 대시보드/이력 | 주/보 PK 2매트릭스 **유지** + 주/보 엔티티 2매트릭스 **추가** — **Phase 6, 맨 마지막** |

---

## 3. 용어·단위

| 용어 | 정의 |
|------|------|
| **PK(행) 단위** | `key_columns`: `CRTR_YM`, `PFM_BIZ_ID`, `INST_ID` — `ops_queue_test_pk` 1행 |
| **엔티티 단위** | `split.group_key`와 동일: `PFM_BIZ_ID` + `INST_ID` (`CRTR_YM` 제외) |
| **주(primary)** | 08 `role=primary` · `ops_queue.primary_algo` |
| **보(aux)** | 08 `role=aux` · `ops_queue.aux_algo` |
| **참(reference)** | 08 `role=reference` (순위 3위, 3모델 이상 Run) |
| **케이스(case)** | 두 모델 점수로 4×4를 만드는 **축 쌍** (아래 §4) |

Percentile A~D 구간은 기존과 동일: `ops_queue.a_top_pct=1`, `b_top_pct=5`, `c_top_pct=10` — **상호 배타**, 절대 점수 컷 없음.

---

## 4. 케이스 3종 · 축 라벨

| `case_id` | 화면 제목 | 행 축 (1차) | 열 축 (2차) | 점수 CSV |
|-----------|-----------|-------------|-------------|----------|
| `primary_aux` | 주 / 보 | 주A~주D | 보A~보D | primary + aux |
| `primary_reference` | 주 / 참 | 주A~주D | 참A~참D | primary + reference |
| `aux_reference` | 보 / 참 | 보A~보D | 참A~참D | aux + reference |

- **우선순위 1~16:** `행등급순위×4 + 열등급순위 + 1` (축 prefix만 바뀌고 공식 동일).
- **reference 미해결** (순위 3위 없음·점수 CSV 없음): `available: false`, `reason` 예 — `참조 모델(reference) 없음 — 08 순위 3위 또는 해당 algo Test 점수 필요`.

---

## 5. 매트릭스 4종 · 번호 규칙

케이스마다 **4개** 4×4. 화면·Excel·API 공통 라벨:

| 번호 | 단위 | 필터 | 설명 |
|------|------|------|------|
| **A-1** | PK | 없음 | 평가(Test) 데이터 **전체** |
| **A-2** | PK | `actual_label` 양성(1) | **실제 타겟 분포** |
| **B-1** | 엔티티 | 없음 | 평가 데이터 **전체** (엔티티 수) |
| **B-2** | 엔티티 | 엔티티 any-positive | **실제 타겟 분포** (엔티티 수) |

**포함 관계:** B-2 ⊆ B-1, A-2 ⊆ A-1 — PK와 동일하게 **양성 필터만** 적용하고 집계 단위만 다름.

**구버전 UI 라벨 `(A)` / `(B)`** → **`(A-1)` / `(A-2)` / `(B-1)` / `(B-2)`** 로 교체.

---

## 6. 집계·등급 규칙

### 6.1 PK 단위 (A-1, A-2) — 현행 유지·일반화

1. 07 Test 점수 CSV 2종을 `key_columns`로 join.
2. 각 모델 점수에 대해 **Test PK 전체 N** 기준 percentile → 행/열 등급.
3. `summarize_matrix(positive_only=False|True)` 로 4×4.

구현: `build_ops_queue` → **`build_ops_pair_queue`** (row_prefix, col_prefix 파라미터).

### 6.2 엔티티 단위 (B-1, B-2)

**입력:** 해당 케이스의 PK queue DataFrame.

**집계 키:** `[PFM_BIZ_ID, INST_ID]`

| 컬럼 | 규칙 |
|------|------|
| 행 모델 점수 | PK 점수 **평균** → **소수점 2자리 반올림** `round(x, 2)` |
| 열 모델 점수 | 동일 |
| 금액·명칭 등 `FIXED_SCORE_EXTRA_HEADERS` | PK 값 **평균** (명칭은 대표값 정책: **첫 PK 행** 또는 **mode** — 구현 시 `PFM_BIZ_NM`/`INST_NM`은 first, 금액은 mean으로 고정) |
| `예측라벨` / `실제라벨` | PK 중 **하나라도 양성(1)이면 1**, 아니면 0 |
| `CRTR_YM` | **열 제거** (엔티티 파일에 없음) |

**등급 부여 (중요):**

1. 엔티티 DataFrame 생성 후,
2. **엔티티 수 N_entity** 풀에서 각 모델 **반올림 평균 점수**로 percentile A~D (**PK 등급을 평균하지 않음**),
3. 조합·우선순위는 엔티티 등급으로 결정.

### 6.3 산출 파일 (로컬 전용 · GitHub 금지)

| 파일 | 단위 | 비고 |
|------|------|------|
| `algorithms/operations/ops_queue_test_pk.csv` | PK | 3케이스 · `case_id` 컬럼 |
| `algorithms/operations/ops_queue_test_pk.xlsx` | PK | 시트 확장 (케이스·A-1~A-2) |
| `algorithms/operations/ops_queue_test_entity.csv` | 엔티티 | **신규** — 3케이스 · `case_id` |
| `algorithms/operations/ops_queue_test_entity.xlsx` | 엔티티 | **신규** |

`ops.sqlite` 적재:

- 기존 `ops_queue_rows` — PK · `case_id='primary_aux'` (마이그레이션: 기존 run은 동일 case로 간주).
- **신규** `ops_queue_entity_rows` — 엔티티 · `case_id` ∈ {3종}.

---

## 7. 웹 UI — `/ops/` (Phase 4)

### 7.1 변경 요약

| 항목 | 변경 |
|------|------|
| **미리보기** 카드 | **삭제** |
| **조합별 건수·우선순위 (상세)** | `<details>` 기본 **접힘**, summary: `조합별 건수·우선순위 (상세)` |
| **알고리즘 명칭** | 카드 상단 배너: 주 / 보 / 참 `algo_id` + registry **label** |
| **4×4** | 케이스 3블록 × 매트릭스 4개 (2×2 그리드 권장) |
| **summary** | 케이스별 테이블 — 컬럼: 조합, 우선순위, **건수(PK 기준)**, **건수(엔티티 기준)** |

### 7.2 케이스 UI

- **탭** 또는 **접이식 섹션** (`주/보` · `주/참` · `보/참`).
- reference 없음: 차트 대신 「해당 없음」 + `reason` (빈 4×4 그리드 대신).

### 7.3 컴포넌트

- `DualMatrices` → **`CaptureMatrixPanel`** (4매트릭스, 동적 행/열 축 라벨).
- `MatrixTable` — 헤더 `주＼보` 하드코딩 제거, props로 `rowAxisLabel` / `colAxisLabel`.

---

## 8. API — `GET /api/runs/{run_id}/ops-queue`

### 8.1 응답 (목표)

```json
{
  "run_id": "...",
  "band_help": { "주A": "...", "보A": "...", "참A": "..." },
  "roles": {
    "primary": "random_forest_v3",
    "aux": "catboost_v3",
    "reference": "stacked_ensemble_v3",
    "primary_label": "RandomForest (v3)",
    "aux_label": "CatBoost (v3)",
    "reference_label": "Stacked Ensemble (v3)"
  },
  "cases": [
    {
      "id": "primary_aux",
      "title": "주 / 보",
      "row_axis": "주",
      "col_axis": "보",
      "available": true,
      "matrices": {
        "pk": {
          "all": { "index": [], "columns": [], "data": [] },
          "positive": { },
          "meta": { "total": 0, "positive": 0 }
        },
        "entity": {
          "all": { },
          "positive": { },
          "meta": { "total": 0, "positive": 0 }
        }
      },
      "summary": [
        {
          "cell": "주A×보A",
          "priority": 1,
          "count_pk": 10,
          "count_entity": 8
        }
      ],
      "positive_in_abc_pct": 42.5
    }
  ]
}
```

### 8.2 하위 호환 (Phase 4~5)

대시보드·이력이 Phase 6 전까지 기존 필드를 쓰므로:

| 필드 | 내용 |
|------|------|
| `test_matrices` | `cases[primary_aux].matrices.pk` 와 동일 (A-1/A-2, 구 `(A)`/`(B)` 메타) |
| `summary` | **deprecated** — ops 페이지는 `cases[].summary` 사용 |
| `preview` / `preview_options` | **제거 또는 deprecated** |

실제 경로: **`/api/runs/{run_id}/ops-queue`** (`local_web_flow.md`의 `/api/ops/*` 표기는 구식).

---

## 9. 구현 Phase (실행 순서)

```text
Phase 0  본 문서 확정 · operations_criteria §5 링크
Phase 1  src/scoring — pair queue, entity aggregate, tests
Phase 2  scripts/10 — 파일·Excel·DB
Phase 3  api/ops_db — repository, ops-queue API
Phase 4  web/app/ops — UI + web/out 빌드
Phase 5  문서·regression checklist
Phase 6  대시보드·Run 이력 — 주/보 PK + 엔티티 4매트릭스 (맨 마지막)
```

| Phase | 산출 | 완료 기준 |
|-------|------|-----------|
| **0** | 본 문서 | 요구·결정·범위 합의 |
| **1** | `aggregate_entity_queue`, `build_ops_pair_queue`, tests | 엔티티 any-positive·round·percentile 단위 테스트 통과 |
| **2** | `10_ops_queue.py`, `ops_queue_test_entity.*` | 로컬 10 재실행 시 CSV/XLSX·DB 적재 |
| **3** | `ops-queue` API | 3케이스·4매트릭스·summary JSON |
| **4** | `/ops/` UI | 접기·명칭·12매트릭스·미리보기 제거 |
| **5** | docs 동기화 | user_guide, pipeline, regression |
| **6** | dashboard, history | 주/보만 B-1/B-2 추가 |

---

## 10. `operations_criteria.md` 와의 관계

| 현행 §5 | 변경 후 |
|---------|---------|
| Test 4×4 = 주/보 PK 2개만 | ops **전용** 3케이스 × 4매트릭스 |
| reference = 4×4 비포함 | **주/참·보/참** 은 **포착 품질 참고용** (점검 우선순위표·primary/aux 선정 규칙은 **변경 없음**) |
| 산출 `ops_queue_test_pk.*` + `ops_queue_test_entity.*` | 3케이스 · PK·엔티티 |

§5.1~5.2 percentile·우선순위 공식은 **유지**. 표현·케이스·단위만 확장.

---

## 11. 테스트·검증 (민감 데이터 없이)

| 테스트 | 내용 |
|--------|------|
| `test_ops_pair_queue` | 3케이스 축 라벨·16조합 |
| `test_entity_aggregate` | 2 PK → 1 entity, any-positive, mean score |
| `test_entity_bands` | round(2) 후 percentile — PK band 평균과 결과 다름을 assert |
| `test_ops_api_shape` | mock DB → cases[] 스키마 |
| **수동** | 07·08·10 완료 Run — 사용자 로컬에서 3케이스·4매트릭스 eyeball |

---

## 12. 리스크·주의

1. **엔티티 N << PK N** — A~D 경계가 PK와 다르게 보이는 것이 **의도된 동작**.
2. **동일 엔티티 다월 PK** — group_random Test에서는 한쪽 split만이나, PK 집계 건수 > 엔티티 건수.
3. **2모델 Run** — 주/참·보/참 「해당 없음」 정상.
4. **DB 마이그레이션** — 기존 `ops.sqlite` run은 10 재실행으로 backfill.
5. **Agent** — `10_ops_queue.py` 실행·ops DB/raw 조회 금지 ([`AGENT_BOUNDARY.md`](AGENT_BOUNDARY.md)).

---

## 13. Phase 6 미리보기 (대시보드 · Run 이력)

ops Phase 4~5 **완료 후** 별도 PR:

| 화면 | 표시 |
|------|------|
| 대시보드 · Run 이력 | **주/보** only |
| PK | (A-1) 전체 + (A-2) 실제 타겟 — **현행 유지** |
| Entity | (B-1) 전체 + (B-2) 실제 타겟 — **신규** |
| 주/참·보/참 | **미표시** |

API: `dashboard` / `history`에 `test_matrices_entity` 블록 추가 또는 `test_matrices` 확장 — Phase 3 설계 시 extension point만 주석으로 남긴다.

---

## 14. 변경 이력

| 일자 | 내용 |
|------|------|
| 2026-08-07 | Phase 0 초안 — 요구사항·3건 결정·Phase 1~6 순서 |
