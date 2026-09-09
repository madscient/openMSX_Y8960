#!/usr/bin/env python3
"""Fit the openMSX command-engine timing model to the 2026 logic-analyzer set.

Usage:
    2026-measurement-check.py <measurement-repo>/part2/5.slots [--cpu] [--plain]

Reads the annotated access traces from
<https://github.com/m9710797/vdp-timing-measurements> and, for every
command-engine step (e.g. HMMM's write -> next read), reports which delays
would reproduce *every* observed access.

The model is openMSX's:

    next access = the first VRAM access slot at or after (previous access +
                  delta), where delta = 'command engine work' + 'request
                  arbitration latency'

with two refinements that the raw captures force (see
2026-measurement-analysis.md; vcd-slot-grid.py does the slot measurement):

  * the delay is counted in the VDP's memory cycles rather than VDP cycles.
    Two memory cycles per line are stretched by two cycles each in the
    horizontal blanking region -- the slot grid there runs
    ... 1316 1324 1334 1344 ... where every other gap is 8 -- and the engine's
    counter does not see the stretch.  '--plain' turns this off.
  * with sprite rendering active every delay is one cycle longer.

For one observed pair (previous access at p, next access at n) the model is
satisfied by every delta in [prevSlot(n) - p + 1, n - p] measured in that time
base; intersecting over all observations of a step gives its band.

Cycle numbers here are openMSX's, which are based on /RAS.  The .txt files of
the measurement repository are based on /CAS and are one higher.
"""
from __future__ import annotations

import argparse
import collections
import glob
import os
import re
import sys

TICKS = 1368                # VDP cycles per display line
DUMMY_CODE, DUMMY_ADDR = 'R..', 0x1FFFF   # the VDP's dummy read
CPU_CODES = ('R.r', 'W.w')  # CPU read / write
VRAM_LINE = 128             # bytes per VRAM line in screen 5

# --------------------------------------------------------------------------
# Access slot tables, exactly as in src/video/VDPAccessSlots.cc.
#
# Measured from /RAS in the raw captures: all 154 / 88 / 31 slots are confirmed
# to within 0.06 cycles.
#
# The .txt analyses in the measurement repository are /CAS based.  /CAS normally
# follows /RAS by one cycle, but for exactly two slots per table -- 1324 and
# 1334 here, 1322 and 1332 for sprites-off -- it follows by two, because those
# two memory cycles are stretched (see V() below).  So the CAS -> RAS conversion
# is not a uniform -1 for those two slots; RELABEL handles them.
# --------------------------------------------------------------------------
SLOTS_DISP_OFF = [
       0,    8,   16,   24,   32,   40,   48,   56,   64,   72,
      80,   88,   96,  104,  112,  120,  164,  172,  180,  188,
     196,  204,  212,  220,  228,  236,  244,  252,  260,  268,
     276,  292,  300,  308,  316,  324,  332,  340,  348,  356,
     364,  372,  380,  388,  396,  404,  420,  428,  436,  444,
     452,  460,  468,  476,  484,  492,  500,  508,  516,  524,
     532,  548,  556,  564,  572,  580,  588,  596,  604,  612,
     620,  628,  636,  644,  652,  660,  676,  684,  692,  700,
     708,  716,  724,  732,  740,  748,  756,  764,  772,  780,
     788,  804,  812,  820,  828,  836,  844,  852,  860,  868,
     876,  884,  892,  900,  908,  916,  932,  940,  948,  956,
     964,  972,  980,  988,  996, 1004, 1012, 1020, 1028, 1036,
    1044, 1060, 1068, 1076, 1084, 1092, 1100, 1108, 1116, 1124,
    1132, 1140, 1148, 1156, 1164, 1172, 1188, 1196, 1204, 1212,
    1220, 1228, 1268, 1276, 1284, 1292, 1300, 1308, 1316, 1324,
    1334, 1344, 1352, 1360,
]
SLOTS_SPR_OFF = [
       6,   14,   22,   30,   38,   46,   54,   62,   70,   78,
      86,   94,  102,  110,  118,  162,  170,  182,  188,  214,
     220,  246,  252,  278,  310,  316,  342,  348,  374,  380,
     406,  438,  444,  470,  476,  502,  508,  534,  566,  572,
     598,  604,  630,  636,  662,  694,  700,  726,  732,  758,
     764,  790,  822,  828,  854,  860,  886,  892,  918,  950,
     956,  982,  988, 1014, 1020, 1046, 1078, 1084, 1110, 1116,
    1142, 1148, 1174, 1206, 1212, 1266, 1274, 1282, 1290, 1298,
    1306, 1314, 1322, 1332, 1342, 1350, 1358, 1366,
]
SLOTS_SPR_ON = [
      28,   92,  162,  170,  188,  220,  252,  316,  348,  380,
     444,  476,  508,  572,  604,  636,  700,  732,  764,  828,
     860,  892,  956,  988, 1020, 1084, 1116, 1148, 1212, 1264,
    1330,
]
TABLES = {'dispOff': SLOTS_DISP_OFF, 'sprOff': SLOTS_SPR_OFF,
          'sprOn': SLOTS_SPR_ON}

