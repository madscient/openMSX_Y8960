# 音列（tones.tcl の書式）を流し、音源のチャンネルごとの出力を WAV に録る。
#   T_OUT=<出力先> T_SEQ=<音列> [T_DEV=<デバイス名>] [T_NCH=<チャンネル数>] openmsx ... -script chrec.tcl
# 出力は <出力先>/ch1.wav ... と、mark の時刻の log.txt。

set renderer none
set sound_driver null

set OUT $::env(T_OUT)
set SEQ $::env(T_SEQ)
set DEV [expr {[info exists ::env(T_DEV)] ? $::env(T_DEV) : "MSX-AUDIO"}]
set NCH [expr {[info exists ::env(T_NCH)] ? $::env(T_NCH) : 15}]

set f [open $SEQ r]
set ::cmds {}
foreach line [split [read $f] "\n"] {
	set line [string trim [regsub {#.*$} $line ""]]
	if {$line eq ""} continue
	lappend ::cmds $line
}
close $f

set ::log [open $OUT/log.txt w]

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
			mark { puts $::log [format "%.4f %s" [expr {[machine_info time] - $::t0}] $a] }
			wait { after time [expr {$a / 1000.0}] step; return }
			default { puts $::log "ERROR unknown command: $c"; finish; return }
		}
	}
	after time 0.3 finish
}

proc finish {} {
	for {set i 1} {$i <= $::NCH} {incr i} {
		set "::${::DEV}_ch${i}_record" ""
	}
	puts $::log "END"
	close $::log
	after time 0.1 exit
}

proc start {} {
	for {set i 1} {$i <= $::NCH} {incr i} {
		set "::${::DEV}_ch${i}_record" [file join $::OUT ch$i.wav]
	}
	set ::t0 [machine_info time]
	after time 0.2 step
}

after time 2 start
