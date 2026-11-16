# Savestate round trip for the OPLL.
#   T_MODE=save T_NAME=<name> T_SEQ=<sequence> T_OUT=<dir> T_DEV=<device> openmsx ... -script opll_state.tcl
#     plays the sequence (chrec.tcl format), waits 0.3 s, saves, then records each channel for 0.5 s
#   T_MODE=load T_NAME=<name> T_OUT=<dir> T_DEV=<device> openmsx ... -script opll_state.tcl
#     loads, then records each channel for 0.5 s
# Writes go one per millisecond: the YM2413 keeps only one write per 18-step slot.
# <dir>/state.txt gets the outcome.

set renderer none
set sound_driver null

set OUT $::env(T_OUT)
set NAME $::env(T_NAME)
set DEV $::env(T_DEV)
set NCH 14
set ::f [open $OUT/state.txt w]

proc mem_write {addr val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$addr}] $val
		}
	}
}

proc step {} {
	while {[llength $::cmds] > 0} {
		set c [lindex $::cmds 0]
		set ::cmds [lrange $::cmds 1 end]
		lassign $c op a b
		switch -- $op {
			mem  { mem_write [scan $a %x] [scan $b %x]; after time 0.001 step; return }
			io   { debug write ioports [scan $a %x] [scan $b %x]; after time 0.001 step; return }
			mark { }
			wait { after time [expr {$a / 1000.0}] step; return }
			default { puts $::f "ERROR unknown command: $c"; close $::f; exit }
		}
	}
	after time 0.3 do_save
}

proc do_save {} {
	if {[catch {savestate $::NAME} msg]} {
		puts $::f "save ERROR: $msg"
		close $::f
		exit
	}
	puts $::f "save OK"
	after time 0.01 start_rec
}

proc do_load {} {
	if {[catch {loadstate $::NAME} msg]} {
		puts $::f "load ERROR: $msg"
		close $::f
		exit
	}
	puts $::f "load OK"
	# Starting the recording right after loadstate wrote no files.
	after time 0.01 start_rec
}

proc start_rec {} {
	for {set i 1} {$i <= $::NCH} {incr i} {
		set "::${::DEV}_ch${i}_record" [file join $::OUT ch$i.wav]
	}
	after time 0.5 {
		for {set i 1} {$i <= $::NCH} {incr i} {
			set "::${::DEV}_ch${i}_record" ""
		}
		close $::f
		exit
	}
}

if {$::env(T_MODE) eq "save"} {
	set fh [open $::env(T_SEQ) r]
	set ::cmds {}
	foreach line [split [read $fh] "\n"] {
		set line [string trim [regsub {#.*$} $line ""]]
		if {$line ne ""} { lappend ::cmds $line }
	}
	close $fh
	after time 2 step
} else {
	after time 2 do_load
}
