# Y8960 エミュレーション実装 — 文書の役割

Y8960 カートリッジのエミュレーションを openMSX に追加する作業のための文書。
Y8960 対応は upstream には存在しない独自機能である。

実装状況の一覧と外部リポジトリとの関係は `doc/fork/README.md`、
作業時の規則はルートの `CLAUDE.md` にある。

## 文書一覧

| 文書 | 役割 |
|---|---|
| `README.md` (本書) | 文書の役割の記録・索引 |
| `hardware-notes.md` | Y8960 ハードウェア仕様の調査結果。一次情報の出典と確度つき |
| `implementation-plan.md` | 実装計画・決定事項・実行経緯 |
| `tests/opll-enabler.tcl` | OPLL I/O Enabler (7FF6h) の回帰テスト |
| `tests/opl2-waveform.tcl` | OPL2 波形選択 (E0h-F5h) の回帰テスト。WAV を書き出す |
| `tests/check-opl2-waveform.py` | 上記 WAV の判定 |
| `tests/ssgs-panpot.tcl` | SSGS のパンポットと SSG 2 系統の分離の回帰テスト |
| `tests/check-ssgs-panpot.py` | 上記 WAV の判定 |
| `tests/ssgs-write-only.tcl` | SSGS がリードに反応しないことの回帰テスト |
| `tests/enabler2.tcl` | I/O Enabler2 (7FFFh) の b2/b3/b7 と、SSGS / DCSG / OPL2 のトンネルの回帰テスト |
| `tests/ssgs-gpio.tcl` | 本体内蔵版 SSGS の GPIO の回帰テスト |
| `tests/timer-irq.tcl` | MSX-TIMER が CPU へ割り込みを上げることの回帰テスト |
| `tests/adpcm-play.tcl` | ADPCM-B の発音の回帰テスト。WAV を書き出す |
| `tests/check-adpcm-play.py` | 上記 WAV の判定。ピークと基本周波数を見る |
| `tests/mixer-output.tcl` | Y8960 と本体の出力の切り替えの回帰テスト。WAV を書き出す |
| `tests/check-mixer-output.py` | 上記 WAV の判定 |
| `tests/mixer-passthrough.tcl` | B6h-B7h がゲインに繋がっていないことの回帰テスト。WAV を書き出す |
| `tests/check-mixer-passthrough.py` | 上記 WAV の判定 |
| `tests/mapper-windows.tcl` | SCC 音源レジスタの窓と MMIO 窓の出現条件の回帰テスト |
| `tests/mapper-cpu-read.tcl` | CPU の読みがデバッガの読みと一致することの回帰テスト |
| `tests/make-builtin-config.py` | カートリッジ版の拡張 XML から本体内蔵版の構成を組み立てる |

`implementation-plan.md` が作業計画と経緯を記録する文書である。
セッションをまたぐ引き継ぎ情報・見送った判断・訂正はすべてここに書く。

## テストの回し方

すべて手で回す。ビルド手順は `doc/fork/build/README.md`。
`openmsx.exe` はコンソールに何も出さないので、結果はファイルに出る。

