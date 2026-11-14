# 機械を起動し、拡張を挿して、名前に _firmware を含む設定と音源の一覧を書き出す。
#   T_OUT=<出力ファイル> T_EXT=<拡張> openmsx -machine C-BIOS_MSX2+ -script firmware.tcl
set renderer none
set sound_driver null
set ::f [open $::env(T_OUT) w]
after time 1 {
	if {[catch {ext $::env(T_EXT)} msg]} {
		puts $::f "ext ERROR: $msg"
	} else {
		puts $::f "ext OK: $msg"
		foreach s [lsort [openmsx_info setting]] {
			if {[string match *_firmware* $s]} { puts $::f "setting $s = [set ::$s]" }
		}
		foreach d [lsort [machine_info sounddevice]] {
			puts $::f "sounddevice $d : [machine_info sounddevice $d]"
		}
		foreach c [lsort [machine_info connector]] {
			puts $::f "connector $c"
		}
		foreach d [lsort [debug list]] {
			if {[string match -nocase *audio* $d] || [string match -nocase *FS-CA1* $d]} { puts $::f "debuggable $d" }
		}
	}
	close $::f
	exit
}
