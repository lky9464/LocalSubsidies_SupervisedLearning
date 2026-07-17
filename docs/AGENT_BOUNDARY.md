# Agent / 로컬 실행 경계

## 원칙

- **Cursor Agent**: 코드·설정 템플릿·문서·집계 리포트 구조만 작성/수정
- **사용자 로컬 Python**: raw 통합, 타겟 수정, 전처리, 누수점검, 학습, 평가, 점수, 리포트 생성 **실행**

## Agent가 하지 않는 것

1. `data_root` / `LocalSubsidies_ML_Data` 하위 파일 읽기·목록 상세 조회
   (`raw/`, `interim/`, `processed/`, `algorithms/**/scores/` 포함)
2. `scripts/01_*.py` ~ `09_*.py` 등 데이터 입출력 스크립트 실행
3. raw·행단위 점수·PII 내용을 채팅에 출력

## 사용자가 로컬에서 실행하는 순서

```text
python scripts/01_merge_raw.py
python scripts/02_fix_target.py
python scripts/03_preprocess.py
python scripts/04_leakage_audit.py
python scripts/05_train.py
python scripts/06_feature_importance.py
python scripts/07_evaluate.py
python scripts/08_report.py
python scripts/09_score_inference.py      # 운영 추론
```

Test 점수 파일(로컬 전용): `{data_root}/algorithms/{algo}/scores/{algo}_test_scores.csv`,  
`{algo}_test_scores_top.xlsx` — 컬럼·순서 상세는 `docs/pipeline.md`.

## 프롬프트 허용/금지

| 허용 | 금지 |
|------|------|
| `{data_root}/raw` 등 **폴더 경로**만 언급 | 개별 CSV 파일명으로 “열어봐/샘플 보여줘” |
| 코드 수정 요청 | “학습 돌려줘”, 행 데이터 첨부 |

관련 Rule: `.cursor/rules/no-sensitive-data.mdc`
