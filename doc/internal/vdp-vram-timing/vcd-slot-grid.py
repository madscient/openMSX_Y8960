#!/usr/bin/env python3
"""Measure the VDP's VRAM access-slot grid from the raw logic-analyzer captures.

Usage:
    vcd-slot-grid.py <measurement-repo>/part2 [mode] [max-captures]

The published analysis in the measurement repository derives access times by
interpolating between the eight DRAM refresh accesses of a line.  This script
does not need that: /RAS pulses once per potential access slot whether or not
the VDP uses the slot, and its pattern repeats every display line, so the RAS
edges themselves are a time base with ~166 anchors per line instead of 8.

  1. Line period: exactly one gap per line is larger than all the others, so
     the sample distance between successive occurrences of that gap is the line
     period.  Fitted over the whole capture.
  2. Numbering: the refresh accesses are 128 cycles apart with the row address
     incrementing by one, and between the last of one line and the first of the
     next there are 472 cycles, so the chain has a unique start.  That one sits
     at cycle 284 in openMSX's numbering -- the slot openMSX omits between 276
     and 292.
  3. Each slot is then averaged over every line of every capture.  Sampling
     jitter is +-1 sample = +-0.27 cycles per edge, so a few hundred edges put
     the mean well inside a tenth of a cycle.

Cycle numbers printed are openMSX's, which are based on /RAS.  The .txt files
in the measurement repository are based on /CAS and are one higher.
"""
from __future__ import annotations

import collections
import glob
import os
import statistics
import sys

TICKS = 1368
SAMPLE = 125          # 100 ps units per sample at a nominal 80 MHz
REFRESH_CYCLE = 284   # openMSX numbering
SIGNALS = {'!': 'A0', '"': 'A1', '#': 'A2', '$': 'A3', '%': 'A4', '&': 'A5',
           "'": 'A6', '(': 'A7', ')': 'RAS', '*': 'CAS0', '+': 'CAS1',
           ',': 'RW', '-': 'VDS', '.': 'IRQ', '/': 'CSW', '0': 'CSR'}

# src/video/VDPAccessSlots.cc
OPENMSX = {
    'dispOff': [
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
        1334, 1344, 1352, 1360],
    'sprOff': [
           6,   14,   22,   30,   38,   46,   54,   62,   70,   78,
          86,   94,  102,  110,  118,  162,  170,  182,  188,  214,
         220,  246,  252,  278,  310,  316,  342,  348,  374,  380,
         406,  438,  444,  470,  476,  502,  508,  534,  566,  572,
         598,  604,  630,  636,  662,  694,  700,  726,  732,  758,
         764,  790,  822,  828,  854,  860,  886,  892,  918,  950,
         956,  982,  988, 1014, 1020, 1046, 1078, 1084, 1110, 1116,
        1142, 1148, 1174, 1206, 1212, 1266, 1274, 1282, 1290, 1298,
        1306, 1314, 1322, 1332, 1342, 1350, 1358, 1366],
    'sprOn': [
          28,   92,  162,  170,  188,  220,  252,  316,  348,  380,
         444,  476,  508,  572,  604,  636,  700,  732,  764,  828,
         860,  892,  956,  988, 1020, 1084, 1116, 1148, 1212, 1264,
        1330],
}


