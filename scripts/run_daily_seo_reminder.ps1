# RoadLog daily SEO reminder (Windows Task Scheduler 09:00 KST)
# NOTE: Real auto-run is Grok durable scheduler (interval 1d, RoadLog daily SEO).
# This script only logs a backup reminder — it does NOT publish by itself.
$ErrorActionPreference = "Stop"
$root = "C:\Users\hysoo\projects\RoadLog"
if (-not (Test-Path "$root\docs\marketing\news_digest")) {
  $root = "C:\Users\hysoo\Projects\RoadLog"
}
$prompt = Join-Path $root "docs\marketing\news_digest\DAILY_SEO_PROMPT.md"
$logDir = Join-Path $root "docs\marketing\news_digest\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$log = Join-Path $logDir "trigger_$stamp.txt"
@"
RoadLog Daily SEO Trigger (backup log only)
time: $(Get-Date -Format o)
prompt: $prompt
primary: Grok durable scheduler — daily SEO (not this PS1)
fallback: Open Grok and say: 로드로그 오늘 뉴스 SEO 올려
"@ | Set-Content -Path $log -Encoding UTF8
Write-Host "Logged backup trigger -> $log"
Write-Host "Primary publisher: Grok scheduled task (1d)."
