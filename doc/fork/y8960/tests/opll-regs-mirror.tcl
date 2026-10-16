# Y8960 の OPLL のレジスタの写しが、BANK レジスタ (40h-48h) で壊れないことの
# 回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script opll-regs-mirror.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# opll-regs-mirror.txt を書き出す。**判定は最終行の RESULT を見る。**
# openmsx は Tcl の `exit` に渡した値をプロセスの終了コードにしない。
#
# OPLL コアはデバッガとセーブステートのためにレジスタの写しを持つ。写しが
# 00h-3Fh の 64 バイトしか無いと、40h 以降への書き込みは下位 6bit で折り返して
# 00h 以降の写しを上書きする。BANK (40h-48h) を書くと、音色の 00h-08h の表示が
# 変わって見え、セーブステートを読み直すと音色まで変わる。
#
# **判別力**: 写しが 64 バイトのままなら、手順 2 で reg 00h が 0x03 に、
# 手順 3 で reg 08h が 0x02 になる。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/opll-regs-mirror.txt" w]
set fails 0

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

# メモリマップド I/O の窓から書く。I/O Enabler に左右されない
proc opll {reg val} {
	mem_write 0x7FF4 $reg
	mem_write 0x7FF5 $val
}
proc r {reg} { debug read "Y8960 OPLL regs" $reg }

proc check {name got want} {
	global log fails
	if {$got == $want} {
		puts $log [format "PASS  %-44s %s" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-44s got %s want %s" $name $got $want]
	}
}

proc run_test {} {
	global log fails

	opll 0x00 0x21
	opll 0x08 0x00
	check "1. reg 00h written"              [r 0x00] 0x21

	opll 0x40 0x03               ;# ch0 の BANK = 3
	check "2. reg 00h untouched by 40h"     [r 0x00] 0x21

	opll 0x48 0x02               ;# ch8 の BANK = 2
	check "3. reg 08h untouched by 48h"     [r 0x08] 0x00

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
