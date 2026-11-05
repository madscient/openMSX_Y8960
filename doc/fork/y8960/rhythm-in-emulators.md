# OPL / OPLL 系のエミュレータでのリズム音の大きさ

Y8960 のリズム音を楽音と 1 : 1 で混ぜるか 2 倍にするかを決める材料として、ほかのエミュレータの実装を読んだ。
対象読者は、このフォークで Y8960 の音量を扱う開発者と AI。

**確度**: 全体は**確認済み(読解)**（2026-11-05。ソースを読んだだけで、走らせていない）。表の行のうち、emu2413 の
`_MO`/`_RO` と足し合わせ、Nuked-OPLL の RO の時間割、ymfm の BD の `result * 2`、DBOPL の `sample <<= 1` は、二人目が
もう一度原典を開いて確かめた。行番号は読んだ版のもの。

## 結論

- **読んだ実装はどれも、リズム音を楽音の実質 2 倍で混ぜている。** やり方は 3 通り
  - リズム側に ×2 か `<< 1` を掛ける（ymfm、DBOPL、Nuked-OPL2-Lite、openMSX の各コア）
  - 楽音側を半分にする（emu2413、emu8950 の `_MO(x) = -(x) >> 1`、`_RO(x) = x`）
  - 実チップのように RO の端子へ 1 フレームに複数回出す（Nuked-OPLL。MO と RO を別々に返し、混ぜ方は呼ぶ側に任せる）
- **2 倍の理由を書いたコメントはどこにも無い。** 近いのは次の 3 つ
  - Nuked-OPLL の RO の時間割（「TODO: This might be incorrect」付き）
  - ymfm の OPLL の「final output is multiplexed; we don't simulate that here except to average over everything」
  - openMSX の `YM2413OriginalNukeYKT.cc` が RO を 1 回だけ取って `* 2` していること（1 フレームに 2 回出るのを置き換えた形）
- FPGA の 2 つは分かれる。JTOPL は元のコードから ×2。IKAOPLL は重みを組み込む側に任せている
- **例外**は 2 つ。旧 fmopl.c（blueMSX の `Fmopl.c`）は SD だけ ×8、ほかのリズム音は ×2。blueMSX-plus_Y8960 の
  `Y8960Opl2Core.cpp` は、2026-10-17 の hra1129 さんの回答に従って 1 : 1 に戻している

- **OPL2 の 2 倍は、ダイの回路に在る。** YM3812-LLE（YM3812 のダイ写真から作った、信号の水準のエミュレータ）は、
  足し合わせの入口でリズムの 6 スロットの出力を 2 倍にしている。JTOPL の `rhy2x`（`|slot[7:2]` の 6 スロット）と同じ形。
  ダイから読んだ回路なので、理由のコメントが無いのは自然（2026-11-05、ユーザーの見方）

ここから言えるのは、エミュレータの作者たちが実チップの出力を 2 倍と見ていることまで。OPL2 は YM3812-LLE がダイの回路で
裏付けている。実チップが本当に 2 倍かは、
`level/` の道具で FM-PAC と MSX-AUDIO の実チップを測れば決まる（`implementation-plan.md` §8 の 2026-11-05 (8)）。

## 一覧

| 実装 | チップ | リズムの重み | MO / RO | SD・HH・TC の位相 | 読んだ版 |
|---|---|---|---|---|---|
| emu2413 | OPLL | 楽音を `>> 1`、リズムはそのまま（相対で ×2） | 内部で ch_out[0..8] と [9..13] に分け、出力で単純に足す | SD は自分（ch8 キャリア）の位相 bit8 と noise。HH・TC は HH と CYM の位相ビットから | v1.6.4 |
| emu8950 | Y8950 / YM3526 / YM3812 | emu2413 と同じ `_MO` / `_RO`。ADPCM はそのまま | 同上 | SD は HH の位相 bit8 と noise（実チップの方式） | v1.2.3 |
| Nuked-OPLL | OPLL | コアは ×2 を掛けない。リズムが RO に 1 フレームで複数回出る | `output_m` と `output_r` を別々に返す | SD = {hh bit8, hh bit8 ^ noise}。HH・TC は rm_bit | 1.0.2 |
| ymfm | OPL / OPL2 / Y8950 / OPL3 / OPLL | BD・HH+SD・TOM+TC に `result * 2` | OPLL は data[0] が楽音、data[1] がリズム。OPL 系は 1 本 | 実チップの方式（`phase_select`） | aaronsgiles/ymfm `81aec25` |
| DBOPL | OPL2 / OPL3 | 5 つのリズム音を足した後に `sample <<= 1` | 分けない | SD は HH の位相 bit8 と noise | DOSBox r4391 |
| Nuked-OPL2-Lite | OPL2 | スロット 13〜17 に `<< 1` | 分けない | 実チップの方式。TC は `\| 0x100` | 0.9 beta |
| Nuked-OPL3 | OPL3 | リズムの ch の `out[0]` と `out[1]` が同じスロットを指し、和が ×2 | 分けない | 実チップの方式。TC だけ `\| 0x80` | 1.8 |
| openMSX `YM2413NukeYKT` | OPLL | リズムに `2.0f * outF` / `2 * ch_out` | 内部で out[9..13] に分ける | 実チップの方式 | openMSX 上流 |
| openMSX `YM2413OriginalNukeYKT` | OPLL | RO を 1 回取って `buf[1] * 2` | `output_m` / `output_r` を振り分ける | Nuked と同じ | openMSX 上流 |
| YM3812-LLE | OPL2 | 足し合わせの入口で、リズムモードのときスロットの数え 16〜21 をシフトレジスタで遅らせた位置（後ろの 6 スロット）だけ `op_out * 2`（`fmopl2.c` の `fsm_out[11]`） | 分けない | 読んでいない | nukeykt/YM3812-LLE `a61c464` |
| openMSX `YM2413Okazaki` | OPLL | `2 *`（SD と CYM は `-2 *`） | 内部で分ける | 旧式。SD は自分の位相 bit7 と noise | 元は emu2413（2001 年版） |
| openMSX `YM2413Burczynski` | OPLL | `2 *`（コメント「output sample always is multiplied by 2」） | 内部で分ける | SD は HH の位相 bit8 と noise | ym2413.c v1.0 |
| openMSX `Y8950` | Y8950 | `2 *` | 内部で分ける | 旧式。SD は自分の位相 MSB と白色雑音の平均 | 元は emu8950（2001 年版） |
| openMSX `YMF262` | OPL3 | `2 *` | 分けない | 実チップの方式 | ymf262.c v0.2 |
| blueMSX `Fmopl.c` | OPL | BD・TOM・TC・HH は `* 2`、SD は `* 8` | 分けない | 旧式。雑音は `rand() & 1` | fmopl.c（1999〜2000 年） |
| JTOPL（FPGA） | OPL / OPL2 | `jtopl_acc.v` の `rhy2x` でリズムの 6 スロットを ×2（コメント「all rhythm channels are amplified by two」） | 分けない | 実チップの方式（`jtopl_pg_rhy.v`） | Y8960_Cartridge の `src/opl2/src`（元のコード）。`src/opl2_patch` も同じ |
| IKAOPLL（FPGA） | OPLL | 決め打ちの重みは無い。足し合わせの出力は楽音に `i_ACC_SIGNED_MOVOL`、リズムに `i_ACC_SIGNED_ROVOL` を掛ける。端子に既定値は無く、組み込む側が決める。hra1129 さんによれば IKAOPLL のマニュアルに推奨値がある（取り込まれた写しの `README.txt` には無く、マニュアルは読んでいない） | 実チップと同じ MO / RO の端子も出す | 実チップの方式 | Y8960_Cartridge の `src/ikaopll/src`（元のコード） |

