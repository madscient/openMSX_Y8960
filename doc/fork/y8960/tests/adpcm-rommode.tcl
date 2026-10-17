# Y8960 の ADPCM に rommode が無いことの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script adpcm-rommode.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# adpcm-rommode.txt を書き出す。**判定は最終行の RESULT を見る。**
# openmsx は Tcl の `exit` に渡した値をプロセスの終了コードにしない。
#
# Y8950 では 08h の b0 が ADPCM を ROM 側に切り替え、RAM への書き込みが
# 捨てられて読みは 0 になる。Y8960 には ADPCM の ROM が無いので、このビットを
# 立てても RAM のままでなければならない。ビットを立てたまま書いて、デバッガブル
# "Y8960 ADPCM RAM" で読み返せるかどうかで、無視されていることが分かる。
#
# **判別力**: Y8950 の rommode をそのまま残した実装では、書き込みが捨てられて
# 番地は初期値 FFh のままになる。書く前に FFh であることも見ているので、
# たまたま一致したのではない。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/adpcm-rommode.txt" w]
set fails 0

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

# C0h がレジスタ番号、C1h がその値
proc r {reg val} {
	debug write ioports 0xC0 $reg
	debug write ioports 0xC1 $val
}
proc ram {addr} { debug read "Y8960 ADPCM RAM" $addr }

proc check {name got want} {
	global log fails
	if {$got == $want} {
		puts $log [format "PASS  %-44s %s" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-44s got %s want %s" $name $got $want]
	}
}

# ニブル単位の開始・終了アドレス。09h/0Ah は値を 3bit 左シフトした位置に入る
proc set_range {start_byte stop_byte} {
	set s [expr {$start_byte / 4}]
	set e [expr {$stop_byte / 4}]
	r 0x09 [expr {$s & 0xFF}]
	r 0x0A [expr {($s >> 8) & 0xFF}]
	r 0x0B [expr {$e & 0xFF}]
	r 0x0C [expr {($e >> 8) & 0xFF}]
}

proc run_test {} {
	global log fails
	mem_write 0x7FF7 0x01        ;# I/O Enabler2 b0: OPL2 を開く

	check "byte 0x30000 starts out erased" [ram 0x30000] 0xFF

	r 0x08 0x01                  ;# ROM ビット（実機には無い）
	set_range 0x30000 0x30010
	r 0x07 0x60                  ;# REC | MEMORY DATA: メモリ書き込みモード
	debug write ioports 0xC0 0x0F
	debug write ioports 0xC1 0x3C
	r 0x07 0x00
	r 0x08 0x00

	check "the ROM bit does not take the RAM away" [ram 0x30000] 0x3C

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
