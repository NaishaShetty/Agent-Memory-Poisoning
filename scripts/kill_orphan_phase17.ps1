# Kill orphaned phase17 python processes before starting a run.
#
# WHY THIS EXISTS (external review round 5, 2026-09-30): stopping a backgrounded shell
# command stops the WRAPPER, not the python child it spawned. Over one session that left four
# phase17 jobs running simultaneously -- eval_round5 (833 CPU-seconds), precompute_features
# (491s), attack_validity_audit and defense_cost -- all competing for a 6GB GPU. The symptom
# was a long run of ollama read timeouts and a server that appeared wedged, which was
# misdiagnosed several times as a concurrency setting, a missing retry and a stale connection
# pool. It was none of those: 4.4GB of 6GB was held by processes that were supposed to be dead,
# so a 5GB model could not load. Always run this between LLM jobs.
Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
  Where-Object { $_.CommandLine -like '*phase17*' } |
  ForEach-Object {
    Write-Output ("killing orphan {0}: {1}" -f $_.ProcessId, ($_.CommandLine -split 'phase17\.')[-1])
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
Start-Sleep -Seconds 5
