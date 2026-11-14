"""mkws.py と同じく試験パッチを書き換え、HH だけを 16 打鳴らすパッチにする。打ごとに 01h を
00h を 4 打、20h を 4 打、00h を 4 打、20h を 4 打と切り替える。波形はずっと 0。

    py mkwse.py <作業用のディレクトリ>/patches/opl2ex.json

01h の b5（波形選択の許可）が HH の発音に関わるかを切り分ける。
"""
import json
import shutil
import sys
from pathlib import Path

WS_REGS = [0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5]
SEQ = [0x00] * 4 + [0x20] * 4 + [0x00] * 4 + [0x20] * 4


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    path = Path(sys.argv[1])
    keep = path.with_suffix('.mkhw.json')
    if not keep.exists():
        shutil.copy2(path, keep)
    src = json.loads(keep.read_text(encoding='utf-8'))
    (chip_name, chip), = src['chips'].items()
    chans = chip['channels']
    lead = [c for c in chans if c.get('ch') == 99]
    bd = [c for c in chans if c.get('_comment', '').startswith('BD ')]
    hh = [c for c in chans if c.get('_comment', '').startswith('HH ')]
    assert len(lead) == 1 and len(bd) == 1 and len(hh) == 1
    bd_init = [w for w in bd[0]['init'] if not (0xE0 <= int(w['reg'], 16) <= 0xF5)]
    out = []
    for k, r01 in enumerate(SEQ):
        init = list(bd_init) if k == 0 else []
        init += [{'reg': f'0x{r:02X}', 'val': '0x0'} for r in WS_REGS]
        init.append({'reg': '0x01', 'val': f'0x{r01:02X}'})
        out.append({'ch': 300 + k, '_comment': f'HH 01h={r01:02X}h (hit {k})', 'init': init,
                    'key_on': hh[0]['key_on'], 'key_off': hh[0]['key_off']})
    chip['init'] = [w for w in chip.get('init', []) if int(w['reg'], 16) != 0x01] + \
                   [{'reg': '0x01', 'val': '0x00'}]
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: HH only, 01h per hit {[hex(x) for x in SEQ]} (mkwse.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} HH hits, 01h {[hex(x) for x in SEQ]}')


if __name__ == '__main__':
    main()
