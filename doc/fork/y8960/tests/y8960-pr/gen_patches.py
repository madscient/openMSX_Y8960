"""Write Nuked-OPLL's tone tables in the form of YM2413NukeYKT's m_patches.

  python gen_patches.py <openMSX src/sound>

Reads patch_ym2413, patch_ym2423, patch_ymf281 and patch_ds1001 from opll.cc
(Nuked-OPLL, already in openMSX) and m_patches from YM2413NukeYKT.cc. The
YM2413 table is converted first and must match m_patches line for line;
that is the check on the conversion. Exits with 1 if it does not. Then the
other three tables are printed, ready to paste.

opll.cc has dc and dm as two fields, YM2413NukeYKT has them as one
dcm = (dc << 1) | dm. All other fields are in the same order.
"""
import re
import sys

SRC = sys.argv[1]
NUM = r'0x[0-9a-fA-F]+|\d+'


def nuked_table(text, name):
    m = re.search(r'static const opll_patch_t ' + name + r'\[opll_patch_max\] = \{(.*?)\n\};', text, re.S)
    assert m, name
    rows = []
    for line in m.group(1).splitlines():
        nums = [int(x, 0) for x in re.findall(NUM, line)]
        if not nums:
            continue
        assert len(nums) == 4 + 2 * 10, (name, line)
        rows.append(nums)
    assert len(rows) == 15 + 6, (name, len(rows))
    return rows[:15]  # the 6 rhythm patches are not used


def fmt(row):
    tl, dc, dm, fb = row[:4]
    pairs = [row[4 + 2 * i: 6 + 2 * i] for i in range(10)]
    am, vib, et, ksr, multi, ksl, ar, dr, sl, rr = pairs
    dec = lambda p: '{%d, %d}' % (p[0], p[1])
    hx = lambda p: '{0x%x, 0x%x}' % (p[0], p[1])
    return 'YM2413::Patch{0x%02x, %d, %d, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s},' % (
        tl, (dc << 1) | dm, fb, dec(am), dec(vib), dec(et), dec(ksr),
        hx(multi), dec(ksl), hx(ar), hx(dr), hx(sl), hx(rr))


opll = open(SRC + '/opll.cc', encoding='utf-8').read()
nuke = open(SRC + '/YM2413NukeYKT.cc', encoding='utf-8').read()
m = re.search(r'YM2413::m_patches = \{\n(.*?)\n\};', nuke, re.S)
assert m
upstream = [l.strip() for l in m.group(1).splitlines() if l.strip().startswith('YM2413::Patch{')]
assert len(upstream) == 15, len(upstream)

mine = [fmt(r) for r in nuked_table(opll, 'patch_ym2413')]
bad = [i for i in range(15) if mine[i] != upstream[i]]
if bad:
    for i in bad:
        print('NG %2d upstream: %s' % (i + 1, upstream[i]))
        print('   %2d mine:     %s' % (i + 1, mine[i]))
    sys.exit(1)
print('// check: patch_ym2413 converted matches m_patches, 15 of 15', file=sys.stderr)

for name in ('patch_ym2423', 'patch_ymf281', 'patch_ds1001'):
    print('\t// ' + name)
    for line in (fmt(r) for r in nuked_table(opll, name)):
        print('\t' + line)
