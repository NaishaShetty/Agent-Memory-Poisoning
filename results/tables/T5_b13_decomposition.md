# T5_b13_decomposition: What B13 depends on: channel + content rules vs owner-conversation corroboration (post-hoc decomposition)

Sources: remediation/b13_decomposition.json

```json
{
  "rows": [
    {
      "holdout": "holdout4",
      "B12_stored": "3/157 (1.9%) | FPR 4/262 (1.5%)",
      "channel_plus_rules": "3/157 (1.9%) | FPR 4/262 (1.5%)",
      "corroboration_only": "76/157 (48.4%) | FPR 28/262 (10.7%)",
      "B13": "79/157 (50.3%) | FPR 31/262 (11.8%)",
      "user_channel_poisoning": "excluded 0/157; flagged-but-admitted 3/157 (1.9%)",
      "corroboration_increment": "+76 attacks (p=2.6e-23), +27 benign FP"
    },
    {
      "holdout": "holdout8",
      "B12_stored": "59/160 (36.9%) | FPR 7/171 (4.1%)",
      "channel_plus_rules": "59/160 (36.9%) | FPR 7/171 (4.1%)",
      "corroboration_only": "81/160 (50.6%) | FPR 8/171 (4.7%)",
      "B13": "118/160 (73.8%) | FPR 15/171 (8.8%)",
      "user_channel_poisoning": "excluded 0/160; flagged-but-admitted 59/160 (36.9%)",
      "corroboration_increment": "+59 attacks (p=3.5e-18), +8 benign FP"
    },
    {
      "holdout": "holdout7",
      "B12_stored": "48/129 (37.2%) | FPR 8/189 (4.2%)",
      "channel_plus_rules": "48/129 (37.2%) | FPR 8/189 (4.2%)",
      "corroboration_only": "23/129 (17.8%) | FPR 23/189 (12.2%)",
      "B13": "70/129 (54.3%) | FPR 29/189 (15.3%)",
      "user_channel_poisoning": "excluded 0/129; flagged-but-admitted 48/129 (37.2%)",
      "corroboration_increment": "+22 attacks (p=4.8e-07), +21 benign FP"
    }
  ]
}
```
