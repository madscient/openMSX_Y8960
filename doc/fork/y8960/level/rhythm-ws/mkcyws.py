"""FitomHwIF の mkhw.py が作業用のディレクトリに書いた OPL2 の試験パッチを書き換え、CY の位相の定数（Nuked-OPL3 の 080h か、
MAME・ymfm の 100h か）を見分ける打を鳴らすパッチにする。

    py mkcyws.py <作業用のディレクトリ>/patches/opl2.json
    py mkcyws.py --tones <出力ファイル>       （同じ打を tones.tcl の音列の書式で。openMSX の MSX-AUDIO の I/O で鳴らす）

CY の位相は rmXor で 2 値を取る。080h / 280h なら、波形 3 で両方とも正の同じ値（0.707）になり、出力は一定の直流になる。
100h / 300h なら、波形 3 で両方とも無音。交流で結んだ録音では、直流は鍵の入りと切りの一瞬の音として現れる。
1 巡は次の 4 打。これを ROUNDS 巡。
  CY-w0  波形 0。鳴る。巡の目印
  CY-w3  波形 3。対象。080h なら一瞬の音が 2 つ、100h なら無音
  SD-w3  波形 3。SD の位相 000h / 100h / 200h / 300h はどれも波形 3 で無音。鍵の操作だけで出る音を見る対照
  CY-w2  波形 2。080h でも 100h でも一定の直流（0.707 か 1.0）。一瞬の音の大きさの基準
最後の巡の後ろにも目印の CY-w0 を 1 打置く（どの巡も次の目印までの間隔から周期を取れるように）。
スロットは mkform.py と同じ（AR 15、DR 0、SL 0、RR 15、持続、MULT 1）で、TL は 0。鍵を押している間は大きさを保つ。
TL 10h・3 巡では、実物の YM3812 の録音で、直流の一瞬の音（2ms ほどで消える）が床の雑音から十分に出ず、判定が決まらなかった。
"""
import json
import shutil
import sys
from pathlib import Path

import rhymodel as M

ROUNDS = 5
NOTE_MS = 600
REST_MS = 1400
KEY = {'SD': 0x28, 'CY': 0x22}
SLOTS = [0x11, 0x12, 0x14, 0x15]   # HH、TT、SD、TC
TL = 0x00
HITS = [('CY', 0), ('CY', 3), ('SD', 3), ('CY', 2)]


def w(reg, val):
    return {'reg': f'0x{reg:02X}', 'val': f'0x{val:02X}'}


def setup():
    out = [w(0x01, 0x20), w(0xBD, 0x20)]
    for s in SLOTS:
        out += [w(0x20 + s, 0x21), w(0x40 + s, TL), w(0x60 + s, 0xF0), w(0x80 + s, 0x0F), w(0xE0 + s, 0x00)]
    for ch, (fnum, block) in ((7, M.F7), (8, M.F8)):
        out += [w(0xA0 + ch, fnum & 0xFF), w(0xB0 + ch, (block << 2) | (fnum >> 8)), w(0xC0 + ch, 0x01)]
    return out


def hits():
    out = []
    for r in range(ROUNDS):
        for snd, ws in HITS:
            out.append((f'{snd}-w{ws}', snd, ws, r))
    out.append(('CY-w0', 'CY', 0, ROUNDS))
    return out


def hit_writes(k, snd, ws):
    init = setup() if k == 0 else []
    slot = 0x14 if snd == 'SD' else 0x15
    return init + [w(0xE0 + slot, ws)]


def write_tones(path):
    lines = ['# mkcyws.py --tones の出力。MSX-AUDIO の I/O C0h/C1h で鳴らす（01h と E0h-F5h は Type::Y8960 だけが受ける）']
    for k, (name, snd, ws, r) in enumerate(hits()):
        lines.append(f'# {name} round {r}')
        for x in hit_writes(k, snd, ws) + [w(0xBD, KEY[snd])]:
            lines += [f'io C0 {int(x["reg"], 16):02X}', f'io C1 {int(x["val"], 16):02X}']
        lines += [f'mark {name}', f'wait {NOTE_MS}', 'io C0 BD', 'io C1 20', f'wait {REST_MS}']
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{path}: {len(hits())} hits')


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
    out = []
    for k, (name, snd, ws, r) in enumerate(hits()):
        out.append({'ch': 400 + k, '_comment': f'{name} (round {r})', 'init': hit_writes(k, snd, ws),
                    'key_on': [w(0xBD, KEY[snd])], 'key_off': [w(0xBD, 0x20)],
                    'note_ms': NOTE_MS, 'rest_ms': REST_MS})
    chip['init'] = [x for x in chip.get('init', []) if int(x['reg'], 16) != 0x01] + [w(0x01, 0x20)]
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: CY phase constant, {len(out)} hits (mkcyws.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} hits after the lead')


if __name__ == '__main__':
    main()
