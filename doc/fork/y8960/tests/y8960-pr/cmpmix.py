"""Compare two directories of final-mix WAVs, file by file.

  python cmpmix.py <A> <B>

For each WAV in A: identical, or the largest difference of any sample, the
number of samples that differ, and the peak of A.
"""
import struct
import sys
import wave
from pathlib import Path

A, B = Path(sys.argv[1]), Path(sys.argv[2])


def load(p):
    with wave.open(str(p), 'rb') as w:
        return struct.unpack('<%dh' % (w.getnframes() * w.getnchannels()), w.readframes(w.getnframes()))


for f in sorted(A.glob('*.wav')):
    a, b = load(f), load(B / f.name)
    if a == b:
        print(f'{f.name:22s} identical')
        continue
    n = min(len(a), len(b))
    d = [abs(a[i] - b[i]) for i in range(n)]
    print(f'{f.name:22s} max diff {max(d):5d}, {sum(1 for x in d if x)} of {n} samples, '
          f'peak {max(abs(x) for x in a)}, length {len(a)} vs {len(b)}')
