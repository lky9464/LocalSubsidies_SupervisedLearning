# 지방보조금 부정수급 위험도 — 지도학습

지방보조금 부정수급 **위험도 점수(0~1000)** 측정을 위한 지도학습 파이프라인입니다.

- 알고리즘: CatBoost, Stacked Ensemble, EasyEnsemble, Gradient Boosting, RandomForest
- 학습 데이터·모델·행단위 점수는 **프로젝트 폴더 밖** 로컬 경로에만 보관
- Cursor Agent는 코드/문서만 다루며, raw·학습 실행은 **사용자 로컬 Python**에서 수행

## 폴더 구조

| 위치 | 내용 |
|------|------|
| 이 repo | 소스, 설정 템플릿, 스키마, 집계 리포트 |
| `{data_root}/raw`, `interim`, `processed` | **공통** 입력·통합·전처리 (1벌) |
| `{data_root}/algorithms/{algo}/` | **알고리즘별** 모델·평가·행단위 점수 (5폴더) |
| `outputs/reports/comparison/` | 5종 비교 집계 리포트 (공통) |
| `outputs/reports/{algo}/` | 알고리즘별 집계 리포트 |

```text
LocalSubsidies_ML_Data/                 # 프로젝트 밖
├── raw/                                # 공통
├── interim/
├── processed/
└── algorithms/
    ├── catboost/
    │   ├── model.joblib
    │   ├── train_meta.json
    │   ├── eval_metrics.json
    │   └── scores/                     # {algo}_test_scores.csv 등 (로컬 전용)
    ├── stacked_ensemble/
    ├── easy_ensemble/
    ├── gradient_boosting/
    └── random_forest/

LocalSubsidies_SupervisedLearning/
└── outputs/reports/
    ├── comparison/                     # 5종 비교 Excel/PDF
    ├── catboost/
    ├── stacked_ensemble/
    ├── easy_ensemble/
    ├── gradient_boosting/
    └── random_forest/
```

## 사전 준비 (사용자)

1. 외부 데이터 루트 생성 후 raw CSV 배치  
   예: `...\LocalSubsidies_ML_Data\raw\`
   (LocalSubsidies_ML_Data 폴더는 본 프로젝트의 폴더와 같은위치에 생성 권장)
3. 설정 복사:
   ```text
   copy configs\local.yaml.example configs\local.yaml
   ```
   `data_root`를 본인 PC 경로로 수정
4. Python 가상환경 및 패키지:
   ```text
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   (`tqdm`이 있으면 진행바, 없으면 텍스트 진행률로 자동 대체됩니다.)

## 로컬 실행 순서

```text
python scripts/01_merge_raw.py
python scripts/02_fix_target.py
python scripts/03_preprocess.py
python scripts/04_leakage_audit.py      # 누수점검 (학습 전)
python scripts/05_train.py              # 모델 학습
python scripts/06_feature_importance.py # Feature TOP10 (evaluate 전에 필수)
python scripts/07_evaluate.py           # 평가·점수 (명칭/금액/TOP10피처값 포함)
python scripts/08_report.py             # 집계 리포트
# 운영 추론 (라벨 미지 데이터, 예: 2026)
python scripts/09_score_inference.py --algo random_forest
```

> 의심 피처가 있으면 Feature 제외 후 `03`부터 다시 실행하고, `04` PASS 후 `05`로 진행합니다.

### 학습(05) — 일괄 / 개별

```text
# 5종 일괄 (알고리즘 전환 + 모델 내부 진행 표시)
python scripts/05_train.py

# 특정 알고리즘만 (--algo 반복 가능)
python scripts/05_train.py --algo catboost
python scripts/05_train.py --algo random_forest --algo gradient_boosting

# 알고리즘별 전용 스크립트
python scripts/05_train_catboost.py
python scripts/05_train_stacked_ensemble.py
python scripts/05_train_easy_ensemble.py
python scripts/05_train_gradient_boosting.py
python scripts/05_train_random_forest.py
```

- 집계 결과: `outputs/reports/comparison/`, `outputs/reports/{algo}/`
- 행단위 점수: `{data_root}/algorithms/{algo}/scores/` (GitHub 금지)  
  - `{algo}_test_scores.csv`: 키·명칭/금액 → 위험도점수·양성확률·예측/실제라벨 → 기여도TOP10  
  - 같은 폴더에 `{algo}_test_scores_top.xlsx` (시트 `상위1%` / `상위5%`, 동일 컬럼 순서)  
  - `01`~`08` 순차 실행만으로 부가 컬럼이 채워진 점수 파일이 생성됨 (`06`→`07` 의존)

## 타겟(TAET_YN) 규칙

기본값은 3개 플래그 중 하나라도 Y이면 양성입니다.  
업무 규칙은 [`docs/label_definition.md`](docs/label_definition.md)와 `configs/default.yaml`의 `label_rule`을 수정하세요.

## 보안 / Agent 경계

- 상세: [`docs/AGENT_BOUNDARY.md`](docs/AGENT_BOUNDARY.md)
- Cursor Rule: `.cursor/rules/no-sensitive-data.mdc`
- `LocalSubsidies_ML_Data`를 Cursor 워크스페이스에 **추가하지 마세요**
- 프롬프트에 **폴더 경로**만 언급하는 것은 가능, raw 파일 내용 요청은 금지

## 지표 해설

[`docs/metrics_guide.md`](docs/metrics_guide.md)

## 파이프라인·점수 산출물

[`docs/pipeline.md`](docs/pipeline.md) — 스크립트 순서, 점수 파일명·컬럼 순서, GitHub 허용/금지

## 운영 기준 (모델 1~3위·점검 컷오프)

[`docs/operations_criteria.md`](docs/operations_criteria.md)

## GitHub

원격 저장소: https://github.com/lky9464/LocalSubsidies_SupervisedLearning  

커밋 대상: 코드·문서·집계 리포트·스키마  
커밋 금지: `configs/local.yaml`, raw/interim/processed, 모델 bin, 행단위 점수
