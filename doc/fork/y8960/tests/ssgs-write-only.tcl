# SSGS がリードに反応しないこと、A0h と A1h にしか書き込めないこと、
# および I/O Enabler2 (7FFFh) の b1 が効くことの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script ssgs-write-only.tcl
#
# 結果は環境変数 Y8960_TEST_OUT のファイルに書く。
#
# SSGS は A0h-A2h で本体 PSG と重なっている。ここでリードに応じると
# MSXMultiIODevice が両者の AND を取り、本体 PSG の読み出しが壊れる。
# 実機は SSG2 のレジスタを指しているときだけ A2h の読みに応じるが、
# エミュレーションは読みに一切応じない。A2h を入力に登録すると、openMSX が
# 拡張を挿すたびに入力ポートの重なりを警告するため（implementation-plan.md §3.6）。
#
# 判別力があるのは 3 点。
#  - A2h から書いた値がそのまま読み戻せること。SSGS がリードに応じていれば
#    0xA5 のようにビットが落ちる値で崩れる
#  - enabler を開ける前は SSGS に書き込みが届かないこと
#  - A2h と A3h への書き込みでレジスタ番号が変わらないこと。変わる実装では
#    A1h の値が reg10 に入る

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
		[debug read "Y8960 SSGS regs" 0]]

	# 本体 PSG の読み出しが汚れていないこと
	puts $OUT [format "2. read back A2h  : 0x%02X (expect 0x5A)" \
		[debug read ioports 0xA2]]
	psg_write 0x00 0xA5
	puts $OUT [format "3. read back A2h  : 0x%02X (expect 0xA5)" \
		[debug read ioports 0xA2]]

	# enabler を開けると SSGS にも重ねて届く
	mem_write 0x7FFF 0x02
	psg_write 0x00 0x5A
	puts $OUT [format "4. enabler open   : SSG.reg0=0x%02X PSG.reg0=0x%02X (expect 0x5A both)" \
		[debug read "Y8960 SSGS regs" 0] [debug read "PSG regs" 0]]

	# A2h と A3h への書き込みはレジスタ番号を変えない
	debug write ioports 0xA0 0x08
	debug write ioports 0xA2 0x09
	debug write ioports 0xA3 0x0A
	debug write ioports 0xA1 0x0F
	puts $OUT [format "5. A2h/A3h writes : SSG.reg8=0x%02X reg9=0x%02X reg10=0x%02X (expect 0x0F 0x00 0x00)" \
		[debug read "Y8960 SSGS regs" 8] [debug read "Y8960 SSGS regs" 9] \
		[debug read "Y8960 SSGS regs" 10]]

	close $OUT
	exit
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
