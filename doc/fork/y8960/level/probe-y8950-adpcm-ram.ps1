# FS-CA1 の ADPCM の RAM に、数か所のアドレスへ 4 バイトずつ書き、読み戻して、RAM が働いているか、大きさがどれだけかを見る。
#   powershell -ExecutionPolicy Bypass -File probe-y8950-adpcm-ram.ps1 -Port COMn [-R08 0|2]
# 音は使わない。書くのは C0h・C1h・7FFFh だけ。C1h は読むだけ。SRST を SPON の後に挟む。-R08 は 08h に書く値
# （00h が 256KB、02h が 64KB の扱い）。
# 読み戻しは、07h=20h の後の最初の 2 回がダミー（直前に書いたか読んだデータが返る）で、3 回目から RAM の中身。
# 期待: 書いた 4 バイトが 3〜6 回目に返る。全部 00 なら、RAM が値を保持していない。
param([string]$Port, [int]$R08 = 0)
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
function IoWr([int]$addr, [int]$val) {
    $r = Cmd ('IOWR,{0:X2},{1:X2}' -f $addr, $val)
    if ($r[-1] -ne 'OK') { throw "IOWR failed: $($r -join ' | ')" }
}
function IoRd([int]$addr) {
    $r = Cmd ('IORD,{0:X2}' -f $addr)
    $m = [regex]::Match($r[0], ': ([0-9a-fA-F]{2})$')
    if (-not $m.Success -or $r[-1] -ne 'OK') { throw "IORD failed: $($r -join ' | ')" }
    return [Convert]::ToInt32($m.Groups[1].Value, 16)
}
function YWr([int]$reg, [int]$val) { IoWr 0xC0 $reg; IoWr 0xC1 $val }
function MemWr([int]$addr, [int]$val) {
    $r = Cmd ('SMWR,{0:X4},{1:X2},1' -f $addr, $val)
    if ($r[-1] -ne 'OK') { throw "SMWR failed: $($r -join ' | ')" }
}

# 開始アドレスのレジスタ（09h・0Ah）は、ニブル単位の値の 3 ビット目から（9h は << 3、0Ah は << 11）。バイトのアドレスは、その半分
function SetAddr([int]$byteAddr, [int]$nBytes) {
    $nib = $byteAddr * 2
    $stop = $nib + 2 * $nBytes - 1
    YWr 0x09 (($nib -shr 3) -band 0xFF)
    YWr 0x0A (($nib -shr 11) -band 0xFF)
    YWr 0x0B (($stop -shr 3) -band 0xFF)
    YWr 0x0C (($stop -shr 11) -band 0xFF)
}

$tests = @(0x00000, 0x07FFC, 0x08000, 0x10000, 0x20000, 0x3FFFC)
$powered = $false
try {
    Drain
    $null = Cmd 'HVER'
    Drain
    $schk = Cmd 'SCHK'
    if ($schk[0] -ne '0010') { throw 'No cartridge in slot 1' }
    $powered = $true
    $r = Cmd 'SPON'
    if ($r[-1] -ne 'OK') { throw "SPON failed: $($r -join ' | ')" }
    Start-Sleep -Milliseconds 500
    $r = Cmd 'SRST'
    if ($r[-1] -ne 'OK') { throw "SRST failed: $($r -join ' | ')" }
    Start-Sleep -Milliseconds 100
    MemWr 0x7FFF 0x01
    Write-Host ('08h = {0:X2}' -f $R08)

    # 書く
    $t = 0
    foreach ($a in $tests) {
        $t++
        YWr 0x07 0x01
        YWr 0x08 $R08
        YWr 0x04 0x78
        SetAddr $a 4
        YWr 0x07 0x60
        YWr 0x04 0x80
        IoWr 0xC0 0x0F
        for ($i = 1; $i -le 4; $i++) { IoWr 0xC1 ((0x10 * $t) + $i) }
        YWr 0x07 0x01
    }
    # 読む
    $t = 0
    foreach ($a in $tests) {
        $t++
        YWr 0x07 0x01
        YWr 0x08 $R08
        YWr 0x04 0x78
        SetAddr $a 4
        YWr 0x07 0x20
        IoWr 0xC0 0x0F
        $got = @()
        for ($i = 0; $i -lt 6; $i++) { $got += ('{0:X2}' -f (IoRd 0xC1)) }
        $want = (1..4 | ForEach-Object { '{0:X2}' -f ((0x10 * $t) + $_) }) -join ' '
        Write-Host ('byte addr {0:X5}: wrote {1} | read {2}' -f $a, $want, ($got -join ' '))
        YWr 0x07 0x01
    }
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)"
}
finally {
    try { if ($powered) { $null = Cmd 'SPOFF'; Write-Host 'SPOFF' } } catch { Write-Host "ERROR in cleanup: $($_.Exception.Message)" }
    $sp.Close()
}
