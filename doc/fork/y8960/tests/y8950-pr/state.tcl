# セーブステートの書き出しと読み込み。
#   T_MODE=save T_NAME=<名前> T_OUT=<出力先> openmsx ... -ext audio -script state.tcl
#     リズム音と楽音を鳴らしたまま 0.5 秒後にセーブステートを書く
#   T_MODE=load T_NAME=<名前> T_OUT=<出力先> T_DEV=<デバイス名> openmsx ... -ext audio -script state.tcl
#     読み込み、チャンネルごとに 0.5 秒録る
# <出力先>/state.txt に結果を書く。

set renderer none
set sound_driver null

set OUT $::env(T_OUT)
set NAME $::env(T_NAME)
set DEV [expr {[info exists ::env(T_DEV)] ? $::env(T_DEV) : "Generic MSX-Audio"}]
set ::f [open $OUT/state.txt w]

proc r {reg val} {
	debug write ioports 0xC0 $reg
	debug write ioports 0xC1 $val
}

proc play {} {
	foreach {m c ch} {0 3 0  1 4 1  2 5 2  16 19 6  17 20 7  18 21 8} {
		r [expr {0x20 + $m}] 0x21
		r [expr {0x20 + $c}] 0x22
		r [expr {0x40 + $m}] 0x14
		r [expr {0x40 + $c}] 0x10
		r [expr {0x60 + $m}] 0xF2
		r [expr {0x60 + $c}] 0xF2
		r [expr {0x80 + $m}] 0x13
		r [expr {0x80 + $c}] 0x13
		r [expr {0xC0 + $ch}] 0x06
		r [expr {0xA0 + $ch}] 0x81
	}
	foreach ch {0 1 2} { r [expr {0xB0 + $ch}] [expr {0x30 + $ch}] }
	foreach ch {6 7 8} { r [expr {0xB0 + $ch}] [expr {0x14 + $ch - 6}] }
	r 0xBD 0x3F
	if {[info exists ::env(T_WAVE)]} {
		r 0x01 0x20
		for {set i 0} {$i < 0x16} {incr i} { r [expr {0xE0 + $i}] [expr {($i + 1) & 3}] }
	}
}

proc do_save {} {
	play
	after time 0.5 {
		if {[catch {savestate $::NAME} msg]} {
			puts $::f "save ERROR: $msg"
			close $::f
			exit
		} else {
			puts $::f "save OK"
			# 書いた後もそのまま録る。読み込んだ側の録音と比べる
			after time 0.01 start_rec
		}
	}
}

proc do_load {} {
	if {[catch {loadstate $::NAME} msg]} {
		puts $::f "load ERROR: $msg"
		close $::f
		exit
		return
	}
	puts $::f "load OK"
	after time 0.01 start_rec
}

proc start_rec {} {
	puts $::f "machine [machine]"
	for {set i 1} {$i <= 15} {incr i} {
		set "::${::DEV}_ch${i}_record" [file join $::OUT ch$i.wav]
	}
	after time 0.5 {
		for {set i 1} {$i <= 15} {incr i} {
			set "::${::DEV}_ch${i}_record" ""
		}
		close $::f
		exit
	}
}

if {$::env(T_MODE) eq "save"} {
	after time 2 do_save
} else {
	after time 2 do_load
}
