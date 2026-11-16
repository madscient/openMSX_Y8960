"""Check bank-c against bank-d0..d3 (see gen_opll.py).

  python cmpbank.py <dir of bank-c> <dir of bank-d0> <dir of bank-d1> <dir of bank-d2> <dir of bank-d3>

Prints, for each melodic channel, which bank-d<b> recordings it is byte-identical
to, and its peak. A channel must match exactly the d<b> of its own tone set and
none of the others. Exits with 1 otherwise.
"""
import sys
import wave
from pathlib import Path

import numpy as np

BANKS = [1, 2, 3, 0, 1, 2, 3, 0, 1]
c = Path(sys.argv[1])
d = [Path(p) for p in sys.argv[2:6]]


def peak(p):
    with wave.open(str(p), 'rb') as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return int(np.abs(a.astype(np.int64)).max())


ok = True
for ch in range(9):
    name = f'ch{ch + 1}.wav'
    a = (c / name).read_bytes()
    same = [b for b in range(4) if (d[b] / name).read_bytes() == a]
    good = same == [BANKS[ch]]
    ok &= good
    print(f'{name}: tone set {BANKS[ch]}, identical to d{same}, peak {peak(c / name)}  {"OK" if good else "NG"}')
print('OK' if ok else 'NG')
sys.exit(0 if ok else 1)