## Y8960 の側との対応

- **Y8960 のハードウェア（v0.9.12）**: OPL2 は JTOPL の `jtopl_acc.v` がリズムの 6 スロットを `rhy2x` で 2 倍にする。
  OPLL は IKAOPLL の足し合わせが各スロットを 1 フレームに 1 回ずつ足し、リズムのサイクルだけ加算値を 1 ビット上げる
  （`IKAOPLL_dac.v` の `dac_acc_add_l/r`。MOVOL と ROVOL は同じ 15）。どちらも 2 倍（**確認済み(読解)**）。
  `opll.v` は最初のコミット（2026-01-18）から MOVOL 10・ROVOL 15（リズムが 1.5 倍）で、v0.9.10 の作業で MOVOL が 15 になり、
  v0.9.11 までは 1 : 1 だった
- **このフォークのエミュレーション**: OPL2 も OPLL も、ほかのエミュレータと同じく 2 倍（`implementation-plan.md` §8 の
  2026-11-05 (11)。それまでは 1 : 1 だった）。OPLL は 1 サンプルを 2 倍にする形で、v0.9.12 のハードウェアと同じ
  （`implementation-plan.md` §8 の 2026-11-05 (12)）
- **SD の作り方**: このフォークの `Y8960OPL2` は Y8950 から引き継いだ旧式（自分の位相 MSB と白色雑音）で、ハードウェアの
  JTOPL は実チップの方式（HH の位相 bit8）。openMSX で測った基本波は、振幅が半分の両極の矩形波の計算値に近かった
  （-3.99dB と -3.92dB）。ハードウェアの側はまだ測っていない。周波数の出どころが違うので、`level/rhythm.txt` は
  キャリアの MUL を変調器の 2 倍にして、両方を同じ周波数に出している

## 読んだ場所

公開のリポジトリにある写しを読んだ。同じ中身の写しは代表の 1 つだけを挙げる。

- emu2413・emu8950: DSAemuEngine の `extern/emu2413/emu2413.c`（987〜988 行、1050〜1054 行、953〜964 行）、
  `extern/emu8950/emu8950.c`（837〜838 行、808 行、958〜962 行）
- Nuked-OPLL・Nuked-OPL2-Lite・Nuked-OPL3: NukedEngine の `cores/opll/opll.c`（508〜511 行、843〜884 行、1063〜1064 行）、
  `cores/opl2/opl2.c`（911〜919 行）、`cores/opl3/opl3.c`（727〜738 行、1125 行）
- ymfm: YMEngine の `extern/ymfm/src/ymfm_fm.ipp`（1108 行、1140 行、1166 行、1135 行）、`ymfm_opl.cpp`（2045〜2050 行）
- DBOPL: DBOPLEngine の `extern/dbopl/dbopl.cpp`（823 行、835 行）
- blueMSX: blueMSX-plus_Y8960 の `blueMSX/Src/SoundChips/Fmopl.c`（505〜540 行）、`Y8960Opl2Core.cpp`（720〜722 行）
- openMSX: このリポジトリの `src/sound/`（`YM2413NukeYKT.cc` 858〜870 行、`YM2413OriginalNukeYKT.cc` 35〜42 行、
  `Y8950.cc` 877〜890 行、`YMF262.cc` 838〜867 行など）

Nuked-OPLL の MO と RO を呼ぶ側でどう混ぜるかは、呼ぶ側ごとに違う。blueMSX-plus_Y8960 の `NukedOpllBackend.cpp` は
18 サイクルをすべて足して `frameSumM + frameSumR`。NukedEngine の `NukedEngineApi.cpp` は楽音をキャリアのサイクルだけ、
リズムを全サイクルで足す。
