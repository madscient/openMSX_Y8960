"""Compare two output trees of runall.sh file by file, byte for byte.

    py cmpout.py <A> <B>

Prints each file that differs or exists on one side only, and a count. Exit 1 if any differ.
"""
import pathlib
import sys

a = pathlib.Path(sys.argv[1])
b = pathlib.Path(sys.argv[2])
fa = {p.relative_to(a) for p in a.rglob('*') if p.is_file()}
fb = {p.relative_to(b) for p in b.rglob('*') if p.is_file()}
diff = 0
same = 0
for r in sorted(fa | fb):
    if r not in fa or r not in fb:
        print(f'only in {"B" if r not in fa else "A"}: {r}')
        diff += 1
    elif (a / r).read_bytes() != (b / r).read_bytes():
        print(f'differs: {r}')
        diff += 1
    else:
        same += 1
wavs = sum(1 for r in fa & fb if r.suffix == '.wav')
print(f'{same} identical ({wavs} wav on both sides), {diff} differ')
sys.exit(1 if diff else 0)
