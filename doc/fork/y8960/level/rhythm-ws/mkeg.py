"""mkfbd.py と同じく試験パッチを書き換え、旋律の ch0 の変調器だけ（CON=1、FB0）で、減衰（DR）とリリース（RR）の速さを測る
パッチにする。

    py mkeg.py <作業用のディレクトリ>/patches/opl2.json      （OPL2EX なら opl2ex.json）

並び（lead と、初期化だけの無音の 1 区間の後。13 打、どれも 1 打 1000ms）:
  A: ブロック 1、F-num 1FFh、MULT 10（484.6Hz）、KSR=0。ksn = 2 で、実物も JTOPL も速さに足す分が 0
     減衰 DR 3・5・7・9・11・12（800ms 鳴らす）、リリース RR 5・7・9（300ms 鳴らして離す）
  B: ブロック 4、F-num 244h、MULT 1（440Hz）。ksn = 9
     減衰 KSR=1 の DR 4・6、KSR=0 の DR 6、リリース KSR=1 の RR 5
減衰は AR=15、SL=15、EG-TYP=1。リリースは AR=15、DR=0、SL=0、EG-TYP=1 で鳴らし続けてから離す。キャリアは AR=0 で鳴らさない。
"""
import json
import shutil
import sys
from pathlib import Path

A = dict(block=1, fnum=0x1FF, mult=10)
B = dict(block=4, fnum=0x244, mult=1)
TESTS = ([dict(A, name=f'A-D{r}', kind='D', r=r, ksr=0) for r in (3, 5, 7, 9, 11, 12)]
         + [dict(A, name=f'A-R{r}', kind='R', r=r, ksr=0) for r in (5, 7, 9)]
         + [dict(B, name='B-K1-D4', kind='D', r=4, ksr=1), dict(B, name='B-K1-D6', kind='D', r=6, ksr=1),
            dict(B, name='B-K0-D6', kind='D', r=6, ksr=0), dict(B, name='B-K1-R5', kind='R', r=5, ksr=1)])

SETUP = [(0xBD, 0x00), (0xE0, 0x00), (0xC0, 0x01),
         (0x23, 0x21), (0x43, 0x3F), (0x63, 0x00), (0x83, 0x0F), (0xE3, 0x00),
         (0x20, 0x21), (0x40, 0x00), (0x60, 0xF0), (0x80, 0xFF), (0xA0, 0x44), (0xB0, 0x12)]


def regs(pairs):
    return [{'reg': f'0x{r:02X}', 'val': f'0x{v:02X}'} for r, v in pairs]


def test_regs(t):
    op20 = 0x20 | (t['ksr'] << 4) | t['mult']
    if t['kind'] == 'D':
        ar_dr, sl_rr = 0xF0 | t['r'], 0xFF
    else:
        ar_dr, sl_rr = 0xF0, t['r']
    b0 = (t['block'] << 2) | (t['fnum'] >> 8)
    return [(0x20, op20), (0x40, 0x00), (0x60, ar_dr), (0x80, sl_rr), (0xA0, t['fnum'] & 0xFF), (0xB0, b0)], b0


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    path = Path(sys.argv[1])
    keep = path.with_suffix('.mkhw.json')
    if not keep.exists():
        shutil.copy2(path, keep)
    src = json.loads(keep.read_text(encoding='utf-8'))
    (chip_name, chip), = src['chips'].items()
    lead = [c for c in chip['channels'] if c.get('ch') == 99]
    assert len(lead) == 1
    out = [{'ch': 499, '_comment': 'setup (silent)', 'init': regs(SETUP), 'key_on': [], 'key_off': []}]
    for k, t in enumerate(TESTS):
        init, b0 = test_regs(t)
        seg = {'ch': 500 + k, '_comment': t['name'], 'init': regs(init),
               'key_on': regs([(0xB0, 0x20 | b0)]), 'key_off': regs([(0xB0, b0)])}
        if t['kind'] == 'R':
            seg['note_ms'], seg['rest_ms'] = 300, 700
        out.append(seg)
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: ch0 modulator only, decay and release rates (mkeg.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} segments after the lead')


if __name__ == '__main__':
    main()
