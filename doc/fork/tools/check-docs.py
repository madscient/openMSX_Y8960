#!/usr/bin/env python3
"""doc/fork/ の文書が壊れていないかを機械的に見る。

  python doc/fork/tools/check-docs.py

見るのは 3 つ。どれも 2026-09-09 のセッションで実際に起きたことである。

1. 制御文字の混入
   ヒアドキュメント経由で書いた文にバックスラッシュが含まれると、
   `\\v` などがエスケープとして解釈されて垂直タブになる。見た目では
   気づきにくく、しかも壊れた文字列を grep しても控えめに空振りする。

2. 参照しているファイルの実在
   文書が挙げるテストや実装ファイルが消えていないか。

3. テスト一覧の網羅
   tests/ に置いたのに索引に載っていないものが無いか。
"""
import os
import re
import sys

FORK = "doc/fork"
CTRL = {0x07, 0x08, 0x0B, 0x0C}


def iter_docs():
    for root, _, files in os.walk(FORK):
        for name in files:
            if name.endswith((".md", ".tcl", ".py", ".sh")):
                yield os.path.join(root, name).replace("\\", "/")
    yield "CLAUDE.md"


def check_control_chars():
    bad = []
    for path in iter_docs():
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        hits = sorted({hex(ord(c)) for c in text if ord(c) in CTRL})
        if hits:
            bad.append((path, hits))
    for path, hits in bad:
        print(f"  NG 制御文字 {hits} : {path}")
    return not bad


def check_referenced_files():
    # 本リポジトリ内を指しているものだけ見る。外部リポジトリの引用
    # (Y8960_Cartridge の RTL など) は当然ここには無いので対象外。
    ours = re.compile(r"`((?:doc/fork|src/sound|src/memory|share/extensions|"
                      r"build/msvc|CLAUDE\.md)[A-Za-z0-9_/.-]*)`")
    missing = []
    for path in iter_docs():
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        for ref in set(ours.findall(text)):
            if not os.path.exists(ref):
                missing.append((path, ref))
    for path, ref in sorted(missing):
        print(f"  NG 参照先が無い: {ref}  ({path})")
    return not missing


def check_test_index():
    index = f"{FORK}/y8960/README.md"
    tests_dir = f"{FORK}/y8960/tests"
    if not os.path.isdir(tests_dir):
        return True
    text = open(index, encoding="utf-8").read()
    missing = [f for f in sorted(os.listdir(tests_dir)) if f not in text]
    for f in missing:
        print(f"  NG 索引に載っていない: tests/{f}")
    return not missing


def main():
    ok = True
    for name, check in (("制御文字", check_control_chars),
                        ("参照先の実在", check_referenced_files),
                        ("テスト索引", check_test_index)):
        if check():
            print(f"  OK {name}")
        else:
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
