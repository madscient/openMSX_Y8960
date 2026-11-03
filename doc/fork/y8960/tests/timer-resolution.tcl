# MSX-TIMER の分解能の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script timer-resolution.tcl
#
# 結果は標準出力と、環境変数 Y8960_TEST_OUT のディレクトリの
# timer-resolution.txt。**判定は最終行の RESULT を見る。** openmsx は Tcl の
# `exit` に渡した値をプロセスの終了コードにしない。
#
# クロックは 42.95454MHz (= 3579545 * 12) で、Unit Time は 2^(10+2r) 分周
# （2026-11-03、hra1129 さんの回答。カートリッジの RTL もこのクロック）。
#
#   reso 0 = 23.839156us    reso 4 = 6102.824055us
#   reso 1 = 95.356626us    reso 5 = 24411.296222us
#   reso 2 = 381.426503us   reso 6 = 97645.184886us
#   reso 3 = 1525.706014us  reso 7 = 390580.739545us
#
# Y8960_Cartridge の src/timer/doc/msx_timer.xlsx は 85.909080MHz で計算していて、
# 値はこの半分になる。そちらは使わない。
#
# Count Time は Unit Time × (終端値 + 1) で、**分解能そのものではない。**
# 下の終端値 5 では、reso 0 が 143.035us、reso 7 が 2.343484s。
#
# **測り方は 2 通り。**
#  - Unit Time: 終端値を大きく取ってカウンタを走らせ、決まった時間だけ
#    進めてからカウンタ (B3h) を読む。読めた値がそのまま刻んだ回数になる
#  - Count Time: 終端値 5 で走らせ、期待値の前後で割り込みフラグ (B2h) を
#    見る。**前で 0、後で 1** の 2 点で挟むので、速すぎても遅すぎても落ちる
#
# **終端値 255 は分けて測る。** 内部の刻み計算は終端値+1 を分解能ぶん左シフト
# するので、終端値 255 かつ reso 7 のときだけ 256<<24 が 32bit を溢れる。
# ここだけ別の分岐に落ちるので、他の 8 件とは独立に見る必要がある。
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
		lappend lines [format "PASS  %-42s %3s" $name $got]
	} else {
		incr fails
		lappend lines [format "FAIL  %-42s %3s (want %s)" $name $got $want]
	}
}

proc report_range {name got lo hi} {
	global lines fails
	if {$got >= $lo && $got <= $hi} {
		lappend lines [format "PASS  %-42s %3s (want %s..%s)" $name $got $lo $hi]
	} else {
		incr fails
		lappend lines [format "FAIL  %-42s %3s (want %s..%s)" $name $got $lo $hi]
	}
}

# 分解能 / 待つ秒数 / 期待するカウンタの下限と上限
set units {
	{0 0.001 41 42}
	{1 0.005 52 53}
	{2 0.02  52 53}
	{3 0.1   65 66}
	{4 0.3   49 50}
	{5 1.0   40 41}
	{6 2.0   20 21}
	{7 8.0   20 21}
}
# 終端値 255 での刻み。上の表と同じ reso 7 を、溢れる側の終端値で測る
set wide {
	{7 255 8.0 20 21}
}
# 分解能 / 期待値より手前の秒数 / 期待値より後の秒数。終端値は 5
set counts {
	{0 0.00012 0.00016}
	{7 2.2     2.5}
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
	if {$ui < [llength $units]} { unit_start } else { wide_start }
}

proc wide_start {} {
	global wide
	set c [lindex $wide 0]
	treg 0 0 [expr {[lindex $c 0] << 4}]
	treg 0 1 [lindex $c 1]
	treg 0 2 0x03
	after time [lindex $c 2] wide_end
}

proc wide_end {} {
	global wide
	set c [lindex $wide 0]
	report_range "unit reso [lindex $c 0] end [lindex $c 1] after [lindex $c 2]s" 		[counter 0] [lindex $c 3] [lindex $c 4]
	treg 0 2 0x00
	count_start
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
