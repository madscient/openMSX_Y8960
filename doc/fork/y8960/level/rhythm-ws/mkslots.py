"""電源投入の直後に、鍵を押していないのに音の出る位置にある EG のスロットを数えるパッチ。

    py mkslots.py <RUN>/patches/opl2ex.json

並び（lead の後。区間は 800ms + 200ms。書き込みは区間の頭）:
  待つ 2 区間 → BDh=20h（HH・SD の雑音を合図にする）→ BDh=00h（旋律に戻すと F-Num 0 で直流になり静かになる）と 1 区間
  → ch0-8 を 1 つずつ: 前のチャンネルの F-Num を 0 に戻し、このチャンネルを CON 1・変調器 MULT 1・キャリア MULT 2・F-Num 244h・
    ブロック 4（鍵は押さない）にして 1 区間 → 最後のチャンネルの F-Num を 0 に戻して 1 区間
  → 終わりの合図: ch0 を AR 15・SL 15・RR 15 にして鍵で鳴らし（F-Num 200h、388Hz と 777Hz）、1 区間
ch0-8 を測る間は、鍵を押す書き込みも、AR・DR・SL・RR・TL の書き込みもしないので、EG の状態は電源投入（実チップではリセット）の直後のまま。
変調器が鳴る位置にあれば 440Hz、キャリアなら 880Hz に線が立つ。実チップは BDh=20h で雑音が出ないので、anaslots.py は終わりの合図から
逆算して窓を置く。
"""
import json
import shutil
import sys
from pathlib import Path

MOD = [0x00, 0x01, 0x02, 0x08, 0x09, 0x0A, 0x10, 0x11, 0x12]
FNUM, BLOCK = 0x244, 4


def w(r, v):
    return {'reg': f'0x{r:02X}', 'val': f'0x{v:02X}'}


def main():
    path = Path(sys.argv[1])
    keep = path.with_suffix('.mkhw.json')
    if not keep.exists():
        shutil.copy2(path, keep)
    src = json.loads(keep.read_text(encoding='utf-8'))
    (chip_name, chip), = src['chips'].items()
    lead = [c for c in chip['channels'] if c.get('ch') == 99]
    assert len(lead) == 1
    out = []

    def seg(comment, init):
        out.append({'ch': 800 + len(out), '_comment': comment, 'init': init, 'key_on': [], 'key_off': []})

    seg('wait', [])
    seg('wait', [])
    seg('rhythm on (marker)', [w(0xBD, 0x20)])
    seg('rhythm off', [w(0xBD, 0x00)])
    seg('hold', [])
    for c in range(9):
        init = [w(0xA0 + c - 1, 0x00), w(0xB0 + c - 1, 0x00)] if c else []
        init += [w(0x20 + MOD[c], 0x01), w(0x23 + MOD[c], 0x02), w(0xC0 + c, 0x01),
                 w(0xA0 + c, FNUM & 0xFF), w(0xB0 + c, (BLOCK << 2) | (FNUM >> 8))]
        seg(f'ch{c} F-Num on (no key)', init)
        seg('hold', [])
    seg('ch8 F-Num off', [w(0xA8, 0x00), w(0xB8, 0x00)])
    seg('hold', [])
    # 終わりの合図: 測り終えた ch0 を鍵で鳴らす（実チップでは BDh=20h の雑音が出ないので、窓はここから逆算する）
    out.append({'ch': 800 + len(out), '_comment': 'end marker: ch0 key on',
                # SL 15: SL 0 だと EG-TYP 0 の音色はアタックの直後に RR 15 で消え、合図が一瞬の音になった
                # A0h は ch1 に移るときに 0 に戻しているので、合図は F-Num 200h で鳴る（anaslots.py もこの値で測る）
                'init': [w(0x60, 0xF0), w(0x63, 0xF0), w(0x80, 0xFF), w(0x83, 0xFF)],
                'key_on': [w(0xB0, 0x20 | (BLOCK << 2) | (FNUM >> 8))],
                'key_off': [w(0xB0, (BLOCK << 2) | (FNUM >> 8))]})
    seg('hold', [])
    chip['init'] = [x for x in chip.get('init', []) if int(x['reg'], 16) != 0x01]
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: which slots sit at an audible EG level after power-on (mkslots.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} segments after the lead')


if __name__ == '__main__':
    main()
