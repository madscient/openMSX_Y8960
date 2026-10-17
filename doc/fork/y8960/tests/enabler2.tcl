# I/O Enabler2 (7FFFh) の b7 (MSX-TIMER) と、メモリマップド I/O の
# トンネルの回帰テスト。
# enabler の b0 (OPL2) と b1 (SSGS) は別のテストで見ている。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script enabler2.tcl
#
# 結果は環境変数 Y8960_TEST_OUT のファイルに書く。
#
# 判別力があるのは「閉じている間は変わらないこと」を見る側である。
# ゲートを入れる前は MSX-TIMER が常時開いていたので、手順 1 の
# タイマーは 0xFF ではなく 0x00 を返し、手順 2 の読み出しは 0x05 になった。
# トンネルは存在しなかったので、手順 3 と 4 では値が変わらなかった。

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

proc run_test {} {
	global OUT

	puts $OUT [format "1. reset            : B0h=0x%02X (expect 0xFF)" \
		[debug read ioports 0xB0]]
	debug write ioports 0xB0 0x05
	puts $OUT [format "1. enabler=00, wrote 05: B0h=0x%02X (expect 0xFF)" \
		[debug read ioports 0xB0]]

	mem_write 0x7FFF 0x80
	puts $OUT [format "2. 7FFF=80          : B0h=0x%02X (expect 0x00)" \
		[debug read ioports 0xB0]]
	debug write ioports 0xB0 0x06
	puts $OUT [format "2. 7FFF=80, wrote 06: B0h=0x%02X (expect 0x06)" \
		[debug read ioports 0xB0]]

	mem_write 0x7FFF 0x00
	mem_write 0x7FF0 0x00
	mem_write 0x7FF1 0x5A
	puts $OUT [format "3. tunnel 7FF0h/7FF1h: SSGS.reg0=0x%02X (expect 0x5A)" \
		[debug read "Y8960 SSGS regs" 0]]

	# 08h は OPL2 のモードレジスタで、リセット直後は 0
	mem_write 0x7FF2 0x08
	mem_write 0x7FF3 0x42
	puts $OUT [format "4. tunnel 7FF2h/7FF3h: OPL2.reg08=0x%02X (expect 0x42)" \
		[debug read "Y8960 OPL2 regs" 0x08]]

	close $OUT
	exit
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
