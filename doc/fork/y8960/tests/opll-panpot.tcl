# Y8960 の OPLL のチャンネルごとの定位 (50h-58h) の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script opll-panpot.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# center/zero/left/right/bd_left の 5 本の WAV を書き出す。
# 判定は check-opll-panpot.py が行う。
#
# 判別力があるのは left / right / bd_left で、定位が効いていなければ
# どれも center と同じ（L=R）になる。zero は 0 を書くと 1 と同じ左端になることを
# 見ている。bd_left はリズム音が ch7 (0 起算で 6) の定位に従うことを見る。
# ch7 を左端、ch8 を右端にして BD を鳴らし、左から出ることを確かめる。
# BD を ch8 の定位に繋いでいれば右から出る。録るのは 12 番目のチャンネル。
# コアのリズム音の出力は HH / TOM / BD / SD / TC の並びで、BD は 3 番目にある。
#
# **OPLL への書き込みは 1 件ずつ時刻をずらす。** コアは書き込みを 18 ステップ
# （1 サンプル）の枠に入れて順に処理するので、同じ時刻に 2 件書くと後の 1 件が
# 前の 1 件を上書きする。Tcl の `debug write` は時刻を進めないので、
# アドレスとデータを続けて書くとデータだけが残り、音にならない。
# レジスタの写し (debug read) はこの枠を通らずに更新されるため、
# 写しを見るテストではこの問題は見えない。

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

# 書き込みの列。run_queue が 0.5ms おきに 1 件ずつ実行し、尽きたら then を呼ぶ
set queue {}
proc q {args} { lappend ::queue $args }
proc run_queue {then} {
	if {[llength $::queue] == 0} { eval $then ; return }
	set item [lindex $::queue 0]
	set ::queue [lrange $::queue 1 end]
	eval $item
	after time 0.0005 [list run_queue $then]
}

# 7Ch がレジスタ番号、7Dh がその値
proc r {reg val} {
	q debug write ioports 0x7C $reg
	q debug write ioports 0x7D $val
}

# ch1 (0 起算で 0) で持続音を鳴らす。音色 1 (バイオリン)
proc note {} {
	r 0x30 0x10                  ;# 音色 1、音量最大
	r 0x10 0xAC                  ;# F-Number 下位
	r 0x20 0x14                  ;# キーオン、ブロック 2
}

proc capture {name pan chan} {
	mem_write 0x7FF6 0x01        ;# I/O Enabler1 b0: 7Ch-7Dh を開く
	r 0x50 $pan                  ;# ch1 の定位
	note
	# アタックが終わってから録る
	run_queue [list after time 0.5 [list record_now $name $chan]]
}

proc record_now {name chan} {
	set "::Y8960 OPLL_ch${chan}_record" "$::OUT/$name.wav"
	after time 0.5 [list stop $chan]
}

proc stop {chan} {
	set "::Y8960 OPLL_ch${chan}_record" ""
	r 0x20 0x04                  ;# キーオフ
	run_queue {after time 0.3 next_step}
}

# BD を ch7 の定位で鳴らす。ch8 の定位は逆側にしておく
proc bd {name} {
	mem_write 0x7FF6 0x01
	r 0x56 1                     ;# ch7 (BD) を左端
	r 0x57 255                   ;# ch8 (HH/SD) を右端
	r 0x16 0x20 ; r 0x26 0x05    ;# BD の周波数
	r 0x36 0x00                  ;# BD 音量最大
	r 0x0E 0x20                  ;# リズムモード
	run_queue [list bd_hit $name]
}

proc bd_hit {name} {
	set "::Y8960 OPLL_ch12_record" "$::OUT/$name.wav"
	r 0x0E 0x30                  ;# BD キーオン
	run_queue {after time 0.3 bd_stop}
}

proc bd_stop {} {
	set "::Y8960 OPLL_ch12_record" ""
	r 0x0E 0x00
	run_queue next_step
}

set step 0
proc next_step {} {
	global step
	set s $step
	incr step
	switch $s {
		0 { capture center 128 1 }
		1 { capture zero   0   1 }
		2 { capture left   1   1 }
		3 { capture right  255 1 }
		4 { bd bd_left }
		default { exit }
	}
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 next_step
