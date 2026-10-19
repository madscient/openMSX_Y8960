# Y8960 の SCC のチャンネルごとの定位（9900h-9904h）の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script scc-panpot.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# scc-panpot.txt にレジスタの検査を、center / left / right / zero / chB_left の
# 5 本の WAV に音を書き出す。判定は check-scc-panpot.py が行い、txt の最終行の
# RESULT も併せて見る。
#
# **判別力の根拠**:
# - 定位が効いていなければ left / right も center と同じ L=R になる
# - chB_left は ch A を右に、ch B を左に振って ch B だけを鳴らす。定位の番地と
#   チャンネルの対応がずれていれば左に出ない
# - zero は 0 を書く。中央として扱えば L=R になる
# - SCC は下位 8bit しか見ないので、9900h-9904h が SCC に届けば波形 ch A の先頭に
#   落ちる。そうならないことと、9905h 以降・読み出し・他の窓の x900h が SCC の
#   ミラーのままであることを、届けば値が変わるように波形を仕込んで見ている
# - RAM モードでも BANK2 に SCC を出していれば 9900h-9904h が定位に届き、SCC には
#   届かないことを見る。RTL はこの書き込みを捨てるが、不具合とみなしている。BANK2 に
#   RAM バンクを置けば、9900h は定位に届かない
#
# カートリッジはスロット 1（拡張なし）に入る。ここは C-BIOS_MSX2+ に固有で、
# 機種を変えたら調べ直すこと。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/scc-panpot.txt" w]
set fails 0

proc cw {addr val} { debug write "slotted memory" [expr {(1 << 18) | $addr}] $val }
proc cr {addr}     { debug read  "slotted memory" [expr {(1 << 18) | $addr}] }

proc wave {ch i} { debug read "Y8960 SCC SCC" [expr {$ch * 32 + $i}] }
proc deform {}   { debug read "Y8960 SCC SCC" 0xC0 }
proc pan {ch}    { debug read "Y8960 SCC pan" $ch }

proc check {name got want} {
	global log fails
	if {$got == $want} {
		puts $log [format "PASS  %-46s %s" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-46s got %s want %s" $name $got $want]
	}
}

proc check_ne {name got notwant} {
	global log fails
	if {$got != $notwant} {
		puts $log [format "PASS  %-46s %s" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-46s got %s (must differ)" $name $got]
	}
}

# ch A と ch B に同じ矩形波（前半 40h、後半 C0h）を置き、約 436Hz、音量最大にする。
# 鳴らすチャンネルは 988Fh で選ぶ
proc setup_wave {} {
	cw 0x9000 0x3F
	for {set i 0} {$i < 32} {incr i} {
		set v [expr {$i < 16 ? 0x40 : 0xC0}]
		cw [expr {0x9800 + $i}] $v
		cw [expr {0x9820 + $i}] $v
	}
	cw 0x9880 0x00 ; cw 0x9881 0x01
	cw 0x9882 0x00 ; cw 0x9883 0x01
	cw 0x988A 0x0F
	cw 0x988B 0x0F
}

proc registers {} {
	# 何も書いていない定位は既定の 128
	for {set ch 0} {$ch < 5} {incr ch} {
		check "pan ch$ch defaults to 128" [pan $ch] 128
	}

	setup_wave

	# 9900h-9904h は定位に届き、SCC には届かない
	cw 0x9900 0x01
	check "9900h sets pan ch A" [pan 0] 1
	check "9900h does not reach wave A\[0\]" [wave 0 0] 0x40
	cw 0x9904 0x02
	check "9904h sets pan ch E" [pan 4] 2
	check "9904h does not reach wave A\[4\]" [wave 0 4] 0x40

	# 9905h 以降は SCC のミラー
	cw 0x9905 0x03
	check "9905h reaches wave A\[5\]" [wave 0 5] 0x03
	cw 0x9805 0x40
	cw 0x9990 0x55
	check "9990h reaches freq of ch A" [debug read "Y8960 SCC SCC" 0xA0] 0x55
	cw 0x9880 0x00

	# 読み出しは 9900h-9904h も SCC のミラー
	check "9900h reads wave A\[0\]" [cr 0x9900] 0x40
	check "9910h reads wave A\[16\]" [cr 0x9910] 0xC0

	# ほかの 3 つの窓の x900h-x904h は定位ではなく SCC のミラー
	foreach {reg addr ch restore} {
		0x5000 0x5902 2 0x00
		0x7000 0x7903 3 0x01
		0xB000 0xB904 4 0x03
	} {
		set before [pan $ch]
		cw $reg 0x3F
		cw $addr 0x11
		check [format "%Xh leaves pan ch %d alone" $addr $ch] [pan $ch] $before
		check [format "%Xh reaches wave A\[%d\]" $addr $ch] [wave 0 $ch] 0x11
		cw [expr {0x9800 + $ch}] 0x40
		cw $reg $restore
	}

	# RAM モードでも定位に届き、SCC には届かない
	cw 0x48FB 0x01
	cw 0x48FE 0x3F
	cw 0x9900 0x66
	check "RAM mode: 9900h sets pan ch A" [pan 0] 0x66
	check "RAM mode: 9900h does not reach wave A\[0\]" [wave 0 0] 0x40
	cw 0x9800 0x40
	# BANK2 に RAM バンクを置けば、9900h はメモリで、定位には届かない
	cw 0x48FE 0x10
	cw 0x9900 0x77
	check "RAM mode, RAM bank: 9900h leaves pan ch A alone" [pan 0] 0x66
	check "RAM mode, RAM bank: 9900h is memory" [cr 0x9900] 0x77
	cw 0x48FE 0x3F
	cw 0x48FB 0x00
	cw 0x9000 0x3F

	# 窓が閉じていれば届かない
	cw 0x9000 0x02
	cw 0x9900 0x44
	check_ne "9900h without the SCC window" [pan 0] 0x44
	cw 0x9000 0x3F

	for {set ch 0} {$ch < 5} {incr ch} { cw [expr {0x9900 + $ch}] 128 }
}

proc capture {name chan enable} {
	global OUT
	cw 0x988F $enable
	set "::Y8960 SCC_ch${chan}_record" "$OUT/$name.wav"
	after time 0.2 [list stop $name]
}

proc stop {name} {
	set "::Y8960 SCC_ch1_record" ""
	set "::Y8960 SCC_ch2_record" ""
	cw 0x988F 0x00
	global step ; incr step ; next
}

proc finish {} {
	global log fails OUT
	# リセットで定位が 128 に戻る。Tcl の reset はスクリプトの実行中には効かないので
	# 時間を進めてから見る
	check "pan ch A back to 128 after reset" [pan 0] 128
	check "pan ch E back to 128 after reset" [pan 4] 128
	if {$fails > 0} {
		puts $log "RESULT: FAILED $fails"
	} else {
		puts $log "RESULT: ALL PASS"
	}
	close $log
	exit
}

set step 0
proc next {} {
	global step
	switch $step {
		0 { registers ; incr step ; next }
		1 { capture center 1 0x01 }
		2 { cw 0x9900 1   ; capture left  1 0x01 }
		3 { cw 0x9900 255 ; capture right 1 0x01 }
		4 { cw 0x9900 0   ; capture zero  1 0x01 }
		5 { cw 0x9900 255 ; cw 0x9901 1 ; capture chB_left 2 0x02 }
		6 { cw 0x9900 1 ; cw 0x9904 255 ; reset ; after time 0.5 finish }
	}
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 next
