# The OPL2 of the Y8960 cartridge: pan per channel (F6h-FEh), the rhythm
# following the pans of channels 7-9, the ADPCM pan (FFh) and the OPL2 volume
# (7FF9h), seen through the final mix only, so that the fork's main and the PR
# branch run the same script. Derived from ../opl2-panpot.tcl.
#
#   Y8960_TEST_OUT=<dir> openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script opl2.tcl
#
# One WAV of the final mix per capture; check_opl2.py judges them.

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
proc r {reg val} {
	debug write ioports 0xC0 $reg
	debug write ioports 0xC1 $val
}

# RR is 0 while the note sounds and 15 for the key off, so that nothing is
# left of it in the captures that follow
proc fm_note {on} {
	r 0x20 0x21 ; r 0x23 0x21
	r 0x40 0x2A ; r 0x43 0x08
	r 0x60 0xF0 ; r 0x63 0xF0
	set rr [expr {$on ? 0x00 : 0x0F}]
	r 0x80 $rr ; r 0x83 $rr
	r 0xA0 0x98
	r 0xB0 [expr {$on ? 0x31 : 0x11}]
}

# the slots of channels 7-9 for the rhythm: HH 11h, SD 14h, TOM 12h, CYM 15h, BD 10h/13h
proc rhythm_setup {} {
	foreach s {0x10 0x11 0x12 0x13 0x14 0x15} {
		r [expr {0x20 + $s}] 0x01
		r [expr {0x40 + $s}] 0x08
		r [expr {0x60 + $s}] 0xF4
		r [expr {0x80 + $s}] 0x05
	}
	r 0xC6 0x00
	r 0xA6 0x98 ; r 0xB6 0x09
	r 0xA7 0x40 ; r 0xB7 0x09
	r 0xA8 0x60 ; r 0xB8 0x09
	r 0xBD 0x20
}

proc rec {name secs then} {
	record start -audioonly "$::OUT/$name.wav"
	after time $secs [list stop $then]
}
proc stop {then} {
	record stop
	eval $then
	after time 0.3 next_step
}

proc hit {name pans bits} {
	foreach {reg val} $pans { r $reg $val }
	rhythm_setup
	after time 1.5 [list hit_now $name $bits]
}
proc hit_now {name bits} {
	r 0xBD [expr {0x20 | $bits}]
	rec $name 0.2 {r 0xBD 0x20}
}

proc adpcm_start {} {
	r 0x08 0x00
	r 0x09 0x00 ; r 0x0A 0x00
	r 0x0C 0x01 ; r 0x0B 0x00
	r 0x07 0x60
	debug write ioports 0xC0 0x0F
	for {set i 0} {$i < 1024} {incr i} {
		debug write ioports 0xC1 [expr {($i & 16) ? 0xFF : 0x77}]
	}
	r 0x07 0x00
	r 0x09 0x00 ; r 0x0A 0x00
	r 0x0C 0x01 ; r 0x0B 0x00
	r 0x10 0x00 ; r 0x11 0x80
	r 0x12 0xFF
	r 0x07 0xB0
}

set step 0
proc next_step {} {
	global step
	set s $step
	incr step
	switch $s {
		0  { mem_write 0x7FFF 0x01 ; r 0xF6 128 ; fm_note 1 ; after time 0.3 {rec fm_center 0.4 {fm_note 0}} }
		1  { r 0xF6 1   ; fm_note 1 ; after time 0.3 {rec fm_left  0.4 {fm_note 0}} }
		2  { r 0xF6 255 ; fm_note 1 ; after time 0.3 {rec fm_right 0.4 {fm_note 0}} }
		3  { r 0xF6 128 ; mem_write 0x7FF9 0x40 ; fm_note 1 ; after time 0.3 {rec vol_half 0.4 {fm_note 0}} }
		4  { mem_write 0x7FF9 0x80 ; mem_write 0x7FF2 0xF6 ; mem_write 0x7FF3 1 ; fm_note 1 ; after time 0.3 {rec fm_tunnel_left 0.4 {fm_note 0 ; r 0xF6 128}} }
		5  { hit bd_left   {0xFC 1 0xFD 255 0xFE 255} 0x10 }
		6  { hit sd_right  {0xFC 1 0xFD 255 0xFE 1} 0x08 }
		7  { hit hh_right  {0xFC 1 0xFD 255 0xFE 1} 0x01 }
		8  { hit tom_left  {0xFC 255 0xFD 255 0xFE 1} 0x04 }
		9  { hit cym_left  {0xFC 255 0xFD 255 0xFE 1} 0x02 }
		10 { r 0xBD 0x00 ; r 0xFC 128 ; r 0xFD 128 ; r 0xFE 128 ; adpcm_start ; r 0xFF 128 ; after time 0.3 {rec adpcm_center 0.4 {}} }
		11 { r 0xFF 1 ; after time 0.3 {rec adpcm_left 0.4 {}} }
		default { exit }
	}
}

after time 2 next_step
