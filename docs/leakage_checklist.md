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
