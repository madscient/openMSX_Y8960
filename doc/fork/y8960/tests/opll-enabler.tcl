# Y8960 の OPLL I/O Enabler (7FF6h) の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script opll-enabler.tcl
#
# 結果は環境変数 Y8960_TEST_OUT のファイルに書く（未設定なら
# カレントの y8960-enabler-test.txt）。openmsx.exe は Windows サブシステムで
# リンクされていて標準出力に何も出せないため、ファイルに書く必要がある。
#
# 判別力があるのは手順 2 と 4 の「変わらないこと」を見る側である。
# enabler を実装する前は writeIO() が無条件に転送していたので、
# 2 では 0x11/0x22 が、4 では OPLL0=0x55 が入っていた。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUTPATH [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT)
                                                       : "y8960-enabler-test.txt"}]
set OUT [open $OUTPATH w]

proc reg30 {n} { debug read "Y8960 OPLL $n regs" 0x30 }

proc report {label} {
	global OUT
	puts $OUT [format "%-44s OPLL0=0x%02X OPLL1=0x%02X" $label [reg30 0] [reg30 1]]
}

proc io_write {addrport dataport val} {
	debug write ioports $addrport 0x30
	debug write ioports $dataport $val
}

# カートリッジがどのスロットに入っても当たるよう全 ps/ss に書く。
# 他スロットの同アドレスは RAM なので、書いても害はない。
proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

proc run_test {} {
	global OUT
	report "1. reset"
	io_write 0x7C 0x7D 0x11
	io_write 0x7A 0x7B 0x22
	report "2. enabler=0, direct I/O (expect unchanged)"

	mem_write 0x7FF6 0x01
	io_write 0x7C 0x7D 0x33
	report "3. 7FF6=01, 0x33 via 7C/7D (expect OPLL0=33)"

	mem_write 0x7FF6 0x02
	io_write 0x7A 0x7B 0x44
	io_write 0x7C 0x7D 0x55
	report "4. 7FF6=02, 0x44 via 7A/7B, 0x55 via 7C/7D"

	mem_write 0x7FF6 0x00
	mem_write 0x7FF4 0x30
	mem_write 0x7FF5 0x66
	report "5. 7FF6=00, 0x66 via tunnel (expect OPLL0=66)"

	close $OUT
	exit
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 run_test
