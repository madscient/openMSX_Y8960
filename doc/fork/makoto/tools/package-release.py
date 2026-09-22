"""Builds the Windows release zip of the makoto branch and checks its contents.

    py doc/fork/makoto/tools/package-release.py <tag>

Run from the repository root after a Release x64 build (-t:Rebuild).
Writes derived/x64-VC-Release/package-windows/openmsx-<tag>-windows-vc-x64-bin.zip.
"""
import hashlib
import os
import subprocess
import sys
import zipfile

PLATFORM, CONFIGURATION = "x64", "Release"

# Upstream's packagezip.py ships neither the root README nor the licenses of
# libraries this fork added, so they are added here.
EXTRA_FILES = {
    "README": "README.txt",
    "src/3rdparty/ymfm/LICENSE": "doc/ymfm-LICENSE.txt",
}

# Every library the fork adds under src/3rdparty must have its license in
# EXTRA_FILES; a new one without it stops the packaging here.
THIRD_PARTY = "src/3rdparty"

REQUIRED = ("README.txt", "openmsx.exe", "share/extensions/Makoto.xml",
            "doc/GPL.txt", "doc/ymfm-LICENSE.txt")
FORBIDDEN_PREFIXES = ("CLAUDE.md", "doc/fork/")
# The YM2608 rhythm ROM is copyrighted and must never ship.
FORBIDDEN_SHA1 = {"50b6c3e288eaa12ad275d4f323267bb72b0445df"}


def fork_added_libraries():
    upstream = subprocess.run(
        ["git", "ls-tree", "--name-only", f"upstream/master:{THIRD_PARTY}"],
        capture_output=True, text=True, check=True).stdout.split()
    here = [d for d in os.listdir(THIRD_PARTY)
            if os.path.isdir(os.path.join(THIRD_PARTY, d))]
    return sorted(set(here) - set(upstream))


def check_licenses_declared():
    declared = {src.split("/")[2] for src in EXTRA_FILES
                if src.startswith(THIRD_PARTY + "/")}
    missing = [lib for lib in fork_added_libraries() if lib not in declared]
    if missing:
        sys.exit(f"no license in EXTRA_FILES for {THIRD_PARTY}/: {missing}")


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    tag = sys.argv[1]
    check_licenses_declared()

    sys.path.insert(0, "build/package-windows")
    sys.path.insert(0, "build")
    from packagewindows import PackageInfo
    info = PackageInfo(PLATFORM, CONFIGURATION, "NOCATAPULT")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (env.get("PYTHONPATH"), "build") if p)
    subprocess.run(
        [sys.executable, "build/package-windows/packagezip.py",
         PLATFORM, CONFIGURATION, "NOCATAPULT"],
        env=env, check=True, stdout=subprocess.DEVNULL)

    src = os.path.join(info.packagePath, info.packageFileName + "-bin.zip")
    dst = os.path.join(info.packagePath,
                       f"openmsx-{tag}-windows-vc-x64-bin.zip")
    if os.path.exists(dst):
        os.unlink(dst)

    # upstream names the zip after git describe, which does not see the fork's tag
    with zipfile.ZipFile(src) as zin, \
            zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        for path, name in EXTRA_FILES.items():
            zout.write(path, name)
    os.unlink(src)

    with zipfile.ZipFile(dst) as z:
        names = z.namelist()
        errors = [f"missing: {r}" for r in REQUIRED if r not in names]
        errors += [f"forbidden: {n}" for n in names
                   if n.startswith(FORBIDDEN_PREFIXES)]
        errors += [f"forbidden content: {n}" for n in names
                   if not n.endswith("/")
                   and hashlib.sha1(z.read(n)).hexdigest() in FORBIDDEN_SHA1]
    print(f"{dst}: {len(names)} entries")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("OK")


main()
