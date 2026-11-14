#!/bin/sh
# usage: PR=<PR の worktree> WORK=<作業用> stage.sh <名前>
# 組んだ exe を $WORK/exe/<名前>.exe に控え、回帰の音列 2 本（mel、rhy）と PCM_BSY と古いセーブステートの読み込みを流して、
# ベース（$WORK/out/base-*）と比べる。ビルドのログ $WORK/build-<名前>.log の最後が exit=0 でなければ止まる。
HERE=$(cd "$(dirname "$0")" && pwd)
N="$1"
cd "${WORK:?}" || exit 99
SYS="${PR:?}/share"
tail -1 "build-$N.log"
echo "errors: $(grep -c ' error ' "build-$N.log")  warnings in Y8950/MSXAudio: $(grep -E 'warning' "build-$N.log" | grep -c -E 'Y8950|MSXAudio')"
if ! tail -1 "build-$N.log" | grep -q '^exit=0 '; then
	echo "BUILD FAILED, not testing"
	exit 97
fi
mkdir -p exe
cp "$PR/derived/x64-VC-Release/install/openmsx.exe" "exe/$N.exe" || exit 98
for s in mel rhy; do
	timeout 150 sh "$HERE/run.sh" "exe/$N.exe" "out/$N-$s" "seq/$s.txt" audio
	echo "== $s (rc $(cat out/$N-$s/rc.txt)) vs base"
	py "$HERE/cmpdir.py" "out/base-$s" "out/$N-$s"
done
OPENMSX_SYSTEM_DATA="$SYS" OPENMSX_USER_DATA="$WORK/user" T_OUT="$WORK/out/$N-pcmbsy.txt" timeout 60 "exe/$N.exe" -machine C-BIOS_MSX2+ -ext audio -script "$HERE/pcmbsy.tcl"
echo "== pcmbsy vs base"
diff out/base-pcmbsy.txt "out/$N-pcmbsy.txt" && echo "pcmbsy same"
mkdir -p "out/st-$N-load"
OPENMSX_SYSTEM_DATA="$SYS" OPENMSX_USER_DATA="$WORK/user" T_MODE=load T_NAME=y8950v1 T_OUT="$WORK/out/st-$N-load" timeout 60 "exe/$N.exe" -machine C-BIOS_MSX2+ -script "$HERE/state.tcl"
echo "== old savestate load"
cat "out/st-$N-load/state.txt"
py "$HERE/cmpdir.py" out/st-base-load "out/st-$N-load" | tail -1
