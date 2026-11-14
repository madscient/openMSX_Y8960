"""mkws.py と同じく試験パッチを書き換え、HH の打ごとに C7h（HH・SD のチャンネルの FB と CON）を切り替えるパッチにする。
HH の間に TT を挟み、位置合わせの目印にする（TT は CON によらず鳴る）。

    py mkcon.py <作業用のディレクトリ>/patches/opl2ex.json [--rhy-first]

並び（lead の後）:
  0: HH  init = BD の init + C7h=00h。BDh の最初の書き込みが HH の鍵（21h）になる（mkwse.py の 1 打目と同じ条件）
  1: TT
  2: HH  C7h=00h / 3: TT / 4: HH  C7h=01h / 5: TT / ... を 00h と 01h の交互で 8 回
  17: TT

--rhy-first は、打 0 の前に BDh=20h（鍵を立てずにリズムだけを有効にする）の区間を置く。打 0 は BDh の 2 回目の書き込みになる。
"""
import json
import shutil
import sys
from pathlib import Path

C7_SEQ = [0x00, 0x01] * 4


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

    def seg(k, name, src_ch, init):
        return {'ch': 400 + k, '_comment': name, 'init': init,
                'key_on': src_ch['key_on'], 'key_off': src_ch['key_off']}

    if '--rhy-first' in sys.argv:
        rhy = {'ch': 399, '_comment': 'rhythm on, no key', 'init': list(bd[0]['init']) + [{'reg': '0xC7', 'val': '0x00'}],
               'key_on': [{'reg': '0xBD', 'val': '0x20'}], 'key_off': [{'reg': '0xBD', 'val': '0x20'}]}
        out = [rhy, seg(0, 'HH C7h=00h (after rhythm on)', hh[0], [{'reg': '0xC7', 'val': '0x00'}])]
    else:
        out = [seg(0, 'HH C7h=00h (first BDh write)', hh[0], list(bd[0]['init']) + [{'reg': '0xC7', 'val': '0x00'}])]
    k = 1
    for c7 in C7_SEQ:
        out.append(seg(k, 'TT anchor', tt[0], []))
        k += 1
        out.append(seg(k, f'HH C7h={c7:02X}h', hh[0], [{'reg': '0xC7', 'val': f'0x{c7:02X}'}]))
        k += 1
    out.append(seg(k, 'TT anchor', tt[0], []))
    chip['channels'] = lead + out
    chip['_comment'] = f'{chip_name}: HH with C7h per hit, TT anchors (mkcon.py)'
    path.write_text(json.dumps(src, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{path}: {len(out)} segments after the lead')


if __name__ == '__main__':
    main()
