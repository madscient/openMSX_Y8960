# Y8960 エミュレーション 実装計画

作成: 2026-09-08 / 最終更新: 2026-09-09
状態: **buppu3 の Y8960 実装を最新 master に載せ替え、I/O enabler (7FF6h) まで実装済み。
次は Phase 1 の OPL2EX**

ハードウェア仕様の調査結果は `hardware-notes.md`。本書はそれを前提に、
openMSX 側をどう作るかを決める文書である。決定・却下・経緯はすべてここに追記する。

---

## 1. 目的とスコープ

Y8960 カートリッジ（hra1129/Y8960_Cartridge）を openMSX の拡張機器として
エミュレートする。

**2026-09-08 に土台が変わった。** buppu3/openMSX の `y8960` ブランチに
既存実装があることが分かったため、一から作るのをやめてそれを土台にする
（経緯は §8、既存実装の内容は §3）。

その結果、**残っている作業は次の 3 つに絞られる**。

1. **OPL2EX (YM3812 + ADPCM-B) ×2 の実装** — 既存実装に唯一入っていないブロック
2. **I/O アドレスの突き合わせ** — 一次情報が三者三様（§4.3）。hra1129 さんへの確認が要る
3. **上流追従** — 土台のブランチは openMSX/master より 417 コミット古い

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
port 40-41: I/O y8960-mixer
port 7A-7B:   O Y8960 OPLL 1
port 7C-7D:   O C-BIOS MSX-MUSIC, Y8960 OPLL 0
port 7E:      O Y8960 DCSG 0
port 7F:      O Y8960 DCSG 1
port A0-A3:   O PSG, Y8960 SSG 0, Y8960 SSG 1
port B0-B3: I/O y8960-timer
```

- 7Ch が本体 MSX-MUSIC と重なって見えるが、**問題にならない**。
  OPLL にはリードアクセスが無いので、衝突しても両方から音が出るだけである。
  さらに I/O enabler の実装後（§3.3）はリセット直後 7Ch が閉じているので、
  ソフトが明示的に開くまで重ならない。
  切り分けたいときは、本体側の MSX-MUSIC を外した機種でテストするのが早い
- A0-A3 の重なりも**設計どおり**。SSG 0/1 はレジスタポインタの bit4 で
  振り分けられる（`chip_select`）

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

**未実装: 7FFFh（I/O Enabler2）。** OPL2 / DCSG / SSG / MSX-TIMER 用の
6 ビットが残っている。OPL2EX を足すとき（Phase 1）に同じ形で実装できる。

### 3.4 OPL2EX の作り方（この計画の主目的）

OPL2EX = YM3812 + ADPCM-B。openMSX の `Y8950` は OPL(OPL1) + ADPCM-B で、
**レジスタ配置・タイマー・ステータス・IRQ・ADPCM (`Y8950Adpcm`) がそのまま使える**。
差分は OPL2 の波形選択だけ。よって `Y8950` をフォークする。

波形選択の実装は、`Y8950.cc` の `sinTable`（dB スケール、正値 [0,DB_MUTE)、
負値 [2*DB_MUTE,3*DB_MUTE) の表現）を 4 面に増やし、
`dB2LinTab[sinTable[pgout & PG_MASK] + egOut]` の参照箇所
（`Y8950.cc:733,744,754` 他）をスロットごとの波形テーブルに差し替える。
無音は DB_MUTE-1 で表現できるので、WS1(半波)・WS2(絶対値)・WS3(疑似鋸)は
表を作るだけで済む見込み。**未検証**（コードは書いていない）。
OPL3 側の波形生成コードが `src/sound/YMF262.cc:394-472` にあり、
表の形式が違うので流用はできないが仕様の確認には使える。

TEST レジスタ 01h の b5（波形選択イネーブル）も実装する。
`Y8950.cc` の 01h のコメントに「YM3812 では波形選択イネーブル」と
既に書かれている（**確認済み**）。

**代案として YMF262 を OPL2 モードで使う案は却下**（§7）。

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

## 4. 外に出る値

### 4.1 既存実装が既に決めている値（追従する）

変更すると既存の拡張定義とセーブステートに波及するため、そのまま使う。

| 項目 | 値 |
|---|---|
| 拡張 XML | `share/extensions/HRA_Y8960.xml` |
| デバイス型名 | `MSX-TIMER` / `Y8960-OPLL` / `Y8960-MIXER`、マッパー種別 `Y8960` |
| サウンドデバイス名 | `Y8960 SSG 0/1`、`Y8960 DCSG 0/1`、`Y8960 OPLL 0/1`、`Y8960 SCC` |
| YM2413 コア名 | `NukeYKT-Banked` |

### 4.2 今回追加する分（この形にする）

既存の命名と、XML に既にあるコメントアウト行に合わせる。

| 項目 | 値 |
|---|---|
| デバイス型名 | `Y8960-OPL2` |
| サウンドデバイス名 | `Y8960 OPL2 0` / `Y8960 OPL2 1`、ADPCM は `Y8960 ADPCM` |
| ミキサーのチャンネル番号 | OPL2 が 2 と 3、ADPCM が 8（`HRA_Y8960.xml` の既存コメント行のとおり） |
| 実装ファイル | `src/sound/Y8960OPL2.{cc,hh}`（`Y8950` のフォーク） |

### 4.3 I/O アドレス

一次情報が三者三様だった。いずれも**確認済み**（3 つの出典をそれぞれ読んだ）。

| | 採用値 | buppu3 実装 (2026-01) | RTL (2026-03) | xlsx |
|---|---|---|---|---|
| DCSG | **7Eh / 7Fh** | 48h-49h / 4Ah-4Bh | 7Eh / 7Fh | 3Eh / 3Fh |
| ミキサー | 40h-41h（据え置き） | 40h-41h | 無し（40h-4Fh は system controller） | — |
| OPLL の対応 | 据え置き（RTL と一致） | 7Ch+7FF4h が OPLL 0 | 7Ch+7FF4h が core 0 | 7Ch+7FF4h が OPLL1 |
| OPL2 | C0h-C1h / C2h-C3h | （未実装） | C0h-C1h / C2h-C3h | C0h-C1h / C2h-C3h |
| MSX-TIMER | B0h-B3h | B0h-B3h | B0h-B3h | — |

**DCSG は 7Eh / 7Fh に変更した**（2026-09-08、ユーザー判断）。
DCSG は 1 ポートずつで、**アドレス bit0 が 2 回路のどちらかを選ぶ**
（**確認済み**: `sn76489_audio_patch/sn76489.v:26-27` の `w_cs0_n` / `w_cs1_n`）。
したがって 7Eh → DCSG 0、7Fh → DCSG 1。

**前提: Y8960 自体が WIP なので、これらは変わりうる。**
そのためアドレスは C++ 側に定数として持たず、`share/extensions/HRA_Y8960.xml` の
`<io base=...>` にのみ書く。変更コストは XML 1 行と本書の表だけに収まる。

**OPLL の対応は buppu3 実装・RTL・xlsx の三者で一致している**（2026-09-09 に
`opll.v:27-28` と `y8960_address_decode.v` を読み直して確認）。
7Ch-7Dh + 7FF4h-7FF5h が 1 番目の回路で、従来の MSX-MUSIC 互換の側である。
以前ここに「RTL とは逆」と書いていたのは誤りだった。

ミキサーの 40h-41h は現 RTL の system controller (40h-4Fh) と衝突し、
`ioport.txt` はミキサーを B6h-B7h と書いている。**据え置き**（確認事項）。

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

### Phase 1 — OPL2EX (YM3812 + ADPCM-B) ×2

- `src/sound/Y8960OPL2.{cc,hh}`（`Y8950` のフォーク）
  - 波形テーブル 4 面 + WS レジスタ E0h-F5h + TEST 01h の b5
  - ADPCM は `Y8950Adpcm` をそのまま使う。RAM 256KB を 2 ブロックで共有
- `DeviceFactory.cc` に `Y8960-OPL2` を追加
- `HRA_Y8960.xml` の OPL2 / ADPCM 行のコメントアウトを外す
- `Y8960Mixer` のチャンネル 2, 3, 8 を有効化
- ビルド系: `src/meson.build` と `build/msvc/openmsx.vcxproj` に追記
  （GNU make は `src/**/*.cc` を自動収集するので不要。**確認済み**:
  `build/main.mk:260-262`）

### Phase 2 — アドレスの整合

§4.3 の確認結果を反映する。変更コストは、アドレス定数と `HRA_Y8960.xml` の
`<io>` 記述、および本書と `hardware-notes.md`。

### Phase 3 — 上流追従（V9968 の扱いを決めてから）

417 コミット分の差をどう埋めるか。V9968 を含めるかで手順が変わる。

### Phase 4 — 仕上げ

- Debuggable、ユーザー文書、buppu3 への還元をどうするか

## 6. 検証方法

**実機が無いので「実機と一致」は検証できない。** できるのは次まで。

1. **Y8960emu との突き合わせ** — OPL2EX は madscient/Y8960emu に
   ymfm ベースの別実装がある。同じレジスタ列を与えて挙動を比べられる。
   これが今回いちばん強い検証手段になる
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
