# Y8960 の OPL2 波形選択 (E0h-F5h) と I/O Enabler2 (7FFFh) の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script opl2-waveform.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# ws0.wav と ws2.wav を書き出す。同じレジスタ列で波形番号だけを変えたものなので、
# 2 つが異なることと、WS2 に負のサンプルが無いことを確かめれば波形選択が
# 効いていると言える。判定は tools/check-opl2-waveform.py が行う。
#
# あわせて enabler も見る。7FFFh を書かないうちは C0h-C1h への書き込みが
# 落ちるので、最初の capture が 7FFFh を開けている点に意味がある。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUTDIR [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

proc r {reg val} {
	debug write ioports 0xC0 $reg
	debug write ioports 0xC1 $val
}

proc setup_note {} {
	r 0x01 0x20   ;# TEST: waveform select enable
	r 0x20 0x21   ;# modulator: MULTI=1
	r 0x23 0x21   ;# carrier
	r 0x40 0x2A   ;# modulator TL
	r 0x43 0x00   ;# carrier TL = max
	r 0x60 0xF0   ;# AR/DR
	r 0x63 0xF0
	r 0x80 0x00   ;# SL/RR
	r 0x83 0x00
	r 0xA0 0x98   ;# F-number
	r 0xB0 0x31   ;# key on, block
}

proc capture {name ws} {
	global OUTDIR
	mem_write 0x7FFF 0x01          ;# I/O Enabler2 b0: open C0h-C1h
	r 0xB0 0x11                    ;# key off
	setup_note
	r 0xE0 $ws                     ;# modulator waveform
	r 0xE3 $ws                     ;# carrier waveform
	set "::Y8960 OPL2 0_ch1_record" "$OUTDIR/ws$name.wav"
	after time 1 [list stop_capture $name]
}

proc stop_capture {name} {
	set "::Y8960 OPL2 0_ch1_record" ""
	global step
	incr step
	next_step
}

set step 0
proc next_step {} {
	global step
	switch $step {
		0 { capture 0 0 }
		1 { capture 2 2 }
		default { exit }
	}
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 next_step
