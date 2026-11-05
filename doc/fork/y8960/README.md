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
| `tests/opll-regs-mirror.tcl` | OPLL のレジスタの写しが BANK レジスタ (40h-48h) で壊れないことの回帰テスト |
| `tests/opll-panpot.tcl` | OPLL のチャンネルごとの定位 (50h-58h) とリズム音の定位の回帰テスト。WAV を書き出す |
| `tests/check-opll-panpot.py` | 上記 WAV の判定 |
| `tests/opl2-waveform.tcl` | OPL2 波形選択 (E0h-F5h) の回帰テスト。WAV を書き出す |
| `tests/check-opl2-waveform.py` | 上記 WAV の判定 |
| `tests/opl2-panpot.tcl` | OPL2 のチャンネルごとの定位 (F6h-FEh)、リズム音の定位と比率、ADPCM の定位 (FFh) の回帰テスト。WAV を書き出す |
| `tests/check-opl2-panpot.py` | 上記 WAV の判定 |
| `tests/ssgs-panpot.tcl` | SSGS のチャンネルごとの定位と音量、SSG 2 系統の分離の回帰テスト |
| `tests/check-ssgs-panpot.py` | 上記 WAV の判定 |
| `tests/ssgs-write-only.tcl` | SSGS がリードに反応せず、A0h と A1h にしか書き込めないことの回帰テスト |
| `tests/enabler2.tcl` | I/O Enabler2 (7FFFh) の b7 と、SSGS / OPL2 のトンネルの回帰テスト |
| `tests/enabler2-read.tcl` | I/O Enabler2 (7FFFh) が読めることの回帰テスト。CPU の読みキャッシュも見る |
| `tests/ssgs-gpio.tcl` | SSGS の GPIO のレジスタが両系統とも記憶域であることの回帰テスト |
| `tests/timer-irq.tcl` | MSX-TIMER が CPU へ割り込みを上げることの回帰テスト |
| `tests/timer-resolution.tcl` | MSX-TIMER の分解能が 42.95454MHz の分周どおりであることの回帰テスト |
| `tests/adpcm-play.tcl` | ADPCM-B の発音の回帰テスト。WAV を書き出す |
| `tests/check-adpcm-play.py` | 上記 WAV の判定。ピークと基本周波数を見る |
| `tests/adpcm-rommode.tcl` | ADPCM の ROM ビット (08h の b0) が SRAM を外すことの回帰テスト。CPU に読ませる |
| `tests/mixer-output.tcl` | Y8960 と本体の出力の切り替えの回帰テスト。WAV を書き出す |
| `tests/check-mixer-output.py` | 上記 WAV の判定 |
| `tests/mixer-volume.tcl` | ミキサーの音量レジスタ (7FF7h-7FFAh) とマスター音量 (7FFEh) の回帰テスト。WAV を書き出す |
| `tests/check-mixer-volume.py` | 上記 WAV の判定 |
| `tests/mixer-remove.tcl` | カートリッジを抜いたら本体の音が戻ることの回帰テスト。WAV を書き出す |
| `tests/check-mixer-remove.py` | 上記 WAV の判定 |
| `tests/mapper-windows.tcl` | SCC 音源レジスタの窓と MMIO 窓の出現条件の回帰テスト |
| `tests/scc-panpot.tcl` | SCC のチャンネルごとの定位 (9900h-9904h) と、その周りの番地が SCC のミラーのままであることの回帰テスト。WAV を書き出す |
| `tests/check-scc-panpot.py` | 上記 WAV と、テストが書き出すレジスタの検査の結果の判定 |
| `tests/mapper-cpu-read.tcl` | CPU の読みがデバッガの読みと一致することの回帰テスト |
| `tests/opm.tcl` | OPM の直接 I/O (7Eh/7Fh)、トンネル (7FFBh/7FFCh)、I/O Enabler2 の b2、ステータスと割り込み、ミキサーの OPM の音量 (7FFDh) の回帰テスト。WAV を書き出す |
| `tests/check-opm.py` | 上記 WAV と、テストが書き出すレジスタの検査の結果の判定 |
| `tests/opl2-read.tcl` | OPL2 のデータポート (C1h) が 0Fh 以外を FFh で読むことと、ADPCM の PCM_BSY の回帰テスト |
| `tests/timer-regs.tcl` | MSX-TIMER のレジスタ 3 と B3h の選択の回帰テスト |
| `tests/sysctrl.tcl` | System Controller (40h-42h) の識別の回帰テスト |
| `level/tones.txt` | 音源どうしの音量比を測る音列。実機と openMSX で同じものを流す |
| `level/tones.tcl` | 上記を openMSX で流して WAV に録る |
| `level/tones-mga.ps1` | 上記を実機のカートリッジで MGA から流し、オーディオインターフェースで録る |
| `level/tone-levels.py` | 2 つの録音を区間ごとに比べ、`<volume>` の案を出す。区間どうしの差も出す |
| `level/rhythm.txt` | OPL2 のリズム音（BD・SD・TOM）と、同じ音色の楽音の大きさを比べる音列 |
| `level/adpcm-tones.py` | ADPCM の正弦波と矩形波を、SSG2・OPL2・OPM の 1ch と比べる音列を書き出す |
| `level/pan9.txt` | OPL2 の F6h-FEh がどの ch に掛かるかを見る音列 |
| `level/pan9-levels.py` | 上記の録音から、区間ごとに左に寄った ch が仕様どおりかを判定する |

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

