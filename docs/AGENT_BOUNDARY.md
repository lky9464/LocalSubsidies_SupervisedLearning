# Agent / 로컬 실행 경계

## 원칙

- **Cursor Agent**: 코드·설정 템플릿·문서·집계 리포트 구조만 작성/수정
- **사용자 로컬 Python**: raw 통합, 타겟 수정, 전처리, 누수점검, 학습, 평가, 점수, 리포트 생성 **실행**

## Agent가 하지 않는 것

1. `data_root` / `LocalSubsidies_ML_Data` 하위 파일 읽기·목록 상세 조회
   (`raw/`, `interim/`, `processed/`, `algorithms/**/scores/` 포함)
2. `scripts/01_*.py` ~ `12_*.py`, `RunWebNext.bat` / uvicorn 등 데이터 입출력·웹 실행
3. raw·행단위 점수·타겟 포착/점검 우선순위표·운영 DB(`ops.sqlite`)·PII 내용을 채팅에 출력

## 사용자가 로컬에서 실행하는 순서

```text
# CLI
python scripts/01_merge_raw.py
...
python scripts/07_evaluate.py
python scripts/08_update_ranking.py
python scripts/09_report.py
python scripts/10_ops_queue.py
python scripts/11_score_inference.py --algo random_forest_v1
# (선택) Validation 하이퍼 탐색 — Test 미사용
python scripts/12_tune_hyperparams.py
# 또는 웹 UI (127.0.0.1 only)
.\RunWebNext.bat
```

로컬 algo 폴더 rename: `docs/algo_id_migration.md`

상세: `docs/pipeline.md`, `docs/web_local.md`  
운영 DB: `{data_root}/ops/ops.sqlite` (런·순위·타겟 포착·점검 우선순위 조회 / **raw 미포함**)

## 프롬프트 허용/금지

| 허용 | 금지 |
|------|------|
| `{data_root}/raw` 등 **폴더 경로**만 언급 | 개별 CSV 파일명으로 “열어봐/샘플 보여줘” |
| 코드 수정 요청 | “학습 돌려줘”, 행 데이터 첨부 |

관련 Rule: `.cursor/rules/no-sensitive-data.mdc`
