# ADPCM の PCM_BSY（状態レジスタの bit0）を R#07 の書き込みと一回再生の終わりで読む。
#   T_OUT=<出力ファイル> openmsx -machine C-BIOS_MSX2+ -ext <audio の拡張> -script pcmbsy.tcl
# 1 行に「場面 状態レジスタ」を書く。

set renderer none
set sound_driver null

set ::f [open $::env(T_OUT) w]

proc r {reg val} {
	debug write ioports 0xC0 $reg
	debug write ioports 0xC1 $val
}
proc st {label} {
	set s [debug read ioports 0xC0]
	puts $::f [format "%-14s %02X bsy=%d eos=%d" $label $s [expr {$s & 1}] [expr {($s >> 4) & 1}]]
}

proc t1 {} {
	r 0x04 0x80
	r 0x07 0x01 ; st "07=01"
	r 0x07 0x81 ; st "07=81"
	r 0x07 0x00 ; st "07=00"
	r 0x07 0xA1 ; st "07=A1"
	r 0x07 0x80 ; st "07=80"
	r 0x07 0x01 ; st "07=01b"
	# 64 バイトの標本を書く
	r 0x08 0x00
	r 0x09 0x00 ; r 0x0A 0x00
	r 0x0B 0x0F ; r 0x0C 0x00
	r 0x07 0x60
	for {set i 0} {$i < 64} {incr i} { r 0x0F [expr {($i * 37 + 11) & 0xFF}] }
	r 0x07 0x01
	r 0x10 0x00 ; r 0x11 0x40
	r 0x12 0xFF
	r 0x04 0x80
	# EOS だけマスクを外す（状態レジスタで見えるように）
	r 0x04 0x68
	r 0x07 0xA0 ; st "play"
	after time 0.3 t2
}
proc t2 {} {
	st "after-end"
	r 0x07 0x00 ; st "07=00c"
	r 0x04 0x80
	r 0x07 0xB0 ; st "repeat"
	after time 0.3 t3
}
proc t3 {} {
	st "repeat-later"
	r 0x07 0x01 ; st "07=01c"
	close $::f
	exit
}

after time 2 t1
