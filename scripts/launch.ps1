param(
    [string]$Profile='configs/bob_home.json',
    [string]$Machine='local/machine.json',
    [string]$Instance='default',
    [ValidateRange(1024,65535)][int]$Port=8765,
    [switch]$Headless,
    [switch]$Offscreen
)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
Push-Location $taskRoot
try {
    $taskArguments=@('-m','erl.manage','launch','--profile',$Profile,'--machine',$Machine,'--instance',$Instance,'--port',[string]$Port)
    if($Headless){$taskArguments+='--headless'}
    if($Offscreen){$taskArguments+='--offscreen'}
    & python @taskArguments
    if($LASTEXITCODE -ne 0){throw 'Instance launch failed'}
} finally {Pop-Location}
