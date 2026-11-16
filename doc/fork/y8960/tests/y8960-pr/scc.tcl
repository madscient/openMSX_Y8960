# The SCC windows, the SCC pan (9900h-9904h) and the SCC and master volumes of
# the Y8960 cartridge, seen through memory writes and the final mix only, so
# that the fork's main and the PR branch run the same script.
#
#   Y8960_TEST_OUT=<dir> openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script scc.tcl
#
# Writes <dir>/scc.txt (register checks, RESULT on the last line) and one WAV
# of the final mix per capture. check_scc.py judges them.
# Derived from ../scc-panpot.tcl, without the checks that read the fork's
# "Y8960 SCC pan" debuggable. The cartridge sits in slot 1 of C-BIOS_MSX2+.

set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/scc.txt" w]
set fails 0

proc cw {addr val} { debug write "slotted memory" [expr {(1 << 18) | $addr}] $val }
proc cr {addr}     { debug read  "slotted memory" [expr {(1 << 18) | $addr}] }
proc wave {ch i}   { debug read "Y8960 SCC SCC" [expr {$ch * 32 + $i}] }

proc check {name got want} {
	global log fails
	if {$got == $want} {
		puts $log [format "PASS  %-46s %s" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-46s got %s want %s" $name $got $want]
	}
}

# channels A and B: the same square wave (40h then C0h), about 436Hz, full volume
proc setup_wave {} {
	cw 0x9000 0x3F
	for {set i 0} {$i < 32} {incr i} {
		set v [expr {$i < 16 ? 0x40 : 0xC0}]
		cw [expr {0x9800 + $i}] $v
		cw [expr {0x9820 + $i}] $v
	}
	cw 0x9880 0x00 ; cw 0x9881 0x01
	cw 0x9882 0x00 ; cw 0x9883 0x01
	cw 0x988A 0x0F
	cw 0x988B 0x0F
}

proc registers {} {
	setup_wave
	cw 0x9900 0x01
	check "9900h does not reach wave A\[0\]" [wave 0 0] 0x40
	cw 0x9904 0x02
	check "9904h does not reach wave A\[4\]" [wave 0 4] 0x40
	cw 0x9905 0x03
	check "9905h reaches wave A\[5\]" [wave 0 5] 0x03
	cw 0x9805 0x40
	cw 0x9990 0x55
	check "9990h reaches freq of ch A" [debug read "Y8960 SCC SCC" 0xA0] 0x55
	cw 0x9880 0x00
	check "9900h reads wave A\[0\]" [cr 0x9900] 0x40
	check "9910h reads wave A\[16\]" [cr 0x9910] 0xC0
	foreach {reg addr ch restore} {
		0x5000 0x5902 2 0x00
		0x7000 0x7903 3 0x01
		0xB000 0xB904 4 0x03
	} {
		cw $reg 0x3F
		cw $addr 0x11
		check [format "%Xh reaches wave A\[%d\]" $addr $ch] [wave 0 $ch] 0x11
		cw [expr {0x9800 + $ch}] 0x40
		cw $reg $restore
	}
	cw 0x48FB 0x01
	cw 0x48FE 0x3F
	cw 0x9900 0x66
	check "RAM mode: 9900h does not reach wave A\[0\]" [wave 0 0] 0x40
	cw 0x48FE 0x10
	cw 0x9900 0x77
	check "RAM mode, RAM bank: 9900h is memory" [cr 0x9900] 0x77
	cw 0x48FE 0x3F
	cw 0x48FB 0x00
	cw 0x9000 0x3F
	for {set ch 0} {$ch < 5} {incr ch} { cw [expr {0x9900 + $ch}] 128 }
}

proc capture {name enable} {
	global OUT
	cw 0x988F $enable
	record start -audioonly "$OUT/$name.wav"
	after time 0.2 [list stop $name]
}

proc stop {name} {
	record stop
	cw 0x988F 0x00
	global step ; incr step ; next
}

proc finish {} {
	global log fails
	puts $log [expr {$fails > 0 ? "RESULT: FAILED $fails" : "RESULT: ALL PASS"}]
	close $log
	exit
}

set step 0
proc next {} {
	global step
	switch $step {
		0  { registers ; incr step ; next }
		1  { capture center 0x01 }
		2  { cw 0x9900 1   ; capture left  0x01 }
		3  { cw 0x9900 255 ; capture right 0x01 }
		4  { cw 0x9900 0   ; capture zero  0x01 }
		5  { cw 0x9900 255 ; cw 0x9901 1 ; capture chB_left 0x02 }
		6  { cw 0x48FB 0x01 ; cw 0x48FE 0x3F ; cw 0x9900 1 ; cw 0x48FB 0x00 ; capture ram_left 0x01 }
		7  { cw 0x9000 0x02 ; cw 0x9900 255 ; cw 0x9000 0x3F ; capture closed_left 0x01 }
		8  { cw 0x9900 128 ; cw 0x7FFA 0x40 ; capture vol_half 0x01 }
		9  { cw 0x7FFA 0x80 ; cw 0x7FFE 0x40 ; capture master_half 0x01 }
		10 { cw 0x7FFE 0x80 ; cw 0x7FFA 0x00 ; capture vol_zero 0x01 }
		11 { cw 0x7FFA 0x80 ; cw 0x7000 0x3F ; cw 0x7FFA 0x00 ; cw 0x7000 0x01 ; capture vol_scc_window 0x01 }
		12 { finish }
	}
}

after time 2 next
