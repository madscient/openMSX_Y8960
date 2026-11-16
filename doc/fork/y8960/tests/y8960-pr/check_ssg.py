"""Judge the output of ssg.tcl.

  python check_ssg.py <dir>

Peaks of the final mix, left and right, over the second half of each
capture. Exits with 1 on any failure.
- center, unit1: L == R, not silent
- left, unit1_left: right exactly 0; right: left exactly 0
- center is left / sqrt(2), half and ssg_vol_half are half of center, within 3%
"""
import struct
import sys
import wave

D = sys.argv[1]


def peaks(name):
    with wave.open(f'{D}/{name}.wav', 'rb') as w:
        assert w.getnchannels() == 2 and w.getsampwidth() == 2
        s = struct.unpack('<%dh' % (w.getnframes() * 2), w.readframes(w.getnframes()))
    s = s[len(s) // 4 * 2:]
    pk = lambda xs: max(max(xs), -min(xs))
    return pk(s[0::2]), pk(s[1::2])


names = ['center', 'left', 'right', 'half', 'unit1', 'unit1_left', 'ssg_vol_half']
p = {n: peaks(n) for n in names}
for n in names:
    print(f'{n:14s} L={p[n][0]:6d} R={p[n][1]:6d}')

fail = []
for n in ('center', 'unit1'):
    if p[n][0] == 0 or p[n][0] != p[n][1]:
        fail.append(f'{n}: silent, or L != R')
for n in ('left', 'unit1_left'):
    if p[n][0] == 0 or p[n][1] != 0:
        fail.append(f'{n}: not hard left')
if p['right'][1] == 0 or p['right'][0] != 0:
    fail.append('right: not hard right')


def near(got, want, name):
    if abs(got - want) > want * 0.03 + 2:
        fail.append(f'{name}: {got}, want {want:.0f}')


near(p['center'][0], p['left'][0] / 2 ** 0.5, 'center vs left')
near(p['half'][0], p['center'][0] / 2, 'half')
near(p['ssg_vol_half'][0], p['center'][0] / 2, 'ssg_vol_half')

for f in fail:
    print('NG:', f)
print('OK' if not fail else 'NG')
sys.exit(1 if fail else 0)
