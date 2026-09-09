# 本体内蔵版 SSGS の GPIO の回帰テスト。
#
#   python doc/fork/y8960/tests/make-builtin-config.py <dir>
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script ssgs-gpio.tcl
#
# 構成は make-builtin-config.py が作る本体内蔵版。カートリッジ版の構成でも
# 走り、そのときは手順 1 と 2 が外れる（そこが判別力のある部分）。
#
# 結果は環境変数 Y8960_TEST_OUT のファイルに書く。
#
# GPIO は**プライマリ側だけ**が持ち、本体 PSG の代替なので繋がるものも同じ
# （ジョイスティック 2 ポート、かなランプ、カセット）。
#
# **読み出しにデバッガブルを使っている理由**: 試験用の構成では C-BIOS の PSG が
# A0h-A2h に残ったままなので、ポートから読むと MSXMultiIODevice が両者の AND を
# 取ってしまう。実物の本体内蔵版では SSGS が PSG を置き換えるのでこの重なりは
# 無い。書き込みは重なっても害が無いのでポート経由でよい。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUTPATH [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT)
                                                       : "y8960-ssgs-gpio.txt"}]
set OUT [open $OUTPATH w]

proc w {reg val} {
	debug write ioports 0xA0 $reg
	debug write ioports 0xA1 $val
}

proc run_test {} {
	global OUT

	# $07 の b6=0 で port A を入力に、b7=1 で port B を出力にする
	w 0x07 0x80
	w 0x27 0x80

	# 同じジョイスティック/カセットを見ているので、本体 PSG と一致するはず
	set a [debug read "Y8960 SSGS regs" 0x0E]
	set p [debug read "PSG regs" 14]
	puts $OUT [format "1. unit0 \$0E=0x%02X  PSG reg14=0x%02X  (expect equal)" $a $p]

	w 0x0F 0x5A
	puts $OUT [format "2. unit0 \$0F write-back = 0x%02X (expect 0x5A)" \
		[debug read "Y8960 SSGS regs" 0x0F]]

	w 0x2E 0x11
	w 0x2F 0x22
	puts $OUT [format "3. unit1 \$2E=0x%02X \$2F=0x%02X (expect FF FF, the secondary has no GPIO)" \
		[debug read "Y8960 SSGS regs" 0x2E] [debug read "Y8960 SSGS regs" 0x2F]]

	close $OUT
	exit
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
