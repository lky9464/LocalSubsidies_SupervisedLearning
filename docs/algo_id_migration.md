# 알고리즘 ID v1 마이그레이션 (로컬)

`algo_id`가 `{family}_v{N}` 형식(예: `random_forest_v1`)으로 통일되었습니다.  
**Cursor Agent는 data_root를 읽거나 변경하지 않습니다.** 아래는 사용자 로컬에서만 수행하세요.

## 1. 폴더 rename

`{data_root}/algorithms/` 아래:

| 구 폴더 | 신 폴더 |
|---------|---------|
| `catboost` | `catboost_v1` |
| `stacked_ensemble` | `stacked_ensemble_v1` |
| `easy_ensemble` | `easy_ensemble_v1` |
| `gradient_boosting` | `gradient_boosting_v1` |
| `random_forest` | `random_forest_v1` |

`operations/` 폴더는 그대로 둡니다.

PowerShell 예:

```powershell
cd $env:LSL_DATA_ROOT\algorithms   # 또는 configs\local.yaml 의 data_root
Rename-Item catboost catboost_v1
Rename-Item stacked_ensemble stacked_ensemble_v1
Rename-Item easy_ensemble easy_ensemble_v1
Rename-Item gradient_boosting gradient_boosting_v1
Rename-Item random_forest random_forest_v1
```

또는 프로젝트 루트에서 (권장):

```text
python scripts/migrate_algo_id_folders.py --dry-run
python scripts/migrate_algo_id_folders.py
```

또는 폴더를 비우고 `05_train.py`로 재학습해도 됩니다.

## 2. 운영 DB (선택)

`ops.sqlite`의 `model_ranking.algo`, `eval_metrics.algo` 등에 구 ID가 있으면:

```sql
UPDATE model_ranking SET algo = algo || '_v1'
WHERE algo IN ('catboost','stacked_ensemble','easy_ensemble','gradient_boosting','random_forest');

UPDATE eval_metrics SET algo = algo || '_v1'
WHERE algo IN ('catboost','stacked_ensemble','easy_ensemble','gradient_boosting','random_forest');
```

(이미 `_v1`인 행은 실행하지 마세요.)

## 3. run_config

`{data_root}/runs/*/run_config.yaml`의 `algorithms:` 목록을 `*_v1`로 맞추거나, 웹에서 「학습 옵션」을 다시 저장합니다.

## 4. CLI 스모크 (권장)

```text
python scripts/05_train.py --algo random_forest_v1 --algo catboost_v1
python scripts/06_feature_importance.py
python scripts/07_evaluate.py
python scripts/08_update_ranking.py
python scripts/10_ops_queue.py
```

주·보 설정: `configs/default.yaml` → `ops_queue.primary_algo: random_forest_v1`, `aux_algo: catboost_v1`
