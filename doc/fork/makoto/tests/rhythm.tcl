set renderer none
set sound_driver null

# Plays the bass drum of the rhythm part and reports the peak of channel 1
# (FM + rhythm + ADPCM). With the rhythm ROM in systemroms the peak is large;
# without it the rhythm part decodes to almost nothing.
# Run with: -machine C-BIOS_MSX2+ -ext Makoto -script rhythm.tcl
# MAKOTO_TEST_OUT names the result file; the WAV goes next to it.

set out_name $::env(MAKOTO_TEST_OUT)
set out [open $out_name w]
set prefix [file join [file dirname $out_name] makoto-rhythm]

proc lo {reg val} {
	debug write ioports 0x14 $reg
	debug write ioports 0x15 $val
}

proc wav_peak {name} {
	set f [open $name rb]
	set data [read $f]
	close $f
	# samples start after the 44-byte header, 16 bit little endian
	binary scan [string range $data 44 end] s* samples
	set peak 0
	foreach s $samples {
		if {abs($s) > $peak} { set peak [expr {abs($s)}] }
	}
	return $peak
}

proc finish {} {
	global out prefix
	record_channels stop
	set files [glob -nocomplain ${prefix}*.wav]
	puts $out "files [llength $files]"
	foreach f $files { puts $out "peak [file tail $f] [wav_peak $f]" }
	close $out
	exit
}

after time 3 {
	if {[catch {
		record_channels start -prefix $prefix Makoto 1
		lo 0x11 0x3F        ;# rhythm total level: loudest
		lo 0x18 0xDF        ;# bass drum: left + right, loudest
		lo 0x10 0x01        ;# key on bass drum
		after time 0.3 finish
	} msg]} {
		puts $out "ERROR $msg"
		close $out
		exit
	}
}
