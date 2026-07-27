# RoadLog daily SEO reminder (Windows Task Scheduler 09:00 KST)
# Opens a note + optional Grok/terminal reminder. Full agent run is via Grok scheduler.
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path "$PSScriptRoot\..\docs\marketing\news_digest")) {
  $root = "C:\Users\hysoo\Projects\RoadLog"
}
$prompt = Join-Path $root "docs\marketing\news_digest\DAILY_SEO_PROMPT.md"
$logDir = Join-Path $root "docs\marketing\news_digest\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$log = Join-Path $logDir "trigger_$stamp.txt"
@"
RoadLog Daily SEO Trigger
time: $(Get-Date -Format o)
prompt: $prompt
action: Run Grok with DAILY_SEO_PROMPT.md (or say: 로드로그 오늘 뉴스 SEO 올려)
"@ | Set-Content -Path $log -Encoding UTF8
Write-Host "Logged trigger -> $log"
Write-Host "Open Grok and run daily SEO prompt for RoadLog."
