# Plays tones.txt on a real Y8960 Cartridge through MGA (MSXPLAYer Game Cartridge Adapter)
# and records the cartridge's line output from a capture device on this PC. tones.tcl plays
# the same sequence in openMSX; tone-levels.py compares the two recordings.
#
#   powershell -ExecutionPolicy Bypass -File tones-mga.ps1 -ListDevices
#   powershell -ExecutionPolicy Bypass -File tones-mga.ps1 -Port COMn -Device <index, or part of
#       a capture device name> -OutDir <dir>
#   powershell -ExecutionPolicy Bypass -File tones-mga.ps1 -Device <...> -OutDir <dir> -RecordOnly 3
#       records 3 seconds without touching MGA, to check the capture side
#
# Writes <OutDir>/tones-mga.wav (16bit stereo 48kHz) and tones-mga.txt (the times of the marks).
#
# What is sent is limited before anything goes out: memory writes only to the sound registers
# (7FF0h-7FFFh, 9000h, 9800h-98FFh, 9900h-9904h) and I/O writes only to OPL2 and OPM (C0h, C1h,
# 7Eh, 7Fh). The System Controller (I/O 40h-4Fh) is never touched, so the Flash cannot change.
# Never sends break: a prototype MGA stopped responding after one.
param(
    [string]$Port,
    [string]$Device,
    [string]$OutDir = '.',
    [string]$Sequence = (Join-Path $PSScriptRoot 'tones.txt'),
    [switch]$ListDevices,
    [int]$RecordOnly = 0
)
$ErrorActionPreference = 'Stop'

# Add-Type's compiler turns "invalid search path in LIB" into an error. Drop the missing
# directories for this process only.
if ($env:LIB) { $env:LIB = (($env:LIB -split ';') | Where-Object { $_ -and (Test-Path -LiteralPath $_) }) -join ';' }

Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

// Records 16bit PCM from a waveIn device. The driver fills the buffers asynchronously, so the
// headers live in unmanaged memory and a thread polls WHDR_DONE and requeues them.
public class Y8960WaveIn
{
    [StructLayout(LayoutKind.Sequential)]
    struct WAVEFORMATEX { public ushort wFormatTag; public ushort nChannels; public uint nSamplesPerSec; public uint nAvgBytesPerSec; public ushort nBlockAlign; public ushort wBitsPerSample; public ushort cbSize; }
    [StructLayout(LayoutKind.Sequential)]
    struct WAVEHDR { public IntPtr lpData; public uint dwBufferLength; public uint dwBytesRecorded; public IntPtr dwUser; public uint dwFlags; public uint dwLoops; public IntPtr lpNext; public IntPtr reserved; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct WAVEINCAPS { public ushort wMid; public ushort wPid; public uint vDriverVersion; [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string szPname; public uint dwFormats; public ushort wChannels; public ushort wReserved1; }

    [DllImport("winmm.dll")] static extern uint waveInGetNumDevs();
    [DllImport("winmm.dll", EntryPoint = "waveInGetDevCapsW", CharSet = CharSet.Unicode)] static extern uint waveInGetDevCaps(UIntPtr id, ref WAVEINCAPS caps, uint size);
    [DllImport("winmm.dll")] static extern uint waveInOpen(out IntPtr h, uint id, ref WAVEFORMATEX fmt, IntPtr cb, IntPtr inst, uint flags);
    [DllImport("winmm.dll")] static extern uint waveInPrepareHeader(IntPtr h, IntPtr hdr, uint size);
    [DllImport("winmm.dll")] static extern uint waveInUnprepareHeader(IntPtr h, IntPtr hdr, uint size);
    [DllImport("winmm.dll")] static extern uint waveInAddBuffer(IntPtr h, IntPtr hdr, uint size);
    [DllImport("winmm.dll")] static extern uint waveInStart(IntPtr h);
    [DllImport("winmm.dll")] static extern uint waveInReset(IntPtr h);
    [DllImport("winmm.dll")] static extern uint waveInClose(IntPtr h);

    const int Count = 8;
    IntPtr handle;
    IntPtr[] hdrs = new IntPtr[Count];
    IntPtr[] bufs = new IntPtr[Count];
    bool[] queued = new bool[Count];
    int hdrSize, bufLen, flagsOff, recOff;
    readonly object sync = new object();
    bool stopping;
    Thread thread;
    MemoryStream data = new MemoryStream();
    public string Error;

