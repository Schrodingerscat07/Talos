param([int]$Episodes = 150)
# Collect teacher demonstrations in four different two-box worlds (relaunches w1 for each).
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$plan = @(@{L='L1';Off=0}, @{L='L2';Off=$Episodes}, @{L='L3';Off=(2*$Episodes)}, @{L='L4';Off=(3*$Episodes)})
foreach ($p in $plan) {
    $layout = $p.L; $offset = $p.Off
    Write-Host "=== layout $layout (seed offset $offset) ==="
    .\scripts\stop.ps1 -Instance w1
    Start-Sleep -Seconds 20
    .\scripts\launch.ps1 -Profile "configs/two_$layout.json" -Instance w1 -Port 8781 -Offscreen
    python -m erl.cli wait --instance w1 --wait-seconds 900
    if ($LASTEXITCODE -ne 0) { throw "world $layout did not start" }
    python -m talos_brain.collect --instances w1 --task two --layout $layout --episodes $Episodes --seed-offset $offset --out "data/multi_$layout"
    if ($LASTEXITCODE -ne 0) { throw "collection failed in $layout" }
}
Write-Host "done: data/multi_L1 .. data/multi_L4"
