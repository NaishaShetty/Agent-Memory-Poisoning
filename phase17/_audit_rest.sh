#!/bin/bash
cd "C:/Agent Memory Poisoning"
export PYTHONIOENCODING=utf-8
OUT=phase17/data/_phase_audit2.txt
: > $OUT
for d in phase6 phase8 phase11 phase12 phase13 phase14 phase15 phase17 attribution tests; do
  [ -d "$d" ] || continue
  echo "### $d" >> $OUT
  timeout 3000 python -m pytest "$d" -q --no-header -p no:cacheprovider 2>&1 | grep -E "passed|failed|error|FAILED|ERROR" | tail -12 >> $OUT
done
echo "AUDIT2 COMPLETE" >> $OUT