    public static string[] Devices()
    {
        uint n = waveInGetNumDevs();
        string[] r = new string[n];
        for (uint i = 0; i < n; i++) {
            WAVEINCAPS c = new WAVEINCAPS();
            waveInGetDevCaps(new UIntPtr(i), ref c, (uint)Marshal.SizeOf(typeof(WAVEINCAPS)));
            r[i] = c.szPname;
        }
        return r;
    }

    public Y8960WaveIn(uint device, int rate, int channels)
    {
        WAVEFORMATEX f = new WAVEFORMATEX();
        f.wFormatTag = 1; f.nChannels = (ushort)channels; f.nSamplesPerSec = (uint)rate;
        f.wBitsPerSample = 16; f.nBlockAlign = (ushort)(channels * 2);
        f.nAvgBytesPerSec = (uint)(rate * channels * 2); f.cbSize = 0;
        Check(waveInOpen(out handle, device, ref f, IntPtr.Zero, IntPtr.Zero, 0), "open");
        hdrSize = Marshal.SizeOf(typeof(WAVEHDR));
        flagsOff = (int)Marshal.OffsetOf(typeof(WAVEHDR), "dwFlags");
        recOff = (int)Marshal.OffsetOf(typeof(WAVEHDR), "dwBytesRecorded");
        bufLen = rate / 10 * channels * 2;
        for (int i = 0; i < Count; i++) {
            bufs[i] = Marshal.AllocHGlobal(bufLen);
            hdrs[i] = Marshal.AllocHGlobal(hdrSize);
            Queue(i);
        }
    }

    static void Check(uint e, string what)
    {
        if (e != 0) throw new Exception("waveIn " + what + " failed: MMRESULT " + e);
    }

    void Queue(int i)
    {
        WAVEHDR w = new WAVEHDR();
        w.lpData = bufs[i]; w.dwBufferLength = (uint)bufLen;
        Marshal.StructureToPtr(w, hdrs[i], false);
        Check(waveInPrepareHeader(handle, hdrs[i], (uint)hdrSize), "prepare");
        Check(waveInAddBuffer(handle, hdrs[i], (uint)hdrSize), "add");
        queued[i] = true;
    }

    public void Start()
    {
        Check(waveInStart(handle), "start");
        thread = new Thread(Loop);
        thread.IsBackground = true;
        thread.Start();
    }

    void Loop()
    {
        int i = 0;
        try {
            while (queued[i]) {
                if ((Marshal.ReadInt32(hdrs[i], flagsOff) & 1) == 0) { Thread.Sleep(5); continue; }
                int n = Marshal.ReadInt32(hdrs[i], recOff);
                byte[] b = new byte[n];
                Marshal.Copy(bufs[i], b, 0, n);
                data.Write(b, 0, n);
                Check(waveInUnprepareHeader(handle, hdrs[i], (uint)hdrSize), "unprepare");
                queued[i] = false;
                // Under the lock so that a buffer is never queued after Stop() has reset the device.
                lock (sync) { if (!stopping) Queue(i); }
                i = (i + 1) % Count;
            }
        } catch (Exception e) {
            Error = e.Message;
        }
    }

    public byte[] Stop()
    {
        lock (sync) { stopping = true; waveInReset(handle); }
        if (thread != null) thread.Join(5000);
        waveInClose(handle);
        for (int i = 0; i < Count; i++) { Marshal.FreeHGlobal(hdrs[i]); Marshal.FreeHGlobal(bufs[i]); }
        return data.ToArray();
    }

