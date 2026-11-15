"""電源投入の直後の雑音が、リズムのどのスロットから出るかを見るパッチ。

    py mkleak.py <RUN>/patches/opl2ex.json tl|rr

並び（lead の後。区間は 800ms + 200ms。書き込みは区間の頭）:
  待つ 2 区間 → BDh=20h とその後 1 区間 → HH・SD・TT・CY の順に 1 スロットずつ黙らせ、それぞれその後 1 区間
  → 4 スロットとも TL 63・RR 15 にしてその後 1 区間
  tl: 黙らせるのは TL 63（40h+オフセット）だけ。rr: RR 15（80h+オフセット、SL 0）だけ
"""
import json
import shutil
import sys
from pathlib import Path

SLOTS = [('HH', 0x11), ('SD', 0x14), ('TT', 0x12), ('CY', 0x15)]


def w(r, v):
    return {'reg': f'0x{r:02X}', 'val': f'0x{v:02X}'}


path = Path(sys.argv[1])
mode = sys.argv[2]
assert mode in ('tl', 'rr')
keep = path.with_suffix('.mkhw.json')
if not keep.exists():
    shutil.copy2(path, keep)
src = json.loads(keep.read_text(encoding='utf-8'))
(chip_name, chip), = src['chips'].items()
lead = [c for c in chip['channels'] if c.get('ch') == 99]
assert len(lead) == 1
out = []


def seg(comment, init):
    out.append({'ch': 700 + len(out), '_comment': comment, 'init': init, 'key_on': [], 'key_off': []})


seg('wait', [])
seg('wait', [])
seg('rhythm on (BDh=20h)', [w(0xBD, 0x20)])
seg('hold', [])
for name, off in SLOTS:
    seg(f'{mode} {name}', [w(0x40 + off, 0x3F)] if mode == 'tl' else [w(0x80 + off, 0x0F)])
    seg('hold', [])
seg('all quiet (TL63, RR15)', [w(r + off, v) for _, off in SLOTS for r, v in ((0x40, 0x3F), (0x80, 0x0F))])
seg('hold', [])
chip['init'] = [x for x in chip.get('init', []) if int(x['reg'], 16) != 0x01]
chip['channels'] = lead + out
chip['_comment'] = f'{chip_name}: which rhythm slot leaks noise after power-on, quieting by {mode} (mkleak.py)'
path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'{path}: {len(out)} segments after the lead')
