param([string]$Profile='configs/bob_home.json',[string]$Machine='local/machine.json')
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskSnapshot=Join-Path $taskRoot 'local/preparation-profile.json'
New-Item -ItemType Directory -Force (Join-Path $taskRoot 'local') | Out-Null
Push-Location $taskRoot
try {
    $taskEngine=& python -c 'import sys; from pathlib import Path; from erl.config import resolve,encoded; p,e=resolve(sys.argv[1],sys.argv[2]); Path(sys.argv[3]).write_bytes(encoded(p)); print(e)' $Profile $Machine $taskSnapshot
    if($LASTEXITCODE -ne 0) {throw 'Profile resolution failed'}
    $taskPrevious=$env:ERL_PREPARATION_PROFILE
    $env:ERL_PREPARATION_PROFILE=$taskSnapshot
    try {
        & (Join-Path $taskEngine 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe') (Join-Path $taskRoot 'unreal/ResearchHarness/ResearchHarness.uproject') -run=pythonscript "-script=$(Join-Path $PSScriptRoot 'prepare_assets.py')" -NullRHI -Unattended -NoSplash -NoSound "-abslog=$(Join-Path $taskRoot 'local/asset-preparation.log')"
        if($LASTEXITCODE -ne 0) {throw "Asset preparation failed: $LASTEXITCODE"}
    } finally {$env:ERL_PREPARATION_PROFILE=$taskPrevious}
} finally {Pop-Location}