# part2/README.md's proposed correction, for comparison (--published-slots)
PUBLISHED_TABLES = {
    'dispOff': [1325 if s == 1324 else 1335 if s == 1334 else s
                for s in SLOTS_DISP_OFF],
    'sprOff': [1323 if s == 1322 else 1333 if s == 1332 else s
               for s in SLOTS_SPR_OFF],
    'sprOn': SLOTS_SPR_ON,
}


def table(mode):
    return (PUBLISHED_TABLES if PUBLISHED[0] else TABLES)[mode]

# CAS -> RAS is -2 rather than -1 for these (after the uniform -1, subtract
# one more)
RELABEL = {'dispOff': {1325: 1324, 1335: 1334},
           'sprOff': {1323: 1322, 1333: 1332},
           'sprOn': {}}

# The VDP pads its line out to 1368 cycles by making a few memory cycles in the
# horizontal blanking region longer than the rest.  Measured from /RAS, and
# confirmed by the R#9 S1/S0 captures, where the padding disappears and the line
# is 1365 cycles: display off and sprites off get two cycles of 10 where the
# rest of that part of the line runs at 8, sprites on gets three cycles one
# cycle longer than the 14/6/10 pattern it would otherwise have.  Each entry is
# the cycle at which one stretch has completed; STRETCH_STEP is how many cycles
# each of them adds.
PAD = {'dispOff': ((1334, 2), (1344, 2)),
       'sprOff': ((1332, 2), (1342, 2)),
       'sprOn':  ((1330, 2), (1337, 1), (1348, 1))}

# VRAM accesses per pixel/byte step, and the role of each
ROLES = {
    'hmmv': ('W',),
    'lmmv': ('R', 'W'),
    'ymmm': ('R', 'W'),
    'hmmm': ('R', 'W'),
    'line': ('R', 'W'),
    'lmmm': ('Rs', 'Rd', 'W'),
}

# The values openMSX uses today, for comparison
OPENMSX = {
    ('hmmv', 'W->W'): 48,  ('hmmv', 'newline'): 104,
    ('lmmv', 'R->W'): 24,  ('lmmv', 'W->R'): 72,  ('lmmv', 'newline'): 134,
    ('ymmm', 'R->W'): 24,  ('ymmm', 'W->R'): 38,  ('ymmm', 'newline'): 104,
    ('hmmm', 'R->W'): 24,  ('hmmm', 'W->R'): 64,  ('hmmm', 'newline'): 128,
    ('lmmm', 'Rd->W'): 24, ('lmmm', 'Rs->Rd'): 32, ('lmmm', 'W->Rs'): 64,
    ('lmmm', 'newline'): 128,
    ('line', 'R->W'): 24,  ('line', 'W->R'): 88,  ('line', 'newline'): 120,
}
OPENMSX_SPR_ON = {('lmmm', 'Rs->Rd'): 48, ('hmmm', 'newline'): 134,
                  ('lmmm', 'newline'): 134}

