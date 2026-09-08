# Y8960 エミュレーション 実装計画

作成: 2026-09-08 / 最終更新: 2026-09-09
状態: **全ブロック実装済み（OPL2EX + ADPCM-B まで完了）。
残るのは I/O アドレスの確認、上流追従、仕上げ**

ハードウェア仕様の調査結果は `hardware-notes.md`。本書はそれを前提に、
openMSX 側をどう作るかを決める文書である。決定・却下・経緯はすべてここに追記する。

---

## 1. 目的とスコープ

Y8960 カートリッジ（hra1129/Y8960_Cartridge）を openMSX の拡張機器として
エミュレートする。

**2026-09-08 に土台が変わった。** buppu3/openMSX の `y8960` ブランチに
既存実装があることが分かったため、一から作るのをやめてそれを土台にする
（経緯は §8、既存実装の内容は §3）。

**2026-09-09 に OPL2EX + ADPCM-B を実装し、全ブロックが揃った**（§3.4）。

**残っている作業**。

1. **I/O アドレスの突き合わせ** — 一次情報が食い違う（§4.3）。hra1129 さんへの確認が要る
2. **上流追従** — 載せ替えの起点は 2026-09-08 時点の openMSX/master
3. **仕上げ** — ADPCM の再生確認、Y8960emu との突き合わせ、7FFFh の残りビット

### スコープ外

- FPGA コンフィグ・SPI Flash・SRAM 初期化シーケンス（`system_controller`）。
  実機の起動手順であって、エミュレータでは SRAM を初期化済みで持てばよい
- ADPCM メモリ 128KB×2 / 256KB×1 の切替（実機にレジスタが無い）

### V9968 は取り込まない（2026-09-08 決定）

`buppu3/y8960` には V9968 VDP の実装（`src/video` に約 6500 行）も乗っているが、
**取り込まない**。よってブランチをそのまま使わず、Y8960 分の 15 コミットだけを
最新の openMSX master に cherry-pick した（§3.0）。

## 2. 前提

以下が変わったら計画を見直す。

- **Y8960 は WIP であり、仕様は動く**。実機も BIOS ROM も存在しない。
  したがって「実機と同じ音」は検証できない。目標は「仕様書と RTL の
  読解結果に一致すること」までである
- 一次情報の優先順位は RTL > xlsx > docx。ただし**既存実装は 2026-01 時点の
  仕様に基づいており、RTL はその後 2026-03 まで動いている**（§4.3）
- `origin` は openMSX/openMSX のまま。buppu3 は 2 つ目の remote として追加済み

## 3. 土台: buppu3 の Y8960 実装を最新 master に載せ替えたもの

### 3.0 ブランチの作り方

`buppu3/y8960` は openMSX/master に対して 61 ahead / 417 behind。
前半 46 コミットが V9968 VDP、後半 **15 コミット**が Y8960
（`fd90ed560..91bd0e7ad`、`git log buppu3/v9968..buppu3/y8960` で取れる）。

V9968 は取り込まないので、**この 15 コミットだけを最新 master に cherry-pick** した。
載せ替え先のローカルブランチは `main`。`origin` は openMSX/openMSX のまま、
`buppu3` は 2 つ目の remote として残してある。

- cherry-pick で著者情報（buppu3）は保持される
- 競合は `src/memory/RomFactory.cc` と `RomInfo.cc` の 2 か所だけ。
  どちらも「上流が足した行を残しつつ Y8960 の行を足す」で解消した
- 載せ替え後の `git diff master..y8960` が buppu3 側の Y8960 差分と
  **完全に一致**することを確認（29 ファイル / +2915 / -22）

再現するなら:

```sh
git checkout -b main master
git cherry-pick fd90ed560..91bd0e7ad
```

### 3.0.1 載せ替えで必要になった修正

`YM2413NukeYKTBanked.cc` が `#include "YM2413NukeYktTables.ii"` していたが、
このファイルは上流の `e06d8d571 YM2413NukeYKT: compute tables via constexpr` で
削除されている。`YM2413NukeYKTBanked` はそれ以前の `YM2413NukeYKT` の fork なので
取り残された。

