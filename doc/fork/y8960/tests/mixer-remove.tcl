# カートリッジを抜いたら本体の音が戻ることの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script mixer-remove.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# muted.wav と restored.wav を書き出す。判定は check-mixer-remove.py が行う。
#
# **なぜこれが要るか**: 出力の切り替えは「聞かない側のデバイスのゲインを 0 に
# する」という形で実装してある。ゲインは openMSX のミキサーが持っていて
# カートリッジより長生きするので、**カートリッジを抜くときに戻さないと、
# 本体の音源が 0 のまま取り残される**。既定が y8960（本体側は 0）なので、
# これは既定の経路で起きる。
#
# **判別力の根拠**は 2 本の対比である。抜く前が無音で抜いた後が鳴っていれば、
# 鳴っているのは抜いたことの結果だと言える。restored だけでは、そもそも
# 切り替えが効いていなかっただけかもしれない。
#
# 本体 PSG と SSGS は A0h-A2h で重なっているが、SSGS の I/O は I/O Enabler2 が
# 閉じたままなので、ここでの書き込みは本体 PSG にしか届かない。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]

proc w {reg val} {
	debug write ioports 0xA0 $reg
	debug write ioports 0xA1 $val
}

proc run_test {} {
	# 本体 PSG の ch A を鳴らす
	w 0 0x00 ; w 1 0x01          ;# 周期 = 256
	w 7 0x3E                     ;# ch A のトーンだけ有効
	w 8 0x0F                     ;# ch A 音量最大

	# 既定は y8960 なので、本体 PSG は聞こえない側にいる
	set ::y8960-mixer_output y8960
	after time 0.5 capture_muted
}

proc capture_muted {} {
	record start -audioonly $::OUT/muted.wav
	after time 0.3 stop_muted
}
proc stop_muted {} {
	record stop
	remove_extension [lindex [list_extensions] 0]
	after time 0.5 capture_restored
}
proc capture_restored {} {
	record start -audioonly $::OUT/restored.wav
	after time 0.3 stop_restored
}
proc stop_restored {} {
	record stop
	after time 0.1 done
}
proc done {} { exit }

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
