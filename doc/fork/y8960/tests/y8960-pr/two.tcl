# A second Y8960 cartridge: both would answer on the System Controller's ports, so the second
# one is to fail to load with an error message while the first runs on.
#   T_OUT=<dir> openmsx -machine ... -ext HRA_Y8960 -script two.tcl
# <dir>/two.txt gets the outcome of the second 'ext', the extensions, and "still running" 2 s later.

set renderer none
set sound_driver null
set out [open $::env(T_OUT)/two.txt w]
if {[catch {ext HRA_Y8960} msg]} { puts $out "second: ERROR: $msg" } else { puts $out "second: OK" }
puts $out "extensions: [list_extensions]"
after time 2 {
	puts $out "still running"
	close $out
	exit
}
