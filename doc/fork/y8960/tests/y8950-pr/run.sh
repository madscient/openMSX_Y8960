#!/bin/sh
# usage: PR=<PR の worktree> WORK=<作業用> run.sh <exe> <出力先> <音列> <拡張> [デバイス名] [チャンネル数]
# chrec.tcl で音列を流し、チャンネルごとに録る。終了コードを <出力先>/rc.txt に書く。
# 機種の定義（C-BIOS）は $WORK/user/machines に置いておく。
HERE=$(cd "$(dirname "$0")" && pwd)
EXE="$1"; OUT="$2"; SEQ="$3"; EXT="$4"; DEV="${5:-Generic MSX-Audio}"; NCH="${6:-15}"
mkdir -p "$OUT"
rm -f "$OUT"/ch*.wav "$OUT"/log.txt
OPENMSX_SYSTEM_DATA="${PR:?}/share" OPENMSX_USER_DATA="${WORK:?}/user" T_OUT="$OUT" T_SEQ="$SEQ" T_DEV="$DEV" T_NCH="$NCH" \
	"$EXE" -machine C-BIOS_MSX2+ -ext "$EXT" -script "$HERE/chrec.tcl"
echo $? > "$OUT/rc.txt"
