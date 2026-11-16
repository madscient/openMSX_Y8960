# The cartridge's open I/O ports across a savestate.
#   T_MODE=save T_NAME=<name> T_ENABLE=<value> [T_WHICH=opll|opl2] T_OUT=<dir> \
#     openmsx ... -ext HRA_Y8960 -script cart_state.tcl
#     writes T_ENABLE to I/O Enabler1 (7FF6h, opll) or I/O Enabler2 (7FFFh, opl2) and saves
#   T_MODE=load T_NAME=<name> [T_WHICH=opll|opl2] T_OUT=<dir> openmsx ... -script cart_state.tcl
#     loads, writes 5Ah to register 30h of the OPLL (ports 7Ch/7Dh) or register 20h of the
#     OPL2 (ports C0h/C1h), and puts that register and, for opl2, 7FFFh as the CPU reads it
#     in <dir>/state.txt
# With the port's bit saved as 1 the register must read 5A, with 0 it must not.

set renderer none
set sound_driver null

set OUT $::env(T_OUT)
set NAME $::env(T_NAME)
set WHICH [expr {[info exists ::env(T_WHICH)] ? $::env(T_WHICH) : "opll"}]
set ::f [open $OUT/state.txt w]

if {$WHICH eq "opll"} {
	set ENABLER 0x7FF6 ; set PORT 0x7C ; set REG 0x30 ; set REGS "Y8960 OPLL regs"
} else {
	set ENABLER 0x7FFF ; set PORT 0xC0 ; set REG 0x20 ; set REGS "Y8960 OPL2 regs"
}

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

proc do_save {} {
	mem_write $::ENABLER $::env(T_ENABLE)
	after time 0.01 {
		if {[catch {savestate $::NAME} msg]} { puts $::f "save ERROR: $msg" } else { puts $::f "save OK" }
		close $::f
		exit
	}
}

proc do_load {} {
	if {[catch {loadstate $::NAME} msg]} {
		puts $::f "load ERROR: $msg"
		close $::f
		exit
	}
	puts $::f "load OK"
	after time 0.01 {
		debug write ioports $::PORT $::REG
		after time 0.001 {
			debug write ioports [expr {$::PORT + 1}] 0x5A
			after time 0.01 {
				puts $::f [format "reg %02X" [debug read $::REGS $::REG]]
				if {$::WHICH eq "opl2"} {
					puts $::f [format "7FFF %02X" [debug read "slotted memory" [expr {(1 << 18) | 0x7FFF}]]]
				}
				close $::f
				exit
			}
		}
	}
}

if {$::env(T_MODE) eq "save"} {
	after time 2 do_save
} else {
	after time 2 do_load
}