# 1a. OPLL のレジスタの写し。判定は最終行の RESULT を見る
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/opll-regs-mirror.tcl"
tail -1 "$OUT/opll-regs-mirror.txt"

# 1b. OPLL の定位。判定は終了コードで分かる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/opll-panpot.tcl"
py $T/check-opll-panpot.py "$OUT"

# 2. OPL2 の波形選択。判定は終了コードで分かる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/opl2-waveform.tcl"
py $T/check-opl2-waveform.py "$OUT"

# 2a. OPL2 と ADPCM の定位、リズム音の比率。判定は終了コードで分かる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/opl2-panpot.tcl"
py $T/check-opl2-panpot.py "$OUT"

# 3. SSGS の定位と音量、SSG 2 系統の分離
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/ssgs-panpot.tcl"
py $T/check-ssgs-panpot.py "$OUT"

# 4. SSGS がリードに反応しないこと。$OUT/wo.txt を目で見る
Y8960_TEST_OUT="$OUT/wo.txt" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/ssgs-write-only.tcl"

# 5. MSX-TIMER。分解能の方は最終行の RESULT を見る。割り込みは目で見る
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/timer-resolution.tcl"
tail -1 "$OUT/timer-resolution.txt"

Y8960_TEST_OUT="$OUT/irq.txt" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/timer-irq.tcl"

# 6. ADPCM-B の発音。判定は終了コードで分かる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/adpcm-play.tcl"
py $T/check-adpcm-play.py "$OUT"

# 6a. ADPCM の ROM ビット。判定は最終行の RESULT を見る
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/adpcm-rommode.tcl"
tail -1 "$OUT/adpcm-rommode.txt"

# 7. ミキサー。判定は終了コードで分かる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/mixer-output.tcl"
py $T/check-mixer-output.py "$OUT"
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/mixer-volume.tcl"
py $T/check-mixer-volume.py "$OUT"
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/mixer-remove.tcl"
py $T/check-mixer-remove.py "$OUT"

# 8. バンクメモリ。判定は出力ファイルの最終行の RESULT を見る
#    （openmsx は Tcl の exit の値を終了コードにしない）
for t in mapper-windows mapper-cpu-read; do
    Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960         -script "$(pwd)/$T/$t.tcl"
    tail -1 "$OUT/$t.txt"
done

# 9. I/O Enabler2 の b7 とトンネル。$OUT/en2.txt を目で見る
Y8960_TEST_OUT="$OUT/en2.txt" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/enabler2.tcl"

# 9a. I/O Enabler2 の読み出し。判定は最終行の RESULT を見る
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/enabler2-read.tcl"
tail -1 "$OUT/enabler2-read.txt"

# 10. SSGS の GPIO のレジスタ。$OUT/gpio.txt を目で見る
Y8960_TEST_OUT="$OUT/gpio.txt" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/ssgs-gpio.tcl"

# 11. SCC の定位。判定は終了コードで分かる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/scc-panpot.tcl"
py $T/check-scc-panpot.py "$OUT"

# 12. OPM。判定は終了コードで分かる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960     -script "$(pwd)/$T/opm.tcl"
py $T/check-opm.py "$OUT"

# 13. OPL2 のデータポートと PCM_BSY、MSX-TIMER のレジスタ、System Controller。
#     判定は最終行の RESULT を見る
for t in opl2-read timer-regs sysctrl; do
    Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960         -script "$(pwd)/$T/$t.tcl"
    tail -1 "$OUT/$t.txt"
done
```

既存機種を壊していないことの確認も併せて行う。終了コード 0 が期待値。

```sh
for e in audio audio2 Panasonic_FS-CA1 2nd_PSG; do
    $EXE -testconfig -machine C-BIOS_MSX2+ -ext "$e"; echo "$e: $?"
