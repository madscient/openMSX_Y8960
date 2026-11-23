# 実機の Y8960 で、R#07 への書き込みと一回再生の終わりのあとの PCM_BSY（状態レジスタ C0h の b0）を読む。
#   powershell -ExecutionPolicy Bypass -File probe-y8960-pcmbsy.ps1 -Port COMn
# 音は使わない。書くのは 7FFFh（OPL2 の I/O を開く）と C0h・C1h だけ。System Controller（40h-4Fh）には触れない。
# SPON の後、ROM ヘッダが見えてから SRST を送り、もう一度ヘッダを待つ。v0.9.16 以前は SPON だけではリセットが届かない。
# 各段は、書いた直後の状態を読む。一回再生は EOS（b4）が立つまで読んで終わりを見る。short は 4 バイトを最速で鳴らし、
# MGA の 1 コマンド（約 1.4ms）の間に終わる。long は 1KB を 10h/11h = 1000h で鳴らし、0.6 秒ほど続く。
# Y8950 の形（START を書いた値のまま取り、一回再生の終わりでも残す）と、v0.9.16 までの Y8960 の形（RESET の後の START、
# 一回再生の終わりで 0）とで、81h・A1h・再生の終わりの 3 段の b0 が分かれる。
param(
    [string]$Port
)
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
    if (@(0xC0, 0xC1) -notcontains $addr) { throw ('Refused I/O port {0:X2}' -f $addr) }
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
function MemRd([int]$a) {
    $r = Cmd ('SMRD,{0:X4},1' -f $a)
    if ($r[-1] -ne 'OK') { throw "SMRD $a failed: $($r -join ' | ')" }
    $m = [regex]::Match($r[0], '^[0-9a-fA-F]{4} : ([0-9a-fA-F]{2})$')
    if (-not $m.Success) { throw "SMRD $a unexpected: $($r -join ' | ')" }
    return [Convert]::ToInt32($m.Groups[1].Value, 16)
}
# Y8960 は電源投入の後に BIOS を Flash から SerialSRAM へ写す。MGA は /WAIT を見ないので、4000h が "AB" で落ち着くまで待つ
function WaitRomHeader([string]$after) {
    $t = [System.Diagnostics.Stopwatch]::StartNew()
    $run = 0
    while ($run -lt 10) {
        $v = MemRd 0x4000
        if ($v -eq 0x41) { $run++ } else { $run = 0 }
        if ($t.ElapsedMilliseconds -gt 10000) { throw "4000h did not settle to 41h (last $v)" }
        Start-Sleep -Milliseconds 20
    }
    if ((MemRd 0x4001) -ne 0x42) { throw '4001h is not 42h' }
    Write-Host ('ROM header seen {0} ms after {1}' -f $t.ElapsedMilliseconds, $after)
}
function Show([string]$label, [int]$s) {
    Write-Host ('{0,-34} status {1:X2}  PCM_BSY {2}  EOS {3}' -f $label, $s, ($s -band 0x01), (($s -shr 4) -band 0x01))
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
    WaitRomHeader 'SPON'
    $r = Cmd 'SRST'
    if ($r[-1] -ne 'OK') { throw "SRST failed: $($r -join ' | ')" }
    WaitRomHeader 'SRST'
    $r = Cmd 'SMWR,7FFF,01,1'
    if ($r[-1] -ne 'OK') { throw "SMWR failed: $($r -join ' | ')" }

    # 割り込みのマスクは外し、EOS を消してから始める
    YWr 0x04 0x00
    YWr 0x04 0x80
    Show 'after SRST' (IoRd 0xC0)

    YWr 0x07 0x81
    Show '07h = 81h (START, RESET)' (IoRd 0xC0)
    YWr 0x07 0x00
    Show '07h = 00h' (IoRd 0xC0)
    YWr 0x07 0xA1
    Show '07h = A1h (START, MEMORY, RESET)' (IoRd 0xC0)
    YWr 0x07 0x01
    Show '07h = 01h (RESET)' (IoRd 0xC0)
    YWr 0x07 0x00

    # 長い方は、再生中に PCM_BSY が 1 と読めることの対照。SRAM の中身を鳴らすので 12h で音量を 0 にする
    YWr 0x12 0x00
    YWr 0x08 0x00
    foreach ($case in @(@{ Name = 'short'; Stop = 0x0000; Delta = 0xFFFF; Limit = 200 },
                        @{ Name = 'long'; Stop = 0x00FF; Delta = 0x1000; Limit = 3000 })) {
        YWr 0x09 0x00; YWr 0x0A 0x00
        YWr 0x0B ($case.Stop -band 0xFF); YWr 0x0C (($case.Stop -shr 8) -band 0xFF)
        YWr 0x10 ($case.Delta -band 0xFF); YWr 0x11 (($case.Delta -shr 8) -band 0xFF)
        YWr 0x04 0x80
        YWr 0x07 0xA0
        $t = [System.Diagnostics.Stopwatch]::StartNew()
        $seen = @()
        while ($true) {
            $s = IoRd 0xC0
            $seen += $s
            if (($s -band 0x10) -or $t.ElapsedMilliseconds -gt $case.Limit) { break }
        }
        $ms = $t.ElapsedMilliseconds
        Show ('{0}: 07h = A0h, first read' -f $case.Name) $seen[0]
        $busy = @($seen | Where-Object { $_ -band 0x01 }).Count
        Write-Host ('{0}: PCM_BSY 1 in {1} of {2} reads' -f $case.Name, $busy, $seen.Count)
        if ($seen[-1] -band 0x10) {
            Show ('{0}: EOS seen at {1} ms' -f $case.Name, $ms) $seen[-1]
        } else {
            Show ('{0}: EOS not seen in {1} ms' -f $case.Name, $ms) $seen[-1]
        }
        Start-Sleep -Milliseconds 50
        Show ('{0}: 50 ms later' -f $case.Name) (IoRd 0xC0)
        YWr 0x04 0x80
        Show ('{0}: 04h = 80h (clear the flags)' -f $case.Name) (IoRd 0xC0)
        YWr 0x07 0x00
        Show ('{0}: 07h = 00h' -f $case.Name) (IoRd 0xC0)
    }
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)"
}
finally {
    try { if ($powered) { $null = Cmd 'SPOFF'; Write-Host 'SPOFF' } } catch { Write-Host "ERROR in cleanup: $($_.Exception.Message)" }
    $sp.Close()
}
