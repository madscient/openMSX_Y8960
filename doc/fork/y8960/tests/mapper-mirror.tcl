# ROM として挿した Y8960 の、0000-3FFF と C000-FFFF の読みの回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -script mapper-mirror.tcl
#
# -ext HRA_Y8960 は付けない。拡張は 4000-BFFF にしか置かないので、この番地を通らない。
# カートリッジは、このスクリプトが 128kB の ROM の像を書き出し、`carta` に
# `-romtype Y8960Cartridge` を付けて挿す。ROM の各バンクは、全バイトがバンク番号。
#
# 結果は標準出力と、環境変数 Y8960_TEST_OUT のディレクトリの mapper-mirror.txt。
# **判定は最終行の RESULT を見る。** openmsx は Tcl の `exit` に渡した値を
# プロセスの終了コードにしない。
#
# 見るもの:
#   - 4 つの region の RAM バンクが、ミラーの番地からも読めること（デバッガ）
#   - ミラーに ROM バンクも出て、SCC は出ず、ミラーへの書き込みは捨てられること
#   - CPU が page 0 から読めること。page 0 を見せたままバンクを替えたあとも、
#     CPU の読みキャッシュが古い ROM を指していないこと
#
# 修正前の実装は、0000-3FFF の読みでバンクレジスタの配列の約 4G 先を引く。
# 落ちて Windows のエラー報告の窓が出るおそれがあるので、修正前の exe で
# 回すときは page 0 を読む部分を外したものを使うこと。
#
# スロット 1 は C-BIOS_MSX2+ のカートリッジスロット A。機種を変えたら調べ直すこと。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set fails 0
set lines {}

set rom [file join $OUT mapper-mirror.rom]
set f [open $rom w]
fconfigure $f -translation binary
for {set b 0} {$b < 16} {incr b} {
	puts -nonewline $f [string repeat [binary format c $b] 8192]
}
close $f
carta $rom -romtype Y8960Cartridge

proc cw {addr val} { debug write "slotted memory" [expr {(1 << 18) | $addr}] $val }
proc cr {addr}     { debug read  "slotted memory" [expr {(1 << 18) | $addr}] }

proc check {name got want} {
	global lines fails
	if {$got == $want} {
		lappend lines [format "PASS  %-52s %s" $name $got]
	} else {
		incr fails
		lappend lines [format "FAIL  %-52s got %s want %s" $name $got $want]
	}
}

# 本体 RAM の C000h に置き、DI のまま走らせる。
# F3        DI
# DB A8     IN A,(A8h)
# 47        LD B,A
# E6 FC     AND FCh
# F6 01     OR 01h        page 0 をスロット 1 に
# D3 A8     OUT (A8h),A
# 3A 00 00  LD A,(0000h)  region 4 のミラー
# 32 20 C0  LD (C020h),A
# 3E 12     LD A,12h
# 32 00 90  LD (9000h),A  page 0 を見せたまま region 4 を RAM バンク 2 に
# 3A 00 00  LD A,(0000h)
# 32 21 C0  LD (C021h),A
# 78        LD A,B
# D3 A8     OUT (A8h),A
# 18 FE     JR $
set stub {0xF3 0xDB 0xA8 0x47 0xE6 0xFC 0xF6 0x01 0xD3 0xA8
          0x3A 0x00 0x00 0x32 0x20 0xC0 0x3E 0x12 0x32 0x00 0x90
          0x3A 0x00 0x00 0x32 0x21 0xC0 0x78 0xD3 0xA8 0x18 0xFE}

proc setup {} {
	global stub
	# ページ 1 (4000-7FFF) と 2 (8000-BFFF) をスロット 1 に向ける
	set a8 [debug read ioports 0xA8]
	debug write ioports 0xA8 [expr {($a8 & 0xC3) | (1 << 2) | (1 << 4)}]

	check "ROM bank 0 at 0x4000 (cartridge in slot 1)" [cr 0x4000] 0

	# RAM モードで RAM バンク 0-3 に印を書く。region 2 は RAM モードで書けないので
	# region 5 を通して書き、それから region 2 に出す
	cw 0x48FB 0x01
	cw 0x48FF 0x11 ; cw 0xA000 0xB6
	cw 0x48FF 0x12 ; cw 0xA000 0xD8
	cw 0x48FE 0x10 ; cw 0x8000 0xA5 ; cw 0x8123 0x5A
	cw 0x48FD 0x13 ; cw 0x6000 0xC7
	cw 0x48FC 0x11
	cw 0x48FB 0x00

	check "RAM bank 1 of region 2 at 0xC000" [cr 0xC000] 0xB6
	check "RAM bank 3 of region 3 at 0xE000" [cr 0xE000] 0xC7
	check "RAM bank 0 of region 4 at 0x0000" [cr 0x0000] 0xA5
	check "RAM bank 0 of region 4 at 0x0123" [cr 0x0123] 0x5A
	check "RAM bank 2 of region 5 at 0x2000" [cr 0x2000] 0xD8

	cw 0x9000 0x05
	check "ROM bank 5 of region 4 at 0x0000" [cr 0x0000] 5

	cw 0x9000 0x3F
	cw 0x9800 0x42
	cw 0x1800 0x24
	check "SCC at 0x9800, the write to 0x1800 dropped" [cr 0x9800] 0x42
	check "no SCC at 0x1800: ROM bank 15" [cr 0x1800] 15

	cw 0x9000 0x10

	set i 0xC000
	foreach b $stub { debug write memory $i $b ; incr i }
	debug write memory 0xC020 0x00
	debug write memory 0xC021 0x00
	reg pc 0xC000
	after time 0.05 finish
}

proc finish {} {
	global OUT lines fails
	check "CPU reads RAM bank 0 at 0x0000" [debug read memory 0xC020] 0xA5
	check "CPU reads RAM bank 2 at 0x0000 after the switch" [debug read memory 0xC021] 0xD8
	check "debugger reads RAM bank 2 at 0x0000 after the switch" [cr 0x0000] 0xD8

	if {$fails > 0} {
		lappend lines "RESULT: FAILED $fails"
	} else {
		lappend lines "RESULT: ALL PASS"
	}
	set f [open "$OUT/mapper-mirror.txt" w]
	foreach l $lines { puts $f $l ; puts $l }
	close $f
	exit
}

after time 2 setup