対処: 上流の `YM2413NukeYKT.cc` にある constexpr のテーブル生成ブロックを
そのまま移植し、旧名 `releaseIndex` / `releaseData` を上流の
`release.index` / `release.data` に合わせた。**確認済み**（ビルドが通った）。
音が同じかどうかは**未検証**。

### 3.1 既存実装（すべて確認済み: 当該ファイルを読んだ）

| ファイル | 規模 | 内容 |
|---|---|---|
| `src/memory/RomY8960.{cc,hh}` | 303+50 | SCC + 16 ROM/16 RAM バンクのマッパー。RamEnable (4?FBh)、両モードのバンクレジスタ、7FF2h/7FF4h から OPLL への I/O トンネル |
| `src/sound/YM2413NukeYKTBanked.{cc,hh}` | 1079+291 | チャンネル別音色バンク付き YM2413 = OPLLEX |
| `src/sound/Y8960OPLL.{cc,hh}` | 39+28 | 上記コアを I/O ポートに載せる薄い `MSXDevice` |
| `src/sound/Y8960Mixer.{cc,hh}` | 153+50 | チャンネルごとのゲイン/バランス。デバイス id 参照で結線 |
| `src/sound/MSXTimer.{cc,hh}` | 517+111 | 4 本のカウンタ。`Schedulable` / `DynamicClock` / `IRQHelper` |
| `share/extensions/HRA_Y8960.xml` | 87 | 拡張定義 |
| `src/sound/MSXPSG.{cc,hh}` ほか | 小 | PSG の `chip_select`、SN76489 の表示名修正、`MSXMixer` 拡張 |

**入っていないのは OPL2EX と ADPCM だけ**（確認済み: 差分ファイル一覧に
OPL2 関連が無く、`HRA_Y8960.xml` で該当ミキサーチャンネルが
`<!-- channel num="2" idref="Y8960 OPL2 0"/ -->` とコメントアウトされている）。

### 3.2 設計方針は「XML で分割」

既存実装は、ブロックごとに別の `MSXDevice` を作り XML で組む方式である。
ブロック間の結線は **id 参照**で行う。

- `RomY8960` の `<opll0>Y8960 OPLL 0</opll0>` → `findDevice()` で解決し、
  7FF4h/7FF2h への書き込みを OPLL デバイスへ中継する
- `Y8960Mixer` の `<channel num="0" idref="Y8960 OPLL 0"/>` → 各チャンネルの
  ゲインを対象デバイスに適用する

**当初計画の「単一 `Y8960` デバイスにする」案は撤回する**（§7）。
既存の `PSG` / `SNPSG` / `Rom8kBBlocks` / `SCC` をそのまま再利用でき、
openMSX の作法にも合っているため、分割方式のほうが良い。

**前提**: id 参照による結線が、追加する OPL2EX にもそのまま使えること。
`Y8960Mixer` の `ChannelCount = 10` に OPL2 用の枠 (num=2,3) と
ADPCM 用の枠 (num=8) が既に確保されているので、成立する見込み（**未検証**）。

### 3.2.1 I/O 割り当て（実測）

`-ext HRA_Y8960` を C-BIOS MSX2+ に挿して `iomap` を取った結果（**確認済み**）。

```
port 3E:      O Y8960 DCSG 0
port 3F:      O Y8960 DCSG 1
port 40-41: I/O y8960-mixer
port 7A-7B:   O Y8960 OPLL 1
port 7C-7D:   O C-BIOS MSX-MUSIC, Y8960 OPLL 0
port A0-A3: I/O PSG, Y8960 SSG
port B0-B3: I/O y8960-timer
port C0-C1: I/O Y8960 OPL2 0
port C2-C3: I/O Y8960 OPL2 1
```

- 7Ch が本体 MSX-MUSIC と重なって見えるが、**問題にならない**。
  OPLL にはリードアクセスが無いので、衝突しても両方から音が出るだけである。
  さらに I/O enabler の実装後（§3.3）はリセット直後 7Ch が閉じているので、
  ソフトが明示的に開くまで重ならない。
  切り分けたいときは、本体側の MSX-MUSIC を外した機種でテストするのが早い
