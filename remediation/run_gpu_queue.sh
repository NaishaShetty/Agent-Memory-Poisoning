#!/bin/bash
# Sequential GPU queue (one Ollama job at a time; embeddings forced to CPU so Ollama keeps the GPU).
cd "/c/Agent Memory Poisoning"
while ! grep -q "^EXIT" remediation/logs/validity_judge_sensitivity.log 2>/dev/null; do sleep 60; done
for m in sleeper_activation_eval propagation_2gen; do
  CUDA_VISIBLE_DEVICES=-1 PYTHONUTF8=1 python -u -m phase17.remediation.$m > remediation/logs/$m.log 2>&1
  echo "EXIT $?" >> remediation/logs/$m.log
done
