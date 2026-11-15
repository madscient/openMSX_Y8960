"""mkfb.py と同じく試験パッチを書き換え、リズム時の BD が C6h の CON（b0）で FM を止めるか、変調器を出力に足すかを見る
パッチにする。対照に旋律の ch0 を同じ音色で鳴らす。

    py mkbd.py <作業用のディレクトリ>/patches/opl2.json      （Y8950 は y8950.json、OPL2EX は opl2ex.json）
    py mkbd.py --tones <出力先>/bd.txt                      （同じ打を tones.tcl の音列で書く。openMSX で鳴らす）

並び（lead と、初期化だけの無音の 1 区間の後。16 打。800ms 鳴らして 200ms 休む）:
  CTL CON0、CTL CON1、BD CON0、BD CON1 を 4 回（CTL は ch0 を B0h で、BD は BDh で鍵を押す）

音色は ch0 と ch6 で同じ。基本の周波数 f はブロック 3・F-num 250h（3.579545MHz で 224.5Hz）。
  キャリア: MULT 2（2f）、TL 16、変調器: MULT 3（3f）、TL 32（FM の深さは約 1.6 rad）、FB 0
  どちらも AR 15、DR 0、SL 15、RR 8、EG-TYP 1。DR 0 なので減衰が進まず、リズム時に持続が無くても鍵を押している間は鳴り続ける
線の出どころ:
  キャリアだけ        : 2f
  キャリアに FM       : 2f ± 3kf → f, 2f, 4f, 5f, 7f, 8f。3f の倍数には立たない
  変調器が出力に混ざる: 3f
"""
import json
import shutil
import sys
from pathlib import Path

SEQ = [('CTL', 0), ('CTL', 1), ('BD', 0), ('BD', 1)] * 4
BLOCK, FNUM = 3, 0x250
NOTE_MS, REST_MS = 800, 200


def w(r, v):
    return {'reg': f'0x{r:02X}', 'val': f'0x{v:02X}'}


def ops(mod, car):
    # mod・car は演算子のレジスタのオフセット（ch0 は 00h・03h、ch6 は 10h・13h）
    return [(0x20 + mod, 0x23), (0x20 + car, 0x22),
            (0x40 + mod, 0x20), (0x40 + car, 0x10),
            (0x60 + mod, 0xF0), (0x60 + car, 0xF0),
            (0x80 + mod, 0xF8), (0x80 + car, 0xF8)]


B_OFF = (BLOCK << 2) | (FNUM >> 8)
# Y8960 v0.9.16 は電源投入の直後、鍵を押していないスロットが RR 0 のまま鳴る位置に残り、リズムを有効にすると HH・SD・CY が
# -11dBFS ほどの雑音になった。使わない 4 スロット（HH 11h、TT 12h、SD 14h、CY 15h）を TL 63・RR 15 にして先に黙らせる
QUIET = [(r + off, v) for off in (0x11, 0x12, 0x14, 0x15) for r, v in ((0x40, 0x3F), (0x80, 0x0F))]
SETUP = ([(0x01, 0x00)] + QUIET + [(0xBD, 0x20)] + ops(0x00, 0x03) + ops(0x10, 0x13)
         + [(0xC0, 0x00), (0xC6, 0x00),
            (0xA0, FNUM & 0xFF), (0xB0, B_OFF), (0xA6, FNUM & 0xFF), (0xB6, B_OFF)])


def hit(name, con):
    if name == 'CTL':
        return [(0xC0, con)], [(0xB0, 0x20 | B_OFF)], [(0xB0, B_OFF)]
    return [(0xC6, con)], [(0xBD, 0x30)], [(0xBD, 0x20)]


def write_tones(path):
    # HRA_Y8960 の拡張は、I/O Enabler2（7FFFh の b0）で C0h/C1h を開けないと OPL2 に届かない
    lines = ['# mkbd.py --tones の出力。MSX-AUDIO の I/O C0h/C1h で鳴らす（01h は Type::Y8960 だけが受ける）',
             'only Y8960 mem 7FFF 01']

    def io(pairs):
        for r, v in pairs:
            lines.extend([f'io C0 {r:02X}', f'io C1 {v:02X}'])
    io(SETUP)
    lines.append(f'wait {NOTE_MS + REST_MS}')
    for name, con in SEQ:
        init, on, off = hit(name, con)
        lines.append(f'# {name} CON{con}')
        io(init + on)
        lines.extend([f'mark {name}{con}', f'wait {NOTE_MS}'])
        io(off)
        lines.append(f'wait {REST_MS}')
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{path}: {len(SEQ)} hits')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.argv[1] == '--tones':
        write_tones(sys.argv[2])
        return
    path = Path(sys.argv[1])
    keep = path.with_suffix('.mkhw.json')
    if not keep.exists():
        shutil.copy2(path, keep)
    src = json.loads(keep.read_text(encoding='utf-8'))
    (chip_name, chip), = src['chips'].items()
    lead = [c for c in chip['channels'] if c.get('ch') == 99]
    assert len(lead) == 1, 'lead (ch 99) must appear exactly once'
    out = [{'ch': 499, '_comment': 'setup (silent)', 'init': [w(r, v) for r, v in SETUP],
            'key_on': [], 'key_off': []}]
    for k, (name, con) in enumerate(SEQ):
        init, on, off = hit(name, con)
        out.append({'ch': 500 + k, '_comment': f'{name} CON{con}', 'init': [w(*x) for x in init],
                    'key_on': [w(*x) for x in on], 'key_off': [w(*x) for x in off]})
    chip['init'] = [x for x in chip.get('init', []) if int(x['reg'], 16) != 0x01] + [w(0x01, 0x00)]
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: BD with C6h CON 0/1 and ch0 as control (mkbd.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} segments after the lead')


if __name__ == '__main__':
    main()