- A0-A3 の重なりも**設計どおり**。SSGS は 1 デバイスで、系統は
  レジスタポインタの bit5 で振り分けられる（§3.6）

### 3.3 I/O enabler — OPLL 分だけ実装済み

buppu3 の実装には I/O 有効化ラッチが入っていなかった。
**2026-09-09 に OPLL 分（7FF6h）だけを実装した。**

| 7FF6h のビット | 開くポート | デバイス |
|---|---|---|
| b0 | 7Ch-7Dh | `Y8960 OPLL 0` |
| b1 | 7Ah-7Bh | `Y8960 OPLL 1` |

**リセット直後は両方とも閉じている。** これは FM-PAC の動作
（`MSXFmPac.cc` の `reset()` で `enable = 0`、`writeIO` は `enable & 1` の
ときだけ通す）に合わせたもので、マニュアル §3.1 の
「起動直後・リセット直後は無効」とも一致する。
**RTL は 7Ah 側をリセット時に有効にしているが、これは取り違えとして採らない**
（`hardware-notes.md` §6.1、2026-09-09 のユーザー判断）。

**メモリマップド I/O（7FF4h/7FF5h と 7FF2h/7FF3h のトンネル）は
enabler の影響を受けない。** そうでないと I/O を開く手段が無くなる。
実装上は `Y8960OPLL::writeIO()`（直接 I/O、ゲートあり）と
`Y8960OPLL::writePort()`（トンネル、ゲート無し）に分けてある。

ポートの登録自体は XML のまま静的に行い、`writeIO()` の中で弾いている。
OPLL はリードアクセスが無いので、書き込みを落とせば挙動は実機と等価になる。
`iomap` の表示上はポートが埋まって見えるが、実害は無い。

回帰テストは `doc/fork/y8960/tests/opll-enabler.tcl`。

### 3.3.1 7FFFh（I/O Enabler2）— OPL2 分だけ実装済み

| 7FFFh のビット | 開くポート | デバイス | 状態 |
|---|---|---|---|
| b0 | C0h-C1h | `Y8960 OPL2 0` | 実装済み |
| b1 | C2h-C3h | `Y8960 OPL2 1` | 実装済み |
| b2 / b3 | DCSG | — | 未実装（常時開） |
| b4 | A0h-A2h | `Y8960 SSG` | 実装済み |
| b7 | MSX-TIMER | — | 未実装（常時開） |

OPLL (7FF6h) と違い、**こちらはビットの割り当てが RTL と一致している**
（b0 が 1 番目の回路 = C0h 側）。リセット直後は両方とも閉じており、
これも RTL と一致する（**確認済み**: `y8960_address_decode.v:209-210, 223-224`）。

OPL2 はリードアクセスがあるので、`writeIO()` だけでなく `readIO()` /
`peekIO()` も閉じているときは 0xFF を返す。OPLL とはここが違う。

### 3.4 OPL2EX の作り方【実装済み 2026-09-09】

OPL2EX = YM3812 + ADPCM-B。openMSX の `Y8950` は OPL(OPL1) + ADPCM-B で、
**レジスタ配置・タイマー・ステータス・IRQ がそのまま使える**。
差分は OPL2 の波形選択だけなので、`Y8950` をフォークして
`src/sound/Y8960OPL2.{cc,hh}` を作った。

**落としたもの**: キーボードコネクタ、13bit DAC、`Y8950Periphery`、
およびそれらを駆動するレジスタ（05h, 06h, 0Dh, 0Eh, 15h-17h, 18h, 19h, 1Ah、
07h の b3）。Y8960 のレジスタ表はこれらを全部「廃止」としており、
対応するハードウェアも無い（**確認済み**: `doc/spec` の `OPL2+ADPCM` シート）。

**波形選択**: `sinTable`（dB スケール、正値 [0,DB_MUTE)、
負値 [2*DB_MUTE,3*DB_MUTE) の表現）から 4 面のテーブルを作り、
`Slot` に `wave`（選択値）と `waveTable`（実際に使う面へのポインタ）を持たせた。
無音は DB_MUTE-1 で表す。E0h-F5h がスロットごとに選び、
TEST レジスタ 01h の b5 が全体のゲートになる（クリアなら全スロットが素のサイン）。
リズム用スロットは `Y8950` と同様にサインを直接使う。