    public static void WriteWav(string path, byte[] pcm, int rate, int channels)
    {
        using (FileStream fs = new FileStream(path, FileMode.Create))
        using (BinaryWriter w = new BinaryWriter(fs)) {
            w.Write(new char[] { 'R', 'I', 'F', 'F' }); w.Write(36 + pcm.Length);
            w.Write(new char[] { 'W', 'A', 'V', 'E', 'f', 'm', 't', ' ' }); w.Write(16);
            w.Write((short)1); w.Write((short)channels); w.Write(rate); w.Write(rate * channels * 2);
            w.Write((short)(channels * 2)); w.Write((short)16);
            w.Write(new char[] { 'd', 'a', 't', 'a' }); w.Write(pcm.Length); w.Write(pcm);
        }
    }
}
'@

if ($ListDevices) {
    $i = 0
    foreach ($n in [Y8960WaveIn]::Devices()) { '{0}: {1}' -f $i, $n; $i++ }
    exit 0
}
if (-not $Device -or (-not $Port -and $RecordOnly -le 0)) { throw 'Give -Port and -Device, or -ListDevices.' }

# --- Read and check the whole sequence before anything is sent ---
function Test-MemAddr([int]$a) {
    return (($a -ge 0x7FF0 -and $a -le 0x7FFF) -or $a -eq 0x9000 -or
            ($a -ge 0x9800 -and $a -le 0x98FF) -or ($a -ge 0x9900 -and $a -le 0x9904))
}
$ioPorts = @(0xC0, 0xC1, 0x7E, 0x7F)
$cmds = New-Object System.Collections.Generic.List[object]
foreach ($raw in Get-Content -LiteralPath $Sequence -Encoding UTF8) {
    $line = ($raw -split '#', 2)[0].Trim()
    if ($line -eq '') { continue }
    $f = $line -split '\s+'
    if ($f[0] -eq 'mem' -or $f[0] -eq 'io') {
        $a = [Convert]::ToInt32($f[1], 16); $v = [Convert]::ToInt32($f[2], 16)
        if ($v -lt 0 -or $v -gt 0xFF) { throw "Value out of range: $line" }
        if ($f[0] -eq 'mem' -and -not (Test-MemAddr $a)) { throw "Refused memory address: $line" }
        if ($f[0] -eq 'io' -and $ioPorts -notcontains $a) { throw "Refused I/O port: $line" }
        $cmds.Add(@($f[0], $a, $v))
    } elseif ($f[0] -eq 'mark') {
        $cmds.Add(@('mark', $f[1], 0))
    } elseif ($f[0] -eq 'wait') {
        $cmds.Add(@('wait', [int]$f[1], 0))
    } else {
        throw "Unknown command: $line"
    }
}

$names = [Y8960WaveIn]::Devices()
if ($Device -match '^\d+$') {
    $hits = @([int]$Device)
    if ($hits[0] -ge $names.Count) { throw "No capture device $Device. Use -ListDevices." }
} else {
    $hits = @(for ($i = 0; $i -lt $names.Count; $i++) { if ($names[$i] -like "*$Device*") { $i } })
}
if ($hits.Count -ne 1) { throw "Capture devices matching '$Device': $($hits.Count). Use -ListDevices." }
$devIndex = [uint32]$hits[0]

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$wavPath = Join-Path (Resolve-Path $OutDir) 'tones-mga.wav'
$logPath = Join-Path (Resolve-Path $OutDir) 'tones-mga.txt'
$log = New-Object System.Collections.Generic.List[string]
$sw = [System.Diagnostics.Stopwatch]::StartNew()
function Log([string]$s) { $line = ('{0,9:F1} ms  {1}' -f $sw.Elapsed.TotalMilliseconds, $s); $log.Add($line); Write-Host $line }
Log "capture device $devIndex : $($names[$devIndex])"

if ($RecordOnly -gt 0) {
    $rec = New-Object Y8960WaveIn ($devIndex, 48000, 2)
    $rec.Start()
    Start-Sleep -Seconds $RecordOnly
    $pcm = $rec.Stop()
    if ($rec.Error) { Log "ERROR in recording: $($rec.Error)" }
    [Y8960WaveIn]::WriteWav($wavPath, $pcm, 48000, 2)
    Log ('recorded {0:F2} s' -f ($pcm.Length / 4 / 48000))
    $log | Set-Content -LiteralPath $logPath -Encoding UTF8
    exit 0
}

$dev = Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match "\($Port\)" }
if (-not $dev -or $dev.PNPDeviceID -notmatch 'VID_0B49&PID_26D2') {
    throw "$Port is not MGA (0b49:26d2): $($dev.PNPDeviceID)"
}

$sp = New-Object System.IO.Ports.SerialPort $Port, 115200, 'None', 8, 'One'
$sp.DtrEnable = $true
$sp.RtsEnable = $true
$sp.NewLine = "`n"
$sp.ReadTimeout = 3000
$sp.Encoding = [System.Text.Encoding]::ASCII
$sp.Open()

function Drain {
    $n = 0
    $quiet = [System.Diagnostics.Stopwatch]::StartNew()
    while ($quiet.ElapsedMilliseconds -lt 300) {
        if ($sp.BytesToRead -gt 0) { $n += $sp.ReadExisting().Length; $quiet.Restart() }
        else { Start-Sleep -Milliseconds 10 }
    }
    return $n
}
$terminators = '^(OK|FAIL|Bad Parameter|Unknow Error|Unknown command:.*)$'
function Cmd([string]$c) {
    $sp.Write("$c`r`n")
    $lines = @()
    while ($true) {
        $l = $sp.ReadLine().TrimEnd("`r")
        $lines += $l
        if ($l -match $terminators) { break }
    }
    # A one-element array would collapse into a string without the comma.
    return ,$lines
}
function MemRd([int]$a) {
    $r = Cmd ('SMRD,{0:X4},1' -f $a)
    if ($r[-1] -ne 'OK') { throw "SMRD $a failed: $($r -join ' | ')" }
    $m = [regex]::Match($r[0], '^[0-9a-fA-F]{4} : ([0-9a-fA-F]{2})$')
    if (-not $m.Success) { throw "SMRD $a unexpected: $($r -join ' | ')" }
    return [Convert]::ToInt32($m.Groups[1].Value, 16)
}
function Send($c) {
    if ($c[0] -eq 'mem') { $r = Cmd ('SMWR,{0:X4},{1:X2},1' -f $c[1], $c[2]) }
    else { $r = Cmd ('IOWR,{0:X2},{1:X2}' -f $c[1], $c[2]) }
    if ($r[-1] -ne 'OK') { throw "$($c -join ' ') failed: $($r -join ' | ')" }
}

$powered = $false
$rec = $null
$pcm = $null
try {
    Log ('drained {0} bytes' -f (Drain))
    $null = Cmd 'HVER'
    Log ('drained {0} bytes after HVER' -f (Drain))
    $schk = Cmd 'SCHK'
    if ($schk[0] -ne '0010') { throw "No cartridge in slot 1: $($schk -join ' | ')" }

    $powered = $true
    $r = Cmd 'SPON'
    if ($r[-1] -ne 'OK') { throw "SPON failed: $($r -join ' | ')" }
    Log 'SPON'

    # The cartridge copies the BIOS from the Flash to the SerialSRAM after power on. MGA does not
    # see /WAIT, so wait until bank 0 at 4000h steadily shows the ROM header "AB".
    $t = [System.Diagnostics.Stopwatch]::StartNew()
    $run = 0
    while ($run -lt 10) {
        $v = MemRd 0x4000
        if ($v -eq 0x41) { $run++ } else { $run = 0 }
        if ($t.ElapsedMilliseconds -gt 10000) { throw "4000h did not settle to 41h (last $v)" }
        Start-Sleep -Milliseconds 20
    }
    if ((MemRd 0x4001) -ne 0x42) { throw '4001h is not 42h' }
    Log ('ROM header seen {0} ms after SPON' -f $t.ElapsedMilliseconds)
    Start-Sleep -Milliseconds 500

    $rec = New-Object Y8960WaveIn ($devIndex, 48000, 2)
    $rec.Start()
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    Log 'recording'
    Start-Sleep -Milliseconds 1000

    foreach ($c in $cmds) {
        switch ($c[0]) {
            'mark' { $log.Add(('{0:F3} {1}' -f $clock.Elapsed.TotalSeconds, $c[1])); Log "mark $($c[1])" }
            'wait' {
                $due = $clock.ElapsedMilliseconds + $c[1]
                while ($clock.ElapsedMilliseconds -lt $due) { Start-Sleep -Milliseconds 2 }
            }
            default { Send $c }
        }
    }
    Start-Sleep -Milliseconds 1000
    $pcm = $rec.Stop()
    $rec = $null
    Log ('recorded {0:F1} s' -f ($pcm.Length / 4 / 48000))
}
catch {
    Log "ERROR: $($_.Exception.Message)"
}
finally {
    if ($null -ne $rec) { try { $null = $rec.Stop() } catch { } }
    try { if ($powered) { $null = Cmd 'SPOFF'; Log 'SPOFF' } } catch { Log "ERROR in cleanup: $($_.Exception.Message)" }
    $sp.Close()
    if ($null -ne $pcm) { [Y8960WaveIn]::WriteWav($wavPath, $pcm, 48000, 2) }
    $log | Set-Content -LiteralPath $logPath -Encoding UTF8
}
if ($null -eq $pcm) { exit 1 }
