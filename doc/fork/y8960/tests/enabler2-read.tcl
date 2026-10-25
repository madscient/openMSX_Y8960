# I/O Enabler2 (7FFFh) が読めることの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script enabler2-read.tcl
#
# 結果は標準出力と、環境変数 Y8960_TEST_OUT のディレクトリの enabler2-read.txt。
# **判定は最終行の RESULT を見る。** openmsx は Tcl の `exit` に渡した値を
# プロセスの終了コードにしない。
#
# デバッガの読み (peekMem) と CPU の読み (読みキャッシュ) の両方を見る。
# 7FFFh は 7F00h-7FFFh のキャッシュラインの末尾にあり、ラインが ROM で
# 埋まっていれば CPU には ROM が見える。CPU の側では、窓が消える RAM モードと、
# 同じバンクのまま互換モードへ戻って窓が再び出るところも読ませる。
#
# 使われていないビット (b3-b6) は 0 で読める、としている。これは実機の
# 仕様が出る前の仮置きで、変わればここの期待値も変わる。
#
# スロット 1 は C-BIOS_MSX2+ に固有で、機種を変えたら調べ直すこと。

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
		lappend lines [format "PASS  %-48s 0x%02X" $name $got]
	} else {
		incr fails
		lappend lines [format "FAIL  %-48s got 0x%02X want 0x%02X" $name $got $want]
	}
}

# F3        DI
# 3A FF 7F  LD A,(7FFFh)
# 32 80 C0  LD (C080h),A
# 3E 01     LD A,01h
# 32 FB 48  LD (48FBh),A  RAM モード
# 3E 10     LD A,10h
# 32 FD 48  LD (48FDh),A  6000h-7FFFh に RAM バンク #16。窓は消える
# 3E 5A     LD A,5Ah
# 32 FF 7F  LD (7FFFh),A  RAM に書く
# 3A FF 7F  LD A,(7FFFh)
# 32 81 C0  LD (C081h),A
# AF        XOR A
# 32 FB 48  LD (48FBh),A  互換モード。バンクはそのままで、窓が再び出る
# 3A FF 7F  LD A,(7FFFh)
# 32 82 C0  LD (C082h),A
# 18 FE     JR $
set stub {0xF3 0x3A 0xFF 0x7F 0x32 0x80 0xC0
          0x3E 0x01 0x32 0xFB 0x48 0x3E 0x10 0x32 0xFD 0x48
          0x3E 0x5A 0x32 0xFF 0x7F 0x3A 0xFF 0x7F 0x32 0x81 0xC0
          0xAF 0x32 0xFB 0x48 0x3A 0xFF 0x7F 0x32 0x82 0xC0 0x18 0xFE}

proc setup {} {
	global stub
	# ページ 1 (4000-7FFF) と 2 (8000-BFFF) をスロット 1 に向ける
	set a8 [debug read ioports 0xA8]
	debug write ioports 0xA8 [expr {($a8 & 0xC3) | (1 << 2) | (1 << 4)}]

	check "debugger reads 7FFFh after reset"        [cr 0x7FFF] 0x00
	cw 0x7FFF 0xFF
	check "debugger reads 7FFFh=FF, unused bits 0"   [cr 0x7FFF] 0x87
	cw 0x7FFF 0x02
	check "debugger reads 7FFFh=02"                  [cr 0x7FFF] 0x02
	cw 0x7FFF 0x85
	check "debugger reads 7FFFh=85"                  [cr 0x7FFF] 0x85

	set i 0xC000
	foreach b $stub { debug write memory $i $b ; incr i }
	debug write memory 0xC080 0x00
	debug write memory 0xC081 0x00
	debug write memory 0xC082 0x00
	reg pc 0xC000
	after time 0.05 finish
}

proc finish {} {
	global OUT lines fails stub
	# 結果の置き場 (C080h-) はスタブより後ろでなければならない。重なると
	# 1 件目の結果がスタブを書き換えて CPU が暴走する
	check "CPU stopped at the JR \$ of the stub"     [reg pc] [expr {0xC000 + [llength $stub] - 2}]
	check "CPU reads 7FFFh"                       [debug read memory 0xC080] 0x85
	check "CPU reads RAM at 7FFFh in RAM mode"       [debug read memory 0xC081] 0x5A
	check "CPU reads 7FFFh back in compat mode"      [debug read memory 0xC082] 0x85
	check "debugger reads 7FFFh in compat mode"      [cr 0x7FFF] 0x85

	if {$fails > 0} {
		lappend lines "RESULT: FAILED $fails"
	} else {
		lappend lines "RESULT: ALL PASS"
	}
	set f [open "$OUT/enabler2-read.txt" w]
	foreach l $lines { puts $f $l ; puts $l }
	close $f
	exit
}

after time 2 setup
