"""Judge the output of scc.tcl.

  python check_scc.py <dir>

Peaks of the final mix, left and right. Exits with 1 on any failure.
- center: L == R and not silent; left, zero, chB_left, ram_left, closed_left:
  right exactly 0; right: left exactly 0
- center is left / sqrt(2) (the centre of the pan law), within 3%
- vol_half and master_half: half of center, within 3%; vol_zero silent
- vol_scc_window: as center. 7FFAh = 0 was written while 7800h-7FFFh showed
  the SCC, so it must not have reached the volume register.
"""
import struct
import sys
import wave

D = sys.argv[1]


def peaks(name):
    with wave.open(f'{D}/{name}.wav', 'rb') as w:
        assert w.getnchannels() == 2 and w.getsampwidth() == 2
        s = struct.unpack('<%dh' % (w.getnframes() * 2), w.readframes(w.getnframes()))
    # The second half only: the mixer's DC filter and resampler still carry
    # the previous capture's sound at the start.
    s = s[len(s) // 4 * 2:]
    pk = lambda xs: max(max(xs), -min(xs))
    return pk(s[0::2]), pk(s[1::2])


fail = []
lines = open(f'{D}/scc.txt', encoding='utf-8').read().splitlines()
fail += [l for l in lines if l.startswith('FAIL')]
if not lines or lines[-1] != 'RESULT: ALL PASS':
    fail.append('register checks did not all pass')

names = ['center', 'left', 'right', 'zero', 'chB_left', 'ram_left', 'closed_left',
         'vol_half', 'master_half', 'vol_zero', 'vol_scc_window']
p = {n: peaks(n) for n in names}
for n in names:
    print(f'{n:15s} L={p[n][0]:6d} R={p[n][1]:6d}')

c = p['center']
if c[0] == 0 or c[0] != c[1]:
    fail.append('center: silent, or L != R')
for n in ('left', 'zero', 'chB_left', 'ram_left', 'closed_left'):
    if p[n][0] == 0 or p[n][1] != 0:
        fail.append(f'{n}: not hard left')
if p['right'][1] == 0 or p['right'][0] != 0:
    fail.append('right: not hard right')
if p['left'][0] >= 32767:
    fail.append('left clips')


def near(got, want, name):
    if abs(got - want) > want * 0.03 + 2:
        fail.append(f'{name}: {got}, want {want:.0f}')


near(c[0], p['left'][0] / 2 ** 0.5, 'center vs left')
near(p['vol_half'][0], c[0] / 2, 'vol_half')
near(p['master_half'][0], c[0] / 2, 'master_half')
if p['vol_zero'] != (0, 0):
    fail.append('vol_zero: not silent')
near(p['vol_scc_window'][0], c[0], 'vol_scc_window')

for f in fail:
    print('NG:', f)
print('OK' if not fail else 'NG')
sys.exit(1 if fail else 0)
