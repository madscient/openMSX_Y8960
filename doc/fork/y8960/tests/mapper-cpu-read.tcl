# CPU の読みが、デバッガの読みと一致することの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script mapper-cpu-read.tcl
#
# 結果は標準出力と、環境変数 Y8960_TEST_OUT のディレクトリの mapper-cpu-read.txt。
# **判定は最終行の RESULT を見る。** openmsx は Tcl の `exit` に渡した値を
# プロセスの終了コードにしない（**確認済み**: 6 件落ちる構成でも 0 が返った）。
#
# **なぜ CPU に実行させるのか**: openMSX の CPU は読みキャッシュを持ち、
# `getReadCacheLine()` が返したポインタから直接読む。デバッガの読みは
# `peekMem()` を通るのでキャッシュを見ない。**両者が食い違う不具合は、
# 実際に Z80 に読ませない限り観測できない。** だから本体 RAM に短い
# ルーチンを置いて走らせ、読んだ値を RAM に書かせて回収する。
#
# 測るのは 2 つ。RAM バンクを置いたページと、SCC 窓が出ているページ。
# どちらも ROM ではないので、キャッシュが ROM で埋まっていれば値が違う。
#
# ページ 1 と 2 をカートリッジのスロットに向けてから走らせる。スロット 1 は
# C-BIOS_MSX2+ に固有で、機種を変えたら調べ直すこと。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set fails 0
set lines {}

proc cw {addr val} { debug write "slotted memory" [expr {(1 << 18) | $addr}] $val }
proc cr {addr}     { debug read  "slotted memory" [expr {(1 << 18) | $addr}] }

proc check {name got want} {
	global lines fails
	if {$got == $want} {
		lappend lines [format "PASS  %-44s %s" $name $got]
	} else {
		incr fails
		lappend lines [format "FAIL  %-44s got %s want %s" $name $got $want]
	}
}

# F3        DI          割り込みハンドラがスロットを触ると測定が崩れる
# 3A 00 60  LD A,(6000h)
# 32 10 C0  LD (C010h),A
# 3A 00 98  LD A,(9800h)
# 32 11 C0  LD (C011h),A
# 18 FE     JR $
set stub {0xF3 0x3A 0x00 0x60 0x32 0x10 0xC0 0x3A 0x00 0x98 0x32 0x11 0xC0 0x18 0xFE}

proc setup {} {
	global stub
	# ページ 1 (4000-7FFF) と 2 (8000-BFFF) をスロット 1 に向ける
	set a8 [debug read ioports 0xA8]
	debug write ioports 0xA8 [expr {($a8 & 0xC3) | (1 << 2) | (1 << 4)}]

	# RAM モード。region 3 に RAM バンク、region 4 に SCC 窓
	cw 0x48FB 0x01
	cw 0x48FD 0x10
	cw 0x48FE 0x3F
	cw 0x6000 0x41
	cw 0x9800 0x5C

	set i 0xC000
	foreach b $stub { debug write memory $i $b ; incr i }
	debug write memory 0xC010 0x00
	debug write memory 0xC011 0x00
	reg pc 0xC000
	after time 0.05 finish
}

proc finish {} {
	global OUT lines fails
	check "debugger sees the RAM bank at 0x6000"  [cr 0x6000] 0x41
	check "CPU sees the RAM bank at 0x6000"       [debug read memory 0xC010] 0x41
	check "debugger sees the SCC window at 0x9800" [cr 0x9800] 0x5C
	check "CPU sees the SCC window at 0x9800"      [debug read memory 0xC011] 0x5C

	if {$fails > 0} {
		lappend lines "RESULT: FAILED $fails"
	} else {
		lappend lines "RESULT: ALL PASS"
	}
	set f [open "$OUT/mapper-cpu-read.txt" w]
	foreach l $lines { puts $f $l ; puts $l }
	close $f
	exit
}

after time 2 setup