# --------------------------------------------------------------------------
# .vcd decoding
# --------------------------------------------------------------------------
def parse_vcd(path):
    state = {n: None for n in SIGNALS.values()}
    out = []
    body = False
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if not body:
                body = ln == '$enddefinitions $end'
                continue
            if not ln.startswith('#'):
                continue
            parts = ln.split()
            for p in parts[1:]:
                state[SIGNALS[p[1:]]] = int(p[0])
            out.append((int(parts[0][1:]) // SAMPLE, dict(state)))
    return out


def ras_edges(trace):
    out, prev = [], None
    for t, s in trace:
        if prev == 1 and s['RAS'] == 0:
            out.append(t)
        prev = s['RAS']
    return out


def accesses(trace):
    """(cas_sample, ras_sample, address, is_read) per VRAM access.

    Row address on A7..A0 at the falling /RAS, column address at the falling
    /CAS0 or /CAS1; which of the two also selects the 64kB bank.
    """
    out = []
    ras_t = row = None
    prev = {'RAS': None, 'CAS0': None, 'CAS1': None}
    for t, s in trace:
        if prev['RAS'] == 1 and s['RAS'] == 0:
            ras_t, row = t, sum(s[f'A{i}'] << i for i in range(8))
        for bank, cas in ((0, 'CAS0'), (1, 'CAS1')):
            if prev[cas] == 1 and s[cas] == 0 and row is not None:
                col = sum(s[f'A{i}'] << i for i in range(8))
                out.append((t, ras_t, (bank << 16) | (row << 8) | col,
                            s['RW'] == 1))
        for k in prev:
            prev[k] = s[k]
    return out


# --------------------------------------------------------------------------
# grid fit
# --------------------------------------------------------------------------
def geometry(edges):
    """(line period in samples, marks) from the unique largest gap per line."""
    gaps = [b - a for a, b in zip(edges, edges[1:])]
    if not gaps:
        return None
    mx = max(gaps)
    marks = [i + 1 for i, g in enumerate(gaps) if g > mx * 0.9]
    if len(marks) < 3:
        return None
    return (edges[marks[-1]] - edges[marks[0]]) / (len(marks) - 1), marks


def refresh_chain_start(acc, cyc, strict=True):
    """RAS sample of the first refresh access of a line, or None.

    Refresh accesses are 128 cycles apart with the row address incrementing by
    one and the bank alternating; the gap before the first of a line is 472.

    Row and bank alone are not enough: in screen 5 a bitmap fetch can look like
    the next link of the chain, and a single false link moves the anchor by a
    refresh cell or by a whole line.  Refresh accesses are single /CAS, where a
    bitmap fetch is a burst, which rules those out.  (The column address is
    *not* constant along the chain -- it carries when the row counter wraps --
    so it cannot be used as a test.)  A handful of captures have no chain that
    passes, and fall back to the loose rule.
    """
    per = collections.Counter(a[1] for a in acc)
    ts = sorted(acc, key=lambda a: a[1])
    ref = set()
    for i, a in enumerate(ts):
        if strict and per[a[1]] != 1:
            continue
        for b in ts[i + 1:]:
            d = (b[1] - a[1]) * cyc
            if d > 131:
                break
            if strict and per[b[1]] != 1:
                continue
            if abs(d - 128) < 2.5 and \
               ((b[2] >> 8) & 0xFF) == (((a[2] >> 8) & 0xFF) + 1) & 0xFF and \
               (b[2] >> 16) != (a[2] >> 16):
                ref.add(a[1])
                ref.add(b[1])
    r = sorted(ref)
    starts = [t for i, t in enumerate(r)
              if i and (t - r[i - 1]) * cyc > 200]
    if not starts and strict:
        return refresh_chain_start(acc, cyc, strict=False)
    return (starts[0], ref) if starts else (None, ref)


def measure(vcd_dir, mode, limit=None):
    paths = sorted(glob.glob(os.path.join(vcd_dir, f'scr5-{mode}-*.vcd')))
    if limit:
        paths = paths[:limit]
    hist, periods, used = [], [], 0
    for p in paths:
        trace = parse_vcd(p)
        edges = ras_edges(trace)
        g = geometry(edges)
        if g is None:
            continue
        period, _ = g
        cyc = TICKS / period
        anchor, _ = refresh_chain_start(accesses(trace), cyc)
        if anchor is None:
            continue
        periods.append(period)
        used += 1
        hist.extend(((e - anchor) * cyc + REFRESH_CYCLE) % TICKS for e in edges)
    if not used:
        return None
    return hist, used, len(paths), statistics.fmean(periods)


def slots_near(hist, target, window=2.0):
    """Mean position of the RAS edges near 'target', unwrapped around it."""
    v = []
    for x in hist:
        d = ((x - target + TICKS / 2) % TICKS) - TICKS / 2
        if abs(d) < window:
            v.append(target + d)
    if not v:
        return None
    return statistics.fmean(v), (statistics.stdev(v) if len(v) > 1 else 0.0), len(v)


def cluster(hist, width=3.0):
    hist = sorted(hist)
    groups, cur = [], [hist[0]]
    for x in hist[1:]:
        if x - cur[-1] < width:
            cur.append(x)
        else:
            groups.append(cur)
            cur = [x]
    groups.append(cur)
    if groups[0][0] + TICKS - groups[-1][-1] < width:
        groups[0] = [x - TICKS for x in groups.pop()] + groups[0]
    return sorted((statistics.fmean(g) % TICKS, len(g)) for g in groups)


# --------------------------------------------------------------------------
def check_published(txt_dir, mode, hist, tol=0.5):
    """How many published access positions do not sit on a measured slot?

    A position is accepted when the mean of the RAS edges around it is within
    'tol' cycles of it; being one cycle off is a mismatch.
    """
    on_grid = {}

    def ok(c):
        if c not in on_grid:
            m = slots_near(hist, c, window=2.5)
            on_grid[c] = m is not None and abs(m[0] - c) <= tol
        return on_grid[c]

    bad, tot = collections.Counter(), 0
    for path in sorted(glob.glob(os.path.join(txt_dir, f'scr5-{mode}-*.txt'))):
        with open(path) as f:
            for ln in f:
                if ':' not in ln:
                    continue
                t = int(ln[:ln.index(':')])
                rest = ln[ln.index(':') + 1:]
                col = 0
                while rest:
                    if rest[2:13].strip():
                        tot += 1
                        c = (TICKS * col + t - 1) % TICKS   # CAS -> RAS
                        if not ok(c):
                            bad[c] += 1
                    rest = rest[13:]
                    col += 1
    return tot, bad


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    part2 = sys.argv[1]
    modes = [sys.argv[2]] if len(sys.argv) > 2 else ['dispOff', 'sprOff', 'sprOn']
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    for mode in modes:
        r = measure(os.path.join(part2, '1.vcd'), mode, limit)
        if r is None:
            print(f'{mode}: no usable captures')
            continue
        hist, used, tot, period = r
        print(f'=== {mode}: {used}/{tot} captures, line period {period:.3f} '
              f'samples, {len(hist)} RAS edges ===')
        cl = cluster(hist)
        med = statistics.median([n for _, n in cl])
        cl = [c for c in cl if c[1] > med * 0.15]
        pos = [round(c[0]) % TICKS for c in cl]
        gaps = collections.Counter((pos[(i + 1) % len(pos)] - p) % TICKS
                                  for i, p in enumerate(pos))
        print(f'  {len(pos)} slots per line; gaps ' +
              ' '.join(f'{k}x{v}' for k, v in sorted(gaps.items())) +
              f'  (sum {sum(k * v for k, v in gaps.items())})')
        # every openMSX slot, checked individually
        worst = (0, None)
        for s in OPENMSX[mode]:
            m = slots_near(hist, s)
            if m is None:
                print(f'  !! openMSX slot {s} has no RAS edge within 2 cycles')
                continue
            d = abs(m[0] - s)
            if d > worst[0]:
                worst = (d, (s, m))
        print(f'  all {len(OPENMSX[mode])} openMSX slots confirmed; worst '
              f'deviation {worst[0]:.3f} cycles'
              + (f' (slot {worst[1][0]}: measured {worst[1][1][0]:.3f}, '
                 f'sd {worst[1][1][1]:.2f}, n {worst[1][1][2]})'
                 if worst[1] else ''))
        n, bad = check_published(os.path.join(part2, '5.slots'), mode, hist)
        nb = sum(bad.values())
        print(f'  published .txt accesses off the measured grid: {nb} of {n} '
              f'({100.0 * nb / max(n, 1):.2f}%)')
        for c, k in bad.most_common(6):
            print(f'     RAS {c} (CAS {c + 1}) x{k}')


if __name__ == '__main__':
    main()
