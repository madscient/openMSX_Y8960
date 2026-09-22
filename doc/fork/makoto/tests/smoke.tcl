set renderer none
set sound_driver null

# Headless smoke test of the Makoto extension.
# Run with: -machine C-BIOS_MSX2+ -ext Makoto -script smoke.tcl
# Results go to the file named by MAKOTO_TEST_OUT (default makoto-smoke.txt).

if {[info exists ::env(MAKOTO_TEST_OUT)]} {
	set out_name $::env(MAKOTO_TEST_OUT)
} else {
	set out_name makoto-smoke.txt
}
set out [open $out_name w]
set failures 0

proc check {name got want} {
	global out failures
	if {$got eq $want} {
		puts $out "PASS $name"
	} else {
		puts $out "FAIL $name: got $got, want $want"
		incr failures
	}
}

proc lo {reg val} {
	debug write ioports 0x14 $reg
	debug write ioports 0x15 $val
}
proc hi {reg val} {
	debug write ioports 0x16 $reg
	debug write ioports 0x17 $val
}
proc regs {addr} { debug read "Makoto regs" $addr }
proc block {debuggable addr len} {
	binary scan [debug read_block $debuggable $addr $len] cu* vals
	return $vals
}
proc hex {bytes} {
	set r {}
	foreach b $bytes { lappend r [format %02X $b] }
	return $r
}

proc test_debuggables {} {
	check "regs debuggable size" [debug size "Makoto regs"] 512
	check "ADPCM RAM debuggable size" [debug size "Makoto ADPCM RAM"] [expr {256 * 1024}]
}

proc test_register_mirror {} {
	lo 0x30 0x71
	check "front register written through 14h/15h" [regs 0x30] 113
	hi 0xB4 0xC0
	check "back register written through 16h/17h" [regs 0x1B4] 192
	# A data write that does not match the latched half is dropped by the chip
	debug write ioports 0x14 0x31
	debug write ioports 0x17 0x55
	check "17h after a 14h address is ignored" [list [regs 0x31] [regs 0x131]] {0 0}
}

proc test_ssg_readback {} {
	lo 0x07 0x38
	check "SSG register reads back through 15h" [debug read ioports 0x15] 56
}

# Writes 8 bytes through the ADPCM-B record path, then reads them back with
# real IN instructions (a debugger read of 17h is only a peek).
proc test_adpcm_ram {} {
	hi 0x00 0x01        ;# reset
	hi 0x00 0x00
	hi 0x01 0x00        ;# x1 bit DRAM
	hi 0x02 0x00
	hi 0x03 0x00        ;# start 0
	hi 0x04 0x00
	hi 0x05 0x01        ;# end 0100h
	hi 0x0C 0xFF
	hi 0x0D 0xFF        ;# limit FFFFh
	hi 0x00 0x60        ;# record + external memory
	foreach b {0x11 0x22 0x33 0x44 0x55 0x66 0x77 0x88} { hi 0x08 $b }
	check "ADPCM RAM holds the recorded bytes" \
		[hex [block "Makoto ADPCM RAM" 0 8]] {11 22 33 44 55 66 77 88}

	hi 0x00 0x00
	# ymfm resets the flag mask to 1Ch, which hides EOS, BRDY and ZERO
	hi 0x10 0x00
	hi 0x00 0x20        ;# external memory, read
	# di / ld a,8 / out (16h),a / in a,(17h) x2 (dummy) / ld hl,C100h / ld b,8
	# loop: in a,(16h) / ld (hl),a / inc hl / in a,(17h) / ld (hl),a / inc hl / djnz
	# jr $
	set code {0xF3 0x3E 0x08 0xD3 0x16 0xDB 0x17 0xDB 0x17 0x21 0x00 0xC1 0x06 0x08
	          0xDB 0x16 0x77 0x23 0xDB 0x17 0x77 0x23 0x10 0xF6 0x18 0xFE}
	debug write_block memory 0xC000 [binary format c* $code]
	reg pc 0xC000
	after time 0.01 {step finish_adpcm_ram}
}

proc finish_adpcm_ram {} {
	set vals [block memory 0xC100 16]
	set data {}
	set brdy {}
	foreach {st d} $vals {
		lappend data $d
		lappend brdy [expr {($st >> 3) & 1}]
	}
	check "ADPCM RAM reads back through 17h" [hex $data] {11 22 33 44 55 66 77 88}
	check "BRDY is set before each read" $brdy {1 1 1 1 1 1 1 1}
	set status {}
	foreach {st d} $vals { lappend status $st }
	puts $::out "INFO status 1 before each read: [hex $status]"
	test_timer_a
}

proc test_timer_a {} {
	lo 0x29 0x81        ;# 6 channel mode, timer A IRQ enabled
	lo 0x24 0xFF
	lo 0x25 0x03        ;# shortest period
	lo 0x27 0x15        ;# reset flag A, enable flag A, load A
	after time 0.001 {step finish_timer_a}
}

proc finish_timer_a {} {
	check "timer A flag in status 0" [expr {[debug read ioports 0x14] & 1}] 1
	lo 0x27 0x30        ;# stop, reset both flags
	check "timer A flag cleared by 27h" [expr {[debug read ioports 0x14] & 1}] 0
	finish
}

proc finish {} {
	global out failures
	puts $out "failures $failures"
	close $out
	exit
}

# Errors raised inside 'after' callbacks never reach a console here, so
# every step reports its own error and ends the run.
proc step {body} {
	global out failures
	if {[catch {uplevel #0 $body} msg]} {
		puts $out "ERROR $msg"
		incr failures
		finish
	}
}

after time 3 {
	step {
		test_debuggables
		test_register_mirror
		test_ssg_readback
		test_adpcm_ram
	}
}