```sh
EXE=./derived/x64-VC-Release/install/openmsx.exe
export OPENMSX_SYSTEM_DATA="$(pwd)/share"
export OPENMSX_USER_DATA="$(pwd)/derived/openmsx-user"
T=doc/fork/y8960/tests
OUT=/tmp/y8960   # 任意の出力先
mkdir -p "$OUT"

# 1. OPLL の I/O Enabler (7FF6h)。$OUT/opll.txt を目で見る
Y8960_TEST_OUT="$OUT/opll.txt" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/opll-enabler.tcl"

# 2. OPL2 の波形選択。判定は終了コードで分かる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/opl2-waveform.tcl"
py $T/check-opl2-waveform.py "$OUT"

# 3. SSGS のパンポットと SSG 2 系統の分離
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/ssgs-panpot.tcl"
py $T/check-ssgs-panpot.py "$OUT"

# 4. SSGS がリードに反応しないこと。$OUT/wo.txt を目で見る
Y8960_TEST_OUT="$OUT/wo.txt" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/ssgs-write-only.tcl"

# 5. MSX-TIMER の割り込み。$OUT/irq.txt を目で見る
Y8960_TEST_OUT="$OUT/irq.txt" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/timer-irq.tcl"

# 6. ADPCM-B の発音。判定は終了コードで分かる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/adpcm-play.tcl"
py $T/check-adpcm-play.py "$OUT"

# 7. ミキサー。判定は終了コードで分かる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/mixer-output.tcl"
py $T/check-mixer-output.py "$OUT"
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/mixer-passthrough.tcl"
py $T/check-mixer-passthrough.py "$OUT"

# 8. バンクメモリ。判定は出力ファイルの最終行の RESULT を見る
#    （openmsx は Tcl の exit の値を終了コードにしない）
for t in mapper-windows mapper-cpu-read; do
    Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960         -script "$(pwd)/$T/$t.tcl"
    tail -1 "$OUT/$t.txt"
done

# 9. I/O Enabler2 の b2/b3/b7 とトンネル。$OUT/en2.txt を目で見る
Y8960_TEST_OUT="$OUT/en2.txt" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/enabler2.tcl"
```

本体内蔵版のぶんは、構成を組み立ててから回す。

```sh
BI=/tmp/y8960-builtin   # 任意
mkdir -p "$BI/machines"; cp Contrib/cbios/* "$BI/machines/"
py $T/make-builtin-config.py "$BI"

# 10. SSGS の GPIO。$OUT/gpio.txt を目で見る
Y8960_TEST_OUT="$OUT/gpio.txt" OPENMSX_USER_DATA="$BI"     $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script "$(pwd)/$T/ssgs-gpio.tcl"

# 11. 同じ構成で enabler2.tcl を回すと、イネーブラーとトンネルが両方無いことが出る
Y8960_TEST_OUT="$OUT/en2-bi.txt" OPENMSX_USER_DATA="$BI"     $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script "$(pwd)/$T/enabler2.tcl"
```

既存機種を壊していないことの確認も併せて行う。終了コード 0 が期待値。

```sh
for e in audio audio2 Panasonic_FS-CA1 2nd_PSG; do
    $EXE -testconfig -machine C-BIOS_MSX2+ -ext "$e"; echo "$e: $?"
done
```

**どのテストも、判別力があることを確かめてある。** 期待値どおりに通ることは、
期待値を外した構成で落ちることを示すまで証拠にならない。テストを足すときも同じ
確認をすること。既に踏んである確かめ方は次の 2 つ。

- 判定スクリプトのある 2 本は、入力を差し替える（`ws2.wav` を `ws0.wav` で
  置き換えると NG になる）
- `enabler2.tcl` と `ssgs-gpio.tcl` は、**もう一方の版の構成**で回す。
  期待値は当然外れ、**どの手順が動くかで切り替えが効いていることが分かる**。
  構成は `make-builtin-config.py` が別の `OPENMSX_USER_DATA` に書き出すので、
  作業ツリーの `share/` は触らずに済む
- `mapper-cpu-read.tcl` は、キャッシュ無効化の順序を元に戻してビルドし直して
  回した。4 件中 2 件（CPU 側の読み）が落ちる
- `mapper-windows.tcl` は、マッパーを変更前のコードに戻してビルドし直して
  回した。13 件中 6 件が落ちる。残る 7 件のうち 2 件は変更前でも通る
  （バンク0 の SCC 窓は変更前には存在せず、範囲外アクセスは Release ビルドに
  assert が無いので黙って通る）。この 2 件は将来の回帰を捕まえるための番人で、
  この変更の証拠にはならない

## 取り込み元

Y8960 の実装本体は buppu3/openMSX の `y8960` ブランチ由来で、
そのうち Y8960 分の 15 コミットを cherry-pick したもの（GPL、著者情報は保持）。
経緯は `implementation-plan.md` §3.0。

一次仕様である hra1129/Y8960_Cartridge からは**何も取り込んでいない**。
`hardware-notes.md` は RTL と仕様書を読解した結果の記述であって、複製ではない。
理由はルートの `CLAUDE.md` §1。
