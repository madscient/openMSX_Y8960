#!/bin/sh
# usage: [ONLY=<regex>] PR=<worktree> WORK=<work dir> runall.sh <exe> <out dir> <tag>
# Runs the Y8960 tests that apply to the PR branch with <exe>, one directory per test under <out dir>:
# the fork's tests, the tests here, savestate round trips, a second cartridge, and -testconfig.
# <tag> names the savestates. ONLY limits the tests to those whose directory name matches.
# The share/ of $PR is read while the tests run: don't switch the worktree's branch meanwhile.
# Machine definitions go in $WORK/user/machines (from $PR/Contrib/cbios), system ROMs in
# $WORK/user/systemroms.
# Fork tests that use names of the old implementation run from copies (in $WORK/copies) with the
# new names. The fork's panpot tests rely on stereo channel recordings and are left out (the tests
# here cover them).
# Each run is cut off after 60 s: a Tcl error inside an 'after' callback leaves openMSX waiting,
# which is what the tests of a block that a commit doesn't have yet do. Their rc.txt reads 124.
EXE="$1"; OUT="$2"; TAG="$3"
P=$(cd "$(dirname "$0")" && pwd)
T=$(cd "$P/.." && pwd)
C="${WORK:?}/copies"
mkdir -p "$OUT" "$C"
export OPENMSX_SYSTEM_DATA="${PR:?}/share" OPENMSX_USER_DATA="$WORK/user"

sed -e 's/Y8960 ADPCM RAM/Y8960 OPL2 RAM/g' "$T/adpcm-rommode.tcl" > "$C/adpcm-rommode.tcl"
# the new probe name has a space in it
sed -e 's/y8960-timer\.IRQ/{Y8960 MSX-TIMER.IRQ}/g' "$T/timer-irq.tcl" > "$C/timer-irq.tcl"
for t in enabler2 ssgs-write-only; do
	sed -e 's/Y8960 SSGS regs/Y8960 SSG 0 regs/g' "$T/$t.tcl" > "$C/$t.tcl"
done
# the old debuggable had both SSGs, 16 registers each
sed -e 's/"Y8960 SSGS regs" 0x1E/"Y8960 SSG 1 regs" 0x0E/g' \
    -e 's/"Y8960 SSGS regs" 0x1F/"Y8960 SSG 1 regs" 0x0F/g' \
    -e 's/Y8960 SSGS regs/Y8960 SSG 0 regs/g' "$T/ssgs-gpio.tcl" > "$C/ssgs-gpio.tcl"

want() { [ -z "$ONLY" ] || echo "$1" | grep -Eq "$ONLY"; }

run() { # <dir> <script> [env...]
	want "$1" || return 0
	d="$OUT/$1"; s="$2"; shift 2
	rm -rf "$d"; mkdir -p "$d"
	env "$@" timeout 60 "$EXE" -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script "$s" > "$d/stdout.txt" 2>&1
	echo $? > "$d/rc.txt"
}

# fork tests, output to a directory
for t in adpcm-play enabler2-read mapper-cpu-read mapper-windows mixer-volume \
         opl2-read opl2-waveform opll-regs-mirror opm sysctrl timer-regs timer-resolution; do
	run "f-$t" "$T/$t.tcl" Y8960_TEST_OUT="$OUT/f-$t"
done
run f-adpcm-rommode "$C/adpcm-rommode.tcl" Y8960_TEST_OUT="$OUT/f-adpcm-rommode"
# insert the cartridge themselves with -romtype, so without -ext HRA_Y8960
for t in mapper-mirror mapper-romblocks; do
	want "f-$t" || continue
	d="$OUT/f-$t"
	rm -rf "$d"; mkdir -p "$d"
	Y8960_TEST_OUT="$d" timeout 60 "$EXE" -machine C-BIOS_MSX2+ -script "$T/$t.tcl" > "$d/stdout.txt" 2>&1
	echo $? > "$d/rc.txt"
done
# fork tests, output to a file
run f-opll-enabler "$T/opll-enabler.tcl" Y8960_TEST_OUT="$OUT/f-opll-enabler/out.txt"
for t in timer-irq enabler2 ssgs-write-only ssgs-gpio; do
	run "f-$t" "$C/$t.tcl" Y8960_TEST_OUT="$OUT/f-$t/out.txt"
done

# tests here
for t in scc mixer opll opl2 ssg; do
	run "p-$t" "$P/$t.tcl" Y8960_TEST_OUT="$OUT/p-$t"
done
for w in opll opl2; do
	for e in 0 1; do
		run "p-state-$w-$e-save" "$P/cart_state.tcl" T_MODE=save T_NAME="$TAG-$w-$e" T_ENABLE=$e T_WHICH=$w T_OUT="$OUT/p-state-$w-$e-save"
		run "p-state-$w-$e-load" "$P/cart_state.tcl" T_MODE=load T_NAME="$TAG-$w-$e" T_WHICH=$w T_OUT="$OUT/p-state-$w-$e-load"
	done
done
run p-timer-save "$P/timer_state.tcl" T_MODE=save T_NAME="$TAG-timer" T_OUT="$OUT/p-timer-save"
run p-timer-load "$P/timer_state.tcl" T_MODE=load T_NAME="$TAG-timer" T_OUT="$OUT/p-timer-load"

# a second cartridge
run p-two "$P/two.tcl" T_OUT="$OUT/p-two"

# other configurations still load
if want testconfig; then
	rm -f "$OUT/testconfig.txt"
	for e in HRA_Y8960 audio audio2 Panasonic_FS-CA1 2nd_PSG fmpac scc; do
		timeout 60 "$EXE" -testconfig -machine C-BIOS_MSX2+ -ext "$e" > /dev/null 2>&1
		echo "$e $?" >> "$OUT/testconfig.txt"
	done
fi
