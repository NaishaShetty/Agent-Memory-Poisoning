# T2_judge_sensitivity: Validity-audit judge sensitivity (fitted probe; C0 vs majority vote; mechanism-checked)

Sources: remediation/validity_judge_sensitivity.json

```json
{
  "rows": [
    {
      "group": "ALL",
      "n": 2628,
      "working_C0": "666/2628 (25.3%)",
      "working_vote": "713/2628 (27.1%)",
      "base_rate_C0": "675/2628 (25.7%)",
      "base_rate_vote": "1246/2628 (47.4%)",
      "paired": "+231/-278 (p=0.041)"
    },
    {
      "group": "own",
      "n": 804,
      "working_C0": "328/804 (40.8%)",
      "working_vote": "356/804 (44.3%)",
      "base_rate_C0": "215/804 (26.7%)",
      "base_rate_vote": "349/804 (43.4%)",
      "paired": "+82/-110 (p=0.051)"
    },
    {
      "group": "external",
      "n": 1824,
      "working_C0": "338/1824 (18.5%)",
      "working_vote": "357/1824 (19.6%)",
      "base_rate_C0": "460/1824 (25.2%)",
      "base_rate_vote": "897/1824 (49.2%)",
      "paired": "+149/-168 (p=0.31)"
    },
    {
      "group": "extdev_agentdojo",
      "n": 27,
      "working_C0": "5/27 (18.5%)",
      "working_vote": "12/27 (44.4%)",
      "base_rate_C0": "2/27 (7.4%)",
      "base_rate_vote": "7/27 (25.9%)",
      "paired": "+2/-9 (p=0.065)"
    },
    {
      "group": "extdev_agentpoison",
      "n": 6,
      "working_C0": "3/6 (50.0%)",
      "working_vote": "3/6 (50.0%)",
      "base_rate_C0": "0/6 (0.0%)",
      "base_rate_vote": "1/6 (16.7%)",
      "paired": "+1/-1 (p=1)"
    },
    {
      "group": "extdev_bipia",
      "n": 150,
      "working_C0": "38/150 (25.3%)",
      "working_vote": "24/150 (16.0%)",
      "base_rate_C0": "82/150 (54.7%)",
      "base_rate_vote": "119/150 (79.3%)",
      "paired": "+20/-6 (p=0.0094)"
    },
    {
      "group": "extdev_injecagent",
      "n": 62,
      "working_C0": "19/62 (30.6%)",
      "working_vote": "16/62 (25.8%)",
      "base_rate_C0": "23/62 (37.1%)",
      "base_rate_vote": "29/62 (46.8%)",
      "paired": "+7/-4 (p=0.55)"
    },
    {
      "group": "extdev_minja",
      "n": 21,
      "working_C0": "7/21 (33.3%)",
      "working_vote": "8/21 (38.1%)",
      "base_rate_C0": "4/21 (19.0%)",
      "base_rate_vote": "9/21 (42.9%)",
      "paired": "+2/-3 (p=1)"
    },
    {
      "group": "exttest_deepset",
      "n": 260,
      "working_C0": "54/260 (20.8%)",
      "working_vote": "53/260 (20.4%)",
      "base_rate_C0": "49/260 (18.8%)",
      "base_rate_vote": "150/260 (57.7%)",
      "paired": "+26/-25 (p=1)"
    },
    {
      "group": "exttest_gandalf",
      "n": 998,
      "working_C0": "148/998 (14.8%)",
      "working_vote": "185/998 (18.5%)",
      "base_rate_C0": "168/998 (16.8%)",
      "base_rate_vote": "371/998 (37.2%)",
      "paired": "+59/-96 (p=0.0037)"
    },
    {
      "group": "holdout2_mosscap",
      "n": 300,
      "working_C0": "64/300 (21.3%)",
      "working_vote": "56/300 (18.7%)",
      "base_rate_C0": "132/300 (44.0%)",
      "base_rate_vote": "211/300 (70.3%)",
      "paired": "+32/-24 (p=0.35)"
    },
    {
      "group": "own_corpus_extended",
      "n": 138,
      "working_C0": "48/138 (34.8%)",
      "working_vote": "55/138 (39.9%)",
      "base_rate_C0": "48/138 (34.8%)",
      "base_rate_vote": "75/138 (54.3%)",
      "paired": "+13/-20 (p=0.3)"
    },
    {
      "group": "own_evasion_47",
      "n": 47,
      "working_C0": "20/47 (42.6%)",
      "working_vote": "25/47 (53.2%)",
      "base_rate_C0": "10/47 (21.3%)",
      "base_rate_vote": "16/47 (34.0%)",
      "paired": "+2/-7 (p=0.18)"
    },
    {
      "group": "own_founding_regen",
      "n": 208,
      "working_C0": "110/208 (52.9%)",
      "working_vote": "139/208 (66.8%)",
      "base_rate_C0": "32/208 (15.4%)",
      "base_rate_vote": "61/208 (29.3%)",
      "paired": "+20/-49 (p=0.00064)"
    },
    {
      "group": "own_frozen75",
      "n": 34,
      "working_C0": "14/34 (41.2%)",
      "working_vote": "12/34 (35.3%)",
      "base_rate_C0": "2/34 (5.9%)",
      "base_rate_vote": "10/34 (29.4%)",
      "paired": "+4/-2 (p=0.69)"
    },
    {
      "group": "own_gemini_30",
      "n": 30,
      "working_C0": "9/30 (30.0%)",
      "working_vote": "11/30 (36.7%)",
      "base_rate_C0": "8/30 (26.7%)",
      "base_rate_vote": "10/30 (33.3%)",
      "paired": "+1/-3 (p=0.62)"
    },
    {
      "group": "own_novel_60",
      "n": 60,
      "working_C0": "17/60 (28.3%)",
      "working_vote": "18/60 (30.0%)",
      "base_rate_C0": "26/60 (43.3%)",
      "base_rate_vote": "29/60 (48.3%)",
      "paired": "+3/-4 (p=1)"
    },
    {
      "group": "own_novel_new120",
      "n": 120,
      "working_C0": "46/120 (38.3%)",
      "working_vote": "40/120 (33.3%)",
      "base_rate_C0": "32/120 (26.7%)",
      "base_rate_vote": "53/120 (44.2%)",
      "paired": "+16/-10 (p=0.33)"
    },
    {
      "group": "own_trackb_15",
      "n": 15,
      "working_C0": "11/15 (73.3%)",
      "working_vote": "13/15 (86.7%)",
      "base_rate_C0": "0/15 (0.0%)",
      "base_rate_vote": "2/15 (13.3%)",
      "paired": "+2/-4 (p=0.69)"
    },
    {
      "group": "own_trackb_regen_9",
      "n": 9,
      "working_C0": "1/9 (11.1%)",
      "working_vote": "4/9 (44.4%)",
      "base_rate_C0": "4/9 (44.4%)",
      "base_rate_vote": "5/9 (55.6%)",
      "paired": "+0/-3 (p=0.25)"
    },
    {
      "group": "own_worm_regen",
      "n": 29,
      "working_C0": "5/29 (17.2%)",
      "working_vote": "4/29 (13.8%)",
      "base_rate_C0": "11/29 (37.9%)",
      "base_rate_vote": "22/29 (75.9%)",
      "paired": "+4/-3 (p=1)"
    },
    {
      "group": "own_zh_native_30",
      "n": 30,
      "working_C0": "17/30 (56.7%)",
      "working_vote": "14/30 (46.7%)",
      "base_rate_C0": "8/30 (26.7%)",
      "base_rate_vote": "12/30 (40.0%)",
      "paired": "+3/-0 (p=0.25)"
    },
    {
      "group": "own_zh_translated_84",
      "n": 84,
      "working_C0": "30/84 (35.7%)",
      "working_vote": "21/84 (25.0%)",
      "base_rate_C0": "34/84 (40.5%)",
      "base_rate_vote": "54/84 (64.3%)",
      "paired": "+14/-5 (p=0.064)"
    }
  ],
  "caveats": [
    "The vote was selected on hold-out-5 compliance items, not on this audit's distribution.",
    "Working-attack status is a property of (agent, task/probe, judge), not of an attack in all settings.",
    "The published working set (union over probes, C0) is unchanged by this analysis."
  ]
}
```
