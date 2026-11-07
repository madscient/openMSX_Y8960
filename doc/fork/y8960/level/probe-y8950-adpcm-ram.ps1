# FS-CA1 の ADPCM の RAM に、数か所のアドレスへ 4 バイトずつ書き、読み戻して、RAM が働いているかを見る。
#   powershell -ExecutionPolicy Bypass -File probe-y8950-adpcm-ram.ps1 -Port COMn [-R08 0|2] [-Revert Mask,Order,Handshake,End]
# 音は使わない。書くのは C0h・C1h・7FFFh だけ。C0h（状態）と C1h は読む。SRST を SPON の後に挟む。
# -R08 は 08h に書く値（00h が 256Kbit の DRAM、02h が 64Kbit の DRAM）。
# 手順は『Y8950 MSX-AUDIO アプリケーション・マニュアル』§III-7 (iii) の RAM-WRITE と RAM/ROM-READ に従う。
# -Revert は、マニュアルとの違いを旧手順に戻す。どの違いが効いているかを 1 つずつ確かめるため。
#   Mask      04h を 00h でなく 78h にする（T1・T2・EOS・BUF_RDY をマスク）。Handshake と併せないと、BUF_RDY の待ちは毎回打ち切りになる
#   Order     07h のモードをアドレスの後に書き、その前に 07h=01h を書く
#   Handshake 1 バイトごとの BUF_RDY の待ちと 04h=80h をしない。0Fh は最初に 1 回だけ選ぶ
#   End       終わりを 07h=00h でなく 07h=01h にする
# 状態は読むたびに記録する（D3 が BUF_RDY、D4 が EOS）。同じ値の連続は「値*回数」と縮める。ready は各バイトの前の待ち、
# post は各バイトの直後で 04h=80h より前（04h=80h は EOS も消すので、EOS がいつ立つかは post でしか見えない）、after は 4 バイトの後。
# 期待: 書いた 4 バイトが、ダミーの 2 回の後の 4 回に返る。全部 00 なら、RAM が値を保持していない。
param(
    [string]$Port,
    [int]$R08 = 0,
    [string]$Revert = ''
)
$ErrorActionPreference = 'Stop'
# -File で渡すとカンマ区切りが配列にならないので、ここで分ける
$revList = @($Revert -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
foreach ($x in $revList) { if (@('Mask', 'Order', 'Handshake', 'End') -notcontains $x) { throw "Unknown -Revert: $x" } }

$dev = Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match "\($Port\)" }
if (-not $dev -or $dev.PNPDeviceID -notmatch 'VID_0B49&PID_26D2') { throw "$Port is not MGA" }

$revMask = $revList -contains 'Mask'
$revOrder = $revList -contains 'Order'
$revHandshake = $revList -contains 'Handshake'
$revEnd = $revList -contains 'End'
$maskValue = if ($revMask) { 0x78 } else { 0x00 }
$endValue = if ($revEnd) { 0x01 } else { 0x00 }
# メモリの 1 バイトはマニュアルの例から 125µs 以内に済むはずで、MGA の 1 コマンドは約 1.4ms。30 回で打ち切る
$PollMax = 30

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

function Compress([int[]]$xs) {
    $out = @()
    $i = 0
    while ($i -lt $xs.Count) {
        $j = $i
        while ($j + 1 -lt $xs.Count -and $xs[$j + 1] -eq $xs[$i]) { $j++ }
        $n = $j - $i + 1
        if ($n -gt 1) { $out += ('{0:X2}*{1}' -f $xs[$i], $n) } else { $out += ('{0:X2}' -f $xs[$i]) }
        $i = $j + 1
    }
    return ($out -join ' ')
}
# BUF_RDY が立つまで状態を読む。読んだ値を縮めた文字列で返し、打ち切りなら末尾に印を付ける
function WaitReady {
    $seen = @()
    for ($k = 0; $k -lt $PollMax; $k++) {
        $s = IoRd 0xC0
        $seen += $s
        if ($s -band 0x08) { return (Compress $seen) }
    }
    return ((Compress $seen) + ' TIMEOUT')
}

