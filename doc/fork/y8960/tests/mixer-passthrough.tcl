# デジタルミキサー (B6h-B7h) が音に触らないことの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script mixer-passthrough.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# before.wav と after.wav を書き出す。判定は check-mixer-passthrough.py が行う。
#
# ミキサーは音源ごとの左右ゲインと全体ゲインを持っているが、**レジスタ仕様が
# 無いので B6h-B7h はそれらに繋がっていない**。ゲインはすべて 1.0 のままなので、
# B6h-B7h に何を書いても音は変わらない。繋がった時点でこのテストは書き換える。
#
# **最終ミックスを録っている**（`record -audioonly`）。デバイスごとの
# `_ch<n>_record` はミキサーの手前で分岐するので、ここでは使えない。
#
# 判別力があるのは after.wav。レジスタをゲインに繋いでしまえば、
# 全レジスタに 0 を書いた時点で音が消えるか小さくなる。

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
	mem_write 0x7FFF 0x10        ;# I/O Enabler2 b4: SSGS を開く
	# 系統 1 ($20-$3F) で鳴らす。C-BIOS も A0h/A1h に書くが、本体 PSG の
	# レジスタ番号は 0-15 にマスクされるので系統 1 には届かない。
	# 系統 0 で鳴らすと C-BIOS の書き込みで音が変わり、測るたびに値が動く
	w 0x20 0x40                  ;# ch A 周波数
	w 0x21 0x01
	w 0x27 0x3E                  ;# ch A のトーンだけ有効
	w 0x28 0x0F                  ;# ch A 音量最大
	# 鳴らし始めてすぐ測らない。openMSX のミキサーは直流分を落とすので、
	# 整定するまでピークが下がっていく
	after time 2 capture_before
}

proc capture_before {} {
	record start -audioonly $::OUT/before.wav
	after time 0.3 step2
}

proc step2 {} {
	record stop
	# 全チャンネルの左右レジスタに 0 を書く
	for {set r 0} {$r < 20} {incr r} {
		debug write ioports 0xB6 $r
		debug write ioports 0xB7 0x00
	}
	record start -audioonly $::OUT/after.wav
	after time 0.3 step3
}

proc step3 {} {
	record stop
	after time 0.1 done
}

proc done {} { exit }

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
