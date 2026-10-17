# デジタルミキサーの音量レジスタ (7FF7h-7FFBh) の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script mixer-volume.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# vol_reset / vol_half / vol_mute / vol_others / vol_ff の 5 本の WAV を書き出す。
# 判定は check-mixer-volume.py が行う。
#
# SSG（7FF7h）だけで鳴らし、その音量を書き換えて録る。
#   vol_reset   リセット直後（128 = 最大）
#   vol_half    64。半分になる
#   vol_mute    0。消える
#   vol_others  SSG を 128 に戻し、他の 4 本 (7FF8h-7FFBh) に 0。SSG は変わらない
#   vol_ff      FFh。bit7 が立てば最大なので reset と同じ
#
# **最終ミックスを録っている**（`record -audioonly`）。デバイスごとの
# `_ch<n>_record` はミキサーの手前で分岐するので、ここでは使えない。

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

proc w {reg val} {
	debug write ioports 0xA0 $reg
	debug write ioports 0xA1 $val
}

proc run_test {} {
	mem_write 0x7FFF 0x02        ;# I/O Enabler2 b1: SSGS を開く
	# 系統 1 (10h-1Fh) で鳴らす。C-BIOS も A0h/A1h に書くが、本体 PSG の
	# レジスタ番号は 0-15 にマスクされるので系統 1 には届かない。
	# 系統 0 で鳴らすと C-BIOS の書き込みで音が変わり、測るたびに値が動く
	w 0x10 0x40                  ;# ch A 周波数
	w 0x11 0x01
	w 0x17 0x3E                  ;# ch A のトーンだけ有効
	w 0x18 0x0F                  ;# ch A 音量最大
	# 鳴らし始めてすぐ測らない。openMSX のミキサーは直流分を落とすので、
	# 整定するまでピークが下がっていく
	after time 2 {capture vol_reset}
}

set steps {
	vol_half   {0x7FF7 64}
	vol_mute   {0x7FF7 0}
	vol_others {0x7FF7 0x80 0x7FF8 0 0x7FF9 0 0x7FFA 0 0x7FFB 0}
	vol_ff     {0x7FF7 0xFF}
}

proc capture {name} {
	record start -audioonly $::OUT/$name.wav
	after time 0.3 [list finish]
}

proc finish {} {
	record stop
	if {[llength $::steps] == 0} {
		after time 0.1 exit
		return
	}
	set name   [lindex $::steps 0]
	set writes [lindex $::steps 1]
	set ::steps [lrange $::steps 2 end]
	foreach {addr val} $writes { mem_write $addr $val }
	# 音量の段差のあとも直流分の過渡が残るので、整定を待つ
	after time 0.5 [list capture $name]
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
