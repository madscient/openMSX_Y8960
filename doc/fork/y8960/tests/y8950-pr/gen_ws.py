"""リズム音の波形選択を符号で見る音列。
    py gen_ws.py <出力ファイル>
01h=20h で波形 0、波形 1（半波）、01h=00h で波形番号 1 のまま、の 3 通りで BD・SD・TOM・CY・HH を 1 打ずつ鳴らす。
mark は <場合>-<音>。波形 1 が掛かれば、その音の出力に負の値が出ない。
"""
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0] if '/' in __file__ else '.')
from gen_seq import reg, wait, mark, rhythm_setup  # noqa: E402


def hit(out, label, bits):
    mark(out, label)
    reg(out, 0xBD, 0x20 | bits)
    wait(out, 250)
    reg(out, 0xBD, 0x20)
    wait(out, 150)


out = []
rhythm_setup(out, 1, 3, 2)
for case, r01, ws in (('w0', 0x20, 0), ('w1', 0x20, 1), ('off', 0x00, 1)):
    reg(out, 0x01, r01)
    for r in range(0xF0, 0xF6):
        reg(out, r, ws)
    for name, bits in (('BD', 0x10), ('SD', 0x08), ('TOM', 0x04), ('CY', 0x02), ('HH', 0x01)):
        hit(out, f'{case}-{name}', bits)
reg(out, 0xBD, 0x00)
open(sys.argv[1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
