set renderer none
set sound_driver null

# Plays SSG tone A and switches the prescaler 6 -> 3 -> 2 while it sounds,
# recording each step to its own WAV. The SSG clock is 8MHz/4, /2 and /1
# for those settings, so tone period 128 must sound at 976.6, 1953.1 and
# 3906.3 Hz. check-prescale.py measures that.
# Run with: -machine C-BIOS_MSX2+ -ext Makoto -script prescale.tcl
# MAKOTO_TEST_OUT names a result file; the WAVs go next to it.
# It records the whole mix rather than one channel: a recorded channel
# goes through its own zero-filled buffer, not the path that is heard.

set out_name $::env(MAKOTO_TEST_OUT)
set out [open $out_name w]
set dir [file dirname $out_name]

proc lo {reg val} {
	debug write ioports 0x14 $reg
	debug write ioports 0x15 $val
}
# The prescaler switches when 2Dh-2Fh is written to the address latch.
proc select {reg} { debug write ioports 0x14 $reg }

proc segment {name} {
	global dir out
	record start -audioonly [file join $dir makoto-prescale-$name.wav]
	puts $out "segment $name"
}

proc fail {msg} {
	global out
	puts $out "ERROR $msg"
	close $out
	exit
}

after time 1 {
	if {[catch {
		lo 0x00 0x80; lo 0x01 0x00    ;# tone A period 128
		lo 0x07 0x3E                   ;# tone A only
		lo 0x08 0x0F                   ;# full volume
		segment p6
		after time 0.5 {
			if {[catch {
				record stop
				select 0x2E
				segment p3
				after time 0.5 {
					if {[catch {
						record stop
						select 0x2F
						segment p2
						after time 0.5 {
							record stop
							puts $out "done"
							close $out
							exit
						}
					} msg]} { fail $msg }
				}
			} msg]} { fail $msg }
		}
	} msg]} { fail $msg }
}
