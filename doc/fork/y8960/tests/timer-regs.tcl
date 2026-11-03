# MSX-TIMER のレジスタ 3 と、B3h の選択の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script timer-regs.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# timer-regs.txt を書き出す。**判定は最終行の RESULT を見る。**
# openmsx は Tcl の `exit` に渡した値をプロセスの終了コードにしない。
#
# - 各コアのレジスタ 3 は無く、読むと 00h
# - B3h に 0-3 以外を書くとどのカウンタも選ばれず、B3h は FFh を読む
# - リセット直後の B3h の選択はコア 0
#
# いずれもカートリッジの RTL（msx_timer.v / msx_timer_core.v）による。
#
# **判別力**: 変更前の実装は、レジスタ 3 を FFh で読み、B3h に書いた値を
# 下位 2 ビットに丸める。リセット直後の選択は初期化されていなかったので、
# 最後の項目は偶然通ることがある。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/timer-regs.txt" w]
set fails 0

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

proc check {name got want} {
	global log fails
	if {$got == $want} {
		puts $log [format "PASS  %-48s 0x%02X" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-48s got 0x%02X want 0x%02X" $name $got $want]
	}
}

# B0h のインデックスは bit3-2 がコア、bit1-0 がレジスタ
proc treg {core reg} {
	debug write ioports 0xB0 [expr {($core << 2) | $reg}]
	debug read ioports 0xB1
}

proc run_test {} {
	mem_write 0x7FFF 0x80        ;# I/O Enabler2 b7: MSX-TIMER を開く

	# コア 1 のカウント値を 0 以外にしておき、選択の取り違えが値に出るようにする
	debug write ioports 0xB0 0x05 ;# コア 1 のレジスタ 1 (カウント値)
	debug write ioports 0xB1 0x10
	debug write ioports 0xB0 0x04 ;# コア 1 のレジスタ 0 (モード)
	debug write ioports 0xB1 0x01 ;# 分解能 0、リピート
	debug write ioports 0xB0 0x06 ;# コア 1 のレジスタ 2 (コントロール)
	debug write ioports 0xB1 0x01 ;# カウント許可
	after time 0.0001 phase2
	check "B3h selects core 0 after reset"           [debug read ioports 0xB3] 0x00
}

proc phase2 {} {
	global log fails
	check "register 3 of core 0 reads 00h"           [treg 0 3] 0x00
	check "register 3 of core 2 reads 00h"           [treg 2 3] 0x00

	debug write ioports 0xB3 0x01
	set c1 [debug read ioports 0xB3]
	if {$c1 == 0x00 || $c1 == 0xFF} {
		incr fails
		puts $log [format "FAIL  %-48s got 0x%02X" "core 1 counter has moved" $c1]
	} else {
		puts $log [format "PASS  %-48s 0x%02X" "core 1 counter has moved" $c1]
	}
	debug write ioports 0xB3 0x04
	check "B3h reads FFh after selecting 04h"        [debug read ioports 0xB3] 0xFF
	debug write ioports 0xB3 0x81
	check "B3h reads FFh after selecting 81h"        [debug read ioports 0xB3] 0xFF
	debug write ioports 0xB3 0x00
	check "B3h reads core 0 again after selecting 0" [debug read ioports 0xB3] 0x00

	if {$fails > 0} {
		puts $log "RESULT: FAILED $fails"
	} else {
		puts $log "RESULT: ALL PASS"
	}
	close $log
	exit
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
