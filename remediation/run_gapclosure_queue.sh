#!/bin/bash
# Gap-closure GPU queue (one Ollama workload at a time; Python embeddings on CPU so Ollama keeps the GPU).
cd "/c/Agent Memory Poisoning"
L=remediation/logs
for exp in ho4 sa1; do
  CUDA_VISIBLE_DEVICES=-1 PYTHONUTF8=1 /c/mem0venv/Scripts/python.exe -u -m phase17.mem0_infer.run_pipeline $exp > $L/mem0_stage1_$exp.log 2>&1
  echo "EXIT $?" >> $L/mem0_stage1_$exp.log
done
for m in sa2_eval probe_robustness mem0_pipeline_eval; do
  CUDA_VISIBLE_DEVICES=-1 PYTHONUTF8=1 python -u -m phase17.remediation.$m > $L/$m.log 2>&1
  echo "EXIT $?" >> $L/$m.log
done
