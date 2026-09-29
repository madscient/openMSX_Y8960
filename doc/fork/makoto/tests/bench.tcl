# Host-CPU benchmark: how long the host takes to emulate BENCH_SECS
# seconds with the throttle off and no video.
# Run with: -machine C-BIOS_MSX2+ [-ext Makoto] -script bench.tcl
# Environment:
#   BENCH_OUT     file the result line is appended to (required)
#   BENCH_LABEL   first words of the result line (required)
#   BENCH_SECS    emulated seconds to time (required)
#   BENCH_DRIVER  sound_driver to use (optional)
#   BENCH_PLAY    if set, keep 6 FM and 3 SSG voices sounding (needs Makoto)
#   BENCH_REC     if set, record the audio to this file, to check BENCH_PLAY

set renderer none
set throttle off
if {[info exists ::env(BENCH_DRIVER)]} { set sound_driver $::env(BENCH_DRIVER) }
proc w {port reg val} {
	debug write ioports $port $reg
	debug write ioports [expr {$port + 1}] $val
}
# FM: 6 channels, algorithm 7 (all carriers), full level, sustained.
# SSG: 3 tones at full volume.
proc play {} {
	w 0x14 0x29 0x80
	foreach port {0x14 0x16} {
		for {set ch 0} {$ch < 3} {incr ch} {
			foreach op {0 4 8 12} {
				set r [expr {$ch + $op}]
				w $port [expr {0x30 + $r}] 0x01
				w $port [expr {0x40 + $r}] 0x00
				w $port [expr {0x50 + $r}] 0x1F
				w $port [expr {0x60 + $r}] 0x00
				w $port [expr {0x70 + $r}] 0x00
				w $port [expr {0x80 + $r}] 0x0F
			}
			w $port [expr {0xB0 + $ch}] 0x07
			w $port [expr {0xB4 + $ch}] 0xC0
			w $port [expr {0xA4 + $ch}] [expr {0x20 + $ch}]
			w $port [expr {0xA0 + $ch}] 0x6A
		}
	}
	foreach ch {0 1 2 4 5 6} { w 0x14 0x28 [expr {0xF0 | $ch}] }
	w 0x14 0 0x80; w 0x14 1 0
	w 0x14 2 0x60; w 0x14 3 0
	w 0x14 4 0x40; w 0x14 5 0
	w 0x14 7 0x38
	w 0x14 8 0x0F; w 0x14 9 0x0F; w 0x14 10 0x0F
}
proc done {} {
	set dt [expr {[clock milliseconds] - $::t0}]
	if {[info exists ::env(BENCH_REC)]} { record stop }
	set f [open $::env(BENCH_OUT) a]
	puts $f "$::env(BENCH_LABEL) host_ms=$dt"
	close $f
	exit
}
after time 10 {
	if {[info exists ::env(BENCH_PLAY)]} play
	if {[info exists ::env(BENCH_REC)]} { record start -audioonly $::env(BENCH_REC) }
	set ::t0 [clock milliseconds]
	after time $::env(BENCH_SECS) done
}
