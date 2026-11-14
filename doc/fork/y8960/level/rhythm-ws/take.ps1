# One take of a FitomHwIF hwtest suite with a recording around it.
#
#   powershell -ExecutionPolicy Bypass -File take.ps1 -RunDir <mkhw run dir> -Suite suite_hw_<NAME>.json `
#       [-ResetSuite suite_reset_<NAME>.json] -OutDir <dir> -Recorder <path to ../tones-mga.ps1> [-Device 1]
#
# Order: reset suite (SPFM Light only: the board keeps the last state, the MGA powers the cartridge off),
# start the recorder, wait PreSeconds so the recording holds >= 1 s of silence before the test (the
# recorder takes ~2.2 s to start), run the suite, wait for the recorder. tones-mga.ps1 always writes
# tones-mga.wav, so give each take its own OutDir. The recorder runs with -NoNewWindow so no window opens.
param(
    [Parameter(Mandatory)] [string]$RunDir,
    [Parameter(Mandatory)] [string]$Suite,
    [string]$ResetSuite,
    [Parameter(Mandatory)] [string]$OutDir,
    [Parameter(Mandatory)] [string]$Recorder,
    [string]$Device = '1',
    [int]$Seconds = 38,
    [int]$PreSeconds = 4
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $OutDir | Out-Null
$exe = Join-Path $RunDir 'FMEngineTest.exe'

if ($ResetSuite) {
    Push-Location $RunDir
    try { & $exe $ResetSuite *> (Join-Path $OutDir 'reset.log') } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "reset suite exit $LASTEXITCODE" }
}

$recArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Recorder,
             '-Device', $Device, '-OutDir', $OutDir, '-RecordOnly', "$Seconds")
$rec = Start-Process powershell -ArgumentList $recArgs -NoNewWindow -PassThru `
    -RedirectStandardOutput (Join-Path $OutDir 'rec.out') -RedirectStandardError (Join-Path $OutDir 'rec.err')
Start-Sleep -Seconds $PreSeconds

$t0 = Get-Date
Push-Location $RunDir
try { & $exe $Suite *> (Join-Path $OutDir 'suite.log') } finally { Pop-Location }
$suiteExit = $LASTEXITCODE
$dt = ((Get-Date) - $t0).TotalSeconds

$rec.WaitForExit()
'suite exit {0}, {1:F1} s' -f $suiteExit, $dt
Get-Content (Join-Path $OutDir 'suite.log') -Tail 3
Get-Content (Join-Path $OutDir 'rec.out') -Tail 2
