"""mkws.py と同じく試験パッチを書き換え、FB（C0h・C7h・C8h の b3-1）を 0 と 7 で切り替えて、旋律の ch0（対照）、TT、HH を鳴らす
パッチにする。リズム時の HH・TOM に FB が掛かるかを見る。

    py mkfb.py <作業用のディレクトリ>/patches/opl2.json      （OPL2EX なら opl2ex.json）

並び（lead の後。20 打）:
  対照 FB0 FB7 FB0 FB7（ch0。変調器だけを CON=1 で出し、キャリアは TL=63。EG-TYP=1 で鳴らし続ける）
  TT   FB0 FB7 を 4 回（C8h = 00h / 0Eh）
  HH   FB0 FB7 を 4 回（C7h = 01h / 0Fh。CON=1 は、Y8960 の HH が CON=0 で鳴らないため）
1 打目の init で、BD の init（リズム音の 6 スロットと ch6-8 の周波数）と ch0 を書き、BDh=20h でリズムを先に有効にする。
"""
import json
import shutil
import sys
from pathlib import Path

CH0 = [(0x20, 0x21), (0x40, 0x00), (0x60, 0xF0), (0x80, 0x0F), (0xE0, 0x00),
       (0x23, 0x21), (0x43, 0x3F), (0x63, 0xF0), (0x83, 0x0F), (0xE3, 0x00),
       (0xA0, 0x44)]
KEY_ON_CH0 = [(0xB0, 0x32)]
KEY_OFF_CH0 = [(0xB0, 0x12)]
SEQ = [('CTL', 0), ('CTL', 7)] * 2 + [('TT', 0), ('TT', 7)] * 4 + [('HH', 0), ('HH', 7)] * 4


def regs(pairs):
    return [{'reg': f'0x{r:02X}', 'val': f'0x{v:02X}'} for r, v in pairs]


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
    tt = [c for c in chans if c.get('_comment', '').startswith('TT ')]
    assert len(lead) == 1 and len(bd) == 1 and len(hh) == 1 and len(tt) == 1
    setup = list(bd[0]['init']) + regs(CH0 + [(0xC7, 0x01), (0xC8, 0x00), (0xBD, 0x20)])
    out = []
    if '--settle' in sys.argv:
        # Y8960 では、初期化の直後の打に、音より約 40dB 低い広い帯域の音が乗った。初期化だけの無音の区間を先に置く
        out.append({'ch': 499, '_comment': 'setup (silent)', 'init': setup, 'key_on': [], 'key_off': []})
    for k, (name, fb) in enumerate(SEQ):
        init = setup if k == 0 and not out else []
        if name == 'CTL':
            init += regs([(0xC0, (fb << 1) | 1)])
            on, off = regs(KEY_ON_CH0), regs(KEY_OFF_CH0)
        elif name == 'TT':
            init += regs([(0xC8, fb << 1)])
            on, off = tt[0]['key_on'], tt[0]['key_off']
        else:
            init += regs([(0xC7, (fb << 1) | 1)])
            on, off = hh[0]['key_on'], hh[0]['key_off']
        out.append({'ch': 500 + k, '_comment': f'{name} FB{fb}', 'init': init, 'key_on': on, 'key_off': off})
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: FB 0/7 on ch0 (control), TT, HH (mkfb.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} segments after the lead')


if __name__ == '__main__':
    main()
