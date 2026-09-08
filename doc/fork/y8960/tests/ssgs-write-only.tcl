# カートリッジ版 SSGS がリードに反応しないこと、および I/O Enabler2 (7FFFh)
# の b4 が効くことの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script ssgs-write-only.tcl
#
# 結果は環境変数 Y8960_TEST_OUT のファイルに書く。
#
# SSGS は A0h-A2h で本体 PSG と重なっている。ここでリードに応じると
# MSXMultiIODevice が両者の AND を取ってしまい、本体 PSG の読み出しが壊れる。
# だからカートリッジ版はライトオンリーである。
#
# 判別力があるのは 2 点。
#  - A2h から書いた値がそのまま読み戻せること。SSGS がリードに応じていれば
#    0xA5 のようにビットが落ちる値で崩れる
#  - enabler を開ける前は SSGS に書き込みが届かないこと

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUTPATH [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT)
                                                       : "y8960-ssgs-write-only.txt"}]
set OUT [open $OUTPATH w]

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

proc psg_write {reg val} {
	debug write ioports 0xA0 $reg
	debug write ioports 0xA1 $val
}

proc run_test {} {
	global OUT
	puts $OUT [iomap]

	# enabler を開ける前: SSGS には届かない
	psg_write 0x00 0x5A
	puts $OUT [format "1. enabler closed : SSG.reg0=0x%02X (expect 0x00)" \
		[debug read "Y8960 SSG regs" 0]]

	# 本体 PSG の読み出しが汚れていないこと
	puts $OUT [format "2. read back A2h  : 0x%02X (expect 0x5A)" \
		[debug read ioports 0xA2]]
	psg_write 0x00 0xA5
	puts $OUT [format "3. read back A2h  : 0x%02X (expect 0xA5)" \
		[debug read ioports 0xA2]]

	# enabler を開けると SSGS にも重ねて届く
	mem_write 0x7FFF 0x10
	psg_write 0x00 0x5A
	puts $OUT [format "4. enabler open   : SSG.reg0=0x%02X PSG.reg0=0x%02X (expect 0x5A both)" \
		[debug read "Y8960 SSG regs" 0] [debug read "PSG regs" 0]]

	close $OUT
	exit
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