**ADPCM は共有した。** `Y8950Adpcm` が `Y8950` に求めるのは
`setStatus` / `resetStatus` / `peekRawStatus` の 3 つとステータスビットだけだったので、
これを `Y8950Status` インターフェースとして `Y8950Adpcm.hh` に切り出し、
`Y8950` と `Y8960OPL2` の双方が実装する形にした。
570 行の ADPCM 実装を二重に持たずに済んでいる。

**代案として YMF262 を OPL2 モードで使う案は却下**（§7）。
**ADPCM も丸ごとフォークする案も却下**（§7）。

### 3.5 OPLLEX は既存実装を使う（作らない）

`YM2413NukeYKTBanked` が既にある。設計を確認した（**確認済み**）:

- `YM2413Core` インターフェースは**変更していない**。`peekRegs()` は
  `std::span<const uint8_t, 64>` のまま
- 4 バンク分の音色を 1 本の配列 `patches[1 + 15*4]` に畳み、
  `inst[ch]` 側でバンクを織り込んで選ぶ
- `<ym2413-core>NukeYKT-Banked</ym2413-core>` で選択する

当初計画では `YM2413Okazaki` をフォークして 4 面の音色テーブルを持たせ、
`YM2413Core` を継承しない独立型にするつもりだった。既存実装のほうが
インターフェースを壊さず、既存の 4 コアと同列に並ぶので優れている。
**当初案は撤回**（§7）。

### 3.6 SSGS【実装済み 2026-09-09】

`src/sound/Y8960SSG.{cc,hh}` と `src/sound/Y8960SsgCore.{cc,hh}`。
レジスタ配置は `hardware-notes.md` の SSG 節にある。

**1 つのステレオ `SoundDevice`（6 チャンネル）にした。**
パンポットがチャンネルごとなのに対し、openMSX の `MSXMixer` は
**デバイス単位の balance しか持たない**（**確認済み**: `MSXMixer.hh` の
`ChannelSettings` は `record` と `mute` だけ）。したがって `PSG` を 2 個並べて
ミキサー設定を動かす方式では 6ch 独立パンポットを表現できない。

`Y8960SsgCore` は `AY8910` のフォークで、`SoundDevice` ではない。
落としたのは periphery（YMZ 系に I/O ポートは無いのでレジスタ 14/15 も無い）、
Debuggable（`Y8960SSG` が $00-$3F 全体で持つ）、`type` による AY/YM 判定
（YM2149 固定）。vibrato/detune の設定は残してある。

パンポットの分配則はデータシートに無いため、EPSGemuEngine と同じく
YMZ280B の則を採った。またコアの出力が片極性なので、**パン適用前に
無音時レベルを差し引いている**。省くと直流が定位に漏れる。

回帰テストは `tests/ssgs-panpot.tcl`。

**未解決**: リセット直後に SSG の I/O を開くかどうか。ここでは他のブロックと
揃えて**閉じた状態**にし、7FFFh の b4 で開く形にした。マニュアル §3.1 とも一致する。
一方 RTL は `ff_ssg_io_en = 1` で開いている。実機では SSG 系統 0 が本体 PSG と
同じレジスタ空間に重なって発音する設計なので、開いていることに意味がある。
どちらが正か hra1129 さんへの確認事項。変更は `Y8960SSGDevice::reset()` の 1 行。

## 4. 外に出る値

### 4.1 既存実装が既に決めている値（追従する）

変更すると既存の拡張定義とセーブステートに波及するため、そのまま使う。

| 項目 | 値 |
|---|---|
| 拡張 XML | `share/extensions/HRA_Y8960.xml` |
| デバイス型名 | `MSX-TIMER` / `Y8960-OPLL` / `Y8960-MIXER`、マッパー種別 `Y8960` |
| サウンドデバイス名 | `Y8960 SSG 0/1`、`Y8960 DCSG 0/1`、`Y8960 OPLL 0/1`、`Y8960 SCC` |
| YM2413 コア名 | `NukeYKT-Banked` |

