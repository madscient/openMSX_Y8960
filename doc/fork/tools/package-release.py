#!/usr/bin/env python3
"""リリース用の Windows バイナリ zip を作る。

  py doc/fork/tools/package-release.py <タグ名>

リポジトリのルートで、x64 Release のビルドを済ませてから走らせる。
出力は derived/x64-VC-Release/package-windows/openmsx-<タグ名>-windows-vc-x64-bin.zip。

upstream の packagezip.py をそのまま使い、足りないものだけ後から足す。
upstream の配布物にはルートの README が入らないが、このフォークでは
README に CC BY-SA の帰属表示があるので、再配布物から落とせない。
"""
import os
import subprocess
import sys
import zipfile

PLATFORM = "x64"
CONFIGURATION = "Release"

# 配布物に入ってはいけないもの。開発者と AI 向けの文書で、利用者には要らない
FORBIDDEN_PREFIXES = ("CLAUDE.md", "doc/fork/")
# 入っていなければならないもの
REQUIRED = ("README.txt", "openmsx.exe", "share/extensions/HRA_Y8960.xml",
            "doc/GPL.txt")


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    tag = sys.argv[1]

    sys.path.insert(0, "build")
    sys.path.insert(0, "build/package-windows")
    from packagewindows import PackageInfo
    info = PackageInfo(PLATFORM, CONFIGURATION, "NOCATAPULT")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (env.get("PYTHONPATH"), "build") if p)
    subprocess.run(
        [sys.executable, "build/package-windows/packagezip.py",
         PLATFORM, CONFIGURATION, "NOCATAPULT"],
        env=env, check=True)

    src = os.path.join(info.packagePath, info.packageFileName + "-bin.zip")
    dst = os.path.join(info.packagePath,
                       f"openmsx-{tag}-windows-vc-x64-bin.zip")
    if os.path.exists(dst):
        os.unlink(dst)

    # upstream の名前は git describe 由来で、fork のタグを反映しないので付け替える
    with zipfile.ZipFile(src) as zin, \
            zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.write("README", "README.txt")
    os.unlink(src)

    with zipfile.ZipFile(dst) as z:
        names = [n.replace("\\", "/") for n in z.namelist()]
    ok = True
    for n in names:
        if n.startswith(FORBIDDEN_PREFIXES):
            print(f"NG 入ってはいけないもの: {n}", file=sys.stderr)
            ok = False
    for r in REQUIRED:
        if r not in names:
            print(f"NG 入っていない: {r}", file=sys.stderr)
            ok = False
    if not ok:
        os.unlink(dst)
        return 1
    print(f"OK {dst} ({len(names)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
