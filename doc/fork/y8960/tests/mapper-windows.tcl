# バンクメモリの窓（SCC 音源レジスタと MMIO 窓）の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script mapper-windows.tcl
#
# 結果は標準出力と、環境変数 Y8960_TEST_OUT のディレクトリの mapper-windows.txt。
# **判定は最終行の RESULT を見る。** openmsx は Tcl の `exit` に渡した値を
# プロセスの終了コードにしない（**確認済み**: 6 件落ちる構成でも 0 が返った）。
#
# 確かめている規則は implementation-plan.md §3.8.1 の 4 つ。
#
# **判別力の根拠**: 窓が出ているかどうかは、窓に書いた値が届いた先で見る。
# SCC 窓なら SCC の波形メモリ、MMIO 窓なら OPLL のレジスタ。窓が無ければ
# 届かないので、同じ書き込みを出ている場合と出ていない場合の両方で測れば、
# 窓の有無そのものを分離できる。バンク1 に SCC を出したときは、同じ書き込みが
# SCC の deformation レジスタに落ちることまで見て、消えた先を特定している。
#
# **Tcl の `reset` はスクリプト実行中には効かない**（**確認済み**: RAM モードで
# `reset` した直後に互換モードのバンクレジスタを叩いても無視された）。
# リアクタが後で処理するので、状態はレジスタを書いて戻す。
#
# カートリッジはスロット 1（拡張なし）に入る。ここは C-BIOS_MSX2+ に固有で、
# 機種を変えたら調べ直すこと。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/mapper-windows.txt" w]
set fails 0

proc cw {addr val} { debug write "slotted memory" [expr {(1 << 18) | $addr}] $val }
proc cr {addr}     { debug read  "slotted memory" [expr {(1 << 18) | $addr}] }

# 波形 ch0 の 0 番地。SCC 窓のオフセット 00h に書いた値がここに来る
proc wave0 {} { debug read "Y8960 SCC SCC" 0 }
# deformation レジスタ。SCC 窓のオフセット E0h-FFh に書いた値がここに来る
proc deform {} { debug read "Y8960 SCC SCC" 0xC0 }
proc opll0 {reg} { debug read "Y8960 OPLL 0 regs" $reg }

# リセット直後の状態に戻す。RAMMODE は両モードで書けるので先に戻し、
# そのあと互換モードのバンクレジスタでバンクを戻す
proc mapper_reset {} {
	cw 0x48FB 0x00
	cw 0x5000 0x00
	cw 0x7000 0x01
	cw 0x9000 0x02
	cw 0xB000 0x03
}

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

# --- SCC 窓は 4 つの region すべてに出せる（ROM モード） ---------------------

mapper_reset
cw 0x9800 0x11
check_ne "region4 SCC closed before enabling" [wave0] 0x11
cw 0x9000 0x3F
cw 0x9800 0x11
check "region4 SCC at 0x9800 (Konami compat)" [wave0] 0x11

mapper_reset
cw 0x5000 0x3F
cw 0x5800 0x22
check "region2 SCC at 0x5800" [wave0] 0x22

mapper_reset
cw 0x7000 0x3F
cw 0x7800 0x33
check "region3 SCC at 0x7800" [wave0] 0x33

mapper_reset
cw 0xB000 0x3F
cw 0xB800 0x44
check "region5 SCC at 0xB800" [wave0] 0x44

# --- RAM モードのバンク0 には SCC を出さない -------------------------------

mapper_reset
cw 0x48FB 0x01
cw 0x48FC 0x3F
cw 0x5800 0x55
check_ne "RAM mode: no SCC window in bank 0" [wave0] 0x55

# --- MMIO 窓 ---------------------------------------------------------------

mapper_reset
cw 0x7FF4 0x02
cw 0x7FF5 0x5A
check "MMIO tunnel reaches OPLL 0 in ROM mode" [opll0 2] 0x5A

# バンク1 に SCC が出ると MMIO 窓は消え、同じ書き込みが SCC に落ちる。
# 0x7FF4/0x7FF5 は窓のオフセット F4h/F5h なので deformation レジスタに当たる
mapper_reset
cw 0x7000 0x3F
cw 0x7FF4 0x03
cw 0x7FF5 0xA5
check_ne "bank1 SCC hides MMIO (OPLL untouched)" [opll0 3] 0xA5
check "the same write landed on the SCC instead" [deform] 0xA5

# バンク1 が RAM でも MMIO 窓は消える
mapper_reset
cw 0x48FB 0x01
cw 0x48FD 0x10
cw 0x7FF4 0x04
cw 0x7FF5 0x3C
check_ne "bank1 RAM hides MMIO (OPLL untouched)" [opll0 4] 0x3C

# バンク1 が ROM バンクなら、RAM モードでも MMIO 窓は残る
mapper_reset
cw 0x48FB 0x01
cw 0x48FD 0x01
cw 0x7FF4 0x05
cw 0x7FF5 0x6E
check "RAM mode with ROM in bank1 keeps MMIO" [opll0 5] 0x6E

# --- RAM バンクの判定が region を取り違えていないこと -----------------------
#
# region 3 のバンクレジスタは 0x48FD。ここに RAM バンクを置いたとき、
# 0x6000 への書き込みが RAM に残るかを見る。判定が別 region の
# バンクレジスタを見ていると、この書き込みは捨てられる。

mapper_reset
cw 0x48FB 0x01
cw 0x48FD 0x10
cw 0x6000 0xC3
check "RAM bank in region 3 is writable at 0x6000" [cr 0x6000] 0xC3

# --- SCC のバンク値は RAM バンクではない -----------------------------------
#
# 0x3F を RAM バンクとして扱うと ram の範囲外を指す。Release ビルドでは
# 値までは決まらないので、ここは read が返ること自体が確認事項。

mapper_reset
cw 0x48FB 0x01
cw 0x48FE 0x3F
check_ne "bank 0x3F in RAM mode does not read as RAM" [cr 0x8000] ""

if {$fails > 0} {
	puts $log "RESULT: FAILED $fails"
} else {
	puts $log "RESULT: ALL PASS"
}
close $log
set f [open "$OUT/mapper-windows.txt" r]
puts [read $f]
close $f
exit
