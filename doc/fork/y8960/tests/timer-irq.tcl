# MSX-TIMER が実際に CPU へ割り込みを上げることの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script timer-irq.tcl
#
# 結果は環境変数 Y8960_TEST_OUT のファイルに書く。
#
# 見ているのは 2 本のプローブ。`y8960-timer.IRQ` はタイマーが上げた線、
# `z80.pendingIRQ` は CPU が受け取っている線である。**フラグ (B2h) だけでは
# 足りない**。フラグが立っていても線が上がっていない場合を捕まえられない。
#
# **最初に VDP の割り込みを止めている**（R#1 の b5）。止めないと
# `z80.pendingIRQ` が VDP の垂直帰線でも上がり、どちらが上げた線か分からない。
#
# 判別力があるのは手順 2・4・5。
#  - 手順 2: intr_enable を落としたままではカウンタが終端に達しても線は上がらない
#  - 手順 4: フラグを落とせば線も下がる。上がりっぱなしならここで落ちる
#  - 手順 5: 繰り返しモードなら、フラグを落とした後にまた上がる
#
# レジスタ: B0h にレジスタ番号を書く。b3:b2 がタイマー番号 0-3、b1:b0 が
# そのタイマーの中のレジスタ番号。B1h がその読み書き。
#   reg0: b0=繰り返し, b6:b4=分解能, b7=割り込み許可
#   reg1: 終端値
#   reg2: b0=カウント許可, b1=カウンタをクリア

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUTPATH [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT)
                                                       : "y8960-timer-irq.txt"}]
set OUT [open $OUTPATH w]

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

proc treg {ch rg val} {
	debug write ioports 0xB0 [expr {($ch << 2) | $rg}]
	debug write ioports 0xB1 $val
}

proc report {label} {
	global OUT
	puts $OUT [format "%-48s timer.IRQ=%s z80.pendingIRQ=%s B2h=0x%02X" $label \
		[debug probe read y8960-timer.IRQ] \
		[debug probe read z80.pendingIRQ] \
		[debug read ioports 0xB2]]
}

proc run_test {} {
	# VDP の割り込みを止める。残しておくと z80.pendingIRQ がどちらの線か
	# 区別できない
	debug write "VDP regs" 1 [expr {[debug read "VDP regs" 1] & ~0x20}]
	# I/O Enabler2 の b7 でタイマーのポートを開ける
	mem_write 0x7FFF 0x80
	after time 0.05 step1
}

proc step1 {} {
	report "1. idle (expect 0 0 00)"

	# 分解能 0、終端値 1、割り込みは許可せずに走らせる
	treg 0 0 0x00
	treg 0 1 0x01
	treg 0 2 0x03
	after time 0.05 step2
}

proc step2 {} {
	report "2. ran without intr_enable (expect 0 0 01)"

	# 割り込みを許可して、カウンタをクリアして走らせ直す
	debug write ioports 0xB2 0x0F
	treg 0 0 0x80
	treg 0 2 0x03
	after time 0.05 step3
}

proc step3 {} {
	report "3. ran with intr_enable (expect 1 1 01)"

	debug write ioports 0xB2 0x01
	report "4. after clearing the flag (expect 0 0 00)"

	# 繰り返しモードで、落とした後にまた上がること
	treg 0 0 0x81
	treg 0 2 0x03
	after time 0.05 step5
}

proc step5 {} {
	report "5. repeat mode, one period later (expect 1 1 01)"
	close $::OUT
	exit
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
