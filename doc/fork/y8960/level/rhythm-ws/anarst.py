"""Judges whether BDh=20h makes the Y8960 sound, per take of tones-mga.ps1 with rstnoise.txt.

  powershell -File ../tones-mga.ps1 -Port COMn -Device <...> -OutDir <take dir> -Sequence rstnoise.txt [-SlotReset]
  py anarst.py <take dir> [<take dir> ...]
  py anarst.py --synth <dir> loud|quiet|mid|early   writes a synthetic take for checking the judge

Windows (from the marks in tones-mga.txt): quiet = 1.0-0.2 s before the BDh=20h mark,
noise = 0.5-1.5 s after it, after = 0.3-0.8 s after BDh=00h.
Judgement, fixed before recording: noise - quiet >= 30 dB "sounds", <= 6 dB "quiet",
otherwise "undecided". Clipping in the noise window is reported.
"""
import math
import random
import re
import struct
import sys
import wave
from pathlib import Path

RATE = 48000


def marks(path):
    m = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        r = re.match(r'^(\d+\.\d{3}) (\S+)$', line.strip())
        if r:
            m[r.group(2)] = float(r.group(1))
    return m


def load(path):
    with wave.open(str(path), 'rb') as w:
        assert w.getnchannels() == 2 and w.getsampwidth() == 2
        assert w.getframerate() == RATE
        data = w.readframes(w.getnframes())
    return struct.unpack('<%dh' % (len(data) // 2), data)


def window(s, t0, t1):
    a, b = int(t0 * RATE) * 2, int(t1 * RATE) * 2
    seg = s[a:b]
    assert len(seg) >= RATE, (t0, t1, len(seg))  # at least 0.5 s of stereo frames
    ms = sum(x * x for x in seg) / len(seg)
    db = 10 * math.log10(ms / 32768.0 ** 2) if ms > 0 else -200.0
    clip = sum(1 for x in seg if abs(x) >= 32767)
    return db, clip


def judge(d):
    if d >= 30:
        return 'sounds'
    if d <= 6:
        return 'quiet'
    return 'undecided'


def take(d):
    d = Path(d)
    m = marks(d / 'tones-mga.txt')
    s = load(d / 'tones-mga.wav')
    # The bd20 mark is logged after the two writes, so the quiet window stops 0.2 s short of it.
    q, _ = window(s, m['bd20'] - 1.0, m['bd20'] - 0.2)
    n, clip = window(s, m['bd20'] + 0.5, m['bd20'] + 1.5)
    a, _ = window(s, m['bd00'] + 0.3, m['bd00'] + 0.8)
    print(f'{d.name}: quiet {q:7.1f} dBFS  noise {n:7.1f} dBFS  after BDh=00h {a:7.1f} dBFS  '
          f'diff {n - q:+6.1f} dB  -> {judge(n - q)}' + (f'  CLIP {clip}' if clip else ''))


def synth(d, kind):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    rnd = random.Random({'loud': 1, 'quiet': 2, 'mid': 3, 'early': 4}[kind])
    t_quiet, t_bd20, t_bd00, total = 2.5, 3.5, 6.5, 8.0
    floor = 32768 * 10 ** (-67 / 20) * math.sqrt(3)
    loud = {'loud': 32768 * 10 ** (-11 / 20) * math.sqrt(3), 'quiet': 0.0,
            'mid': 32768 * 10 ** (-50 / 20) * math.sqrt(3),
            'early': 32768 * 10 ** (-11 / 20) * math.sqrt(3)}[kind]
    # 'early': the sound starts 20 ms before the mark, as on the real cartridge
    start = t_bd20 - (0.02 if kind == 'early' else 0.0)
    frames = []
    for i in range(int(total * RATE)):
        t = i / RATE
        amp = floor + (loud if start <= t < t_bd00 else 0.0)
        for _ in range(2):
            frames.append(max(-32768, min(32767, int(rnd.uniform(-amp, amp)))))
    with wave.open(str(d / 'tones-mga.wav'), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack('<%dh' % len(frames), *frames))
    (d / 'tones-mga.txt').write_text(
        f'{t_quiet:.3f} quiet\n{t_bd20:.3f} bd20\n{t_bd00:.3f} bd00\n', encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1] == '--synth':
        synth(sys.argv[2], sys.argv[3])
    else:
        for a in sys.argv[1:]:
            take(a)