# Best fit under the refined model: one value per step, +1 with sprites on,
# +1 when the previous access was in a slot only 6 cycles after another slot
FITTED = {
    ('hmmv', 'W->W'): 46,  ('hmmv', 'newline'): 104,
    ('lmmv', 'R->W'): 24,  ('lmmv', 'W->R'): 72,  ('lmmv', 'newline'): 130,
    ('ymmm', 'R->W'): 24,  ('ymmm', 'W->R'): 36,  ('ymmm', 'newline'): 104,
    ('hmmm', 'R->W'): 24,  ('hmmm', 'W->R'): 60,  ('hmmm', 'newline'): 128,
    ('lmmm', 'Rd->W'): 24, ('lmmm', 'Rs->Rd'): 32, ('lmmm', 'W->Rs'): 60,
    ('lmmm', 'newline'): 128,
    ('line', 'R->W'): 24,  ('line', 'W->R'): 84,  ('line', 'newline'): 120,
}

# Slots that follow another slot after only 6 cycles.  Only the sprites-off
# table has them, 25 of its 88.
TIGHT = {m: {s for s in t if (s - 6) in set(t)} for m, t in TABLES.items()}

# Cycles that sprite rendering adds to every command engine step.  The
# measurements admit 1 or 2 and cannot separate them; openMSX uses 1.
SPR_ON_EXTRA = 1

PLAIN = [False]     # --plain: VDP cycles, and no sprites-on adjustment
TIGHT_RULE = [True]  # the extra cycle after an access in a 6-cycle-pair slot
PUBLISHED = [False]  # --published-slots: use part2/README.md's slot correction


def V(mode, t):
    """The engine's own time: absolute cycle minus the stretch seen so far.

    Deliberately not periodic -- it loses 4 cycles per line -- which is fine
    because the engine's counter restarts at every access, so only intervals
    matter.
    """
    if PLAIN[0]:
        return t
    line, c = divmod(t, TICKS)
    pad = PAD[mode]
    return t - (sum(n for _, n in pad) * line
                + sum(n for a, n in pad if c >= a))


def meta(path):
    """scr5-<mode>-<command>-<cpu>[-<variant>...]-<n><suffix>.txt"""
    name = os.path.basename(path)
    if not name.endswith('.txt'):
        return None
    parts = name[:-4].split('-')
    if len(parts) < 5 or parts[0] != 'scr5' or parts[1] not in TABLES:
        return None
    if not re.fullmatch(r'\d+[a-z]?', parts[-1]):
        return None
    return {'mode': parts[1], 'cmd': parts[2], 'cpu': parts[3],
            'variant': parts[4:-1], 'name': name}


def parse(path):
    """[(absolute cycle, code, address)] in time order, RAS numbering.

    The files have one row per cycle-within-a-line and one column per display
    line, so the absolute CAS cycle is 1368 * column + row, and RAS is one
    lower.
    """
    rel = {} if PUBLISHED[0] else RELABEL[meta(path)['mode']]
    items = []
    with open(path) as f:
        for ln in f:
            if ':' not in ln:
                continue
            row, rest = ln.rstrip('\n').split(':', 1)
            t = int(row)
            col = 0
            while rest:
                cell = rest[2:13]
                if cell.strip():
                    line, c = divmod(TICKS * col + t - 1, TICKS)
                    items.append((line * TICKS + rel.get(c, c),
                                  cell[0:3], int(cell[6:11], 16)))
                rest = rest[13:]
                col += 1
    items.sort()
    return items