### 4.2 Phase 1 で追加した分（確定済み）

| 項目 | 値 |
|---|---|
| デバイス型名 | `Y8960-OPL2` |
| サウンドデバイス名 | `Y8960 OPL2 0` / `Y8960 OPL2 1` |
| ミキサーのチャンネル番号 | OPL2 が 2 と 3。ADPCM の 8 は使わない（§5 Phase 1） |
| XML の結線要素 | `<opl2_0>` / `<opl2_1>`（OPLL の `<opll0>` / `<opll1>` に倣った） |
| `<sampleram>` | 256（KB）。ブロックごとに持つ |
| 実装ファイル | `src/sound/Y8960OPL2.{cc,hh}`, `Y8960OPL2Device.{cc,hh}` |

ADPCM は独立したサウンドデバイスにならないので `Y8960 ADPCM` という名前は使わなかった。

### 4.3 I/O アドレス

一次情報が食い違っている。いずれも**確認済み**（各出典を読んだ）。
**hra1129 さんからの直接の回答があるものは、それを最優先する。**

| | 採用値 | buppu3 実装 (2026-01) | RTL (2026-03) | xlsx |
|---|---|---|---|---|
| DCSG | **3Eh / 3Fh** | 48h-49h / 4Ah-4Bh | 7Eh / 7Fh | 3Eh / 3Fh |
| ミキサー | 40h-41h（据え置き） | 40h-41h | 無し（40h-4Fh は system controller） | — |
| OPLL の対応 | 据え置き（RTL と一致） | 7Ch+7FF4h が OPLL 0 | 7Ch+7FF4h が core 0 | 7Ch+7FF4h が OPLL1 |
| OPL2 | C0h-C1h / C2h-C3h | （未実装） | C0h-C1h / C2h-C3h | C0h-C1h / C2h-C3h |
| MSX-TIMER | B0h-B3h | B0h-B3h | B0h-B3h | — |

**DCSG は 3Eh / 3Fh**。2026-09-09 に hra1129 さんから直接の回答があり、
xlsx の 3Eh/3Fh が正、RTL の 7Eh は古いと確定した。**これが最も強い出典**で、
RTL より優先する。
DCSG は 1 ポートずつで、**アドレス bit0 が 2 回路のどちらかを選ぶ**
（**確認済み**: `sn76489_audio_patch/sn76489.v:26-27` の `w_cs0_n` / `w_cs1_n`）。
したがって 3Eh → DCSG 0、3Fh → DCSG 1。

**前提: Y8960 自体が WIP なので、これらは変わりうる。**
そのためアドレスは C++ 側に定数として持たず、`share/extensions/HRA_Y8960.xml` の
`<io base=...>` にのみ書く。変更コストは XML 1 行と本書の表だけに収まる。

**OPLL の対応は buppu3 実装・RTL・xlsx の三者で一致している**（2026-09-09 に
`opll.v:27-28` と `y8960_address_decode.v` を読み直して確認）。
7Ch-7Dh + 7FF4h-7FF5h が 1 番目の回路で、従来の MSX-MUSIC 互換の側である。
以前ここに「RTL とは逆」と書いていたのは誤りだった。

ミキサーの 40h-41h は現 RTL の system controller (40h-4Fh) と衝突し、
`ioport.txt` はミキサーを B6h-B7h と書いている。**据え置き**（確認事項）。

**OPL2 のメモリマップド側は xlsx が自己矛盾している。** xlsx は C0h-C1h を
OPL2-1、7FECh-7FEDh を OPL2-2 と書いているが、RTL では両方とも
`bus_address[1]==0` で同じ 1 番目の回路に届く（**確認済み**:
`opl2_patch/opl2.v:102-103`、`y8960_address_decode.v:100-101, 106-107`）。
両立しないので RTL を採り、C0h-C1h と 7FECh-7FEDh を同じ回路に繋いだ。
OPLL 側は同じ規則で xlsx と一致していたので、食い違うのは OPL2 だけ。確認事項。

