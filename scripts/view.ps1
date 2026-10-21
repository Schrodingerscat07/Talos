param([Parameter(Mandatory=$true)][string]$Run, [ValidateRange(1024,65535)][int]$Port=8870)
$ErrorActionPreference='Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskRunsRoot = [IO.Path]::GetFullPath((Join-Path $taskRoot 'runs'))
$taskRunRoot = (Resolve-Path -LiteralPath $Run).Path
if (!$taskRunRoot.StartsWith($taskRunsRoot + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Select a run inside this project runs directory' }
if (!(Test-Path -LiteralPath (Join-Path $taskRunRoot 'report.html') -PathType Leaf)) { throw 'Run has no visual report' }
$taskViewerPid=Join-Path $taskRoot 'local\viewer.pid'
if(Test-Path -LiteralPath $taskViewerPid) {
    $taskPriorId=[int](Get-Content -LiteralPath $taskViewerPid -Raw)
    $taskPrior=Get-Process -Id $taskPriorId -ErrorAction SilentlyContinue
    if($taskPrior) {
        $taskInfo=Get-CimInstance Win32_Process -Filter "ProcessId = $taskPriorId"
        if(!$taskInfo.CommandLine -or !$taskInfo.CommandLine.Contains('http.server') -or !$taskInfo.CommandLine.Contains($taskRunsRoot+[IO.Path]::DirectorySeparatorChar)) {throw 'Recorded viewer PID is not this project run server; refusing to stop it'}
        Stop-Process -Id $taskPriorId
        $taskPrior.WaitForExit(10000) | Out-Null
    }
}
$taskArguments=@('-m','http.server',[string]$Port,'--bind','127.0.0.1','--directory',"`"$taskRunRoot`"")
$taskPython = (Get-Command python -ErrorAction Stop).Source
$taskViewer = Start-Process -FilePath $taskPython -ArgumentList $taskArguments -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRoot 'local\viewer-out.log') -RedirectStandardError (Join-Path $taskRoot 'local\viewer-error.log')
[IO.File]::WriteAllText((Join-Path $taskRoot 'local\viewer.pid'),[string]$taskViewer.Id)
Write-Output "http://127.0.0.1:$Port/report.html"
Write-Output "Serving this run only, PID $($taskViewer.Id). The local session token is outside the served directory."
