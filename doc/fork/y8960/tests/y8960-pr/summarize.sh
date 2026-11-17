#!/bin/sh
# usage: summarize.sh <out dir of runall.sh>
# Prints the verdict of each test: the exit codes, the RESULT lines, the check scripts, the
# savestate round trips, the second cartridge and -testconfig.
O="$1"
P=$(cd "$(dirname "$0")" && pwd)
T=$(cd "$P/.." && pwd)
chk() { # <label> <cmd...>
	l="$1"; shift
	"$@" > /dev/null 2>&1; echo "$l: check exit $?"
}
for d in "$O"/*/; do
	printf '%-24s rc=%s\n' "$(basename "$d")" "$(cat "$d/rc.txt" 2>/dev/null)"
done
echo "-- RESULT lines"
for f in "$O"/f-*/*.txt "$O"/p-mixer/*.txt; do
	case "$f" in */stdout.txt|*/rc.txt) continue;; esac
	r=$(grep -a 'RESULT' "$f" 2>/dev/null | tail -1)
	[ -n "$r" ] && echo "$(basename "$(dirname "$f")"): $r"
done
echo "-- check scripts"
chk p-scc  py "$P/check_scc.py"  "$O/p-scc"
chk p-opll py "$P/check_opll.py" "$O/p-opll"
chk p-opl2 py "$P/check_opl2.py" "$O/p-opl2"
chk p-ssg  py "$P/check_ssg.py"  "$O/p-ssg"
chk f-adpcm-play    py "$T/check-adpcm-play.py"    "$O/f-adpcm-play"
chk f-opl2-waveform py "$T/check-opl2-waveform.py" "$O/f-opl2-waveform"
chk f-mixer-output  py "$T/check-mixer-output.py"  "$O/f-mixer-output"
chk f-mixer-volume  py "$T/check-mixer-volume.py"  "$O/f-mixer-volume"
chk f-mixer-remove  py "$T/check-mixer-remove.py"  "$O/f-mixer-remove"
chk f-opm           py "$T/check-opm.py"           "$O/f-opm"
echo "-- savestates"
for w in opll opl2; do
	for e in 0 1; do
		echo "$w enable=$e: $(tr '\n' ' ' < "$O/p-state-$w-$e-save/state.txt")| $(tr '\n' ' ' < "$O/p-state-$w-$e-load/state.txt")"
	done
done
echo "timer save: $(tr '\n' ' ' < "$O/p-timer-save/state.txt")"
echo "timer load: $(tr '\n' ' ' < "$O/p-timer-load/state.txt")"
echo "-- second cartridge"
cat "$O/p-two/two.txt"
echo "-- testconfig"
cat "$O/testconfig.txt"
