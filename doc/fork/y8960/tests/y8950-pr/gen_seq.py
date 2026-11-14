"""回帰用の音列を tones.tcl の書式で書き出す。MSX-AUDIO の I/O（C0h/C1h）に書く。

    py gen_seq.py <出力先ディレクトリ>

書き出すもの
    mel.txt  : 楽音 9ch（MULT・FB・CON・AM・PM・KSR・KSL をばらす）、リズムの BD と TOM、ADPCM の再生。
               01h=20h と E0h-F5h の波形番号も書く（Type::Y8950 は無視するはず）
    rhy.txt  : リズムの SD・CY・HH（単独と重ね打ち、MULT を替える）
    y8960.txt: mel.txt の前に I/O Enabler2 を開く行を足したもの（フォークの HRA_Y8960 で同じ音を鳴らす）
"""
import sys
from pathlib import Path

MOD = [0, 1, 2, 8, 9, 10, 16, 17, 18]


def reg(out, r, v):
    out.append(f"io C0 {r:02X}")
    out.append(f"io C1 {v:02X}")


def wait(out, ms):
    out.append(f"wait {ms}")


def mark(out, label):
    out.append(f"mark {label}")


def melodic(out):
    reg(out, 0x01, 0x20)
    for i in range(0x16):
        reg(out, 0xE0 + i, (i * 3 + 1) & 3)
    reg(out, 0x08, 0x00)
    reg(out, 0xBD, 0xC0)
    for ch in range(9):
        m = MOD[ch]
        c = m + 3
        reg(out, 0x20 + m, ((ch & 1) << 7) | (((ch >> 1) & 1) << 6) | 0x20 | ((ch >= 4) << 4) | ((ch * 3 + 1) & 15))
        reg(out, 0x20 + c, ((ch % 3 == 0) << 7) | ((ch % 3 == 1) << 6) | 0x20 | ((ch & 1) << 4) | ((ch + 1) & 15))
        reg(out, 0x40 + m, ((ch & 3) << 6) | (0x10 + ch * 2))
        reg(out, 0x40 + c, (((ch + 1) & 3) << 6) | (4 + ch))
        reg(out, 0x60 + m, 0xF0 | (ch + 2))
        reg(out, 0x60 + c, 0xC0 | (ch + 3))
        reg(out, 0x80 + m, 0x24 + ch)
        reg(out, 0x80 + c, 0x35 + ch)
        reg(out, 0xC0 + ch, ((ch & 7) << 1) | (ch & 1))
        fnum = 0x157 + ch * 0x20
        block = 2 + ch % 4
        reg(out, 0xA0 + ch, fnum & 0xFF)
    mark(out, "mel-on")
    for ch in range(9):
        fnum = 0x157 + ch * 0x20
        block = 2 + ch % 4
        reg(out, 0xB0 + ch, 0x20 | (block << 2) | (fnum >> 8))
    wait(out, 400)
    for ch in range(9):
        fnum = 0x157 + ch * 0x20
        block = 2 + ch % 4
        reg(out, 0xB0 + ch, (block << 2) | (fnum >> 8))
    wait(out, 300)
    # 2 巡目: LFO の深さを浅く、ブロックを替え、波形選択を切る
    reg(out, 0xBD, 0x00)
    reg(out, 0x01, 0x00)
    mark(out, "mel2-on")
    for ch in range(9):
        fnum = 0x157 + ch * 0x20
        block = 1 + (ch * 2) % 7
        reg(out, 0xB0 + ch, 0x20 | (block << 2) | (fnum >> 8))
    wait(out, 300)
    for ch in range(9):
        reg(out, 0xB0 + ch, 0x00)
    wait(out, 300)


def rhythm_setup(out, m_hh, m_sd, m_tc, m_tom=2):
    # ch6: BD、ch7: HH(mod)/SD(car)、ch8: TOM(mod)/CY(car)
    for ch, mm, mc in ((6, 1, 2), (7, m_hh, m_sd), (8, m_tom, m_tc)):
        m = MOD[ch]
        c = m + 3
        reg(out, 0x20 + m, 0x00 | mm)
        reg(out, 0x20 + c, 0x00 | mc)
        reg(out, 0x40 + m, 0x10)
        reg(out, 0x40 + c, 0x14)
        reg(out, 0x60 + m, 0xF6)
        reg(out, 0x60 + c, 0xF5)
        reg(out, 0x80 + m, 0x47)
        reg(out, 0x80 + c, 0x46)
        reg(out, 0xC0 + ch, 0x0A if ch == 6 else 0x00)
    reg(out, 0xA6, 0x57)
    reg(out, 0xB6, 0x09)
    reg(out, 0xA7, 0x93)  # 659 = 0x293, block 5
    reg(out, 0xB7, (5 << 2) | 0x02)
    reg(out, 0xA8, 0x5F)  # 863 = 0x35F, block 5
    reg(out, 0xB8, (5 << 2) | 0x03)


def hit(out, label, bits, ms=250):
    mark(out, label)
    reg(out, 0xBD, 0x20 | bits)
    wait(out, ms)
    reg(out, 0xBD, 0x20)
    wait(out, 120)


def bd_tom(out):
    rhythm_setup(out, 1, 1, 1)
    hit(out, "BD", 0x10)
    hit(out, "TOM", 0x04)
    hit(out, "BD+TOM", 0x14)
    reg(out, 0xBD, 0x00)
    wait(out, 100)


def sd_cy_hh(out):
    for (mh, ms_, mt) in ((1, 3, 1), (2, 1, 1), (1, 1, 4), (4, 1, 1), (3, 5, 2)):
        rhythm_setup(out, mh, ms_, mt)
        tag = f"{mh}{ms_}{mt}"
        hit(out, "SD" + tag, 0x08)
        hit(out, "CY" + tag, 0x02)
        hit(out, "HH" + tag, 0x01)
    hit(out, "ALL", 0x1F, 400)
    # 打っている間に AM と PM を掛ける
    reg(out, 0xBD, 0xE0)
    hit(out, "ALL-LFO", 0x1F | 0xC0, 400)
    reg(out, 0xBD, 0x00)
    wait(out, 100)


def adpcm(out):
    reg(out, 0x07, 0x01)
    reg(out, 0x08, 0x00)
    reg(out, 0x09, 0x00)
    reg(out, 0x0A, 0x00)
    reg(out, 0x0B, 0x1F)  # 32 単位 = 128 バイト
    reg(out, 0x0C, 0x00)
    reg(out, 0x07, 0x60)
    x = 0x35
    for _ in range(128):
        x = (x * 73 + 41) & 0xFF
        reg(out, 0x0F, x)
    reg(out, 0x07, 0x01)
    reg(out, 0x10, 0x00)
    reg(out, 0x11, 0x20)
    reg(out, 0x12, 0xC0)
    mark(out, "adpcm")
    reg(out, 0x07, 0xA0)
    wait(out, 300)
    reg(out, 0x07, 0x01)
    wait(out, 50)


def write(path, out):
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    d = Path(sys.argv[1])
    d.mkdir(parents=True, exist_ok=True)
    mel = []
    melodic(mel)
    bd_tom(mel)
    adpcm(mel)
    write(d / "mel.txt", mel)
    rhy = []
    sd_cy_hh(rhy)
    write(d / "rhy.txt", rhy)
    write(d / "y8960.txt", ["mem 7FFF 01"] + mel)


if __name__ == '__main__':
    main()