def transitions(path):
    """Yield (step, prev cycle, next cycle) for one trace."""
    info = meta(path)
    if info is None or info['cmd'] not in ROLES:
        return
    roles = ROLES[info['cmd']]
    acc = [a for a in parse(path) if a[1] not in CPU_CODES]
    # The dummy read shows up as an unclassified read of 0x1ffff, but in a few
    # YMMM captures the command's own source pointer walks through the top of
    # VRAM, so only drop it when nothing else in the trace is near.
    real = any(a[2] != DUMMY_ADDR and abs(a[2] - DUMMY_ADDR) < 0x400
               for a in acc)
    eng = [a for a in acc if real or (a[1], a[2]) != (DUMMY_CODE, DUMMY_ADDR)]
    writes = [i for i, a in enumerate(eng) if a[1][0] == 'W']
    groups = []
    for a, b in zip(writes, writes[1:]):
        grp = eng[a + 1:b + 1]
        if len(grp) == len(roles) and \
                tuple(x[1][0] for x in grp) == tuple(r[0] for r in roles):
            groups.append(grp)
    for gi, grp in enumerate(groups):
        for i in range(len(grp) - 1):
            yield f'{roles[i]}->{roles[i + 1]}', grp[i][0], grp[i + 1][0]
        if gi + 1 < len(groups):
            nxt = groups[gi + 1]
            if (nxt[-1][2] // VRAM_LINE) == (grp[-1][2] // VRAM_LINE):
                yield f'{roles[-1]}->{roles[0]}', grp[-1][0], nxt[0][0]
            elif 0 < nxt[-1][2] - grp[-1][2] <= 2 * VRAM_LINE:
                yield 'newline', grp[-1][0], nxt[0][0]
            # else: the command restarted, no useful constraint


def next_slot(mode, p, delta, taken=frozenset()):
    """First slot at least 'delta' engine cycles after p and not taken by the
    CPU (which has priority)."""
    tab = table(mode)
    line = p // TICKS
    for k in range(4):
        for s in tab:
            t = (line + k) * TICKS + s
            if t > p and V(mode, t) - V(mode, p) >= delta and t not in taken:
                return t
    raise AssertionError('no slot found')


def prev_slot(mode, n):
    tab = table(mode)
    line, off = divmod(n, TICKS)
    earlier = [s for s in tab if s < off]
    return (line * TICKS + earlier[-1] if earlier
            else (line - 1) * TICKS + tab[-1])


def delta_for(table, spron, key, mode, prev=None):
    """Delay for one command step.

    A step that starts from a slot which itself follows another slot after only
    6 cycles takes one cycle longer -- as if that memory cycle, squeezed against
    its predecessor, finished one cycle late.  Such slots exist only in the
    sprites-off table (25 of its 88), which is why the effect shows up in that
    mode alone.  1778 transitions in the 2026 set start from one; the rule is
    needed by 32 of them and, at +3 or more, contradicted by 1281.
    """
    if (TIGHT_RULE[0] and prev is not None and
            (prev % TICKS) in TIGHT[mode] and not PLAIN[0]):
        return delta_for(table, spron, key, mode) + 1
    if mode == 'sprOn':
        if key in spron:
            return spron[key]
        return table[key] + (0 if PLAIN[0] else SPR_ON_EXTRA)
    return table[key]


def bands(files):
    out = collections.defaultdict(lambda: (1, 400))
    n = collections.Counter()
    for f in files:
        mode = meta(f)['mode']
        cmd = meta(f)['cmd']
        for step, p, nx in transitions(f):
            key = (cmd, step, mode)
            lo = V(mode, prev_slot(mode, nx)) - V(mode, p) + 1
            hi = V(mode, nx) - V(mode, p)
            a, b = out[key]
            out[key] = (max(a, lo), min(b, hi))
            n[key] += 1
    return out, n


def count_misses(files, table, spron, cpu_traces=False, plain=None):
    saved = PLAIN[0]
    if plain is not None:
        PLAIN[0] = plain
    tot = bad = contended = 0
    per = collections.Counter()
    for f in files:
        info = meta(f)
        # The CPU takes slots away from the engine.  So does the dummy read
        # the VDP does when the CPU's request wins a 6-cycle-pair slot: it
        # cannot carry the CPU access, so that memory cycle is spent on a read
        # of 0x1ffff and the CPU's access happens in the next slot.
        taken = {a[0] for a in parse(f)
                 if a[1] in CPU_CODES
                 or ((a[1], a[2]) == (DUMMY_CODE, DUMMY_ADDR)
                     and (a[0] % TICKS) in TIGHT[info['mode']])} \
            if cpu_traces else frozenset()
        for step, p, nx in transitions(f):
            key = (info['cmd'], step)
            d = delta_for(table, spron, key, info['mode'], p)
            first = next_slot(info['mode'], p, d)
            got = next_slot(info['mode'], p, d, taken)
            tot += 1
            contended += (got != first)
            if got != nx:
                bad += 1
                per[key + (info['mode'],)] += 1
    PLAIN[0] = saved
    return tot, bad, contended, per


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('slots_dir')
    ap.add_argument('--cpu', action='store_true',
                    help='use the rdCpu/wrCpu traces and test the arbitration')
    ap.add_argument('--plain', action='store_true',
                    help='no memory-cycle stretch and no sprites-on +1')
    ap.add_argument('--published-slots', action='store_true',
                    help="use part2/README.md's one-cycle slot correction")
    ap.add_argument('--no-tight', action='store_true',
                    help='drop the extra cycle after a 6-cycle-pair slot')
    args = ap.parse_args()
    PLAIN[0] = args.plain
    PUBLISHED[0] = args.published_slots
    TIGHT_RULE[0] = not args.no_tight

    files = [f for f in sorted(glob.glob(os.path.join(args.slots_dir,
                                                      'scr5-*.txt')))
             if meta(f) and '-wrong-' not in f]
    files = [f for f in files
             if (meta(f)['cpu'] != 'noCpu') == bool(args.cpu)]
    if not files:
        sys.exit(f'no traces found in {args.slots_dir}')

    if args.cpu:
        for label, tbl, spron, pl in (
                ('openMSX today', OPENMSX, OPENMSX_SPR_ON, True),
                ('fitted model', FITTED, {}, False)):
            tot, bad, cont, _ = count_misses(files, tbl, spron, True, pl)
            print(f'{len(files)} traces with CPU activity, {tot} engine '
                  f'transitions, the CPU took the slot the engine wanted in '
                  f'{100.0 * cont / tot:.1f}% of them')
            print(f'    {label:16}: {bad} mispredicted '
                  f'({100.0 * bad / tot:.3f}%)')
        return

    b, n = bands(files)
    print(f'{len(files)} traces, {sum(n.values())} engine-to-engine transitions'
          + ('   [--plain: VDP cycles]' if args.plain else ''))
    print()
    print(f'{"cmd":5} {"step":9} {"dispOff":>12} {"sprOff":>12} {"sprOn":>12}'
          f'   all modes')
    print('-' * 72)
    for cmd, step in sorted({(k[0], k[1]) for k in b}):
        cells, lo, hi = [], 1, 400
        for mode in ('dispOff', 'sprOff', 'sprOn'):
            k = (cmd, step, mode)
            if k not in b:
                cells.append('-')
                continue
            a, z = b[k]
            cells.append(f'[{a},{z}]' + ('!' if a > z else ''))
            if mode == 'sprOn' and not args.plain:
                a, z = a - SPR_ON_EXTRA, z - SPR_ON_EXTRA
            lo, hi = max(lo, a), min(hi, z)
        allb = f'[{lo},{hi}]' + ('   no single value' if lo > hi else '')
        print(f'{cmd:5} {step:9} ' + ' '.join(f'{c:>12}' for c in cells)
              + f'   {allb}')
    print()
    for label, tbl, spron, pl in (
            ('openMSX today', OPENMSX, OPENMSX_SPR_ON, True),
            ('fitted model', FITTED, {}, args.plain)):
        tot, bad, _, per = count_misses(files, tbl, spron, plain=pl)
        print(f'{label:16}: {bad} of {tot} mispredicted '
              f'({100.0 * bad / tot:.3f}%)')
        for k, v in sorted(per.items(), key=lambda kv: -kv[1])[:4]:
            print(f'    {k[0]:5} {k[1]:9} {k[2]:8} {v}')


if __name__ == '__main__':
    main()
