# Y8960 の ADPCM の 08h の b0（ROM ビット）が SRAM を外すことの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script adpcm-rommode.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# adpcm-rommode.txt を書き出す。**判定は最終行の RESULT を見る。**
# openmsx は Tcl の `exit` に渡した値をプロセスの終了コードにしない。
#
# Y8960 の ADPCM の後ろにはサンプル ROM が無いが、ROM ビットを立てると、
# 何もつながっていない ROM を選んだのと同じになる。書き込みは SRAM に届かず、
# メモリ読み出しは 0 になる（カートリッジの v0.9.5 以降の RTL とマニュアル 6.5）。
#
# 読み出しはデバッガ (peekIO) では空読みの数え方が進まないので、CPU に
# IN A,(C1h) を実行させる。空読み 2 回の後の 3 回目がデータ。
#
# **判別力**: ROM ビットを無視する実装では、ROM ビットを立てた書き込みが
# SRAM に届き、読み出しも SRAM の値になる。同じ手順を ROM ビット無しでも
# 行って、書き込みと読み出しの経路そのものは働いていることを見ている。

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
		puts $log [format "PASS  %-48s 0x%02X" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-48s got 0x%02X want 0x%02X" $name $got $want]
	}
}

# 開始・終了アドレスは 4 バイト単位
proc set_range {start_byte stop_byte} {
	set s [expr {$start_byte / 4}]
	set e [expr {$stop_byte / 4}]
	r 0x09 [expr {$s & 0xFF}]
	r 0x0A [expr {($s >> 8) & 0xFF}]
	r 0x0B [expr {$e & 0xFF}]
	r 0x0C [expr {($e >> 8) & 0xFF}]
}

# メモリ書き込みモードで 1 バイト書く
proc adpcm_write {rom val} {
	r 0x08 $rom
	r 0x07 0x60                  ;# REC | MEMORY DATA
	r 0x0F $val
	r 0x07 0x00
	r 0x08 0x00
}

# F3        DI
# 3E 0F     LD A,0Fh
# D3 C0     OUT (C0h),A
# DB C1     IN A,(C1h)     空読み
# DB C1     IN A,(C1h)     空読み
# DB C1     IN A,(C1h)
# 32 80 C0  LD (C080h),A   ROM ビットを立てたままの読み
# 3E 08     LD A,08h
# D3 C0     OUT (C0h),A
# AF        XOR A
# D3 C1     OUT (C1h),A    ROM ビットを下ろす
# 3E 07     LD A,07h
# D3 C0     OUT (C0h),A
# 3E 20     LD A,20h
# D3 C1     OUT (C1h),A    メモリ読み出しをやり直す
# 3E 0F     LD A,0Fh
# D3 C0     OUT (C0h),A
# DB C1     IN A,(C1h)     空読み
# DB C1     IN A,(C1h)     空読み
# DB C1     IN A,(C1h)
# 32 81 C0  LD (C081h),A   ROM ビット無しの読み
# 18 FE     JR $
set stub {0xF3 0x3E 0x0F 0xD3 0xC0 0xDB 0xC1 0xDB 0xC1 0xDB 0xC1 0x32 0x80 0xC0
          0x3E 0x08 0xD3 0xC0 0xAF 0xD3 0xC1
          0x3E 0x07 0xD3 0xC0 0x3E 0x20 0xD3 0xC1
          0x3E 0x0F 0xD3 0xC0 0xDB 0xC1 0xDB 0xC1 0xDB 0xC1 0x32 0x81 0xC0
          0x18 0xFE}

proc run_test {} {
	global stub
	mem_write 0x7FFF 0x01        ;# I/O Enabler2 b0: OPL2 を開く
	set_range 0x30000 0x30003

	check "byte 0x30000 starts out erased"           [ram 0x30000] 0xFF
	adpcm_write 0x01 0x5A
	check "a write with the ROM bit leaves SRAM"     [ram 0x30000] 0xFF
	adpcm_write 0x00 0x3C
	check "a write without the ROM bit reaches SRAM" [ram 0x30000] 0x3C

	# CPU に読ませる。メモリ読み出しモードに入った直後の状態から始める
	r 0x08 0x01
	r 0x07 0x20                  ;# MEMORY DATA: メモリ読み出しモード
	set i 0xC000
	foreach b $stub { debug write memory $i $b ; incr i }
	debug write memory 0xC080 0xEE
	debug write memory 0xC081 0xEE
	reg pc 0xC000
	after time 0.05 finish
}

proc finish {} {
	global log fails stub
	# 結果の置き場 (C080h-) はスタブより後ろでなければならない
	check "CPU stopped at the JR \$ of the stub"      [reg pc] [expr {0xC000 + [llength $stub] - 2}]
	check "a read with the ROM bit gives 0"          [debug read memory 0xC080] 0x00
	check "a read without the ROM bit gives SRAM"    [debug read memory 0xC081] 0x3C

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
