#!/bin/bash
# Run every phase's suite, record pass/fail counts and failure names.
#
# REFUSES TO START while a phase17 GPU stage is running. The first version of this script did
# not, and running it alongside the powered adaptive test put two processes on a 6GB card: VRAM
# went to 5,716MB, the adaptive run made no progress for 13 minutes, and the moment pytest was
# killed it advanced immediately. That is the same contention failure this project's runbook
# exists to prevent, and a reminder in the runbook plainly was not enough.
cd "C:/Agent Memory Poisoning"
export PYTHONIOENCODING=utf-8

BUSY=$(powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | Where-Object { \$_.CommandLine -like '*phase17.*' -and \$_.CommandLine -notlike '*pytest*' } | Measure-Object | Select-Object -ExpandProperty Count" | tr -d ' 
')
if [ "${BUSY:-0}" != "0" ]; then
  echo "REFUSING: $BUSY phase17 process(es) still running. Several phase suites load models, and"
  echo "two GPU jobs on this card stall each other. Wait for them, or pass --force if you are"
  echo "certain nothing is using the GPU."
  [ "$1" != "--force" ] && exit 2
fi

FROM="${1:---all}"
OUT=phase17/data/_phase_audit.txt
PHASES="phase3 phase4 phase5 phase6 phase7 phase8 phase11 phase12 phase13 phase14 phase15 phase17 attribution tests"
SEEN=0
[ "$FROM" = "--all" ] || [ "$FROM" = "--force" ] && SEEN=1 && : > $OUT
for d in $PHASES; do
  [ -d "$d" ] || continue
  if [ "$SEEN" = "0" ]; then
    [ "$d" = "$FROM" ] && SEEN=1 || continue
  fi
  echo "### $d" >> $OUT
  timeout 3000 python -m pytest "$d" -q --no-header -p no:cacheprovider 2>&1 | tail -40 >> $OUT
  echo "" >> $OUT
done
echo "AUDIT COMPLETE" >> $OUT