done
```

**どのテストも、判別力があることを確かめてある。** 期待値どおりに通ることは、
期待値を外した構成で落ちることを示すまで証拠にならない。テストを足すときも同じ
確認をすること。既に踏んである確かめ方は次のとおり。

- 判定スクリプトのある 2 本は、入力を差し替える（`ws2.wav` を `ws0.wav` で
  置き換えると NG になる）
- `enabler2.tcl` は、閉じている間に値が変わらないことを見る手順に判別力がある
  （テスト冒頭の注記）。`ssgs-gpio.tcl` は、GPIO の書き込みを捨てていた頃の
  コードで 0xFF が返ることを確かめてある
- `enabler2-read.tcl` は、読み出しを入れる前のビルドで落ちることと、CPU の読みの項目が
  `getReadCacheLine()` の分岐を外したビルドで落ちることを確かめてある
- `mapper-cpu-read.tcl` は、キャッシュ無効化の順序を元に戻してビルドし直して
  回した。4 件中 2 件（CPU 側の読み）が落ちる
- `scc-panpot.tcl` は、番地の解き方を 4 つの窓に広げた版で、ミラー・読み出し・他の窓の
  項目が落ちる。RAM モードで定位を捨てる版（今の RTL の形）と、窓が閉じていても定位に書く版を
  合わせると 3 件が落ちる。値 0 を中央に戻すと zero の WAV が落ちる（`opll-panpot.tcl` の
  zero も同じ）
- `opm.tcl` は、XML の結線を外した版（ROM の `<opm>`、ミキサーのチャンネル）、OPM をミキサーの別の
  チャンネルに繋いだ版、Enabler2 のビットを取り違えたビルド、7Eh の読み出しに応じて閉じたポートへの
  書き込みを通すビルドで、それぞれ狙った項目が落ちる。left_only だけは壊した版で確かめていない
  （上流の `YM2151` がステレオであることの番人）
- `mapper-windows.tcl` は、マッパーを変更前のコードに戻してビルドし直して
  回した。13 件中 6 件が落ちる。残る 7 件のうち 2 件は変更前でも通る
  （バンク0 の SCC 窓は変更前には存在せず、範囲外アクセスは Release ビルドに
  assert が無いので黙って通る）。この 2 件は将来の回帰を捕まえるための番人で、
  この変更の証拠にはならない。後から足した #32 以上のバンク値の 8 件は、修正前の
  コードで 6 件が落ち、終了時にセグメンテーション違反で落ちる。残る 2 件
  （30h で MMIO が消える、BFh が SCC になる）は修正前でも通る番人。
  互換モードの RAM バンクの 4 件は、互換モードで ROM を見せていたコードで 3 件が落ちる。
  「MMIO が出る」は修正前でも通る番人
- `mapper-cpu-read.tcl` の互換モードの 2 件は、互換モードで ROM を見せていたコードで落ちる
- `adpcm-rommode.tcl`、`opl2-read.tcl`、`timer-regs.tcl`、`sysctrl.tcl` は、変更前のビルドと変更前の
  `HRA_Y8960.xml` の組み合わせで、それぞれ 2 件、6 件、5 件、3 件が落ちる。残りは変更前でも通る番人。
  `timer-regs.tcl` の「リセット直後の選択はコア 0」は、変更前は初期化されていない値を読むので、
  たまたま通ることがある。`ssgs-write-only.tcl` の 5 番は、変更前のビルドでは A1h の値が reg10 に入る
- `timer-resolution.tcl` は、クロックが 85.9MHz のままのビルドで 13 件中 11 件が落ちる。残る 2 件
  （期待値の後でフラグが 1）は速すぎても通る番人

## 音源どうしの音量比を実機に合わせる

`share/extensions/HRA_Y8960.xml` の `<volume>` 5 本（SSGS、OPLL、OPL2、OPM、SCC）を、実機で測った比に合わせるための
道具が `level/` にある。ハードウェアの版が上がって音量が変わったら測り直す。回帰テストではない。

`level/tones.txt` の音列は、5 音源の 1ch ずつを約 1kHz・最大の音量で、定位を中央と左端にして鳴らす。
同じ音列を openMSX と実機で流し、区間ごとの基本波の振幅を比べる。

```sh
# openMSX の側。$OUT/tones-openmsx.wav ができる
Y8960_TEST_OUT="$OUT" $EXE -machine C-BIOS_MSX2+ -ext HRA_Y8960 -script "$(pwd)/doc/fork/y8960/level/tones.tcl"

