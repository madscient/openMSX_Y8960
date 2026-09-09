# Y8960 の出力と MSX 本体の出力の切り替えの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script mixer-output.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# 5 本の WAV を書き出す。判定は check-mixer-output.py が行う。
#
# カートリッジは音声を本体に戻さない。実機ではその 2 本の線を人が外で
# 切り替えるかミックスする。`y8960-mixer_output` 設定がそれで、
# y8960 / msx / mix の 3 値をとる。カートリッジ版の既定は y8960。
#
# 判別力があるのは**無音を期待している 2 本**である。切り替えが効いて
# いなければ、そこに音が出る。
#
# 本体 PSG と SSGS は A0h-A2h で重なっている。片方だけを鳴らすために、
#  - 前半は SSGS の I/O を閉じたまま書く（本体 PSG にしか届かない）
#  - 後半は SSGS 系統 1 ($20-) を使い、本体 PSG はデバッガブルで黙らせる
#    （C-BIOS のレジスタ番号は 0-15 にマスクされるので系統 1 には届かない）

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

# 直流分が落ち着いてから測る。openMSX のミキサーが除去するまで振幅が動く
proc capture {name mode next} {
	set ::y8960-mixer_output $mode
	after time 0.5 [list capture2 $name $next]
}
proc capture2 {name next} {
	record start -audioonly $::OUT/$name.wav
	after time 0.3 [list capture3 $next]
}
proc capture3 {next} {
	record stop
	after time 0.1 $next
}

# 前半: SSGS は閉じたまま。本体 PSG だけが鳴る
proc run_test {} {
	w 0x00 0x40 ; w 0x01 0x01 ; w 0x07 0x3E ; w 0x08 0x0F
	capture psg_msx msx step2
}
proc step2 {} { capture psg_y8960 y8960 step3 }

# 後半: SSGS 系統 1 だけが鳴る
proc step3 {} {
	mem_write 0x7FFF 0x10
	w 0x20 0x40 ; w 0x21 0x01 ; w 0x27 0x3E ; w 0x28 0x0F
	debug write "PSG regs" 7 0x3F
	debug write "PSG regs" 8 0x00
	capture ssgs_y8960 y8960 step4
}
proc step4 {} { capture ssgs_msx msx step5 }

# 最後: 本体 PSG を戻して両方鳴らす
proc step5 {} {
	debug write "PSG regs" 7 0x3E
	debug write "PSG regs" 8 0x0F
	capture both_mix mix done
}

proc done {} { exit }

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
