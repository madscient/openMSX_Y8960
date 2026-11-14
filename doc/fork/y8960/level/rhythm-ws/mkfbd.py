"""mkfb.py と同じく試験パッチを書き換え、旋律の ch0 の変調器だけ（CON=1）を FB と TL を変えて鳴らす。FB の深さと、
2 つ前までの出力の和が溢れるかを、倍音の形で見る。

    py mkfbd.py <作業用のディレクトリ>/patches/opl2.json      （OPL2EX なら opl2ex.json）

並び（lead と、初期化だけの無音の 1 区間の後。24 打。どれも 440Hz、800ms 鳴らして 200ms 休む）:
  CAL  MULT 1-8、FB0、TL0（周波数特性を測る正弦波。MULT 1 は TL0 の FB0 を兼ねる）
  TL0  FB 1-7
  TL12 FB 0-7（変調器の出力が -9dB。2 つの出力の和は 13 ビットに収まる）
  CAL  MULT 1 の繰り返し（回の中のずれを見る）
キャリアは AR=0 で鳴らさない。EG-TYP=1、AR=15、DR=0、SL=0 で、鍵を押している間は TL の大きさで鳴り続ける。
"""
import json
import shutil
import sys
from pathlib import Path

SEQ = ([('CAL', m, 0, 0) for m in range(1, 9)]
       + [('TL0', 1, fb, 0) for fb in range(1, 8)]
       + [('TL12', 1, fb, 12) for fb in range(0, 8)]
       + [('CAL', 1, 0, 0)])


def regs(pairs):
    return [{'reg': f'0x{r:02X}', 'val': f'0x{v:02X}'} for r, v in pairs]


def tone_regs(mult, fb, tl):
    return [(0x20, 0x20 | mult), (0x40, tl), (0xC0, (fb << 1) | 1)]


SETUP = [(0xBD, 0x00),
         (0x60, 0xF0), (0x80, 0x0F), (0xE0, 0x00),
         (0x23, 0x21), (0x43, 0x3F), (0x63, 0x00), (0x83, 0x0F), (0xE3, 0x00),
         (0xA0, 0x44), (0xB0, 0x12)]


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
    out = [{'ch': 499, '_comment': 'setup (silent)', 'init': regs(SETUP + tone_regs(1, 0, 0)),
            'key_on': [], 'key_off': []}]
    for k, (name, mult, fb, tl) in enumerate(SEQ):
        out.append({'ch': 500 + k, '_comment': f'{name} MULT{mult} FB{fb} TL{tl}',
                    'init': regs(tone_regs(mult, fb, tl)),
                    'key_on': regs([(0xB0, 0x32)]), 'key_off': regs([(0xB0, 0x12)])})
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: ch0 modulator only, FB 0-7 at TL 0 and 12, MULT 1-8 calibration (mkfbd.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} segments after the lead')


if __name__ == '__main__':
    main()