# 実機の側（Windows の PowerShell）。カートリッジを MGA に挿し、音声出力をオーディオインターフェースにつなぐ。
# 録音デバイスの番号を -ListDevices で見てから流す。$OUT/tones-mga.wav ができる
powershell -ExecutionPolicy Bypass -File doc/fork/y8960/level/tones-mga.ps1 -ListDevices
powershell -ExecutionPolicy Bypass -File doc/fork/y8960/level/tones-mga.ps1 -Port COMn -Device <番号> -OutDir <OUT>

# 比べる。区間ごとの値、定位の掛け方の比較、<volume> の案が出る
py doc/fork/y8960/level/tone-levels.py "$OUT/tones-openmsx.wav" "$OUT/tones-mga.wav"
```

- `tones-mga.ps1` は、送る前に音列の全体を検査し、音源のレジスタへの書き込みしか通さない。System Controller には
  触れないので Flash は変わらない。ポートは MGA の USB の ID を確かめてから開く。実機に送るので、走らせる前に
  ユーザーに一声かける
- `tones.tcl` は書き込みごとに 1ms 進める。同じ時刻に続けて書くと、NukeYKT の OPLL が番地の書き込みを捨てて鳴らない。
  `tone-levels.py` は区間の数が mark の数と合わないと止まるので、鳴らない音源があれば気づく
- `tone-levels.py` の案の 3 列は全体の大きさの揃え方の違いで、比は同じ。今の値は「最大を 30000」で揃えた。
  実機は本体の音とはミックスされないので、本体内蔵の音源と大きさを合わせる必要は無い

ほかの音列も、`tones.tcl` には環境変数 `Y8960_TONES`、`tones-mga.ps1` には `-Sequence` で渡して同じように流す。
録音の名前は音列によらず `tones-openmsx.wav` / `tones-mga.wav` なので、音列ごとに出力先を分ける。
解析は Python 3 と numpy が要る。

```sh
# OPL2 のリズム音。リズム音と同じ音色の楽音との差が、openMSX と実機で並ぶ
py doc/fork/y8960/level/tone-levels.py --seq doc/fork/y8960/level/rhythm.txt \
    --rel bd=ch7-melody --rel sd=ch8-melody --rel tom=ch9-melody --ref opl2-ch1 \
    "$OUT/rhythm/tones-openmsx.wav" "$OUT/rhythm/tones-mga.wav"

# ADPCM。音列は 2 万行を超えるので、測るたびに書き出す
py doc/fork/y8960/level/adpcm-tones.py "$OUT/adpcm.txt"
py doc/fork/y8960/level/tone-levels.py --seq "$OUT/adpcm.txt" --ref opl2-center \
    "$OUT/adpcm/tones-openmsx.wav" "$OUT/adpcm/tones-mga.wav"

# OPL2 の定位。録音ごとに判定し、仕様と違う区間があれば終了コード 1
py doc/fork/y8960/level/pan9-levels.py "$OUT/pan9/tones-openmsx.wav" "$OUT/pan9/tones-mga.wav"
```

- `rhythm.txt` の SD は正弦波ではないので、基本波を比べる。ハードウェア（JTOPL）は ch8 の変調器の位相の bit8 から、
  エミュレーションは ch8 のキャリアの位相から作る。キャリアの MUL を変調器の 2 倍にして、両方を同じ周波数に出している。
  HH と TC は正弦波の成分が無く、両者で作り方も違うので、参考に鳴らすだけ
- `adpcm-tones.py` は、復号器の式（Y8950 の ADPCM。ハードウェアは jt10_adpcmb）で 1 サンプルずつ符号を選ぶ。
  ADPCM のメモリへの書き込みは 1 バイトにつき 1 回なので、MGA では転送に時間がかかる
- 音列の環境変数 `Y8960_TONES` と `-Sequence` で別の音列を流せる。測りたいものに合わせて音列を足すときは、
  `tones-mga.ps1` が通す番地とポートの範囲に収める

## 取り込み元

Y8960 の実装本体は buppu3/openMSX の `y8960` ブランチ由来で、
そのうち Y8960 分の 15 コミットを cherry-pick したもの（GPL、著者情報は保持）。
履歴に残っているのは 14 件で、1 件は取り消した変更だったので追従のときに空になった。
経緯は `implementation-plan.md` §3.0。

一次仕様である hra1129/Y8960_Cartridge からは**何も取り込んでいない**。
`hardware-notes.md` は RTL と仕様書を読解した結果の記述であって、複製ではない。
理由はルートの `CLAUDE.md` §1。
