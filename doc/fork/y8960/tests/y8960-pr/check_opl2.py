"""Judge the output of opl2.tcl.

  python check_opl2.py <dir>

Peaks of the final mix, left and right, over the second half of each FM and
ADPCM capture and over all of each rhythm capture. Exits with 1 on failure.
- fm_center, adpcm_center: L == R, not silent
- fm_left, fm_tunnel_left, adpcm_left, bd_left, tom_left, cym_left: right
  exactly 0; fm_right, sd_right, hh_right: left exactly 0
- fm_center is fm_left / sqrt(2), and vol_half half of fm_center, within 3%
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


tonal = ['fm_center', 'fm_left', 'fm_right', 'vol_half', 'fm_tunnel_left', 'adpcm_center', 'adpcm_left']
rhythm = ['bd_left', 'sd_right', 'hh_right', 'tom_left', 'cym_left']
p = {n: peaks(load(n, True)) for n in tonal}
p.update({n: peaks(load(n, False)) for n in rhythm})
for n in tonal + rhythm:
    print(f'{n:16s} L={p[n][0]:6d} R={p[n][1]:6d}')

fail = []
for n in ('fm_center', 'adpcm_center'):
    if p[n][0] == 0 or p[n][0] != p[n][1]:
        fail.append(f'{n}: silent, or L != R')
for n in ('fm_left', 'fm_tunnel_left', 'adpcm_left', 'bd_left', 'tom_left', 'cym_left'):
    if p[n][0] == 0 or p[n][1] != 0:
        fail.append(f'{n}: not hard left')
for n in ('fm_right', 'sd_right', 'hh_right'):
    if p[n][1] == 0 or p[n][0] != 0:
        fail.append(f'{n}: not hard right')


def near(got, want, name):
    if abs(got - want) > want * 0.03 + 2:
        fail.append(f'{name}: {got}, want {want:.0f}')


near(p['fm_center'][0], p['fm_left'][0] / 2 ** 0.5, 'fm_center vs fm_left')
near(p['vol_half'][0], p['fm_center'][0] / 2, 'vol_half')

for f in fail:
    print('NG:', f)
print('OK' if not fail else 'NG')
sys.exit(1 if fail else 0)
