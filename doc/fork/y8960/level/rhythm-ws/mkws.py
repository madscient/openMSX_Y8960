"""FitomHwIF の mkhw.py が作業用のディレクトリに書いた OPL2 / OPL2EX の試験パッチを書き換え、リズム音の 6 スロットの
波形を 0、1、2、3、0 と変えながら 5 つのリズム音を鳴らすパッチにする。01h の b5（波形選択の許可）を立てる。

    py mkws.py <作業用のディレクトリ>/patches/opl2.json      （OPL2EX なら opl2ex.json）

mkhw.py が書いたものは *.mkhw.json として隣に残し、mkhw.py が延ばしたリード（ch 99）はそのまま使う。
"""
import json
import shutil
import sys
from pathlib import Path

WS_SEQ = [0, 1, 2, 3, 0]
INSTR = ['BD', 'SD', 'TT', 'CY', 'HH']
# リズム音のスロットの E0h + オペレータの番地: ch6 10h/13h、ch7 11h/14h、ch8 12h/15h
WS_REGS = [0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5]


def is_ws_reg(w):
    v = int(w['reg'], 16)
    return 0xE0 <= v <= 0xF5


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
    assert len(lead) == 1, 'lead (ch 99) must appear exactly once'
    rhythm = {}
    for c in chans:
        for name in INSTR:
            if c.get('_comment', '').startswith(name + ' '):
                rhythm[name] = c
    assert sorted(rhythm) == sorted(INSTR), f'rhythm entries found: {sorted(rhythm)}'
    # 元のパッチでは、BD の init がリズム音の 3 チャンネルをまとめて設定し、ほかの 4 音の init は空
    bd_init = [w for w in rhythm['BD']['init'] if not is_ws_reg(w)]
    for name in INSTR[1:]:
        assert rhythm[name]['init'] == [], f'{name} has its own init'

    out = []
    first = True
    for k, ws in enumerate(WS_SEQ):
        for i, name in enumerate(INSTR):
            init = list(bd_init) if first else []
            first = False
            init += [{'reg': f'0x{r:02X}', 'val': f'0x{ws:X}'} for r in WS_REGS]
            out.append({'ch': 100 + 10 * k + i,
                        '_comment': f'{name} WS{ws} (pass {k})',
                        'init': init,
                        'key_on': rhythm[name]['key_on'],
                        'key_off': rhythm[name]['key_off']})
    chip['init'] = [w for w in chip.get('init', []) if int(w['reg'], 16) != 0x01] + \
                   [{'reg': '0x01', 'val': '0x20'}]
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: rhythm sounds with WS {WS_SEQ} on all six rhythm slots (mkws.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} segments after the lead, WS {WS_SEQ} x {INSTR}')


if __name__ == '__main__':
    main()
