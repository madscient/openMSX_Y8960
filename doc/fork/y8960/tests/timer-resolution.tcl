# MSX-TIMER の分解能が xlsx の値どおりであることの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script timer-resolution.tcl
#
# 結果は標準出力と、環境変数 Y8960_TEST_OUT のディレクトリの
# timer-resolution.txt。**判定は最終行の RESULT を見る。** openmsx は Tcl の
# `exit` に渡した値をプロセスの終了コードにしない。
#
# 出典は Y8960_Cartridge の src/timer/doc/msx_timer.xlsx。Base Clock は
# 85.909080MHz (= 3579545 * 24) で、Unit Time は 2^(10+2r) 分周。
#
#   reso 0 = 11.919578us    reso 4 = 3051.412028us
#   reso 1 = 47.678313us    reso 5 = 12205.648111us
#   reso 2 = 190.713252us   reso 6 = 48822.592443us
#   reso 3 = 762.853007us   reso 7 = 195290.369772us
#
# xlsx にはもう 1 列 Count Time があり、これは Unit Time × (終端値 + 1)。
# **分解能そのものではない。** シートの例は終端値 5 で、reso 0 が 71.517us、
# reso 7 が 1171742us。この 2 つを分解能と取り違えないこと。
#
# **測り方は 2 通り。**
#  - Unit Time: 終端値を大きく取ってカウンタを走らせ、決まった時間だけ
#    進めてからカウンタ (B3h) を読む。読めた値がそのまま刻んだ回数になる
#  - Count Time: 終端値 5 で走らせ、期待値の前後で割り込みフラグ (B2h) を
#    見る。**前で 0、後で 1** の 2 点で挟むので、速すぎても遅すぎても落ちる
#
# 終端値に 255 を使わないのは、reso 7 のとき内部計算が 32bit を溢れるため。
# 溢れる条件は終端値 255 かつ reso 7 だけ。
#
# カウンタの読みは端数の持ち越しで 1 ずれうるので、幅で見る。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set fails 0
set lines {}

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps << 18) | ($ss << 16) | $offset}] $val
		}
	}
}

# B0h にレジスタ番号（b3:b2 がタイマー番号、b1:b0 がその中の番号）、B1h が値
#   reg0: b0=繰り返し, b6:b4=分解能, b7=割り込み許可
#   reg1: 終端値
#   reg2: b0=カウント許可, b1=カウンタをクリア
proc treg {ch rg val} {
	debug write ioports 0xB0 [expr {($ch << 2) | $rg}]
	debug write ioports 0xB1 $val
}

proc counter {ch} {
	debug write ioports 0xB3 $ch
	debug read ioports 0xB3
}

proc report {name got want} {
	global lines fails
	if {$got == $want} {
		lappend lines [format "PASS  %-34s %3s" $name $got]
	} else {
		incr fails
		lappend lines [format "FAIL  %-34s %3s (want %s)" $name $got $want]
	}
}

proc report_range {name got lo hi} {
	global lines fails
	if {$got >= $lo && $got <= $hi} {
		lappend lines [format "PASS  %-34s %3s (want %s..%s)" $name $got $lo $hi]
	} else {
		incr fails
		lappend lines [format "FAIL  %-34s %3s (want %s..%s)" $name $got $lo $hi]
	}
}

# 分解能 / 待つ秒数 / 期待するカウンタの下限と上限
set units {
	{0 0.001 83 84}
	{1 0.005 104 105}
	{2 0.02  104 105}
	{3 0.1   131 132}
	{4 0.3    98  99}
	{5 1.0    81  82}
	{6 2.0    40  41}
	{7 8.0    40  41}
}
# 分解能 / 期待値より手前の秒数 / 期待値より後の秒数。終端値は 5
set counts {
	{0 0.00006 0.00008}
	{7 1.1     1.25}
}

set ui 0
set ci 0

proc unit_start {} {
	global units ui
	set c [lindex $units $ui]
	treg 0 0 [expr {[lindex $c 0] << 4}]
	treg 0 1 200
	treg 0 2 0x03
	after time [lindex $c 1] unit_end
}

proc unit_end {} {
	global units ui
	set c [lindex $units $ui]
	report_range "unit reso [lindex $c 0] after [lindex $c 1]s" \
		[counter 0] [lindex $c 2] [lindex $c 3]
	treg 0 2 0x00
	incr ui
	if {$ui < [llength $units]} { unit_start } else { count_start }
}

proc count_start {} {
	global counts ci
	set c [lindex $counts $ci]
	debug write ioports 0xB2 0x0F
	treg 0 0 [expr {[lindex $c 0] << 4}]
	treg 0 1 5
	treg 0 2 0x03
	after time [lindex $c 1] count_before
}

proc count_before {} {
	global counts ci
	set c [lindex $counts $ci]
	report "count reso [lindex $c 0] at [lindex $c 1]s" [debug read ioports 0xB2] 0
	after time [expr {[lindex $c 2] - [lindex $c 1]}] count_after
}

proc count_after {} {
	global counts ci
	set c [lindex $counts $ci]
	report "count reso [lindex $c 0] at [lindex $c 2]s" [debug read ioports 0xB2] 1
	treg 0 2 0x00
	incr ci
	if {$ci < [llength $counts]} { count_start } else { finish }
}

proc finish {} {
	global OUT lines fails
	if {$fails > 0} {
		lappend lines "RESULT: FAILED $fails"
	} else {
		lappend lines "RESULT: ALL PASS"
	}
	set f [open "$OUT/timer-resolution.txt" w]
	foreach l $lines { puts $f $l ; puts $l }
	close $f
	exit
}

proc run_test {} {
	# I/O Enabler2 の b7 でタイマーのポートを開ける
	mem_write 0x7FFF 0x80
	after time 0.05 unit_start
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
