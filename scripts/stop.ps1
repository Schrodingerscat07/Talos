param([string]$Instance='default')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
if(Test-Path -LiteralPath (Join-Path $taskRoot "local/instances/$Instance/state.json")) {
    Push-Location $taskRoot
    try { & python -m erl.manage stop --instance $Instance; if($LASTEXITCODE -ne 0){throw 'Instance stop failed'} } finally {Pop-Location}
    return
}
if($Instance -ne 'default'){throw 'Unknown instance'}
$taskPidPath = Join-Path $taskRoot 'local\unreal.pid'
if (!(Test-Path -LiteralPath $taskPidPath)) { throw 'No recorded harness process ID' }
$taskProcessId = [int](Get-Content -LiteralPath $taskPidPath -Raw)
$taskProcess = Get-Process -Id $taskProcessId -ErrorAction SilentlyContinue
if (!$taskProcess) { Write-Output 'Harness already stopped'; return }
if ($taskProcess.ProcessName -ne 'UnrealEditor') { throw 'Recorded PID no longer belongs to UnrealEditor; not stopping it' }
# Verify the command line as well as the executable to avoid stopping another editor after PID reuse.
$taskInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $taskProcessId"
$taskExpected = Join-Path $taskRoot 'unreal\ResearchHarness\ResearchHarness.uproject'
if (!$taskInfo.CommandLine.Contains($taskExpected)) { throw 'Process is not this research harness; not stopping it' }
$taskEngineDirectory = Split-Path -Parent $taskProcess.Path
$taskWorkers = Get-CimInstance Win32_Process -Filter "ParentProcessId = $taskProcessId AND Name = 'ShaderCompileWorker.exe'"
foreach ($taskWorker in $taskWorkers) {
    if ($taskWorker.ExecutablePath -and (Split-Path -Parent $taskWorker.ExecutablePath) -eq $taskEngineDirectory) {
        Stop-Process -Id $taskWorker.ProcessId -ErrorAction SilentlyContinue
    }
}
Stop-Process -Id $taskProcessId
$taskProcess.WaitForExit(10000) | Out-Null
Write-Output "Stopped research harness PID $taskProcessId"