# 256Kbit の DRAM では、09h・0Ah はバイトのアドレスを 4 で割った値（マニュアル p.20）
function SetAddr([int]$byteAddr, [int]$nBytes) {
    $start = $byteAddr -shr 2
    $stop = ($byteAddr + $nBytes - 1) -shr 2
    YWr 0x09 ($start -band 0xFF)
    YWr 0x0A (($start -shr 8) -band 0xFF)
    YWr 0x0B ($stop -band 0xFF)
    YWr 0x0C (($stop -shr 8) -band 0xFF)
}
# 07h のモードとアドレスの順は、マニュアルでは 4 つのメモリの手順すべてでモードが先
function Setup([int]$byteAddr, [int]$mode) {
    if ($revOrder) {
        YWr 0x07 0x01
        YWr 0x08 $R08
        YWr 0x04 $maskValue
        SetAddr $byteAddr 4
        YWr 0x07 $mode
        YWr 0x04 0x80
    } else {
        YWr 0x04 $maskValue
        YWr 0x04 0x80
        YWr 0x07 $mode
        YWr 0x08 $R08
        SetAddr $byteAddr 4
    }
}

$tests = @(0x00000, 0x07FFC, 0x08000, 0x10000, 0x20000, 0x3FFFC)
if ($R08 -band 0x02) {
    # 64Kbit の DRAM では 09h の D3 と 0Ah の D4 が 0 でなければならない（マニュアル p.20）
    $tests = @($tests | Where-Object { (($_ -shr 2) -band 0x1008) -eq 0 })
}
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
    Write-Host ('08h = {0:X2}, 04h = {1:X2}, end 07h = {2:X2}, revert: {3}' -f $R08, $maskValue, $endValue, ($(if ($revList.Count) { $revList -join ',' } else { 'none' })))
    Write-Host ('status after SRST: {0:X2}' -f (IoRd 0xC0))

    $t = 0
    foreach ($a in $tests) {
        $t++
        $vals = 1..4 | ForEach-Object { (0x10 * $t) + $_ }
        Setup $a 0x60
        $st = @()
        $post = @()
        if ($revHandshake) {
            IoWr 0xC0 0x0F
            foreach ($v in $vals) { IoWr 0xC1 $v; $post += IoRd 0xC0 }
        } else {
            foreach ($v in $vals) {
                $st += (WaitReady)
                IoWr 0xC0 0x0F
                IoWr 0xC1 $v
                $post += IoRd 0xC0
                YWr 0x04 0x80
            }
        }
        $after = IoRd 0xC0
        YWr 0x07 $endValue
        $w = ($vals | ForEach-Object { '{0:X2}' -f $_ }) -join ' '
        Write-Host ('W {0:X5}: {1} | ready {2} | post {3} | after {4:X2}' -f $a, $w, ($(if ($st.Count) { $st -join ' / ' } else { '-' })),
            (($post | ForEach-Object { '{0:X2}' -f $_ }) -join ' '), $after)
    }
    $t = 0
    foreach ($a in $tests) {
        $t++
        $want = (1..4 | ForEach-Object { '{0:X2}' -f ((0x10 * $t) + $_) }) -join ' '
        Setup $a 0x20
        IoWr 0xC0 0x0F
        $dummy = @((IoRd 0xC1), (IoRd 0xC1))
        $got = @()
        $st = @()
        $post = @()
        for ($i = 0; $i -lt 4; $i++) {
            if ($revHandshake) {
                $got += IoRd 0xC1
                $post += IoRd 0xC0
            } else {
                $st += (WaitReady)
                IoWr 0xC0 0x0F
                $got += IoRd 0xC1
                $post += IoRd 0xC0
                YWr 0x04 0x80
            }
        }
        $after = IoRd 0xC0
        YWr 0x07 $endValue
        Write-Host ('R {0:X5}: want {1} | dummy {2} | read {3} | ready {4} | post {5} | after {6:X2}' -f $a, $want,
            (($dummy | ForEach-Object { '{0:X2}' -f $_ }) -join ' '), (($got | ForEach-Object { '{0:X2}' -f $_ }) -join ' '),
            ($(if ($st.Count) { $st -join ' / ' } else { '-' })), (($post | ForEach-Object { '{0:X2}' -f $_ }) -join ' '), $after)
    }
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)"
}
finally {
    try { if ($powered) { $null = Cmd 'SPOFF'; Write-Host 'SPOFF' } } catch { Write-Host "ERROR in cleanup: $($_.Exception.Message)" }
    $sp.Close()
}
