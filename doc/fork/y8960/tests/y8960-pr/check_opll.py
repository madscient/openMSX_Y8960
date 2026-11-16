"""Judge the output of opll.tcl.

  python check_opll.py <dir>

Peaks of the final mix, left and right, over the second half of each melodic
capture and over all of each rhythm capture. Exits with 1 on any failure.
- center: L == R and not silent; zero, left, ch2_left, ch3_tunnel_left: right
  exactly 0; right: left exactly 0; center is left / sqrt(2) within 3%
- vol_half: half of center within 3%
- bank1: not silent, and not the same samples as center (tone set 1)
- bd_left, tom_left, tc_left: right exactly 0; hh_right, sd_right: left exactly 0
"""
import struct
import sys
import wave

D = sys.argv[1]


def load(name, half):
    with wave.open(f'{D}/{name}.wav', 'rb') as w:
        assert w.getnchannels() == 2 and w.getsampwidth() == 2
        s = struct.unpack('<%dh' % (w.getnframes() * 2), w.readframes(w.getnframes()))
    return s[len(s) // 4 * 2:] if half else s


def peaks(s):
    pk = lambda xs: max(max(xs), -min(xs))
    return pk(s[0::2]), pk(s[1::2])


melodic = ['center', 'zero', 'left', 'right', 'ch2_left', 'ch3_tunnel_left', 'vol_half', 'bank1']
rhythm = ['bd_left', 'hh_right', 'tom_left', 'sd_right', 'tc_left']
data = {n: load(n, True) for n in melodic}
data.update({n: load(n, False) for n in rhythm})
p = {n: peaks(s) for n, s in data.items()}
for n in melodic + rhythm:
    print(f'{n:16s} L={p[n][0]:6d} R={p[n][1]:6d}')

fail = []
c = p['center']
if c[0] == 0 or c[0] != c[1]:
    fail.append('center: silent, or L != R')
for n in ('zero', 'left', 'ch2_left', 'ch3_tunnel_left', 'bd_left', 'tom_left', 'tc_left'):
    if p[n][0] == 0 or p[n][1] != 0:
        fail.append(f'{n}: not hard left')
for n in ('right', 'hh_right', 'sd_right'):
    if p[n][1] == 0 or p[n][0] != 0:
        fail.append(f'{n}: not hard right')


def near(got, want, name):
    if abs(got - want) > want * 0.03 + 2:
        fail.append(f'{name}: {got}, want {want:.0f}')


near(c[0], p['left'][0] / 2 ** 0.5, 'center vs left')
near(p['vol_half'][0], c[0] / 2, 'vol_half')
if p['bank1'][0] == 0 or data['bank1'] == data['center']:
    fail.append('bank1: silent, or the same as tone set 0')

for f in fail:
    print('NG:', f)
print('OK' if not fail else 'NG')
sys.exit(1 if fail else 0)
