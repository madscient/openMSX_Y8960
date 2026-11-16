# The SSGs of the Y8960 cartridge: volume (20h-26h) and pan (28h-2Eh) per
# channel, the two SSGs kept apart (10h-1Fh is the second), and the SSG volume
# (7FF7h), seen through the final mix only, so that the fork's main and the PR
# branch run the same script. Derived from ../ssgs-panpot.tcl.
#
#   Y8960_TEST_OUT=<dir> openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script ssg.tcl
#
# Writes go through the memory mapped tunnel (7FF0h/7FF1h): ports A0h/A1h are
# shared with the MSX's own PSG, which would play the same notes.
# One WAV of the final mix per capture; check_ssg.py judges them.

set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}
proc w {reg val} {
	mem_write 0x7FF0 $reg
	mem_write 0x7FF1 $val
}

# channel A of SSG 'unit': a tone, not loud enough to clip
proc note {unit on} {
	set base [expr {$unit * 0x10}]
	w [expr {$base + 0x00}] 0x40
	w [expr {$base + 0x01}] 0x01
	w [expr {$base + 0x07}] 0x3E
	w [expr {$base + 0x08}] [expr {$on ? 0x0B : 0x00}]
}

proc capture {name unit vol pan} {
	w [expr {0x20 + $unit * 4}] $vol
	w [expr {0x28 + $unit * 4}] $pan
	note $unit 1
	after time 0.3 [list rec $name $unit]
}
proc rec {name unit} {
	record start -audioonly "$::OUT/$name.wav"
	after time 0.4 [list stop $unit]
}
proc stop {unit} {
	record stop
	note $unit 0
	after time 0.3 next
}

set step 0
proc next {} {
	global step
	set s $step
	incr step
	switch $s {
		0 { capture center    0 128 128 }
		1 { capture left      0 128 1 }
		2 { capture right     0 128 255 }
		3 { capture half      0 64  128 }
		4 { capture unit1     1 128 128 }
		5 { capture unit1_left 1 128 1 }
		6 { mem_write 0x7FF7 0x40 ; capture ssg_vol_half 0 128 128 }
		default { exit }
	}
}

after time 2 next
