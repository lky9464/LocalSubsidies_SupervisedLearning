# tune batch

5종 `12_tune_hyperparams` 순차 실행.

```powershell
python tune_batch/run_tune_batch.py
# Run 덮어쓰기: --run-id {Run ID}
```

- 설정: `configs/tune.yaml` (`data_run_id`, `tune.algorithms`, `output_tag`)
- 로그: `tune_batch/logs/`
- 상태: `tune_batch/status.json`
- 산출물: `outputs/reports/tuning/{output_tag}/`
