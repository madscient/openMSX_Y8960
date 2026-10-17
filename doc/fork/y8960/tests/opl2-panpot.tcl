# Y8960 の OPL2 のチャンネルごとの定位 (F6h-FEh)、ADPCM の定位 (FFh) と
# ADPCM の音量 (7FFAh) の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script opl2-panpot.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# fm_center / fm_left / fm_right / ch7_left / bd_left / adpcm_center /
# adpcm_left / adpcm_half の 8 本の WAV を書き出す。判定は check-opl2-panpot.py が行う。
#
# 判別力があるのは fm_left / fm_right / bd_left / adpcm_left / adpcm_half で、
# 定位が効いていなければ L=R になり、ADPCM の音量が効いていなければ
# adpcm_half が adpcm_center と同じ大きさになる。bd_left は ch7 を左端、
# ch8 を右端にして BD を鳴らし、BD が ch7 の定位に従うことを見る。
# ch7_left は同じスロットの設定で ch7 をメロディとして鳴らしたもので、
# BD と同じ大きさになる（リズム音はメロディと 1 : 1）。2 倍なら BD が倍になる。
#
# デバイスごとの録音 (`_ch<n>_record`) は音源の出力をそのまま録る。
# ch1-9 が FM、ch10-14 がリズム音 (BD / SD / CYM / HH / TOM)、ch15 が ADPCM。
# ADPCM の音量は OPL2 の中で掛かるので、この録音に見える。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]

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

# ch1 で持続音を鳴らす
proc fm_note {} {
	r 0x20 0x21 ; r 0x23 0x21    ;# MULTI=1
	r 0x40 0x2A ; r 0x43 0x08    ;# TL。carrier を 6dB 下げ、左右端でも 16bit に収める
	r 0x60 0xF0 ; r 0x63 0xF0    ;# AR/DR
	r 0x80 0x00 ; r 0x83 0x00    ;# SL/RR
	r 0xA0 0x98                  ;# F-Number
	r 0xB0 0x31                  ;# キーオン、ブロック 4
}

proc fm {name pan} {
	r 0xF6 $pan                  ;# ch1 の定位
	fm_note
	after time 0.3 [list rec $name 1 [list fm_off]]
}
proc fm_off {} { r 0xB0 0x11 }

# ch7 のスロット。BD もこれを使う。ch8 の定位は逆側にしておく
proc ch7_slots {} {
	r 0xF6 128
	r 0xFC 1                     ;# ch7 を左端
	r 0xFD 255                   ;# ch8 を右端
	r 0x30 0x01 ; r 0x33 0x01
	r 0x50 0x00 ; r 0x53 0x08
	r 0x70 0xF0 ; r 0x73 0xF0
	r 0x90 0x00 ; r 0x93 0x00
	r 0xC6 0x00                  ;# FM。BD は常に FM で鳴る
	r 0xA6 0x98
}

proc ch7 {name} {
	ch7_slots
	r 0xB6 0x29                  ;# キーオン
	after time 0.05 [list rec $name 7 [list ch7_off]]
}
proc ch7_off {} { r 0xB6 0x09 }

proc bd {name} {
	ch7_slots
	r 0xB6 0x09
	r 0xBD 0x20                  ;# リズムモード
	r 0xBD 0x30                  ;# BD キーオン
	after time 0.05 [list rec $name 10 [list bd_off]]
}
proc bd_off {} { r 0xBD 0x00 }

proc adpcm_start {} {
	r 0x08 0x00                  ;# RAM、18bit アドレス
	r 0x09 0x00 ; r 0x0A 0x00    ;# 開始 = ニブル 0
	r 0x0C 0x01 ; r 0x0B 0x00    ;# 終了 = ニブル 2048 = 1024 バイト
	r 0x07 0x60                  ;# REC | MEMORY DATA: メモリ書き込みモード
	debug write ioports 0xC0 0x0F
	for {set i 0} {$i < 1024} {incr i} {
		debug write ioports 0xC1 [expr {($i & 16) ? 0xFF : 0x77}]
	}
	r 0x07 0x00
	r 0x09 0x00 ; r 0x0A 0x00
	r 0x0C 0x01 ; r 0x0B 0x00
	r 0x10 0x00 ; r 0x11 0x80    ;# DELTA-N = 8000h
	r 0x12 0xFF                  ;# 音量最大
	r 0x07 0xB0                  ;# START | MEMORY DATA | REPEAT
}

proc adpcm {name pan volume} {
	r 0xFF $pan
	mem_write 0x7FFA $volume
	after time 0.3 [list rec $name 15 {}]
}

proc rec {name chan after_script} {
	set "::Y8960 OPL2_ch${chan}_record" "$::OUT/$name.wav"
	after time 0.3 [list stop $chan $after_script]
}

proc stop {chan after_script} {
	set "::Y8960 OPL2_ch${chan}_record" ""
	eval $after_script
	after time 0.2 next_step
}

# 手順 0 の 7FFFh は I/O Enabler2 の b0 で、C0h-C1h を開く
set step 0
proc next_step {} {
	global step
	set s $step
	incr step
	switch $s {
		0 { mem_write 0x7FFF 0x01 ; fm fm_center 128 }
		1 { fm fm_left  1 }
		2 { fm fm_right 255 }
		3 { ch7 ch7_left }
		4 { bd bd_left }
		5 { adpcm_start ; adpcm adpcm_center 128 128 }
		6 { adpcm adpcm_left 1 128 }
		7 { adpcm adpcm_half 128 64 }
		default { exit }
	}
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 next_step
