| Config | Novel-mechanism excluded | Dataset-arena benign excluded | Track-A success (n=300) | URS | Track-B forged (n=9) | Latency |
|---|---|---|---|---|---|---|
| B0 | not measured | not measured | 122/300 | N/A (baseline) | 3/9 | no defense (bound: ALWAYS_ALLOW) |
| B9-live | 0/60 | not measured | 122/300 | 1.000 | 0/9 | 1 admission pass, no LLM |
| B10 | not measured | not measured | 124/300 | 1.016 | 0/9 | 1 admission pass + untrained GNN/GLN blend, no LLM |
| B12 | 35/60 | 0/247 | 122/300 | 1.000 | 0/9 | 1 admission pass + ~0.4s/memory (2 judge calls) + embedding |
| B11 | 20/60 | 0/247 | 122/300 | 1.000 | 0/9 | 1 admission pass + ~0.2-0.4s/memory (1-2 judge calls) |