#!/usr/bin/env python3
"""replace-deployed.py を、偽のデプロイ先で試験する。本物のデプロイ先（OPENMSX_DIR）には触れない。

  py doc/fork/tools/test-replace-deployed.py [--exe <openmsx.exe>] [--tool <replace-deployed.py の写し>]

偽のデプロイ先と zip は一時ディレクトリに作り、終わると消す。道具には、偽のデプロイ先を指す
OPENMSX_DIR を渡す。

見るのは、一通りの入れ替えと、道具が止まるべきところで止まること。期待値は、ここで作る中身から
手で書いてある。

「openMSX が動いていると write が止まる」を見るために、openMSX を窓なしで 8 秒ほど起動する。
既定は作業ツリーの x64 Release のビルドで、--exe で別の exe を渡せる。exe が無ければその項目は落ちる。
openMSX か Catapult が既に動いているときは、write がどれも止まるので、始めずに終わる。

--tool は、この試験が落ちられることを確かめるためのもの。道具の写しから確認を 1 つ外して渡すと、
その確認を見ている項目だけが落ちる。
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
# 先頭の 2 行は、窓を作らせないためのもの（CLAUDE.md §5）
PROBE = "set renderer none\nset sound_driver null\nafter realtime 8 exit\n"

count = 0
fails = 0


def check(name, cond, detail=""):
    global count, fails
    count += 1
    if not cond:
        fails += 1
    print(("PASS " if cond else "FAIL ") + name
          + ("" if cond else " : " + detail.strip()[-300:]))


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def busy():
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                         check=True).stdout.decode("ascii", "replace")
    names = {line.split('","')[0].strip('"').lower() for line in out.splitlines()}
    return sorted(n for n in names if n.startswith(("openmsx", "catapult")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", default=str(
        REPO / "derived/x64-VC-Release/install/openmsx.exe"))
    ap.add_argument("--tool", default=str(HERE / "replace-deployed.py"))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    running = busy()
    if running:
        print(f"running: {', '.join(running)}: every write would refuse. not started")
        return 2

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        base = pathlib.Path(tmp)

        def fixture(name):
            d = base / name
            dep, work, z = d / "dep", d / "work", d / "pkg.zip"
            work.mkdir(parents=True)
            put(dep / "openmsx.exe", b"old exe")
            put(dep / "readme.txt", b"old readme")
            put(dep / "share/a.txt", b"same")
            put(dep / "share/b.txt", b"old b")
            put(dep / "Catapult/x.txt", b"catapult")
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("openmsx.exe", b"new exe")
                # 大文字と小文字だけが違う名前は、デプロイ先の同じファイルとして扱われること
                zf.writestr("README.txt", b"new readme")
                zf.writestr("share/a.txt", b"same")
                zf.writestr("share/b.txt", b"new b")
                zf.writestr("share/sub/c.txt", b"added")
            return dep, work, z

        def run(dep, *a, env_drop=False):
            env = dict(os.environ)
            env.pop("OPENMSX_DIR", None)
            if not env_drop:
                env["OPENMSX_DIR"] = str(dep)
            p = subprocess.run([sys.executable, args.tool, *map(str, a)], env=env,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
            return p.returncode, p.stdout + p.stderr

        def untouched(dep):
            return ((dep / "openmsx.exe").read_bytes() == b"old exe"
                    and (dep / "share/b.txt").read_bytes() == b"old b"
                    and (dep / "readme.txt").read_bytes() == b"old readme"
                    and not (dep / "share/sub/c.txt").exists())

        def upto_backup(name):
            dep, work, z = fixture(name)
            for step in ("extract", "compare", "backup"):
                rc, out = run(dep, step, work, *([z] if step == "extract" else []))
                if rc != 0:
                    check(f"{name}: setup {step}", False, out)
            return dep, work, z

        # A: 一通り
        dep, work, z = fixture("a")
        rc, out = run(dep, "extract", work, z)
        check("A extract", rc == 0 and "zip 5 files, extracted 5 files" in out, out)
        rc, out = run(dep, "compare", work)
        check("A compare counts", rc == 0 and "zip 5 files, deployed 5 files" in out
              and "same 1, overwrite 3, add 1, only in deployed 1" in out, out)
        plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
        check("A plan lists", plan == {
            "overwrite": ["README.txt", "openmsx.exe", "share/b.txt"],
            "add": ["share/sub/c.txt"], "only": ["Catapult/x.txt"]}, json.dumps(plan))
        check("A compare writes nothing", untouched(dep))
        rc, out = run(dep, "backup", work)
        check("A backup", rc == 0
              and "deployed 5 files, backup 5 files, identical: True" in out, out)
        rc, out = run(dep, "write", work)
        check("A write", rc == 0 and "written 4 files" in out, out)
        check("A written contents",
              (dep / "openmsx.exe").read_bytes() == b"new exe"
              and (dep / "share/b.txt").read_bytes() == b"new b"
              and (dep / "share/sub/c.txt").read_bytes() == b"added"
              and (dep / "readme.txt").read_bytes() == b"new readme")
        check("A files not in the plan are as before",
              (dep / "share/a.txt").read_bytes() == b"same"
              and (dep / "Catapult/x.txt").read_bytes() == b"catapult")
        check("A backup holds the old files",
              (work / "old/openmsx.exe").read_bytes() == b"old exe"
              and (work / "old/share/b.txt").read_bytes() == b"old b")
        rc, out = run(dep, "verify", work)
        check("A verify", rc == 0
              and "deployed vs backup: 4 files differ, plan.json has 4, "
                  "the same files: True" in out
              and "zip vs deployed: 0 files differ" in out
              and "only in deployed: 1 files, unchanged since the backup: True" in out,
              out)

        # D: verify が食い違いを見つける（A の木の上で）
        put(dep / "share/b.txt", b"tampered")
        rc, out = run(dep, "verify", work)
        check("D verify: a written file changed afterwards",
              rc == 1 and "zip vs deployed: 1 files differ" in out, out)
        put(dep / "share/b.txt", b"new b")
        put(dep / "Catapult/x.txt", b"tampered")
        rc, out = run(dep, "verify", work)
        check("D verify: a file only in deployed changed",
              rc == 1 and "unchanged since the backup: False" in out, out)
        put(dep / "Catapult/x.txt", b"catapult")
        rc, out = run(dep, "verify", work)
        check("D verify passes again after putting both back", rc == 0, out)

        # B: 退避の後にデプロイ先が変わった
        dep, work, z = upto_backup("b")
        put(dep / "Catapult/x.txt", b"someone wrote this")
        rc, out = run(dep, "write", work)
        check("B write refuses: deployed differs from the backup",
              rc == 1 and "differs from the backup" in out and untouched(dep), out)

        # C: compare の後に差が変わった（退避の前なので、退避とは一致する）
        dep, work, z = fixture("c")
        run(dep, "extract", work, z)
        run(dep, "compare", work)
        put(dep / "share/a.txt", b"changed after compare")
        rc, out = run(dep, "backup", work)
        check("C backup still matches", rc == 0, out)
        rc, out = run(dep, "write", work)
        check("C write refuses: plan.json is stale",
              rc == 1 and "plan.json" in out and untouched(dep)
              and (dep / "share/a.txt").read_bytes() == b"changed after compare", out)

        # F: new/ と old/ を上書きしない
        dep, work, z = upto_backup("f")
        rc, out = run(dep, "extract", work, z)
        check("F extract refuses: new/ exists",
              rc == 1 and "new/ exists already" in out, out)
        rc, out = run(dep, "backup", work)
        check("F backup refuses: old/ exists",
              rc == 1 and "old/ exists already" in out, out)

        # G: 木の置き場所
        dep, work, z = fixture("g")
        rc, out = run(dep, "compare", dep / "w")
        check("G refuses: work inside the deployed tree",
              rc == 1 and "must not contain each other" in out, out)
        rc, out = run(dep.parent, "compare", work)
        check("G refuses: no openmsx.exe in OPENMSX_DIR",
              rc == 1 and "no openmsx.exe" in out, out)
        rc, out = run(dep, "compare", work, env_drop=True)
        check("G refuses: OPENMSX_DIR not set",
              rc == 1 and "OPENMSX_DIR is not set" in out, out)
        rc, out = run(dep)
        check("H usage", rc == 2, out)
        rc, out = run(dep, "compare", work, "extra")
        check("H usage: an argument too many", rc == 2, out)

        # E: openMSX が動いている
        dep, work, z = upto_backup("e")
        user = base / "user"
        shutil.copytree(REPO / "Contrib/cbios", user / "machines")
        probe = base / "probe.tcl"
        probe.write_text(PROBE, encoding="ascii")
        env = dict(os.environ, OPENMSX_SYSTEM_DATA=str(REPO / "share"),
                   OPENMSX_USER_DATA=str(user))
        try:
            proc = subprocess.Popen([args.exe, "-machine", "C-BIOS_MSX2+",
                                     "-script", str(probe)], env=env)
        except OSError as e:
            proc = None
            check("E openMSX started", False, str(e))
        if proc:
            try:
                time.sleep(1.5)
                alive = proc.poll() is None
                rc, out = run(dep, "write", work)
                check("E openMSX was running during the write",
                      alive and proc.poll() is None)
                check("E write refuses: openMSX is running",
                      rc == 1 and "running: " in out and "openmsx" in out.lower()
                      and "nothing written" in out and untouched(dep), out)
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                check("E openMSX exited by itself", False)
            rc, out = run(dep, "write", work)
            check("E the same write goes through once openMSX has exited",
                  rc == 0 and "written 4 files" in out, out)

    print(f"{count} checks, {fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
