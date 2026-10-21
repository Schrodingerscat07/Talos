param([string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskProject = Join-Path $taskRoot 'unreal\ResearchHarness\ResearchHarness.uproject'
New-Item -ItemType Directory -Path (Join-Path $taskRoot 'local') -Force | Out-Null
& (Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat') ResearchHarnessEditor Win64 Development "-Project=$taskProject" -WaitMutex -NoHotReloadFromIDE -NoUBA -MaxParallelActions=1 "-Log=$(Join-Path $taskRoot 'local\build.log')"
if ($LASTEXITCODE -ne 0) { throw "Unreal build failed with exit code $LASTEXITCODE" }