**OPLL の enable まわりは RTL と xlsx／マニュアルが食い違う**
（`hardware-notes.md` §6.1）。7FF6h の bit0 が 7Ah 側を開き、リセット直後は
7Ch-7Dh が無効・7Ah-7Bh が有効になっている。I/O enabler を実装する段
（§7 の保留事項）で、どちらに従うかを決める必要がある。確認事項。

## 5. フェーズ計画

各フェーズの終わりに「何を確かめたか」を §8 に書く。

### Phase 0 — 環境と土台の整備

- ビルド環境の構築 → `doc/fork/build/README.md`（済み）
- `buppu3` remote の追加と、`buppu3/y8960` を追跡するローカルブランチ `y8960`（済み）
- 作業ブランチのビルドと起動確認（済み）。
  `-ext HRA_Y8960` を挿した構成で Y8960 の全デバイスが登録されることを
  `machine_info` で確認した
- **残**: hra1129 さんへの I/O アドレス確認（§4.3）
- **残**: V9968 を取り込むかどうかの判断

### Phase 1 — OPL2EX (YM3812 + ADPCM-B) ×2 【完了 2026-09-09】

- `src/sound/Y8960OPL2.{cc,hh}` — `Y8950` のフォーク（§3.4）
- `src/sound/Y8960OPL2Device.{cc,hh}` — C0h-C1h / C2h-C3h に載せる `MSXDevice`
- `src/sound/Y8950Adpcm.{cc,hh}` — `Y8950Status` インターフェースを切り出し、
  ADPCM 実装を 2 つのチップで共有できるようにした（§3.4）
- `RomY8960` に 7FECh/7FEEh のトンネルと 7FFFh の I/O Enabler2 を追加
- `HRA_Y8960.xml` に OPL2 を 2 個追加し、ミキサーのチャンネル 2 と 3 を有効化
- ビルド系: `src/meson.build` と `build/msvc/openmsx.vcxproj` に追記
  （GNU make は `src/**/*.cc` を自動収集するので不要。**確認済み**:
  `build/main.mk:260-262`）

**ミキサーのチャンネル 8（ADPCM）は有効化していない。** ADPCM は
`Y8960OPL2` の内部で FM と同じサウンドデバイスに混ぜられており、
独立した `SoundDevice` ではないため、id 参照で結線できる相手が存在しない。

**残**: ADPCM を実際に再生させての確認。レジスタ経路は `Y8950` と同一だが、
音を鳴らして確かめてはいない（**未検証**）。

### Phase 2 — アドレスの整合

§4.3 の確認結果を反映する。変更コストは、アドレス定数と `HRA_Y8960.xml` の
`<io>` 記述、および本書と `hardware-notes.md`。

### Phase 3 — 上流追従（V9968 の扱いを決めてから）

417 コミット分の差をどう埋めるか。V9968 を含めるかで手順が変わる。

### Phase 4 — 仕上げ

- ADPCM の再生確認、Y8960emu との突き合わせ
- 7FFFh の残りビット（b2/b3 DCSG、b4 SSG、b7 タイマー）。
  対象デバイスにゲートが無いので、それぞれに `setIoEnabled()` を足す必要がある
- Debuggable、ユーザー文書、buppu3 への還元をどうするか

## 6. 検証方法

**実機が無いので「実機と一致」は検証できない。** できるのは次まで。

0. **実施済み（2026-09-09）**: 波形選択が音を変えることを実測した。
   同じレジスタ列で波形番号だけを変えて 2 回録音し、WS0 は負サンプル 50.5%、
   WS2 は 0.0%（`|sin|` の形）。テストは
   `tests/opl2-waveform.tcl` + `tests/check-opl2-waveform.py`。
   判定器が誤って通らないことも、WS2 を WS0 で置き換えて NG になることで確認した。
   MSX-AUDIO の非回帰も確認済み（`audio` / `audio2` / `Panasonic_FS-CA1` が
   終了コード 0。`Boosted_audio` は変更前も同じく失敗し、必要な BIOS ROM が
   手元に無いことを SHA1 照合で確かめた）
