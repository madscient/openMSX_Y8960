#!/usr/bin/env python3
"""デプロイ先（環境変数 OPENMSX_DIR のディレクトリ）の openMSX を、配布 zip の中身に入れ替える。

  py doc/fork/tools/replace-deployed.py extract <作業用> <zip>   zip を <作業用>/new に展開する
  py doc/fork/tools/replace-deployed.py compare <作業用>         デプロイ先と比べ、書く一覧を <作業用>/plan.json に書く
  py doc/fork/tools/replace-deployed.py backup  <作業用>         デプロイ先の全体を <作業用>/old に写して突き合わせる
  py doc/fork/tools/replace-deployed.py write   <作業用>         plan.json のファイルだけを書く
  py doc/fork/tools/replace-deployed.py verify  <作業用>         書いた結果を、退避と zip の両方と突き合わせる

zip は package-release.py が作ったもの。<作業用> は derived/ の下の新しいディレクトリにする。
この順に 1 段ずつ走らせ、compare の出力（上書き、追加、デプロイ先にしか無いもの）を見てから先へ進む。

比べるのはファイルごとの sha1。書くのは、zip に在って、デプロイ先と中身が違うかデプロイ先に無いファイルだけ。
デプロイ先にしか無いファイル（Catapult など）は消さず、触らない。

デプロイ先は兄弟のリポジトリの試験が共有している。write は次のどれかに当たると、何も書かずに止まる。

- openMSX か Catapult のプロセスが動いている。回っている試験の結果に 2 つの版が混ざる
- デプロイ先が退避と違う。退避の後に誰かが書いている
- 今の差が plan.json と違う。compare の後にデプロイ先か展開先が変わっている。一覧を組み直さずに止まるのは、
  書く対象を、compare で見せた一覧のままにしておくため

write が途中で失敗したときは、入れ替える前のファイルが <作業用>/old に残っている。
出力は英語。コンソールの文字コードに左右されないようにしている。
"""
import collections
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import zipfile

BUSY = ("openmsx", "catapult")


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree(root):
    """casefold した相対パス -> (相対パス, sha1)"""
    out = {}
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            key = rel.casefold()
            if key in out:
                sys.exit(f"two files differ in case only: {rel}")
            out[key] = (rel, sha1(p))
    return out


def group(rels):
    c = collections.Counter(
        "/".join(r.split("/")[:2]) if "/" in r else r for r in rels)
    return ", ".join(f"{n} ({v})" for n, v in sorted(c.items())) or "-"


def make_plan(tn, td):
    return {
        "overwrite": sorted(tn[k][0] for k in tn
                            if k in td and tn[k][1] != td[k][1]),
        "add": sorted(tn[k][0] for k in tn if k not in td),
        "only": sorted(td[k][0] for k in td if k not in tn),
    }


def running():
    exe = shutil.which("tasklist")
    if not exe:
        sys.exit("tasklist not found: cannot tell whether openMSX is running")
    out = subprocess.run([exe, "/FO", "CSV", "/NH"], capture_output=True,
                         check=True).stdout.decode("ascii", "replace")
    names = {line.split('","')[0].strip('"') for line in out.splitlines()}
    return sorted(n for n in names if n.lower().startswith(BUSY))


def deployed_dir(work):
    d = os.environ.get("OPENMSX_DIR")
    if not d:
        sys.exit("OPENMSX_DIR is not set")
    deploy = pathlib.Path(d).resolve()
    if not (deploy / "openmsx.exe").is_file():
        sys.exit("no openmsx.exe in OPENMSX_DIR")
    w = work.resolve()
    if w == deploy or deploy in w.parents or w in deploy.parents:
        sys.exit("the work directory and OPENMSX_DIR must not contain each other")
    return deploy


def main():
    steps = ("extract", "compare", "backup", "write", "verify")
    if len(sys.argv) < 3 or sys.argv[1] not in steps \
            or len(sys.argv) != (4 if sys.argv[1] == "extract" else 3):
        print(__doc__, file=sys.stderr)
        return 2
    step, work = sys.argv[1], pathlib.Path(sys.argv[2])
    new, old, plan_file = work / "new", work / "old", work / "plan.json"

    if step == "extract":
        if new.exists():
            sys.exit("new/ exists already")
        with zipfile.ZipFile(sys.argv[3]) as z:
            z.extractall(new)
            entries = sum(1 for i in z.infolist() if not i.is_dir())
        files = len(tree(new))
        print(f"zip {entries} files, extracted {files} files")
        return 0 if entries == files else 1

    deploy = deployed_dir(work)

    if step == "compare":
        tn, td = tree(new), tree(deploy)
        plan = make_plan(tn, td)
        same = len(tn) - len(plan["overwrite"]) - len(plan["add"])
        print(f"zip {len(tn)} files, deployed {len(td)} files")
        print(f"same {same}, overwrite {len(plan['overwrite'])}, "
              f"add {len(plan['add'])}, only in deployed {len(plan['only'])}")
        for key, label in (("overwrite", "overwrite"), ("add", "add"),
                           ("only", "only in deployed")):
            print(f"{label}: {group(plan[key])}")
        plan_file.write_text(json.dumps(plan, indent=1) + "\n",
                             encoding="utf-8")
        return 0

    if step == "backup":
        if old.exists():
            sys.exit("old/ exists already")
        shutil.copytree(deploy, old)
        td, to = tree(deploy), tree(old)
        print(f"deployed {len(td)} files, backup {len(to)} files, "
              f"identical: {td == to}")
        return 0 if td == to else 1

    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    todo = plan["overwrite"] + plan["add"]

    if step == "write":
        busy = running()
        if busy:
            sys.exit(f"running: {', '.join(busy)}: nothing written")
        td = tree(deploy)
        if td != tree(old):
            sys.exit("the deployed tree differs from the backup: nothing written")
        if make_plan(tree(new), td) != plan:
            sys.exit("the differences are not those of plan.json any more: "
                     "run compare again. nothing written")
        for rel in todo:
            dst = deploy / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(new / rel, dst)
        print(f"written {len(todo)} files")
        return 0

    # verify
    want = {r.casefold() for r in todo}
    tn, td, to = tree(new), tree(deploy), tree(old)
    changed = {k for k in td if k not in to or td[k][1] != to[k][1]} \
        | {k for k in to if k not in td}
    print(f"deployed vs backup: {len(changed)} files differ, "
          f"plan.json has {len(want)}, the same files: {changed == want}")
    bad = [k for k in tn if k not in td or td[k][1] != tn[k][1]]
    print(f"zip vs deployed: {len(bad)} files differ")
    only = [k for k in td if k not in tn]
    kept = all(k in to and to[k][1] == td[k][1] for k in only)
    print(f"only in deployed: {len(only)} files, "
          f"unchanged since the backup: {kept}")
    return 0 if changed == want and not bad and kept else 1


if __name__ == "__main__":
    sys.exit(main())
