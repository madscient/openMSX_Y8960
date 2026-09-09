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
| `tests/enabler2.tcl` | I/O Enabler2 (7FFFh) の b2/b3/b7 と、SSGS / DCSG のトンネルの回帰テスト |

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

# 5. I/O Enabler2 の b2/b3/b7 とトンネル。$OUT/en2.txt を目で見る
Y8960_TEST_OUT="$OUT/en2.txt" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/enabler2.tcl"
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
- `enabler2.tcl` は、ゲートと結線を外した XML を別の `OPENMSX_USER_DATA` の
  `extensions/` に置いて回す。作業ツリーの `share/` を触らずに済む

## 取り込み元

Y8960 の実装本体は buppu3/openMSX の `y8960` ブランチ由来で、
そのうち Y8960 分の 15 コミットを cherry-pick したもの（GPL、著者情報は保持）。
経緯は `implementation-plan.md` §3.0。

一次仕様である hra1129/Y8960_Cartridge からは**何も取り込んでいない**。
`hardware-notes.md` は RTL と仕様書を読解した結果の記述であって、複製ではない。
理由はルートの `CLAUDE.md` §1。
