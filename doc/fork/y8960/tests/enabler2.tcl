# I/O Enabler2 (7FFFh) の b2/b3 (DCSG) と b7 (MSX-TIMER)、および
# メモリマップド I/O のトンネルの回帰テスト。
# enabler の b0/b1 (OPL2) と b4 (SSGS) は別のテストで見ている。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script enabler2.tcl
#
# 結果は環境変数 Y8960_TEST_OUT のファイルに書く。
#
# **トンネルでは 2 回路のうち 1 番目が高位側のアドレスに座る。** 直接 I/O は
# OPL2 と DCSG では低位側が 1 番目なので、並びが逆になる。どちらも過去の実装
# との互換のためで、一方から他方は導けない（hra1129 さん、2026-09-09）。
# 手順 6 と 8 がここを見ている。逆に繋ぐと 2 つの値が入れ替わって出る。
#
# 判別力があるのは「閉じている間は変わらないこと」を見る側である。
# ゲートを入れる前は DCSG も MSX-TIMER も常時開いていたので、手順 1 の
# タイマーは 0xFF ではなく 0x00 を返し、手順 2 では DCSG に値が入り、
# 手順 5 の読み出しは 0x05 になった。トンネルは存在しなかったので、
# 手順 6 と 8 では値が変わらなかった。
#
# DCSG は 1 バイト書き込みのレジスタラッチ方式で、b7 が立った 1rrrdddd が
# レジスタ rrr の下位 4bit を書く。ここで見ているのは reg1 = ch0 の減衰量で、
# リセット直後は 0xF (無音)。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUTPATH [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT)
                                                       : "y8960-enabler2.txt"}]
set OUT [open $OUTPATH w]

# カートリッジがどのスロットに入っても当たるよう全 ps/ss に書く。
# 他スロットの同アドレスは RAM なので、書いても害はない。
proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

# SN76489 のデバッガブルの index 2 が reg1 の下位 4bit
proc dcsg_att {n} { debug read "Y8960 DCSG $n regs" 2 }

proc report {label} {
	global OUT
	puts $OUT [format "%-52s DCSG0=0x%X DCSG1=0x%X" $label [dcsg_att 0] [dcsg_att 1]]
}

proc run_test {} {
	global OUT

	report "1. reset (expect F F)"
	puts $OUT [format "1. reset            : B0h=0x%02X (expect 0xFF)" \
		[debug read ioports 0xB0]]

	debug write ioports 0x3E 0x91
	debug write ioports 0x3F 0x92
	debug write ioports 0xB0 0x05
	report "2. enabler=00, direct I/O (expect F F)"

	mem_write 0x7FFF 0x04
	debug write ioports 0x3E 0x93
	debug write ioports 0x3F 0x94
	report "3. 7FFF=04 (expect 3 F)"

	mem_write 0x7FFF 0x08
	debug write ioports 0x3E 0x95
	debug write ioports 0x3F 0x96
	report "4. 7FFF=08 (expect 3 6)"

	mem_write 0x7FFF 0x80
	puts $OUT [format "5. 7FFF=80          : B0h=0x%02X (expect 0x00)" \
		[debug read ioports 0xB0]]
	debug write ioports 0xB0 0x06
	puts $OUT [format "5. 7FFF=80, wrote 06: B0h=0x%02X (expect 0x06)" \
		[debug read ioports 0xB0]]

	# 7FF1h が 1 番目、7FF0h が 2 番目
	mem_write 0x7FFF 0x00
	mem_write 0x7FF0 0x97
	mem_write 0x7FF1 0x98
	report "6. 7FFF=00, tunnel 7FF0h=97 7FF1h=98 (expect 8 7)"

	mem_write 0x7FEA 0x00
	mem_write 0x7FEB 0x5A
	puts $OUT [format "7. tunnel 7FEAh/7FEBh: SSGS.reg0=0x%02X (expect 0x5A)" \
		[debug read "Y8960 SSGS regs" 0]]

	# 7FEEh が 1 番目、7FECh が 2 番目。08h は OPL2 のモードレジスタで、
	# リセット直後は 0
	mem_write 0x7FEC 0x08
	mem_write 0x7FED 0x21
	mem_write 0x7FEE 0x08
	mem_write 0x7FEF 0x42
	puts $OUT [format "8. tunnel 7FECh=21 7FEEh=42: OPL2_0.reg08=0x%02X OPL2_1.reg08=0x%02X (expect 0x42 0x21)" \
		[debug read "Y8960 OPL2 0 regs" 0x08] [debug read "Y8960 OPL2 1 regs" 0x08]]

	close $OUT
	exit
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
