# The OPLL of the Y8960 cartridge: pan per channel (50h-58h), the rhythm
# following the pans of channels 7-9, the OPLL volume (7FF8h) and a tone set
# (40h-48h), seen through the final mix only, so that the fork's main and the
# PR branch run the same script. Derived from ../opll-panpot.tcl.
#
#   Y8960_TEST_OUT=<dir> openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script opll.tcl
#
# One WAV of the final mix per capture; check_opll.py judges them.
# Writes to the OPLL go one per 0.5 ms: the core keeps one write per 18-step
# slot, and 'debug write' does not move time on.

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

set queue {}
proc q {args} { lappend ::queue $args }
proc run_queue {then} {
	if {[llength $::queue] == 0} { eval $then ; return }
	set item [lindex $::queue 0]
	set ::queue [lrange $::queue 1 end]
	eval $item
	after time 0.0005 [list run_queue $then]
}
# Through the memory mapped tunnel, not ports 7Ch/7Dh: C-BIOS_MSX2+ has an
# MSX-MUSIC there, which would play the same notes, unpanned.
proc r {reg val} {
	q mem_write 0x7FF4 $reg
	q mem_write 0x7FF5 $val
}

# a note on channel 'ch' (0-based): instrument 1, full volume
proc note {ch on} {
	r [expr {0x30 + $ch}] 0x10
	r [expr {0x10 + $ch}] 0xAC
	r [expr {0x20 + $ch}] [expr {$on ? 0x14 : 0x04}]
}

proc capture {name setup ch} {
	foreach {reg val} $setup { r $reg $val }
	note $ch 1
	run_queue [list after time 0.5 [list record_now $name $ch]]
}
proc record_now {name ch} {
	record start -audioonly "$::OUT/$name.wav"
	after time 0.5 [list stop $ch]
}
proc stop {ch} {
	record stop
	note $ch 0
	run_queue {after time 0.3 next_step}
}

# rhythm: 'bits' is the key bit of one sound, after 'setup'
proc hit {name setup bits} {
	foreach {reg val} $setup { r $reg $val }
	r 0x16 0x20 ; r 0x26 0x05
	r 0x17 0x50 ; r 0x27 0x05
	r 0x18 0xC0 ; r 0x28 0x01
	r 0x36 0x04 ; r 0x37 0x44 ; r 0x38 0x44
	r 0x0E 0x20
	# let the release of the melodic note before die out first
	run_queue [list after time 1.5 [list hit_now $name $bits]]
}
proc hit_now {name bits} {
	record start -audioonly "$::OUT/$name.wav"
	r 0x0E [expr {0x20 | $bits}]
	run_queue {after time 0.2 hit_stop}
}
proc hit_stop {} {
	record stop
	r 0x0E 0x00
	r 0x56 128 ; r 0x57 128 ; r 0x58 128
	run_queue {after time 0.3 next_step}
}

set step 0
proc next_step {} {
	global step
	set s $step
	incr step
	switch $s {
		0  { capture center  {0x50 128} 0 }
		1  { capture zero    {0x50 0}   0 }
		2  { capture left    {0x50 1}   0 }
		3  { capture right   {0x50 255} 0 }
		4  { capture ch2_left {0x50 255 0x51 1} 1 }
		5  { q mem_write 0x7FF4 0x52 ; q mem_write 0x7FF5 1 ; capture ch3_tunnel_left {} 2 }
		6  { capture vol_half {0x50 128} 0 ; mem_write 0x7FF8 0x40 }
		7  { mem_write 0x7FF8 0x80 ; capture bank1 {0x40 1} 0 }
		8  { hit bd_left  {0x40 0 0x56 1 0x57 255 0x58 255} 0x10 }
		9  { hit hh_right {0x56 1 0x57 255 0x58 1} 0x01 }
		10 { hit tom_left {0x56 255 0x57 255 0x58 1} 0x04 }
		11 { hit sd_right {0x56 1 0x57 255 0x58 1} 0x08 }
		12 { hit tc_left  {0x56 255 0x57 255 0x58 1} 0x02 }
		default { exit }
	}
}

after time 2 next_step
