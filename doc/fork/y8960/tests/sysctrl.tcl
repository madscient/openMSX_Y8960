# System Controller (I/O 40h-4Fh) の識別の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script sysctrl.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# sysctrl.txt を書き出す。**判定は最終行の RESULT を見る。**
# openmsx は Tcl の `exit` に渡した値をプロセスの終了コードにしない。
#
# 40h に 80h を書くと有効になって 40h が 7Fh を読む。41h に 02h を書くと
# このカートリッジが選ばれて 41h が FDh を読む。42h に 01h を書くと 42h が
# FEh を読み、他の値では FFh。選ばれていないときは 41h と 42h は FFh。
# Config ROM の読み書き (43h-47h) は持たないので、43h 以降は FFh。
# カートリッジの RTL（system_controller.v）と doc/spec/system_controller.md による。
#
# **判別力**: System Controller が無い構成では、40h に 80h を書いても FFh を読む。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/sysctrl.txt" w]
set fails 0

proc check {name got want} {
	global log fails
	if {$got == $want} {
		puts $log [format "PASS  %-48s 0x%02X" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-48s got 0x%02X want 0x%02X" $name $got $want]
	}
}
proc w {port val} { debug write ioports $port $val }
proc rd {port}    { debug read ioports $port }

proc run_test {} {
	global log fails
	check "40h before enabling"                      [rd 0x40] 0xFF

	w 0x40 0x80
	check "40h after writing 80h"                    [rd 0x40] 0x7F
	check "41h before selecting the board"           [rd 0x41] 0xFF
	check "42h before selecting the board"           [rd 0x42] 0xFF
	w 0x42 0x01
	check "42h ignores writes before the board"      [rd 0x42] 0xFF

	w 0x41 0x02
	check "41h after selecting the board (02h)"      [rd 0x41] 0xFD
	check "42h before choosing a function"           [rd 0x42] 0xFF
	w 0x42 0x01
	check "42h after choosing the Config ROM (01h)"  [rd 0x42] 0xFE
	check "43h (Config ROM is not emulated)"         [rd 0x43] 0xFF
	check "47h (Config ROM is not emulated)"         [rd 0x47] 0xFF
	check "4Fh"                                      [rd 0x4F] 0xFF
	w 0x42 0x03
	check "42h after choosing another function"      [rd 0x42] 0xFF

	w 0x42 0x01
	w 0x41 0x01
	check "41h after selecting another board"        [rd 0x41] 0xFF
	check "42h after selecting another board"        [rd 0x42] 0xFF
	w 0x41 0x02
	check "42h forgot the function"                  [rd 0x42] 0xFF

	w 0x40 0x00
	check "40h after writing 00h"                    [rd 0x40] 0xFF
	check "41h after writing 00h to 40h"             [rd 0x41] 0xFF

	if {$fails > 0} {
		puts $log "RESULT: FAILED $fails"
	} else {
		puts $log "RESULT: ALL PASS"
	}
	close $log
	exit
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
