# tones.txt の音列を openMSX で流し、最終ミックスを WAV に録る。実機は tones-mga.ps1 が同じものを流す。
#
#   Y8960_TEST_OUT=<出力先> openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script <このファイル>
#
# 書き出すのは <出力先>/tones-openmsx.wav と、mark を通った時刻の記録 tones-openmsx.txt。
# 音列は環境変数 Y8960_TONES で替えられる（省くとこのファイルの隣の tones.txt）。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set SEQ [expr {[info exists ::env(Y8960_TONES)] ? $::env(Y8960_TONES) \
	: [file join [file dirname [info script]] tones.txt]}]

set f [open $SEQ r]
set ::cmds {}
foreach line [split [read $f] "\n"] {
	set line [string trim [regsub {#.*$} $line ""]]
	if {$line ne ""} { lappend ::cmds $line }
}
close $f

set ::log [open $OUT/tones-openmsx.txt w]

# カートリッジのスロットを探さず、全スロットに書く。他のスロットは ROM か、C-BIOS が
# 使っていない RAM なので害が無い（mixer-volume.tcl と同じ）
proc mem_write {addr val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$addr}] $val
		}
	}
}

# 書き込みごとに 1ms 進める。実機の側は MGA との 1 往復が約 1ms かかる。同じ時刻に続けて
# 書くと、NukeYKT の OPLL は番地の書き込みをデータの書き込みで上書きして捨てる
# （YM2413NukeYKT.cc の writePort が writes[cycle_offset] に置く）
proc step {} {
	while {[llength $::cmds] > 0} {
		set c [lindex $::cmds 0]
		set ::cmds [lrange $::cmds 1 end]
		lassign $c op a b
		switch -- $op {
			mem  { mem_write [scan $a %x] [scan $b %x]; after time 0.001 step; return }
			io   { debug write ioports [scan $a %x] [scan $b %x]; after time 0.001 step; return }
			mark { puts $::log [format "%.3f %s" [expr {[machine_info time] - $::t0}] $a] }
			wait { after time [expr {$a / 1000.0}] step; return }
			default { puts $::log "ERROR unknown command: $c"; finish; return }
		}
	}
	# 後ろに 1 秒の無音を置いて終える（実機の側と同じ）
	after time 1.0 finish
}

proc finish {} {
	record stop
	close $::log
	after time 0.1 exit
}

proc start {} {
	record start -audioonly $::OUT/tones-openmsx.wav
	set ::t0 [machine_info time]
	# 前に 1 秒の無音を置く。解析が雑音の床を取るのに使う
	after time 1.0 step
}

# 起動が落ち着いてから始める
after time 2 start
