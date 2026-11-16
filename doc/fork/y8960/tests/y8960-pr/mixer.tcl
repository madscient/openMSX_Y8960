# The "Y8960 mixer" debuggable: values after reset, writes through the
# cartridge reaching it, writes that must not, and writes through the
# debuggable itself.
#
#   Y8960_TEST_OUT=<dir> openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script mixer.tcl
#
# Writes <dir>/mixer.txt, RESULT on the last line. The cartridge sits in slot 1
# of C-BIOS_MSX2+.

set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/mixer.txt" w]
set fails 0

proc cw {addr val} { debug write "slotted memory" [expr {(1 << 18) | $addr}] $val }
proc mx {reg}      { debug read "Y8960 mixer" $reg }

proc check {name got want} {
	global log fails
	if {$got == $want} {
		puts $log [format "PASS  %-50s %s" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-50s got %s want %s" $name $got $want]
	}
}

proc defaults {when} {
	for {set r 0} {$r <= 5} {incr r} { check "$when: volume $r" [mx $r] 128 }
	for {set r 6} {$r < 0x1E} {incr r} { check [format "$when: pan %02Xh" $r] [mx $r] 128 }
	for {set r 0} {$r < 16} {incr r} {
		set want [expr {($r & 3) == 3 ? 0 : ($r < 8 ? 128 : 128)}]
		check [format "$when: SSG %02Xh" [expr {0x20 + $r}]] [mx [expr {0x1E + $r}]] $want
	}
}

proc registers {} {
	check "size" [debug size "Y8960 mixer"] 46
	defaults "reset"

	cw 0x7FF7 0x11 ; check "7FF7h SSG volume"   [mx 0] 0x11
	cw 0x7FF8 0x12 ; check "7FF8h OPLL volume"  [mx 1] 0x12
	cw 0x7FF9 0x13 ; check "7FF9h OPL2 volume"  [mx 2] 0x13
	cw 0x7FFA 0x14 ; check "7FFAh SCC volume"   [mx 3] 0x14
	cw 0x7FFD 0x15 ; check "7FFDh OPM volume"   [mx 4] 0x15
	cw 0x7FFE 0x16 ; check "7FFEh master volume" [mx 5] 0x16

	cw 0x9000 0x3F
	for {set ch 0} {$ch < 5} {incr ch} {
		cw [expr {0x9900 + $ch}] [expr {0x21 + $ch}]
		check "990${ch}h SCC pan" [mx [expr {0x19 + $ch}]] [expr {0x21 + $ch}]
	}
	cw 0x9905 0x77 ; check "9905h is not a pan" [mx 0x1D] 0x25

	# 7FFAh while 0x6000-0x7FFF shows the SCC, or RAM in RAM mode
	cw 0x7000 0x3F ; cw 0x7FFA 0x44 ; cw 0x7000 0x01
	check "7FFAh under the SCC" [mx 3] 0x14
	cw 0x48FB 0x01 ; cw 0x48FD 0x10 ; cw 0x7FFA 0x45 ; cw 0x48FD 0x01 ; cw 0x48FB 0x00
	check "7FFAh under RAM" [mx 3] 0x14
	cw 0x9000 0x02 ; cw 0x9900 0x55 ; cw 0x9000 0x3F
	check "9900h without the SCC" [mx 0x19] 0x21

	debug write "Y8960 mixer" 3 0x66 ; check "debug write volume" [mx 3] 0x66
	debug write "Y8960 mixer" 0x21 0x77 ; check "debug write SSG 23h stays 0" [mx 0x21] 0
	debug write "Y8960 mixer" 0x26 0x78 ; check "debug write SSG 28h" [mx 0x26] 0x78
}

proc finish {} {
	global log fails
	defaults "after reset"
	puts $log [expr {$fails > 0 ? "RESULT: FAILED $fails" : "RESULT: ALL PASS"}]
	close $log
	exit
}

after time 2 {
	registers
	reset
	after time 0.5 finish
}
