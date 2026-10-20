# Y8960 の OPM (YM2151) の回帰テスト。直接 I/O (7Eh/7Fh)、メモリマップド I/O の
# トンネル (7FFBh/7FFCh)、I/O Enabler2 の b2、ステータスの読み出し、割り込み、
# ミキサーの OPM の音量 (7FFDh) を見る。
#
#   openmsx -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script opm.tcl
#
# 出力先は環境変数 Y8960_TEST_OUT のディレクトリ（未設定ならカレント）。
# opm.txt にレジスタの検査を、closed_note / mmio_note / io_note / left_only /
# mix_full / mix_half / mix_mute / mix_others の 8 本の WAV に音を書き出す。
# 判定は check-opm.py が行い、txt の最終行の RESULT も併せて見る。
#
# **判別力の根拠**:
# - 7Fh の読み出しは、閉じていれば FFh、開いていればステータス。タイマー A の
#   フラグを立てておくので、開いていれば 01h になる。7FFFh の b2 以外のビットを
#   立てても開かないことを見て、ビットの取り違えを捕まえる
# - 閉じている間に 7Eh/7Fh へ書いたタイマーの起動が効かないことを、開け直して
#   ステータスが 00h のままであることで見る
# - 割り込みは OPM の線 (`Y8960 OPM.IRQ`) と CPU の線 (`z80.pendingIRQ`) の両方を
#   見る。VDP の割り込みは止めておく（timer-irq.tcl と同じ理由）
# - closed_note は閉じたポートで鳴らそうとして無音になること、mmio_note は
#   ポートを閉じたまま 7FFBh/7FFCh で鳴ること、io_note は 7FFBh/7FFCh で
#   キーオフしたあと 7Eh/7Fh でキーオンして鳴ること
# - left_only は OPM 自身の RL ビットで左だけにする。ステレオのデバイスとして
#   繋がっていなければ右にも出る
# - mix_* は最終ミックスを録る。7FFDh が 64 で半分、0 で無音。他の音源の音量
#   (7FF7h-7FFAh) を 0 にしても OPM は変わらない

# 人間の並行作業とキー入力が衝突しないよう、ウィンドウを出さずに走らせる。
# この 2 行は必ず先頭に置くこと（設定が効く前にウィンドウが作られてしまう）。
set renderer none
set sound_driver null

set OUT [expr {[info exists ::env(Y8960_TEST_OUT)] ? $::env(Y8960_TEST_OUT) : "."}]
set log [open "$OUT/opm.txt" w]
set fails 0

proc mem_write {offset val} {
	for {set ps 0} {$ps < 4} {incr ps} {
		for {set ss 0} {$ss < 4} {incr ss} {
			debug write "slotted memory" [expr {($ps<<18)|($ss<<16)|$offset}] $val
		}
	}
}

# 直接 I/O と、メモリマップド I/O のトンネル
proc io {reg val} { debug write ioports 0x7E $reg ; debug write ioports 0x7F $val }
proc mm {reg val} { mem_write 0x7FFB $reg ; mem_write 0x7FFC $val }

proc status {}  { debug read ioports 0x7F }
proc opm_irq {} { debug probe read "Y8960 OPM.IRQ" }
proc cpu_irq {} { debug probe read z80.pendingIRQ }

proc check {name got want} {
	global log fails
	if {$got == $want} {
		puts $log [format "PASS  %-46s %s" $name $got]
	} else {
		incr fails
		puts $log [format "FAIL  %-46s got %s want %s" $name $got $want]
	}
}

