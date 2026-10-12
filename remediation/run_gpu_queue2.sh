#!/bin/bash
# Second queue (after restructuring both experiments into one-model-at-a-time phases).
cd "/c/Agent Memory Poisoning"
for m in propagation_2gen sleeper_activation_eval; do
  CUDA_VISIBLE_DEVICES=-1 PYTHONUTF8=1 python -u -m phase17.remediation.$m > remediation/logs/$m.log 2>&1
  echo "EXIT $?" >> remediation/logs/$m.log
done
