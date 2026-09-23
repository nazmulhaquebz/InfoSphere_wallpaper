param([switch]$Quiet)

$ErrorActionPreference = "Stop"
$projectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$records = @(
    @{ File = Join-Path $projectPath "output\infosphere_engine.pid.json"; Names = @("python", "pythonw") },
    @{ File = Join-Path $projectPath "output\jarvis.pid.json"; Names = @("node") }
)
$stopped = 0

foreach ($recordInfo in $records) {
    if (-not (Test-Path -LiteralPath $recordInfo.File)) { continue }
    try {
        $record = Get-Content -LiteralPath $recordInfo.File -Raw -Encoding UTF8 | ConvertFrom-Json
        $process = Get-Process -Id ([int]$record.pid) -ErrorAction Stop
        if ($recordInfo.Names -notcontains $process.ProcessName.ToLowerInvariant()) {
            throw "PID $($record.pid) belongs to $($process.ProcessName), not InfoSphere"
        }
        $recordedStart = [DateTimeOffset]::Parse([string]$record.started_at).UtcDateTime
        $difference = [Math]::Abs(($process.StartTime.ToUniversalTime() - $recordedStart).TotalSeconds)
        if ($difference -gt 120) {
            throw "PID $($record.pid) start time does not match the ownership record"
        }
        Stop-Process -Id $process.Id -Force
        $stopped++
        if (-not $Quiet) { Write-Host "[OK] Stopped $($process.ProcessName) PID $($process.Id)" }
    } catch {
        if (-not $Quiet) { Write-Warning $_.Exception.Message }
    } finally {
        Remove-Item -LiteralPath $recordInfo.File -Force -ErrorAction SilentlyContinue
    }
}

if (-not $Quiet) {
    if ($stopped -eq 0) { Write-Host "[INFO] No owned InfoSphere processes were running." }
    else { Write-Host "[OK] Stopped $stopped owned process(es)." }
}

# Ensure all InfoSphere wallpaper and child processes are cleaned up
if (-not $Quiet) { Write-Host "[INFO] Cleaning up InfoSphere wallpaper and WebView processes..." }
Get-Process -Name "infosphere_wallpaper" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name = 'msedgewebview2.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*InfoSphere*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
if (-not $Quiet) { Write-Host "[OK] InfoSphere engine fully stopped." }