1. **Y8960emu との突き合わせ** — OPL2EX は madscient/Y8960emu に
   ymfm ベースの別実装がある。同じレジスタ列を与えて挙動を比べられる。
   **未実施**
2. **ユニットテスト** (`src/unittest/`) — 波形テーブルの生成は純粋な計算なので
   直接テストできる
3. **既存機種の非回帰** — `Y8950` を**フォーク**する（改造ではない）ので、
   MSX-AUDIO 搭載機の音は変わらないはず

**非回帰テストの注意**: 修正後に通ることは、修正前に落ちることを
示すまで証拠にならない。テストを書いたら、まず期待値を壊して落ちるのを確認する。

## 7. 見送った提案

- **ブロックを 1 つの `Y8960` デバイスに集約する** — 撤回（2026-09-08）。
  既存実装が XML 分割 + id 参照で同じ問題を解いており、既存の
  `PSG` / `SNPSG` / `Rom8kBBlocks` を再利用できる分そちらが良い（§3.2）
- **OPLLEX のために `YM2413Okazaki` をフォークする** — 撤回（2026-09-08）。
  `YM2413NukeYKTBanked` が既にあり、`YM2413Core` を壊さずに実現している（§3.5）
- **buppu3/openMSX を `origin` に差し替える** — 却下。buppu3 の master は
  openMSX/master に対して 0 ahead / 417 behind で、upstream に据えても
  得るものが無く、上流修正を失う。2 つ目の remote として追加した（§8）
- **`Y8950Adpcm` も丸ごとフォークする** — 却下（2026-09-09）。
  `Y8950` に求めているのが 3 メソッドとステータスビットだけだったので、
  `Y8950Status` インターフェースを切り出して共有した。570 行の重複を避けられる。
  上流ファイルに手が入るが、変更は機械的で衝突面は小さい（§3.4）
- **ymfm を導入して Y8960emu のコアをそのまま移植する** — 却下。
  openMSX に無い依存を持ち込むことになる
- **YMF262 を OPL2 モードで使い、ADPCM を別に足す** — 却下。
  `YMF262` は OPL3 で、Y8950 が持っているタイマー/ステータス/IRQ/ADPCM の
  結線を作り直すことになる。`Y8950` フォークの方が差分が小さい（§3.4）
- **I/O enabler (7FF6h) を実装する** — 2026-09-09 に実施済み（§3.3）。
  7FFFh 側（OPL2 / DCSG / SSG / MSX-TIMER）は Phase 1 に持ち越し

## 8. 実行経緯

### 2026-09-08

- Y8960_Cartridge / Y8960emu / EPSGemuEngine を調査し、`hardware-notes.md` を作成
- openMSX 側の受け皿を調査し、一から作る前提で本書の初版を作成
- ビルド環境を構築（`doc/fork/build/README.md`）。Python 3.13 の追加と
  PlatformToolset v145 での上書きが必要だった
- **buppu3/openMSX に `y8960` ブランチがあることが判明**。Y8960 実装が
  すでにかなり入っており、OPL2EX/ADPCM だけが空いていることを確認
- 決定: `origin` は openMSX/openMSX のまま、`buppu3` を 2 つ目の remote として追加。
  `y8960` ブランチを土台にする
- 決定: 当初の「単一デバイス」案と「Okazaki フォーク」案を撤回（§7）
- 決定: **V9968 は取り込まない**。よって Y8960 分の 15 コミットだけを
  最新 master に cherry-pick し、ローカルブランチ `y8960` を作り直した（§3.0）
- 決定: **DCSG のポートは 7Eh / 7Fh**（§4.3）。Y8960 が WIP で変わりうるため、
  アドレスは C++ に持たせず XML にのみ書く
- 載せ替えで `YM2413NukeYktTables.ii` の欠落に当たり、上流の constexpr 化を
  移植して解消（§3.0.1）
- 載せ替え後のビルドと起動を確認。`iomap` で 7Eh/7Fh への割り当てを実測（§3.2.1）
- 発見: **7Ch で本体 MSX-MUSIC と衝突する**（§3.2.1）。I/O enabler 未実装が原因で、
  実機では起きない。§7 の保留事項「I/O enabler を実装する」の優先度が上がった
