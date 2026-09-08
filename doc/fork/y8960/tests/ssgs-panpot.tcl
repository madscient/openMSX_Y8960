# Y8960 の SSGS のパンポット ($10-$12) と 2 系統の分離、
# および I/O Enabler2 (7FFFh) の b4 の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script ssgs-panpot.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# center/left/right/unit1 の 4 本の WAV を書き出す。
# 判定は check-ssgs-panpot.py が行う。
#
# 判別力があるのは left と right で、パンポットが効いていなければ
# 3 本とも center と同じ（L=R）になる。unit1 は $20 起点に書いた音が
# 4 番目のチャンネルから出ることを見ており、2 系統の分離を確かめている。
# 最初に 7FFFh へ書いているのは、それが無いと SSG の I/O が閉じたままで
# 何も鳴らないため。

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

# 系統 base の ch A で一定の音を鳴らす
proc note {base} {
	w [expr {$base+0x00}] 0x40   ;# ch A 周波数
	w [expr {$base+0x01}] 0x01
	w [expr {$base+0x07}] 0x3E   ;# ch A のトーンだけ有効
	w [expr {$base+0x08}] 0x0F   ;# ch A 音量最大
}

proc capture {name base pan chan} {
	global OUT
	mem_write 0x7FFF 0x10        ;# I/O Enabler2 b4: SSG を開く
	note $base
	w [expr {$base+0x10}] $pan   ;# ch A のパンポット
	set "::Y8960 SSG_ch${chan}_record" "$OUT/$name.wav"
	after time 1 [list stop $name]
}

proc stop {name} {
	set "::Y8960 SSG_ch1_record" ""
	set "::Y8960 SSG_ch4_record" ""
	global step ; incr step ; next
}

set step 0
proc next {} {
	global step
	switch $step {
		0 { capture center 0x00 8  1 }
		1 { capture left   0x00 0  1 }
		2 { capture right  0x00 15 1 }
		3 { capture unit1  0x20 8  4 }
		default { exit }
	}
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 next
