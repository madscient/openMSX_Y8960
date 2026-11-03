# OPL2 のデータポート (C1h) の読み出しと、ADPCM の PCM_BSY の回帰テスト。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script opl2-read.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# opl2-read.txt を書き出す。**判定は最終行の RESULT を見る。**
# openmsx は Tcl の `exit` に渡した値をプロセスの終了コードにしない。
#
# - C1h で読み戻せるのは ADPCM データ (0Fh) だけで、他のレジスタは FFh。
#   デバッガの I/O の読み (peekIO) と CPU の IN の両方を見る。レジスタの
#   デバッガブルは書いた値のままであること
# - PCM_BSY (ステータスの b0) は START に従う。一回再生が終わると START と
#   一緒に 0 に戻る。R#07 に 81h（START と RESET）を書くと 0 のまま
#
# どちらもカートリッジの v0.9.5 以降の RTL とマニュアル 6.2.1 / 6.3 による。
#
# **判別力**: Y8950 と同じ実装では、C1h が書いた値を返し、PCM_BSY は
# 再生の終わりと 81h の後も 1 のまま残る。

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/opl2-read.txt" w]
set fails 0

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

# C0h がレジスタ番号、C1h がその値
proc r {reg val} {
	debug write ioports 0xC0 $reg
	debug write ioports 0xC1 $val
}
proc peek_data {reg} {
	debug write ioports 0xC0 $reg
	debug read ioports 0xC1
}
proc pcm_bsy {} { expr {[debug read ioports 0xC0] & 0x01} }

proc check {name got want} {
	global log fails
	if {$got == $want} {
		puts $log [format "PASS  %-48s 0x%02X" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-48s got 0x%02X want 0x%02X" $name $got $want]
	}
}

# F3        DI
# 3E 20     LD A,20h
# D3 C0     OUT (C0h),A
# DB C1     IN A,(C1h)
# 32 80 C0  LD (C080h),A
# 18 FE     JR $
set stub {0xF3 0x3E 0x20 0xD3 0xC0 0xDB 0xC1 0x32 0x80 0xC0 0x18 0xFE}

proc run_test {} {
	global stub
	mem_write 0x7FFF 0x01        ;# I/O Enabler2 b0: OPL2 を開く

	# データポートの読み (デバッガ)
	r 0x20 0x21
	r 0x12 0x80
	check "C1h reads FFh for an FM register"         [peek_data 0x20] 0xFF
	check "C1h reads FFh for 12h (EG-CTRL)"          [peek_data 0x12] 0xFF
	check "C1h reads FFh for 13h"                    [peek_data 0x13] 0xFF
	check "the regs debuggable still shows 20h"      [debug read "Y8960 OPL2 regs" 0x20] 0x21

	# PCM_BSY: START と RESET を同時に書く
	r 0x07 0x81
	check "PCM_BSY after writing 81h to R#07"        [pcm_bsy] 0
	# PCM_BSY: 4 バイト (8 ニブル) を最速で一回再生する
	r 0x08 0x00
	r 0x09 0x00 ; r 0x0A 0x00
	r 0x0B 0x00 ; r 0x0C 0x00
	r 0x10 0xFF ; r 0x11 0xFF
	r 0x07 0xA0                  ;# START | MEMORY DATA
	check "PCM_BSY right after START"                [pcm_bsy] 1
	after time 0.01 run_cpu
}

proc run_cpu {} {
	global stub
	check "PCM_BSY after a one-shot sample ended"    [pcm_bsy] 0

	set i 0xC000
	foreach b $stub { debug write memory $i $b ; incr i }
	debug write memory 0xC080 0xEE
	reg pc 0xC000
	after time 0.05 finish
}

proc finish {} {
	global log fails stub
	check "CPU stopped at the JR \$ of the stub"      [reg pc] [expr {0xC000 + [llength $stub] - 2}]
	check "CPU reads FFh from C1h for an FM register" [debug read memory 0xC080] 0xFF

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
