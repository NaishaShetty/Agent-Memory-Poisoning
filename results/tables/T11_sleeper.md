# T11_sleeper: Sleeper / conditional poisoning: hold-out 8 anomaly thresholds corrected; SA-1 activation experiment

Sources: remediation/ho8_anomaly_devfit.json, remediation/sleeper_activation_eval.json

```json
{
  "ho8_anomaly": {
    "original_transductive:p90": {
      "anomaly": "145/160 (90.6%) | FPR 9/85 (10.6%)",
      "union2": "154/160 (96.2%) | FPR 16/85 (18.8%)",
      "B13": "118/160 (73.8%) | FPR 7/85 (8.2%)"
    },
    "original_transductive:p99": {
      "anomaly": "59/160 (36.9%) | FPR 1/85 (1.2%)",
      "union2": "141/160 (88.1%) | FPR 8/85 (9.4%)",
      "B13": "118/160 (73.8%) | FPR 7/85 (8.2%)"
    },
    "dev_fitted:p90": {
      "anomaly": "158/160 (98.8%) | FPR 142/171 (83.0%)",
      "union2": "160/160 (100.0%) | FPR 145/171 (84.8%)",
      "B13": "118/160 (73.8%) | FPR 15/171 (8.8%)"
    },
    "dev_fitted:p99": {
      "anomaly": "138/160 (86.2%) | FPR 99/171 (57.9%)",
      "union2": "160/160 (100.0%) | FPR 104/171 (60.8%)",
      "B13": "118/160 (73.8%) | FPR 15/171 (8.8%)"
    },
    "owner_adaptive_leakfree:p90": {
      "anomaly": "154/160 (96.2%) | FPR 12/85 (14.1%)",
      "union2": "158/160 (98.8%) | FPR 17/85 (20.0%)",
      "B13": "118/160 (73.8%) | FPR 7/85 (8.2%)"
    },
    "owner_adaptive_leakfree:p99": {
      "anomaly": "131/160 (81.9%) | FPR 4/85 (4.7%)",
      "union2": "153/160 (95.6%) | FPR 11/85 (12.9%)",
      "B13": "118/160 (73.8%) | FPR 7/85 (8.2%)"
    }
  },
  "ho8_dedicated_sleeper_guard": "0/160 attacks, 0/171 benign (eval_holdout8.json sleeper)",
  "SA1": "PENDING"
}
```
