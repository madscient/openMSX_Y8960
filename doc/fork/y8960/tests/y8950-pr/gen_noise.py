"""リズム音の雑音の並びを読み取るための音列を書く（tones.tcl の書式、MSX-AUDIO の I/O）。
    py gen_noise.py <出力ファイル>
ch7・ch8 の F-Num と BLOCK を 0 にすると、HH と CY のスロットの位相は 0 のまま動かず、rmXor は 0 になる。
そのとき SD の位相は 雑音 ? 100h : 000h（出力は最大か 0）、HH の位相は 雑音 ? 0D0h : 034h（出力は 0.957 か 0.316）で、
どちらの出力からも雑音のビットが 1 サンプルごとに読める。波形は 0、TL 10h（TL 0 では HH の 0.957 の側がチャンネルの録音の 16 ビットで飽和し、2 つの大きさを読み分けられなかった）、AR 15、DR 0、SL 0、持続。HH と SD を同時に 1.5 秒鳴らす。
"""
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0] if '/' in __file__ else '.')
from gen_seq import reg, wait, mark, MOD  # noqa: E402

out = []
reg(out, 0x01, 0x00)
reg(out, 0xBD, 0x20)
for ch in (7, 8):
    for s in (MOD[ch], MOD[ch] + 3):
        reg(out, 0x20 + s, 0x21)
        reg(out, 0x40 + s, 0x10)
        reg(out, 0x60 + s, 0xF0)
        reg(out, 0x80 + s, 0x0F)
    reg(out, 0xA0 + ch, 0x00)
    reg(out, 0xB0 + ch, 0x00)
    reg(out, 0xC0 + ch, 0x00)
mark(out, 'noise')
reg(out, 0xBD, 0x29)
wait(out, 1500)
reg(out, 0xBD, 0x20)
wait(out, 200)
reg(out, 0xBD, 0x00)
open(sys.argv[1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