# ch 0 に正弦波 1 個（CON=7 で M1 だけを鳴らす）。D1R=0 なので鳴り続ける
proc voice {w rl} {
	$w 0x20 [expr {($rl << 6) | 0x07}]   ;# RL、FB=0、CON=7
	$w 0x28 0x4A                          ;# KC: オクターブ 4、A
	$w 0x30 0x00
	$w 0x38 0x00
	foreach slot {0x00 0x08 0x10 0x18} tl {0x00 0x7F 0x7F 0x7F} {
		$w [expr {0x40 + $slot}] 0x01     ;# MUL=1
		$w [expr {0x60 + $slot}] $tl
		$w [expr {0x80 + $slot}] 0x1F     ;# AR 最大
		$w [expr {0xA0 + $slot}] 0x00
		$w [expr {0xC0 + $slot}] 0x00
		$w [expr {0xE0 + $slot}] 0x0F     ;# RR 最大
	}
}
proc key_on  {w} { $w 0x08 0x78 }
proc key_off {w} { $w 0x08 0x00 }

proc registers1 {} {
	debug write "VDP regs" 1 [expr {[debug read "VDP regs" 1] & ~0x20}]

	check "7Fh reads FFh after reset" [status] 0xFF
	check "OPM irq low after reset" [opm_irq] 0

	# ポートを閉じたまま、トンネルからタイマー A を最短周期で走らせる
	mm 0x10 0xFF
	mm 0x11 0x03
	mm 0x14 0x05                 ;# LOAD A、IRQ EN A
	after time 0.01 registers2
}

proc registers2 {} {
	check "OPM irq raised by timer A" [opm_irq] 1
	check "CPU sees the irq" [cpu_irq] 1
	check "7Fh still FFh while closed" [status] 0xFF

	mem_write 0x7FFF 0x83
	check "7FFFh without b2 keeps 7Fh closed" [status] 0xFF
	mem_write 0x7FFF 0x04
	check "7Fh reads status: timer A flag" [status] 0x01
	check "7Eh does not answer a read" [debug read ioports 0x7E] 0xFF

	io 0x14 0x30                 ;# フラグを落とし、タイマーを止める
	check "flags cleared through 7Eh/7Fh" [status] 0x00
	check "OPM irq low after clearing" [opm_irq] 0

	# 閉じたポートへの書き込みは届かない
	mem_write 0x7FFF 0x00
	io 0x14 0x05
	after time 0.01 registers3
}

proc registers3 {} {
	mem_write 0x7FFF 0x04
	check "write to closed 7Fh is ignored" [status] 0x00
	check "OPM irq stays low" [opm_irq] 0
	mem_write 0x7FFF 0x00
	incr ::step
	next
}

proc rec_dev {name} {
	set "::Y8960 OPM_ch1_record" "$::OUT/$name.wav"
	after time 0.3 [list rec_dev_stop]
}
proc rec_dev_stop {} {
	set "::Y8960 OPM_ch1_record" ""
	after time 0.2 [list incr_next]
}

# 最終ミックス。ミキサーは直流分を落とすので、音量を変えたら整定を待ってから録る
proc rec_mix {name} {
	after time 0.5 [list record start -audioonly "$::OUT/$name.wav"]
	after time 0.8 [list rec_mix_stop]
}
proc rec_mix_stop {} {
	record stop
	after time 0.1 [list incr_next]
}

proc incr_next {} { incr ::step ; next }

proc finish {} {
	global log fails
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
	switch $::step {
		0 { registers1 }
		1 { voice io 3 ; key_on io ; rec_dev closed_note }
		2 { voice mm 3 ; key_on mm ; rec_dev mmio_note }
		3 { key_off mm ; mem_write 0x7FFF 0x04 ; after time 0.1 { key_on io ; rec_dev io_note } }
		4 { io 0x20 [expr {(1 << 6) | 0x07}] ; rec_dev left_only }
		5 { io 0x20 [expr {(3 << 6) | 0x07}] ; rec_mix mix_full }
		6 { mem_write 0x7FFD 64 ; rec_mix mix_half }
		7 { mem_write 0x7FFD 0 ; rec_mix mix_mute }
		8 {
			mem_write 0x7FFD 0x80
			foreach a {0x7FF7 0x7FF8 0x7FF9 0x7FFA} { mem_write $a 0 }
			rec_mix mix_others
		}
		default { finish }
	}
}

# 起動直後はまだリセットが走りきっていないので、少し進めてから測る
after time 2 next
