# バンクメモリの romblocks デバッガブルが答える番号の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -script mapper-romblocks.tcl
#
# -ext HRA_Y8960 は付けない。拡張の ROM は像が無い（`<rom/>`）ので、ROM のバンクは
# 割り当てなしの 255 と答え、ROM の番号を見られない。カートリッジは、このスクリプトが
# 128kB の ROM の像を書き出し、`carta` に `-romtype Y8960Cartridge` を付けて挿す。
#
# 結果は環境変数 Y8960_TEST_OUT のディレクトリの mapper-romblocks.txt。
# **判定は最終行の RESULT を見る。** openmsx は Tcl の `exit` に渡した値を
# プロセスの終了コードにしない。
#
# 期待する番号（implementation-plan.md の 2026-11-23 (63) の決定）:
#   - ROM のバンクは ROM のブロック番号 0〜15
#   - RAM のバンク n は 16 + n（16〜31。そのバンクを選ぶ 0〜31 の番号）
#   - SCC のバンク（63）は 15。レジスタの下に ROM のブロック 15 が見える
# バンク番号は下位 6 ビットだけが効き、32〜62 は 0〜30 と同じ。期待値はこの規則から
# 1 つずつ書いた。ミラー（C000h-FFFFh と 0000h-3FFFh）も同じ番号を答える。
#
# **判別力**: RAM のバンクを ROM のブロック数の剰余で答える実装では、RAM を選んだ
# 項目がすべて 16 小さく出て落ちる。ROM と SCC の項目は通る。
#
# **Tcl の `reset` はスクリプト実行中には効かない**ので、最後にレジスタを書いて戻す。
# スロット 1 は C-BIOS_MSX2+ のカートリッジスロット A。機種を変えたら調べ直すこと。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/mapper-romblocks.txt" w]
set fails 0

set rom [file join $OUT mapper-romblocks.rom]
set f [open $rom w]
fconfigure $f -translation binary
for {set b 0} {$b < 16} {incr b} {
	puts -nonewline $f [string repeat [binary format c $b] 8192]
}
close $f
carta $rom -romtype Y8960Cartridge

proc cw {addr val} { debug write "slotted memory" [expr {(1 << 18) | $addr}] $val }
# デバッガブルの名前は ROM のパスで始まる
proc rb {addr} {
	set name [lsearch -inline -glob [debug list] "*mapper-romblocks.rom romblocks"]
	debug read $name $addr
}

proc check {name got want} {
	global log fails
	if {$got == $want} {
		puts $log [format "PASS  %-44s %d" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-44s got %d want %d" $name $got $want]
	}
}

proc run_test {} {
	global log fails

	# 互換モードのバンクレジスタ 5000h（4000h-5FFFh）に書いた値と、期待する番号
	foreach {val want what} {
		0x00  0 "ROM 0"
		0x05  5 "ROM 5"
		0x0F 15 "ROM 15"
		0x10 16 "RAM 0"
		0x1A 26 "RAM 10"
		0x1F 31 "RAM 15"
		0x20  0 "32, the same as ROM 0"
		0x30 16 "48, the same as RAM 0"
		0x3E 30 "62, the same as RAM 14"
		0x3F 15 "SCC"
		0x45  5 "low 6 bits: ROM 5"
		0x5A 26 "low 6 bits: RAM 10"
		0xFF 15 "low 6 bits: SCC"
	} {
		cw 0x5000 $val
		check [format "4000h, bank %02Xh (%s)" $val $what] [rb 0x4000] $want
	}

	# ミラー: 4000h-7FFFh は C000h-FFFFh に、8000h-BFFFh は 0000h-3FFFh に出る
	cw 0x5000 0x1A
	check "C000h mirrors 4000h, bank 1Ah"            [rb 0xC000] 26
	cw 0x9000 0x13
	check "8000h, bank 13h (RAM 3)"                  [rb 0x8000] 19
	check "0000h mirrors 8000h, bank 13h"            [rb 0x0000] 19
	cw 0xB000 0x04
	check "A000h, bank 04h (ROM 4)"                  [rb 0xA000] 4
	check "2000h mirrors A000h, bank 04h"            [rb 0x2000] 4

	# RAM モードのバンクレジスタ（48FCh-48FFh が 4000h-BFFFh の 4 つ）
	cw 0x48FB 0x01
	cw 0x48FD 0x11
	check "RAM mode, 6000h, bank 11h (RAM 1)"        [rb 0x6000] 17
	cw 0x48FD 0x07
	check "RAM mode, 6000h, bank 07h (ROM 7)"        [rb 0x6000] 7

	# 戻す
	cw 0x48FB 0x00
	cw 0x5000 0x00
	cw 0x7000 0x01
	cw 0x9000 0x02
	cw 0xB000 0x03
	check "back to bank 0 at 4000h"                  [rb 0x4000] 0

	if {$fails > 0} {
		puts $log "RESULT: FAILED $fails"
	} else {
		puts $log "RESULT: ALL PASS"
	}
	close $log
	exit
}

after time 2 run_test
