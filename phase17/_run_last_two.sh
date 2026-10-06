#!/bin/bash
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
# Wait for the neutralisation run to release the GPU; two jobs on this card stall each other.
for i in $(seq 1 120); do
  n=$(powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | Where-Object { \$_.CommandLine -like '*phase17.neutralise*' } | Measure-Object | Select-Object -ExpandProperty Count" | tr -d "[:space:]")
  [ "${n:-0}" = "0" ] && break
  sleep 20
done
echo "=== GPU free; starting B14 ablation ==="
timeout 3000 python -u -m phase17.b14_ablate_deberta
echo "=== starting calibration 2 ==="
timeout 6000 python -u -m phase17.eval_calibration2
echo "ALL DONE"
