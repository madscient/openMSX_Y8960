#!/bin/sh
# usage: PR=<PR の worktree> WORK=<作業用> perf.sh <ベースの exe の名前> <新しい exe の名前> <Y8960 の差し込みの exe の名前>
# perf.tcl を exe ごとに交互に 5 巡流し、実時間を $WORK/out/perf-results.txt に書く。exe は $WORK/exe/<名前>.exe。
HERE=$(cd "$(dirname "$0")" && pwd)
B="$1"; E="$2"; H="$3"
cd "${WORK:?}" || exit 99
SYS="${PR:?}/share"
R="$WORK/out/perf-results.txt"
: > "$R"
one() {
	tag=$1; exe=$2; ext=$3; dev=$4; extra=$5
	mkdir -p "out/perf-$tag"
	env $extra OPENMSX_SYSTEM_DATA="$SYS" OPENMSX_USER_DATA="$WORK/user" T_OUT="$WORK/out/perf-$tag" T_DEV="$dev" \
		timeout 600 "exe/$exe.exe" -machine C-BIOS_MSX2+ -ext "$ext" -script "$HERE/perf.tcl"
	echo "$tag $(cat out/perf-$tag/perf.txt)" >> "$R"
}
for round in 1 2 3 4 5; do
	one silent-base "$B" audio "Generic MSX-Audio" T_SILENT=1
	one base "$B" audio "Generic MSX-Audio" ""
	one y8950 "$E" audio "Generic MSX-Audio" ""
	one y8960 "$H" audio-y8960test "Y8960 test" T_WAVE=1
	one silent-new "$E" audio "Generic MSX-Audio" T_SILENT=1
done
cat "$R"
