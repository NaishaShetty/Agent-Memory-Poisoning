#!/bin/bash
# Run every phase's suite, record pass/fail counts and failure names.
#
# REFUSES TO START while a phase17 GPU stage is running. The first version did not, and
# running it beside the powered adaptive test put two processes on a 6GB card: VRAM reached
# 5,716MB, the adaptive run made no progress for 13 minutes, and it advanced the moment pytest
# was killed. A reminder in the runbook was not enough.
#
# The refusal check is ordered so it does not depend on the environment: the test override is
# read FIRST, and the process query is only attempted if powershell is actually available.
# An earlier version hardcoded an absolute Windows path and called powershell unconditionally,
# so under a stricter bash it failed both and reported CLEAR while a stage was running --
# exactly the wrong way for a safety check to fail.
cd "$(dirname "$0")/.." || exit 1
export PYTHONIOENCODING=utf-8

# --fake-busy N exercises the refusal branch directly in the guard test. An environment
# variable was tried first and did not propagate into the bash pytest launches, so the override
# is an ARGUMENT: arguments always reach the script.
FAKE=""
for a in "$@"; do
  case "$prev" in --fake-busy) FAKE="$a";; esac
  prev="$a"
done
if [ -n "$FAKE" ]; then
  BUSY="$FAKE"
elif command -v powershell >/dev/null 2>&1; then
  BUSY=$(powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | Where-Object { \$_.CommandLine -like '*phase17.*' -and \$_.CommandLine -notlike '*pytest*' } | Measure-Object | Select-Object -ExpandProperty Count" | tr -d "[:space:]")
else
  echo "WARNING: powershell unavailable, cannot check for running phase17 stages." >&2
  BUSY=0
fi

if [ "${BUSY:-0}" != "0" ]; then
  echo "REFUSING: $BUSY phase17 process(es) still running. Several phase suites load models, and"
  echo "two GPU jobs on this card stall each other. Wait for them, or pass --force if you are"
  echo "certain nothing is using the GPU."
  [ "$1" != "--force" ] && exit 2
fi
if [ "$1" = "--check" ]; then
  echo "CLEAR: no phase17 process detected; the audit would run."
  exit 0
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
