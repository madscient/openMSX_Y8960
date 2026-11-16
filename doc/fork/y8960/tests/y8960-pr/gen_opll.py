"""Write the OPLL test sequences (chrec.tcl format, ../y8950-pr/chrec.tcl).

  python gen_opll.py <openMSX src/sound> <out dir>

Every sequence first sets 7FF6h = 01h (the FM-PAC's I/O enable) and then writes
the OPLL through I/O 7Ch/7Dh, one write per millisecond.

  mus.txt         the 16 instruments one by one, then all 9 channels at once,
                  then the rhythm. For MSX-MUSIC before and after a change.
  bank-c.txt      tone set per channel 1,2,3,0,1,2,3,0,1 (registers 40h-48h),
                  instruments 1-15 on all channels at once.
  bank-d<b>.txt   the same writes at the same times, but every channel plays
                  the user tone (instrument 0), and 00h-07h hold entry i of
                  tone set b, taken from opll.cc. A channel of bank-c.txt with
                  tone set b must come out the same as in bank-d<b>.txt.
  rhy-b0.txt      the rhythm, with 0 written to 40h-48h once it is on
  rhy-b3.txt      the same with 3 written there. While the rhythm is on it
                  uses its own tones, so all 14 channels must match.

The expected tones come from the raw tables in opll.cc, not from the tables
in YM2413NukeYKT.cc.
"""
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)


def nuked_tables():
    import re
    text = (SRC / 'opll.cc').read_text(encoding='utf-8')
    res = []
    for name in ('patch_ym2413', 'patch_ym2423', 'patch_ymf281', 'patch_ds1001'):
        m = re.search(r'static const opll_patch_t ' + name + r'\[opll_patch_max\] = \{(.*?)\n\};', text, re.S)
        rows = []
        for line in m.group(1).splitlines():
            nums = [int(x, 0) for x in re.findall(r'0x[0-9a-fA-F]+|\d+', line)]
            if nums:
                assert len(nums) == 24
                rows.append(nums)
        assert len(rows) == 21
        res.append(rows[:15])
    return res


def user_regs(row):
    """00h-07h for one opll_patch_t row: tl, dc, dm, fb, then pairs (mod, car)."""
    tl, dc, dm, fb = row[:4]
    p = lambda k: row[4 + 2 * k: 6 + 2 * k]
    am, vib, et, ksr, mul, ksl, ar, dr, sl, rr = (p(k) for k in range(10))
    r = []
    for s in (0, 1):
        r.append((am[s] << 7) | (vib[s] << 6) | (et[s] << 5) | (ksr[s] << 4) | mul[s])
    r.append((ksl[0] << 6) | tl)
    r.append((ksl[1] << 6) | (dc << 4) | (dm << 3) | fb)
    for s in (0, 1):
        r.append((ar[s] << 4) | dr[s])
    for s in (0, 1):
        r.append((sl[s] << 4) | rr[s])
    return r


class Seq:
    def __init__(self):
        self.out = ['mem 7FF6 01']

    def reg(self, r, v):
        self.out += [f'io 7C {r:02X}', f'io 7D {v:02X}']

    def wait(self, ms):
        self.out.append(f'wait {ms}')

    def mark(self, s):
        self.out.append(f'mark {s}')

    def save(self, name):
        (OUT / name).write_text('\n'.join(self.out) + '\n', encoding='utf-8')


FNUM = [0xAD, 0xB7, 0xC1, 0xCC, 0xD8, 0xE5, 0xF2, 0x101, 0x110]
BLK = 4


def key(s, ch, inst, vol, on, fnum=0xAD, blk=BLK):
    s.reg(0x10 + ch, fnum & 0xFF)
    s.reg(0x30 + ch, (inst << 4) | vol)
    s.reg(0x20 + ch, (0x10 if on else 0) | (blk << 1) | ((fnum >> 8) & 1))


def rhythm(s, label, bank=None):
    s.mark(label)
    s.reg(0x16, 0x20); s.reg(0x26, 0x05)
    s.reg(0x17, 0x50); s.reg(0x27, 0x05)
    s.reg(0x18, 0xC0); s.reg(0x28, 0x01)
    s.reg(0x36, 0x02)            # BD volume
    s.reg(0x37, 0x31)            # HH volume 3, SD volume 1
    s.reg(0x38, 0x52)            # TOM volume 5, TC volume 2
    if bank is not None:
        # Only once the rhythm is on: before that, channels 7 and 8 run
        # their phase at the MULT of their melodic tone, and SD, CY and HH
        # are built from those phases, so the tone set would show up anyway.
        s.reg(0x0E, 0x20)
        for ch in range(9):
            s.reg(0x40 + ch, bank)
    for bits in (0x30, 0x28, 0x24, 0x22, 0x21, 0x3F):
        s.reg(0x0E, 0x20)
        s.reg(0x0E, bits)
        s.wait(250)
    s.reg(0x0E, 0x00)
    s.wait(200)


tables = nuked_tables()

# mus.txt
s = Seq()
for r, v in enumerate([0x61, 0x61, 0x1E, 0x17, 0xF0, 0x7F, 0x00, 0x17]):
    s.reg(r, v)
for inst in range(16):
    ch = inst % 9
    s.mark(f'inst{inst}')
    key(s, ch, inst, 0, True, FNUM[ch])
    s.wait(300)
    key(s, ch, inst, 0, False, FNUM[ch])
    s.wait(150)
s.mark('all9')
for ch in range(9):
    key(s, ch, (ch * 3 + 1) % 16, ch % 4, True, FNUM[ch])
s.wait(500)
for ch in range(9):
    key(s, ch, (ch * 3 + 1) % 16, ch % 4, False, FNUM[ch])
s.wait(200)
rhythm(s, 'rhythm')
s.save('mus.txt')

# bank-c.txt and bank-d<b>.txt
BANKS = [1, 2, 3, 0, 1, 2, 3, 0, 1]
TAIL = 5


def bank_seq(d):
    """d is None for bank-c, else the tone set whose entries go in 00h-07h."""
    s = Seq()
    for ch in range(9):
        s.reg(0x40 + ch, BANKS[ch])
    for i in range(1, 16):
        s.mark(f'inst{i}')
        src = tables[d if d is not None else 0][i - 1]
        for r, v in enumerate(user_regs(src)):
            s.reg(r, v)
        for ch in range(9):
            key(s, ch, i if d is None else 0, 0, True, FNUM[ch])
        s.wait(250)
        for ch in range(9):
            key(s, ch, i if d is None else 0, 0, False, FNUM[ch])
        # Let the release run on a ROM tone in both sequences. Otherwise the
        # next user tone written for bank-d would change the tail, and the
        # tail decides where the next note's envelope starts.
        for ch in range(9):
            s.reg(0x30 + ch, TAIL << 4)
        s.wait(150)
    return s


bank_seq(None).save('bank-c.txt')
for b in range(4):
    bank_seq(b).save(f'bank-d{b}.txt')

# rhy-b0.txt and rhy-b3.txt
for b in (0, 3):
    s = Seq()
    rhythm(s, f'rhythm-b{b}', b)
    s.save(f'rhy-b{b}.txt')

# state.txt: notes left sounding for opll_state.tcl, with tone sets per
# channel and a user tone on channel 0
s = Seq()
for ch in range(9):
    s.reg(0x40 + ch, BANKS[ch])
for r, v in enumerate(user_regs(tables[2][4])):
    s.reg(r, v)
for ch in range(9):
    key(s, ch, 0 if ch == 0 else (ch * 2 + 1) % 16, ch % 3, True, FNUM[ch])
s.save('state.txt')

print('written to', OUT)
