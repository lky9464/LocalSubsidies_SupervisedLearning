# 타겟여부(TAET_YN) 정의서

## 목적

지도학습 종속변수 `TAET_YN`의 의미를 고정하여 재현 가능하게 한다.

## 수정에 사용하는 컬럼 (Feature 제외)

| 컬럼명 | 한글명 |
|--------|--------|
| ISDP_RGSTR_YN | 부정수급자등록여부 |
| ISRC_DSCL_YN | 부정수급적발여부 |
| PMBZ_CFMTN_YN | 문제사업확정여부 |

위 3개 컬럼은 타겟 수정에만 쓰고 **모델 Feature에서 제외**한다.

## 확정 규칙 (2026-07-17)

`configs/default.yaml` → `label_rule.mode = any_of_y`

- 위 3개 중 **하나라도 `Y`** 이면 `TAET_YN = Y`
- 그렇지 않으면 `TAET_YN = N`

## 규칙 변경 시 체크리스트

- [x] 규칙 확정 및 `label_rule` 반영
- [ ] 양성 건수·비율 집계만 확인 (행 샘플 출력 금지) — `02_fix_target.py` 실행 후
- [ ] 학습·평가 파이프라인 재실행

## 조합 요약

| 조건 | TAET_YN |
|------|---------|
| ISDP_RGSTR_YN / ISRC_DSCL_YN / PMBZ_CFMTN_YN 중 1개 이상 Y | Y |
| 그 외 | N |
