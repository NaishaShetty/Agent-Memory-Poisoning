# T22_propagation_v2: WS-B 4-generation propagation and containment (HO4 held-out; dev diagnostic)

Sources: defence_v2/prop_eval.json, defence_v2/prop_dev.json

```json
{
  "carry_flagged": [
    "69/79",
    "36/79",
    "22/79",
    "18/79"
  ],
  "influence_undefended": [
    "21/79",
    "15/79",
    "14/79",
    "12/79"
  ],
  "withheld_carrying_flagged": {
    "A0": [
      "0/69",
      "0/36",
      "0/22",
      "0/18"
    ],
    "FG": [
      "67/69",
      "16/36",
      "6/22",
      "5/18"
    ],
    "FG-noinh": [
      "67/69",
      "0/36",
      "0/22",
      "0/18"
    ],
    "RCL": [
      "67/69",
      "32/36",
      "20/22",
      "15/18"
    ],
    "RECHECK": [
      "15/69",
      "6/36",
      "2/22",
      "2/18"
    ],
    "RCL|RECHECK": [
      "67/69",
      "32/36",
      "21/22",
      "15/18"
    ],
    "FG|RECHECK": [
      "67/69",
      "18/36",
      "8/22",
      "7/18"
    ]
  },
  "influence_remaining": {
    "A0": [
      "21/79",
      "15/79",
      "14/79",
      "12/79"
    ],
    "FG": [
      "1/79",
      "7/79",
      "7/79",
      "8/79"
    ],
    "FG-noinh": [
      "1/79",
      "15/79",
      "14/79",
      "12/79"
    ],
    "RCL": [
      "1/79",
      "1/79",
      "3/79",
      "4/79"
    ],
    "RECHECK": [
      "18/79",
      "14/79",
      "13/79",
      "11/79"
    ],
    "RCL|RECHECK": [
      "1/79",
      "1/79",
      "3/79",
      "4/79"
    ],
    "FG|RECHECK": [
      "1/79",
      "6/79",
      "7/79",
      "7/79"
    ]
  },
  "collateral_unflagged_benign": {
    "A0": [
      "0/40",
      "0/40",
      "0/40",
      "0/40"
    ],
    "FG": [
      "0/40",
      "0/40",
      "0/40",
      "0/40"
    ],
    "FG-noinh": [
      "0/40",
      "0/40",
      "0/40",
      "0/40"
    ],
    "RCL": [
      "0/40",
      "0/40",
      "0/40",
      "0/40"
    ],
    "RECHECK": [
      "2/40",
      "5/40",
      "6/40",
      "7/40"
    ],
    "RCL|RECHECK": [
      "2/40",
      "5/40",
      "6/40",
      "7/40"
    ],
    "FG|RECHECK": [
      "2/40",
      "5/40",
      "6/40",
      "7/40"
    ]
  },
  "collateral_flagged_benign": {
    "A0": [
      "0/31",
      "0/31",
      "0/31",
      "0/31"
    ],
    "FG": [
      "24/31",
      "8/31",
      "5/31",
      "4/31"
    ],
    "FG-noinh": [
      "24/31",
      "0/31",
      "0/31",
      "0/31"
    ],
    "RCL": [
      "24/31",
      "15/31",
      "14/31",
      "12/31"
    ],
    "RECHECK": [
      "7/31",
      "2/31",
      "6/31",
      "4/31"
    ],
    "RCL|RECHECK": [
      "25/31",
      "16/31",
      "17/31",
      "13/31"
    ],
    "FG|RECHECK": [
      "25/31",
      "8/31",
      "9/31",
      "6/31"
    ]
  },
  "recovery_after_release": [
    "0/31",
    "0/31",
    "0/31",
    "0/31"
  ],
  "paired": {
    "gen2_RCL_vs_FG": {
      "n": 36,
      "detected_a": 32,
      "detected_b": 16,
      "only_a": 17,
      "only_b": 1,
      "p_exact": 0.00014495849609375
    },
    "gen4_RCL_vs_FG": {
      "n": 18,
      "detected_a": 15,
      "detected_b": 5,
      "only_a": 10,
      "only_b": 0,
      "p_exact": 0.001953125
    },
    "gen4_influence_RCL_vs_A0": {
      "n": 79,
      "detected_a": 4,
      "detected_b": 12,
      "only_a": 0,
      "only_b": 8,
      "p_exact": 0.0078125
    }
  },
  "acceptance": {
    "C1_gen4_withheld>=60%_drop<=15": true,
    "C2_RCL>FG_gen2_gen4_holm": true,
    "holm_p": [
      0.0002899169921875,
      0.001953125
    ],
    "C3_unflagged_collateral<=5%": true,
    "C4_gen4_influence_RCL<A0": true,
    "accepted": true
  },
  "dev_withheld_carrying_flagged": {
    "A0": [
      "0/102",
      "0/71",
      "0/41",
      "0/31"
    ],
    "FG": [
      "76/102",
      "24/71",
      "11/41",
      "5/31"
    ],
    "FG-noinh": [
      "76/102",
      "0/71",
      "0/41",
      "0/31"
    ],
    "RCL": [
      "76/102",
      "43/71",
      "22/41",
      "10/31"
    ]
  }
}
```
