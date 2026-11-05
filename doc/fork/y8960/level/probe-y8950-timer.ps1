# Y8950 のタイマー 1・2 のフラグで、クロックと書き込みがチップに届いているかを見る。音は使わない。
#   powershell -ExecutionPolicy Bypass -File probe-y8950-timer.ps1 -Port COMn
# 書くのは C0h・C1h・7FFFh だけ（tones-mga.ps1 の MSXAUDIO が許す範囲）。SPON の後に SRST を挟む。
# 期待: SRST の後、7FFFh=01 で I/O が開いて 06（フラグ無し）。04h=03 の後、T1（1.28ms）が先に、T2（5.12ms）が後に
# 立つ（CE、EE）。立たなければ、Y8950 にクロックが来ていない。
param([string]$Port)
$ErrorActionPreference = 'Stop'

$dev = Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match "\($Port\)" }
if (-not $dev -or $dev.PNPDeviceID -notmatch 'VID_0B49&PID_26D2') { throw "$Port is not MGA" }

$sp = New-Object System.IO.Ports.SerialPort $Port, 115200, 'None', 8, 'One'
$sp.DtrEnable = $true
$sp.RtsEnable = $true
$sp.NewLine = "`n"
$sp.ReadTimeout = 3000
$sp.Encoding = [System.Text.Encoding]::ASCII
$sp.Open()
$sw = [System.Diagnostics.Stopwatch]::StartNew()

function Drain {
    $quiet = [System.Diagnostics.Stopwatch]::StartNew()
    while ($quiet.ElapsedMilliseconds -lt 300) {
        if ($sp.BytesToRead -gt 0) { $null = $sp.ReadExisting(); $quiet.Restart() }
        else { Start-Sleep -Milliseconds 10 }
    }
}
$terminators = '^(OK|FAIL|Bad Parameter|Unknow Error|Unknown command:.*)$'
function Cmd([string]$cmdText) {
    $sp.Write("$cmdText`r`n")
    $lines = @()
    while ($true) {
        $l = $sp.ReadLine().TrimEnd("`r")
        $lines += $l
        if ($l -match $terminators) { break }
    }
    return ,$lines
}
function Decode([int]$v) {
    $names = @('PCM', 'b1', 'b2', 'BUF', 'EOS', 'T2', 'T1', 'IRQ')
    $on = @()
    for ($b = 7; $b -ge 0; $b--) { if ($v -band (1 -shl $b)) { $on += $names[$b] } }
    return ($on -join ' ')
}
function IoRd([int]$addr, [string]$label) {
    $r = Cmd ('IORD,{0:X2}' -f $addr)
    $m = [regex]::Match($r[0], ': ([0-9a-fA-F]{2})$')
    if (-not $m.Success -or $r[-1] -ne 'OK') { throw "IORD failed: $($r -join ' | ')" }
    $v = [Convert]::ToInt32($m.Groups[1].Value, 16)
    Write-Host ('{0,8:F1} ms  {1,-28} {2:X2}  [{3}]' -f $sw.Elapsed.TotalMilliseconds, $label, $v, (Decode $v))
}
function IoWr([int]$addr, [int]$val) {
    $r = Cmd ('IOWR,{0:X2},{1:X2}' -f $addr, $val)
    if ($r[-1] -ne 'OK') { throw "IOWR failed: $($r -join ' | ')" }
}
function YWr([int]$reg, [int]$val) { IoWr 0xC0 $reg; IoWr 0xC1 $val }
function MemWr([int]$addr, [int]$val) {
    $r = Cmd ('SMWR,{0:X4},{1:X2},1' -f $addr, $val)
    if ($r[-1] -ne 'OK') { throw "SMWR failed: $($r -join ' | ')" }
}

$powered = $false
try {
    Drain
    $null = Cmd 'HVER'
    Drain
    $schk = Cmd 'SCHK'
    if ($schk[0] -ne '0010') { throw "No cartridge in slot 1: $($schk -join ' | ')" }
    $powered = $true
    $r = Cmd 'SPON'
    if ($r[-1] -ne 'OK') { throw "SPON failed: $($r -join ' | ')" }
    Start-Sleep -Milliseconds 500

    IoRd 0xC0 'a0 SPON 直後'
    $r = Cmd 'SRST'
    if ($r[-1] -ne 'OK') { throw "SRST failed: $($r -join ' | ')" }
    Start-Sleep -Milliseconds 100
    IoRd 0xC0 'a1 SRST 後、7FFFh の前'
    MemWr 0x7FFF 0x01
    IoRd 0xC0 'b1 7FFFh=01 の後'
    IoRd 0xC0 'b2'

    YWr 0x04 0x80
    IoRd 0xC0 'c1 04h=80（フラグのリセット）'
    IoRd 0xC0 'c2'
    IoRd 0xC0 'c3'

    YWr 0x04 0x00
    YWr 0x04 0x80
    IoRd 0xC0 'e1 04h=00 のあと 04h=80'
    IoRd 0xC0 'e2'
    IoRd 0xC0 'e3'

    YWr 0x02 0xF0
    YWr 0x03 0xF0
    YWr 0x04 0x03
    $t0 = $sw.Elapsed.TotalMilliseconds
    Write-Host ('{0,8:F1} ms  T1=F0（1.28ms）T2=F0（5.12ms）で 04h=03 を書いた' -f $t0)
    for ($i = 1; $i -le 8; $i++) { IoRd 0xC0 ('t{0} 開始から約 {1} 往復後' -f $i, $i) }

    YWr 0x04 0x00
    YWr 0x04 0x80
    IoRd 0xC0 'z1 止めてリセット'
    IoRd 0xC0 'z2'
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)"
}
finally {
    try { if ($powered) { $null = Cmd 'SPOFF'; Write-Host 'SPOFF' } } catch { Write-Host "ERROR in cleanup: $($_.Exception.Message)" }
    $sp.Close()
}
