# OPL2EX の ADPCM-B が実際に音を出すことの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script adpcm-play.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# playing.wav と stopped.wav を書き出す。判定は check-adpcm-play.py が行う。
#
# サンプル RAM に三角波を書き、繰り返し再生させて最終ミックスを録る。
# **判別力があるのは 2 本の対比**である。playing が鳴っていて stopped が
# 無音なら、その音が ADPCM から出たものだと言える。playing だけでは、
# 別の音源が鳴っているだけかもしれない。
#
# 波形は 4bit の差分の最大値を並べたもの。7h が最大の正、Fh が最大の負なので、
# 77h を 16 バイト、FFh を 16 バイトで 1 周期 64 ニブルの三角波になる。
# ニブルの消費は 49716 * DELTA-N / 65536 [ニブル/秒] なので、DELTA-N が 8000h、
# 1 周期 64 ニブルなら 49716 * 0.5 / 64 = 388.4Hz。
# **判定器はこの周波数も見る。** 音が出ているだけでなく、書いた波形が
# 意図した速さで読まれていることまで確かめられる。
#
# ADPCM は FM と同じサウンドデバイスに混ざっていて独立に取り出せないので、
# デバイスごとの録音ではなく最終ミックスを録っている。他の音源は鳴らして
# いないため、聞こえるのは ADPCM だけである。

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

# OPL2-0 は C0h がレジスタ番号、C1h がその値
proc r {reg val} {
	debug write ioports 0xC0 $reg
	debug write ioports 0xC1 $val
}

proc run_test {} {
	mem_write 0x7FFF 0x01        ;# I/O Enabler2 b0: OPL2-0 を開く

	# --- サンプル RAM への書き込み ---
	r 0x08 0x00                  ;# RAM、18bit アドレス
	r 0x09 0x00 ; r 0x0A 0x00    ;# 開始 = ニブル 0
	r 0x0C 0x01 ; r 0x0B 0x00    ;# 終了 = ニブル 2048 = 1024 バイト
	r 0x07 0x60                  ;# REC | MEMORY DATA: メモリ書き込みモード
	debug write ioports 0xC0 0x0F
	for {set i 0} {$i < 1024} {incr i} {
		debug write ioports 0xC1 [expr {($i & 16) ? 0xFF : 0x77}]
	}

	# --- 再生 ---
	r 0x07 0x00                  ;# 一度止める
	r 0x09 0x00 ; r 0x0A 0x00
	r 0x0C 0x01 ; r 0x0B 0x00
	r 0x10 0x00 ; r 0x11 0x80    ;# DELTA-N = 8000h
	r 0x12 0xFF                  ;# 音量最大
	r 0x07 0xB0                  ;# START | MEMORY DATA | REPEAT

	# 直流分が落ち着いてから測る
	after time 1 capture_playing
}

proc capture_playing {} {
	record start -audioonly $::OUT/playing.wav
	after time 0.3 stop_playing
}
proc stop_playing {} {
	record stop
	r 0x07 0x00                  ;# 止める
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
