"""mkws.py と同じく試験パッチを書き換え、HH だけを 20 打鳴らすパッチにする。リズム音の 6 スロットの波形は
0 1 2 3 を 4 巡、続けて 0 を 4 打。01h の b5 を立てる。

    py mkhh.py <作業用のディレクトリ>/patches/opl2.json      （OPL2EX なら opl2ex.json）

HH は雑音で打ごとの揺らぎが大きく、mkws.py の 1 打ずつでは決まらないことがある。
"""
import json
import shutil
import sys
from pathlib import Path

WS_REGS = [0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5]
SEQ = [0, 1, 2, 3] * 4 + [0] * 4


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
    assert len(lead) == 1
    bd = [c for c in chans if c.get('_comment', '').startswith('BD ')]
    hh = [c for c in chans if c.get('_comment', '').startswith('HH ')]
    assert len(bd) == 1 and len(hh) == 1
    bd_init = [w for w in bd[0]['init'] if not (0xE0 <= int(w['reg'], 16) <= 0xF5)]
    out = []
    for k, ws in enumerate(SEQ):
        init = list(bd_init) if k == 0 else []
        init += [{'reg': f'0x{r:02X}', 'val': f'0x{ws:X}'} for r in WS_REGS]
        out.append({'ch': 200 + k, '_comment': f'HH WS{ws} (hit {k})', 'init': init,
                    'key_on': hh[0]['key_on'], 'key_off': hh[0]['key_off']})
    chip['init'] = [w for w in chip.get('init', []) if int(w['reg'], 16) != 0x01] + \
                   [{'reg': '0x01', 'val': '0x20'}]
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: HH only, WS {SEQ} (mkhh.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} HH hits, WS {SEQ}')


if __name__ == '__main__':
    main()
