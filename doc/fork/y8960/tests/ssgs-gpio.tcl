# SSGS の GPIO のレジスタ (0Eh/0Fh, 1Eh/1Fh) の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script ssgs-gpio.tcl
#
# 結果は環境変数 Y8960_TEST_OUT のファイルに書く。
#
# GPIO のレジスタは両系統にあり、どちらも何も繋がっていないので、書いた値が
# そのまま読み戻せる。読み戻しにはデバッガブルを使う（カートリッジはリードに
# 反応しない）。判別力: GPIO の書き込みを捨てる実装では 0xFF が返る。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUTPATH [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT)
                                                       : "y8960-ssgs-gpio.txt"}]
set OUT [open $OUTPATH w]

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

proc w {reg val} {
	debug write ioports 0xA0 $reg
	debug write ioports 0xA1 $val
}

proc run_test {} {
	global OUT

	mem_write 0x7FFF 0x02        ;# I/O Enabler2 b1: SSGS を開く
	# $07 の b6=1 / b7=1 で両ポートを出力にする
	w 0x07 0xC0
	w 0x17 0xC0

	w 0x0E 0x33
	w 0x0F 0x5A
	puts $OUT [format "1. unit0 \$0E=0x%02X \$0F=0x%02X (expect 33 5A)" \
		[debug read "Y8960 SSGS regs" 0x0E] [debug read "Y8960 SSGS regs" 0x0F]]

	w 0x1E 0x11
	w 0x1F 0x22
	puts $OUT [format "2. unit1 \$1E=0x%02X \$1F=0x%02X (expect 11 22)" \
		[debug read "Y8960 SSGS regs" 0x1E] [debug read "Y8960 SSGS regs" 0x1F]]

	close $OUT
	exit
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
