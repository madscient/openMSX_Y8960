# A running MSX-TIMER counter across a savestate.
#   T_MODE=save T_NAME=<name> T_OUT=<dir> openmsx ... -ext HRA_Y8960 -script timer_state.tcl
#     starts counter 0 (resolution 1, terminal FFh), saves 3 ms later, and
#     reads the count and the flags 5 ms after that
#   T_MODE=load T_NAME=<name> T_OUT=<dir> openmsx ... -script timer_state.tcl
#     loads and reads the same 5 ms later
# Both write "count <B3h> flags <B2h>" to <dir>/state.txt; they must match.

set renderer none
set sound_driver null

set OUT $::env(T_OUT)
set NAME $::env(T_NAME)
set ::f [open $OUT/state.txt w]

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}
proc reg {r v} {
	debug write ioports 0xB0 $r
	debug write ioports 0xB1 $v
}
proc report {} {
	puts $::f [format "count %02X flags %02X" [debug read ioports 0xB3] [debug read ioports 0xB2]]
	close $::f
	exit
}

proc do_save {} {
	mem_write 0x7FFF 0x80
	reg 0 0x10
	reg 1 0xFF
	reg 2 0x03
	debug write ioports 0xB3 0
	after time 0.003 {
		if {[catch {savestate $::NAME} msg]} { puts $::f "save ERROR: $msg" ; close $::f ; exit }
		after time 0.005 report
	}
}

proc do_load {} {
	if {[catch {loadstate $::NAME} msg]} { puts $::f "load ERROR: $msg" ; close $::f ; exit }
	after time 0.005 report
}

if {$::env(T_MODE) eq "save"} {
	after time 2 do_save
} else {
	after time 2 do_load
}
