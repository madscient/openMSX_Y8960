"""FitomHwIF の mkhw.py が作業用のディレクトリに書いた Y8950 / OPL2 の試験パッチを書き換え、リズム音の SD・CY・HH の
作り方を見分ける 12 打（rhymodel.HITS。6 打 × 2 巡）を鳴らすパッチにする。

    py mkform.py <作業用のディレクトリ>/patches/y8950.json      （OPL2 なら opl2.json）

打ごとに HH（11h）・SD（14h）・TC（15h）の MULT を替える。MULT の組は、今の openMSX の Y8950 の作り方と YM3812 の作り方
（Nuked-OPL3、openMSX の YMF262）で、線スペクトルの位置が違うように選んだ（rhymodel.py）。
  - SD-a / SD-b: YM3812 の形は HH のスロットの位相の bit8 から作るので HH の 2 倍の周波数、Y8950 の形は SD 自身の位相から作る
  - CY / HH の a と b: YM3812 の形は HH と TC のスロットの位相（MULT が効く）から作り、Y8950 の形は F-Num と BLOCK だけで回る
    別のカウンタから作る（MULT が効かない）
スロットは AR 15、DR 0、SL 0、持続（EG-TYP 1）で、鍵を押している間は大きさを保つ。FB 0、CON 1、波形 0。
mkhw.py が書いたものは *.mkhw.json として隣に残し、mkhw.py が延ばしたリード（ch 99）はそのまま使う。
"""
import json
import shutil
import sys
from pathlib import Path

import rhymodel as M

KEY = {'SD': 0x28, 'CY': 0x22, 'HH': 0x21}
SLOTS = [0x11, 0x12, 0x14, 0x15]   # HH、TT、SD、TC
# SPFM Light の RE1-Y8950 を TL 0 で録ると、SD の打（RMS -5dBFS）が録音でクリップした。線の位置は TL によらない
TL = 0x10


def w(reg, val):
    return {'reg': f'0x{reg:02X}', 'val': f'0x{val:02X}'}


def setup():
    out = [w(0xBD, 0x20)]
    for s in SLOTS:
        out += [w(0x20 + s, 0x21), w(0x40 + s, TL), w(0x60 + s, 0xF0), w(0x80 + s, 0x0F), w(0xE0 + s, 0x00)]
    for ch, (fnum, block) in ((7, M.F7), (8, M.F8)):
        out += [w(0xA0 + ch, fnum & 0xFF), w(0xB0 + ch, (block << 2) | (fnum >> 8)), w(0xC0 + ch, 0x01)]
    return out


def hit_writes(k, r):
    init = setup() if k == 0 else []
    return init + [w(0x31, 0x20 | r['m_hh']), w(0x34, 0x20 | r['m_sd']), w(0x35, 0x20 | r['m_tc'])]


def write_tones(path):
    # 同じ打を tones.tcl / tones-mga.ps1 の音列の書式で書く（openMSX の Y8950 で流して、模型の y8950 と比べるため）
    lines = ['# mkform.py --tones の出力。rhymodel.HITS を MSX-AUDIO の I/O C0h/C1h で鳴らす',
             'only MSXAUDIO mem 7FFF 01', 'io C0 01', 'io C1 00']
    for k, (snd, name, r) in enumerate(M.HITS):
        lines.append(f'# {name}')
        for x in hit_writes(k, r) + [w(0xBD, KEY[snd])]:
            lines += [f'io C0 {int(x["reg"], 16):02X}', f'io C1 {int(x["val"], 16):02X}']
        lines += [f'mark {name}', 'wait 800', 'io C0 BD', 'io C1 20', 'wait 200']
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{path}: {len(M.HITS)} hits')


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
    for k, (snd, name, r) in enumerate(M.HITS):
        init = hit_writes(k, r)
        out.append({'ch': 300 + k, '_comment': f'{name} (hit {k})', 'init': init,
                    'key_on': [w(0xBD, KEY[snd])], 'key_off': [w(0xBD, 0x20)]})
    chip['init'] = [x for x in chip.get('init', []) if int(x['reg'], 16) != 0x01] + [w(0x01, 0x00)]
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: SD/CY/HH generation forms, {len(out)} hits (mkform.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} hits after the lead: ' + ' '.join(h[1] for h in M.HITS))


if __name__ == '__main__':
    main()
