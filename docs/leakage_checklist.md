# 데이터 누수(Leakage) 점검 체크리스트

학습 전에 사용할 수 없는 정보(사후 확정·타겟 파생)가 Feature에 들어가지 않았는지 확인합니다.

**권장 시점:** `03_preprocess.py` 완료 직후 → `04_leakage_audit.py` → (PASS 시) `05_train.py`

- [x] `TAET_YN` Feature 제외
- [x] `ISDP_RGSTR_YN`, `ISRC_DSCL_YN`, `PMBZ_CFMTN_YN` Feature 제외 (타겟 수정용)
- [x] 주민등록번호·사업자번호·명칭류·감사 컬럼 제외 (`configs/default.yaml`)
- [x] 사후성 후보(`RDP_TRGT_SUM_AMT`, `CUMU_NACK_*` 등) 기본 제외
- [x] `04_leakage_audit.py` 단변량 의심 피처 점검 (PASS, 2026-07-17)
- [ ] 점수 시점에 업무적으로 가용한 컬럼만 남겼는지 업무 담당자 확인
- [ ] Train에서만 전처리 fit, Test는 transform만 사용하는지 코드 확인
- [ ] 시계열 분할이 `CRTR_YM` 기준으로 미래가 Train에 섞이지 않는지 확인
- [ ] 그룹(사업·기관) 중복 점검 — `04` **그룹중복(group_overlap)** 시트 확인 (아래 §그룹 누수)

---

## 그룹 누수 (엔티티 중복)

한 행은 `CRTR_YM` × `PFM_BIZ_ID` × `INST_ID` 조합이므로, 같은 사업이 여러 달에 걸쳐 여러 행으로
존재합니다. `split.mode: random`은 **행 단위** 분할이라 같은 사업의 1·3월이 Train, 2·5월이 Test로
갈립니다. 라벨(`TAET_YN`)이 사업 상태에 가까워 여러 달 동안 유지되면, 모델은 판별이 아니라
**엔티티 암기**로 점수를 얻습니다. 식별자를 피처에서 제외해도 금액·기관·사업유형 조합이 사실상
지문 역할을 하므로 완전히 막히지 않습니다.

`04`가 산출하는 지표 (`outputs/reports/comparison/leakage_audit.xlsx` → 그룹중복 시트,
`leakage_audit_summary.json` → `group_overlap`):

| 지표 | 의미 |
|------|------|
| `pos_entity_seen_positive_ratio` | **핵심.** Test 양성 엔티티 중 Train에서 이미 양성으로 등장한 비율 |
| `pos_entity_seen_ratio` | Test 양성 엔티티 중 Train에 (양성 여부 무관) 등장한 비율 |
| `pos_row_seen_positive_ratio` | 같은 개념의 행 기준 가중값 |
| `label_stickiness` | 양성 엔티티의 (양성 행 / 전체 행) 평균 — 1에 가까우면 라벨이 상태값 |
| `expected_overlap_under_random` | 행 단위 random 분할이라면 기대되는 중복 비율 |
| `entity_overlap_ratio` | Test 엔티티 중 Train에도 등장하는 비율 |

판정 임계는 `configs/default.yaml` → `audit.group_warn_ratio`(0.5) ·
`audit.group_strong_warn_ratio`(0.8). 점검 대상 키는 `audit.group_keys` (기본 `PFM_BIZ_ID`,
`PFM_BIZ_ID+INST_ID`). 개별 ID는 출력하지 않고 건수·비율만 집계합니다.

**해석**

- 실측 비율이 `expected_overlap_under_random`과 비슷하면 원인은 행 단위 random 분할입니다.
- 비율이 높으면 현재 Test 지표는 "신규 사업 탐지"가 아니라 **"기존 사업 재탐지"** 성능입니다.
  상위 1% 리프트가 모든 알고리즘에서 천장(=100/K)에 붙어 편차가 사라지는 원인일 수 있습니다.
- 대조 방법: 학습 실행 UI **「사업단위 랜덤(무중복)」** (`split.mode=group_random`) · `split.mode=time`으로 기간 분리(반드시 `train_end` < `test_start`로 조정,
  기본값은 겹칩니다) 사업 단위 그룹 분할을 사용합니다. 그룹 분할 모드는 아직 미구현입니다.
- 시간 분할은 최근 월의 적발·확정이 진행 중이어서 라벨이 미성숙할 수 있으므로, 성능 하락만으로
  누수를 단정하지 말고 위 중복 비율과 함께 판단합니다.

이 점검은 `WARN`만 내고 파이프라인을 멈추지 않습니다 (하드 FAIL은 제외 컬럼 잔존만).
