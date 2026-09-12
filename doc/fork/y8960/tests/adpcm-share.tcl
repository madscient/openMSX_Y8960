# 2 個の OPL2EX が 1 個の ADPCM サンプルメモリを共有していることの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script adpcm-share.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# adpcm-share.txt と playing.wav / stopped.wav を書き出す。
# **レジスタ側の判定は adpcm-share.txt の最終行 RESULT を見る。**
# openmsx は Tcl の `exit` に渡した値をプロセスの終了コードにしない。
# WAV の判定は check-adpcm-play.py が行う（波形も判定条件も adpcm-play.tcl と
# 同じなので、判定器を分けていない）。
#
# **判別力の根拠**は 3 つに分かれる。
#
# - **書き込みの相乗り**。OPL2-1 がバイト 20000h に書いた値が、デバッガブル
#   "Y8960 ADPCM RAM" の同じ番地に現れる。回路ごとに別のメモリを持っていれば
#   ここは初期値 FFh のままなので、書いた値が見えること自体が共有の証拠になる。
#   書く前に FFh であることも見ているので、たまたま一致したのではない
# - **読み出しの相乗り**。OPL2-0 が書いた三角波を OPL2-1 が再生して音になる。
#   別メモリなら OPL2-1 が読むのは FFh の並び（最大の負の差分の繰り返し）で、
#   388Hz の三角波にはならない
# - **鳴っていることと止まっていることの対比**。playing が鳴っていて stopped が
#   無音なら、その音が ADPCM から出たものだと言える
#
# ついでに **rommode が無いこと**も見ている。Y8950 では 08h の b0 が ADPCM を
# ROM 側に切り替えるが、Y8960 には ADPCM の ROM が無い。ビットを立てたまま
# 書いて読み返せるかどうかで、無視されていることが分かる。
#
# 三角波の作り方と周波数の根拠は adpcm-play.tcl を見ること。
#
# **この試験が共有していないときに落ちること**は、2 個の OPL2 を別々の
# Y8960-ADPCM-RAM に繋いだ拡張定義を作って確かめられる。`<adpcm_memory>` の
# 片方だけを別の id に向ければよい。そのときレジスタ側は 2 件 FAIL し、
# 再生される音も 388Hz にならない。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/adpcm-share.txt" w]
set fails 0

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

# OPL2-0 は C0h/C1h、OPL2-1 は C2h/C3h がレジスタ番号とその値
proc r0 {reg val} {
	debug write ioports 0xC0 $reg
	debug write ioports 0xC1 $val
}
proc r1 {reg val} {
	debug write ioports 0xC2 $reg
	debug write ioports 0xC3 $val
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
proc set_range {port_proc start_byte stop_byte} {
	set s [expr {$start_byte / 4}]
	set e [expr {$stop_byte / 4}]
	$port_proc 0x09 [expr {$s & 0xFF}]
	$port_proc 0x0A [expr {($s >> 8) & 0xFF}]
	$port_proc 0x0B [expr {$e & 0xFF}]
	$port_proc 0x0C [expr {($e >> 8) & 0xFF}]
}

proc run_test {} {
	global log fails
	mem_write 0x7FFF 0x03        ;# I/O Enabler2 b0/b1: OPL2 を両方開く

	# --- OPL2-0 が三角波を 0 番地から 1024 バイト書く ---
	r0 0x08 0x00                 ;# RAM、18bit アドレス
	set_range r0 0 1024
	r0 0x07 0x60                 ;# REC | MEMORY DATA: メモリ書き込みモード
	debug write ioports 0xC0 0x0F
	for {set i 0} {$i < 1024} {incr i} {
		debug write ioports 0xC1 [expr {($i & 16) ? 0xFF : 0x77}]
	}
	r0 0x07 0x00

	check "OPL2-0 wrote byte 0"    [ram 0]    0x77
	check "OPL2-0 wrote byte 16"   [ram 16]   0xFF
	check "OPL2-0 wrote byte 1000" [ram 1000] 0x77

	# --- OPL2-1 が 20000h に書いた値が同じメモリに現れる ---
	check "byte 0x20000 starts out erased" [ram 0x20000] 0xFF
	r1 0x08 0x00
	set_range r1 0x20000 0x20010
	r1 0x07 0x60
	debug write ioports 0xC2 0x0F
	debug write ioports 0xC3 0x5A
	debug write ioports 0xC3 0xA5
	r1 0x07 0x00

	check "OPL2-1 wrote byte 0x20000" [ram 0x20000] 0x5A
	check "OPL2-1 wrote byte 0x20001" [ram 0x20001] 0xA5
	check "OPL2-0's data is still there" [ram 0] 0x77

	# --- rommode は Y8960 に無い ---
	#
	# Y8950 では 08h の b0 が ADPCM を ROM 側に切り替え、RAM への書き込みが
	# 捨てられて読みは 0 になる。Y8960 には ADPCM の ROM が無いので、
	# このビットを立てても RAM のままでなければならない。
	r0 0x08 0x01                 ;# ROM ビット（実機には無い）
	set_range r0 0x30000 0x30010
	r0 0x07 0x60
	debug write ioports 0xC0 0x0F
	debug write ioports 0xC1 0x3C
	r0 0x07 0x00
	r0 0x08 0x00

	check "the ROM bit does not take the RAM away" [ram 0x30000] 0x3C

	if {$fails > 0} {
		puts $log "RESULT: FAILED $fails"
	} else {
		puts $log "RESULT: ALL PASS"
	}
	close $log
	set f [open "$::OUT/adpcm-share.txt" r]
	puts [read $f]
	close $f

	# --- OPL2-1 が OPL2-0 の書いた三角波を再生する ---
	set_range r1 0 1024
	r1 0x10 0x00 ; r1 0x11 0x80  ;# DELTA-N = 8000h
	r1 0x12 0xFF                 ;# 音量最大
	r1 0x07 0xB0                 ;# START | MEMORY DATA | REPEAT

	# 直流分が落ち着いてから測る
	after time 1 capture_playing
}

proc capture_playing {} {
	record start -audioonly $::OUT/playing.wav
	after time 0.3 stop_playing
}
proc stop_playing {} {
	record stop
	r1 0x07 0x00                 ;# 止める
	after time 0.5 capture_stopped
}
proc capture_stopped {} {
	record start -audioonly $::OUT/stopped.wav
	after time 0.3 stop_stopped
}
proc stop_stopped {} {
	record stop
	after time 0.1 done
}
proc done {} { exit }

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