- 未決: ミキサー 40h-41h（§4.3）。hra1129 さんへの確認事項
- 作業ブランチを `y8960` から `main` にリネーム（公開リポジトリの既定ブランチにするため）

### 2026-09-09 (3) — SSGS

- hra1129 さんから 2 点の訂正。**DCSG は 3Eh/3Fh**（xlsx が正、RTL が古い）、
  **SSG は SSG×2 ではなく SSGS (YMZ705 相当)**
- 2026-08-30 の議論で YMZ732 のレジスタ配置に合わせることが決まっていた。
  レジスタ配置は madscient/EPSGemuEngine の `src/YmzSsg.{h,cpp}` で確定
  （$00-$1F / $20-$3F の 2 系統、各系統の $10-$12 が 4bit パンポット、
  $40 以上の ADPCM / シーケンサは Y8960 では使わない）
- 決定: `AY8910` をフォークして `Y8960SsgCore` を作り、
  6ch ステレオの `Y8960SSG` にまとめる（§3.6）。
  EPSGemuEngine 側のフォークは採らなかった。openMSX に実績のある `AY8910` が
  あり、本体 PSG と音の素性が揃うため
- パンポットと 2 系統の分離を WAV で実測（`tests/ssgs-panpot.tcl`）
- 7FFFh の b4 を実装。b2/b3 (DCSG) と b7 (タイマー) は未実装のまま
- **訂正**: 前回「ADPCM 8 音とシーケンサ 2 系統が丸ごと欠けている」と書いたが、
  Y8960 が使うのは SSG 互換部だけだった。行き過ぎた読みだった

### 2026-09-09 (2) — Phase 1

- **OPL2EX + ADPCM-B を実装し、全ブロックが揃った**（§3.4、§5 Phase 1）
- 決定: ADPCM は `Y8950Status` インターフェース経由で `Y8950Adpcm` を共有する（§7）
- 7FFFh (I/O Enabler2) の OPL2 分と、7FECh/7FEEh のトンネルを実装（§3.3.1）
- 発見: **OPL2 のメモリマップド側で xlsx が自己矛盾している**（§4.3）。RTL を採った
- 波形選択が音を変えることを WAV で実測。MSX-AUDIO の非回帰も確認（§6）
- **指摘を受けて修正**: テストで openMSX の GUI ウィンドウを出していた。
  人間の並行作業とキー入力が衝突する。`renderer none` / `sound_driver null` を
  スクリプト先頭に置く形にし、規則をルートの `CLAUDE.md` §5 に明記した

### 2026-09-09

- **決定: I/O enabler は FM-PAC を正とする。** 7FF6h の b0 が 7Ch-7Dh、
  b1 が 7Ah-7Bh を開く。リセット直後は両方とも閉じる。
  RTL の現状（b0 が 7Ah 側、7Ah がリセット時有効）は取り違えとして採らない
- 実装し、`doc/fork/y8960/tests/opll-enabler.tcl` で検証した（§3.3）
- ついでに `RomY8960::reset()` で `ramEnabled` を初期化するようにした。
  メンバに初期化子が無く `reset()` でも設定されていなかったため、
  値が不定だった。RTL は `rammode` をリセットで 0 にする
- **訂正**: 「OPLL の番号が RTL と逆」は誤りだった。`opll.v:27-28` と
  `y8960_address_decode.v` を読み直したところ、回路とアドレスの対応は
  buppu3 実装・RTL・xlsx の三者で一致している。7Ch-7Dh + 7FF4h-7FF5h が
  1 番目の回路（従来の MSX-MUSIC 互換の側）。`hardware-notes.md` §6.1 に詳述
- 新たな食い違いを発見: **7FF6h の enable ビットの割り当てが xlsx と RTL で逆**、
  かつ**リセット直後に有効なのは 7Ch-7Dh ではなく 7Ah-7Bh の側**。
  マニュアル §3.1 の「起動直後は無効」とも食い違う。
  FM-PAC と同じ手順（7FF6h に 01h）では 7Ch 側が開かない。
  I/O enabler を実装する段で決める必要がある。確認事項
