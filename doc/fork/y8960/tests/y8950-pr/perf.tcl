# 速度制限を外し、MSX-AUDIO の楽音 6ch とリズム 5 音を鳴らしたまま、エミュレーションの 60 秒にかかる実時間を測る。
# チャンネルの録音を有効にして、音を作る処理を必ず走らせる。
#   T_OUT=<出力先> T_DEV=<デバイス名> [T_WAVE=1] openmsx ... -script perf.tcl
set renderer none
set sound_driver null

set OUT $::env(T_OUT)
set DEV $::env(T_DEV)
set ::f [open $OUT/perf.txt w]

proc r {reg val} {
	debug write ioports 0xC0 $reg
	debug write ioports 0xC1 $val
}

proc go {} {
	if {![info exists ::env(T_SILENT)]} play
	for {set i 1} {$i <= 1} {incr i} {
		set "::${::DEV}_ch${i}_record" [file join $::OUT ch$i.wav]
	}
	set ::throttle off
	set ::t0 [clock milliseconds]
	after time 300 done
}

proc play {} {
	foreach {m c ch} {0 3 0  1 4 1  2 5 2  8 11 3  9 12 4  10 13 5  16 19 6  17 20 7  18 21 8} {
		r [expr {0x20 + $m}] 0xE1
		r [expr {0x20 + $c}] 0xE2
		r [expr {0x40 + $m}] 0x14
		r [expr {0x40 + $c}] 0x10
		r [expr {0x60 + $m}] 0xF2
		r [expr {0x60 + $c}] 0xF2
		r [expr {0x80 + $m}] 0x03
		r [expr {0x80 + $c}] 0x03
		r [expr {0xC0 + $ch}] 0x06
		r [expr {0xA0 + $ch}] [expr {0x81 + $ch * 8}]
	}
	foreach ch {0 1 2 3 4 5} { r [expr {0xB0 + $ch}] [expr {0x30 + $ch}] }
	foreach ch {6 7 8} { r [expr {0xB0 + $ch}] [expr {0x14 + $ch - 6}] }
	r 0xBD 0xFF
	if {[info exists ::env(T_WAVE)]} {
		r 0x01 0x20
		for {set i 0} {$i < 0x16} {incr i} { r [expr {0xE0 + $i}] [expr {($i + 1) & 3}] }
	}
}

proc done {} {
	set ms [expr {[clock milliseconds] - $::t0}]
	for {set i 1} {$i <= 1} {incr i} {
		set "::${::DEV}_ch${i}_record" ""
	}
	puts $::f "wall_ms $ms"
	close $::f
	exit
}

after time 2 go
