#!/usr/bin/env python3
"""カートリッジ版の拡張 XML から、本体内蔵版の構成を組み立てる。

  python doc/fork/y8960/tests/make-builtin-config.py <OPENMSX_USER_DATA にするディレクトリ>

`share/extensions/HRA_Y8960.xml` を読んで、`<dir>/extensions/HRA_Y8960.xml` に
本体内蔵版を書き出す。両版の違いはこのファイルが持つ 4 点だけであり、
**差分をここに実行可能な形で置いてあるので、手で書いた写しのように
カートリッジ版から取り残されることがない。**

本体内蔵版そのものはまだ無いので、これは試験用の構成である。実物では
SSGS が本体 PSG を置き換えるが、ここでは C-BIOS の PSG が A0h-A2h に残った
ままなので、**リードは重なって AND される**。SSGS の中身を見るときは
I/O ポートではなくデバッガブル (`debug read "Y8960 SSGS regs" ...`) を使うこと。
"""
import os
import sys
import xml.etree.ElementTree as ET

SOURCE = "share/extensions/HRA_Y8960.xml"
DOCTYPE = "<!DOCTYPE msxconfig SYSTEM 'msxconfig2.dtd'>"

# I/O イネーブラーを持つデバイスの型名
GATED = ("Y8960-OPLL", "Y8960-OPL2", "Y8960-SSGS", "Y8960-DCSG", "MSX-TIMER")


def set_child(parent, tag, text):
    child = parent.find(tag)
    if child is None:
        child = ET.SubElement(parent, tag)
    child.text = text


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out_dir = os.path.join(sys.argv[1], "extensions")
    os.makedirs(out_dir, exist_ok=True)

    tree = ET.parse(SOURCE)
    devices = tree.getroot().find("devices")

    for device in devices.iter():
        if device.tag in GATED:
            # 1. I/O イネーブラー無し（常時開）
            set_child(device, "use_io_enabler", "false")
        if device.tag == "Y8960-SSGS":
            # 2. リード可、3. GPIO 有り
            set_child(device, "readable", "true")
            set_child(device, "gpio", "true")
            # <io> が出力専用のままだと readIO() まで来ないので type を外す
            device.find("io").attrib.pop("type", None)
        if device.tag == "ROM" and device.findtext("mappertype") == "Y8960":
            # 4. メモリマップド I/O の窓ごと無し
            set_child(device, "use_mmio_tunnel", "false")

    path = os.path.join(out_dir, "HRA_Y8960.xml")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" ?>\n' + DOCTYPE + "\n")
        f.write(ET.tostring(tree.getroot(), encoding="unicode"))
        f.write("\n")
    print(path)


if __name__ == "__main__":
    main()
