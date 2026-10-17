# Y8960 の SSGS のチャンネルごとの定位 (28h-2Eh) と音量 (20h-26h)、
# SSG 2 系統の分離、および I/O Enabler2 (7FFFh) の b1 の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script ssgs-panpot.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# center/left/right/half/unit1 の 5 本の WAV を書き出す。
# 判定は check-ssgs-panpot.py が行う。
#
# 判別力があるのは left / right / half で、定位が効いていなければ left と
# right も center と同じ（L=R）になり、音量が効いていなければ half は
# center と同じ大きさになる。音量は 128 が最大で、64 はその半分。
# 判定器は 3% の幅で見ている。center 以下を 128 で鳴らしているのは、bit7 を
# 最大として扱わないと無音になるのを捕まえるため。unit1 は 10h 起点に書いた音が
# 4 番目のチャンネルから出ることを見ており、SSG 2 系統の分離を確かめている。
# 最初に 7FFFh へ書いているのは、それが無いと SSGS の I/O が閉じたままで
# 何も鳴らないため。
#
# チャンネルの音量は 0Fh ではなく 0Bh にしてある。最大にすると 16bit に
# 収まらずクリップし、half が半分にならない。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]

proc w {reg val} {
	debug write ioports 0xA0 $reg
	debug write ioports 0xA1 $val
}

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

# 系統 unit (0/1) の ch A で一定の音を鳴らす
proc note {unit} {
	set base [expr {$unit * 0x10}]
	w [expr {$base+0x00}] 0x40   ;# ch A 周波数
	w [expr {$base+0x01}] 0x01
	w [expr {$base+0x07}] 0x3E   ;# ch A のトーンだけ有効
	w [expr {$base+0x08}] 0x0B   ;# ch A 音量（クリップしない程度）
}

proc capture {name unit vol pan chan} {
	global OUT
	mem_write 0x7FFF 0x02        ;# I/O Enabler2 b1: SSG を開く
	note $unit
	w [expr {0x20 + $unit*4}] $vol   ;# ch A の音量
	w [expr {0x28 + $unit*4}] $pan   ;# ch A の定位
	set "::Y8960 SSGS_ch${chan}_record" "$OUT/$name.wav"
	after time 1 [list stop $name]
}

proc stop {name} {
	set "::Y8960 SSGS_ch1_record" ""
	set "::Y8960 SSGS_ch4_record" ""
	global step ; incr step ; next
}

set step 0
proc next {} {
	global step
	switch $step {
		0 { capture center 0 128 128 1 }
		1 { capture left   0 128 1   1 }
		2 { capture right  0 128 255 1 }
		3 { capture half   0 64  128 1 }
		4 { capture unit1  1 128 128 4 }
		default { exit }
	}
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 next
