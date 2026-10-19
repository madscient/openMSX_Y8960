# Y8960 カートリッジ ハードウェア仕様 調査ノート

調査日: 2026-09-08 / 改訂: 2026-10-19
対象: hra1129/Y8960_Cartridge の xlsx は `80d9682`（2026-10-19）、RTL は `d6d16a3`。
ただし SCC の定位（§6.7）と定位の値 0（§6.1）は `80d9682` の RTL を読んだ。

**xlsx と RTL は同じ時点を指していない。** `d6d16a3` 以降のコミット（`b9de3c1` から
`7e45f89` まで）が変えたのは `doc/spec/Y8960_Specifications.xlsx` だけで、RTL は
`d6d16a3` のまま（**確認済み**: `git diff --stat d6d16a3 6ab414e` と、`7e45f89` の
変更ファイル一覧）。xlsx の改訂で
DCSG と 2 番目の OPLL / OPL2 が無くなり、窓の番地が詰め直され、定位と音量が足されたが、
`d6d16a3` の RTL はどれも反映していない。本書の RTL の記述は、断りが無ければ改訂前の構成のものである。

**`b614b76`（2026-10-18）と `80d9682`（2026-10-19）で RTL も動いた。** 両コミットは xlsx と
一緒に RTL の多数のファイルを変えている（**確認済み**: GitHub API の変更ファイル一覧）。
同リポジトリの `history.md` は、SSG・OPLL・OPL2・ADPCM・SCC の定位、ミキサーの音量と
マスター音量を RTL に入れたと記録している（**確認済み(読解)**: `history.md` の 2026-10-16 夜から
2026-10-19 朝の各項。記録を読んだだけで、SCC 以外の RTL は読んでいない）。

改訂ごとに何が変わったかは `implementation-plan.md` §8 の 2026-10-16 から 2026-10-18 までの各項にある。

**パスの読み方**: 本書が `src/...` と書くとき、断りが無ければ
hra1129/Y8960_Cartridge の `fpga/Y8960_Cartridge_TangPrimer25K/src/...` を指す。
`doc/spec/` や `doc/manual/` も同リポジトリのもの。
本リポジトリ（openMSX フォーク）のファイルは `src/sound/...` のように
openMSX 側の階層で書き、文脈で区別できるようにしている。

**確度について**: 本書の記述はすべて上記リポジトリの成果物と hra1129 さんの回答から
得たもので、実機での確認は行っていない（実機は未完成）。各項目の確度は個別に付記する。

- **確認済み(読解)** — 当該ファイルを読んで確認した。ファイル名と行を示す
- **未検証** — 読解はしたが、実機・シミュレーションで動作を確かめていない
- **推測** — 出典を示せない

一次情報は複数あり、**互いに食い違っている**。優先順位は次のとおり。

1. **hra1129 さんからの直接の回答**（Discord など。ユーザー経由を含む）
2. `doc/spec/*.xlsx` / `doc/manual/*.docx`
3. `fpga/.../src/*.v` (RTL)

**RTL は最下位である。** 2026-09-09 に hra1129 さんから
「RTL は WIP とみなしてよい、SSGS も反映されていないのでプレースホルダ」との
確認があった。DCSG のアドレス、OPLL の enabler ビット、SSG のブロック構成の
いずれも RTL が古かった。

食い違いは §7 に列挙する。

## 1. 全体構成

MSX 用サウンドカートリッジ。Tang Primer 25K (Gowin FPGA) 上に実装。
xlsx の `modules` シートが挙げるブロック（**確認済み(読解)**）:

| ブロック | 相当チップ | 回路数 | RTL の IP | ライセンス |
|---|---|---|---|---|
| SSG | YM2149 | 2 系統（1 ブロック） | 自作 (`src/ssg/ssg_core.v`) | MIT |
| OPLL | YM2413 + 音色バンク拡張 | 1 | IKAOPLL | BSD-2 |
| OPL2 | YM3812 | 1 | jtopl2 | GPL3 |
| ADPCM | YM2608 ADPCM-B | 1 | jt10_adpcmb | GPL3 |
| SCC | Konami SCC + 独自マッパー | 1 | IKASCC | BSD-2 |
| MSX-TIMER | 独自 | 1 | 自作 (`src/timer/`) | MIT |
| Digital Mixer | 独自 | 1 | 自作 | MIT |

DCSG（SN76489 相当）は 2026-10-16 の改訂で無くなった。RTL（`d6d16a3`）には
まだ DCSG と、OPLL / OPL2 / ADPCM の 2 番目の回路がある
（**確認済み(読解)**: `src/y8960_cartridge_tangprimer25k.v`）。

音声は 24bit ステレオで I2S 出力。RTL のミキサーは **L と R に完全に同じ式**を
代入しており、定位も音量も無い（**確認済み(読解)**: 同 `w_mix_l` / `w_mix_r`）。
仕様上の定位と音量は §6 と §6.5。

## 2. I/O ポートマップ

xlsx（`7e45f89`）の各シートの直接 I/O の表（**確認済み(読解)**）:

| ポート | ブロック | RW |
|---|---|---|
| A0h | SSG レジスタ番号 | WO |
| A1h | SSG 書き込み | WO（「Read すると 255」） |
| A2h | SSG 読み出し | RO |
| 7Ch / 7Dh | OPLL アドレス / データ | WO |
| C0h / C1h | OPL2 アドレス / データ | （欄が空） |

MSX-TIMER（B0h-B3h）はこの xlsx に無い。出典は 2026-09-09 の hra1129 さんの回答と、
`src/timer/` の RTL（§6.6）。

SSG / OPLL / OPL2 / MSX-TIMER の直接 I/O は、リセット直後は閉じていて、
メモリマップド I/O の I/O Enabler で開く。Panasonic FM-PAC と同じ方式
（**確認済み(読解)**: manual §3.1）。ミキサーには I/O ポートが無い（`MIXIER` シート）。

`ioport.txt` にある `B6h-B7h: MSX-SOUND MIXER` は、ミキサーが MMIO のみになったので
使われない。

### RTL（`d6d16a3`）の I/O ポート

**確認済み(読解)**: `src/y8960_address_decode/y8960_address_decode.v` の localparam 群。
2 番目の回路と DCSG を含む改訂前の構成で、リセット時の有効/無効も xlsx と違う。

| ポート | ブロック | リセット時 |
|---|---|---|
| A0h-A1h, A2h-A3h | SSG | **有効** |
| 7Ah-7Bh | OPLL #1 | **有効** |
| 7Ch-7Dh | OPLL #2 | 無効 |
| 7Eh-7Fh | DCSG #1/#2 | 無効 |
| C0h-C1h / C2h-C3h | OPL2 #1 / #2 | 無効 |
| B0h-B3h | MSX-TIMER | 無効 |
| 40h-4Fh | System Controller (device_id = 61h) | 常時（enabler 無し） |

### 本体デバイスとの衝突

- A0h-A2h は MSX 本体 PSG と衝突する。これは**設計上の意図**である。
  RTL の SSG #1 は `BUILTIN=0` でインスタンス化されており、リードデータを駆動しない
  （**確認済み(読解)**: top の `dual_ssg #(.BUILTIN(0))` と `ssg_core.v` の
  `generate if(builtin)`）。xlsx でも SSG1 のレジスタ (00h-0Fh) は WO
- xlsx は SSG2 (10h-1Fh) と音量・定位 (20h-2Fh) を RW としている。A2h から
  読めるという意味に取れる。openMSX 側の実装はカートリッジの読み出しに一切応じない
  （§7 の 7）
- 7Ch-7Dh (MSX-MUSIC)、C0h-C1h (MSX-AUDIO) はリセット直後は閉じているので、
  本体の同じアドレスの音源とは、開かない限り衝突しない

## 3. メモリマップド I/O

xlsx（`7e45f89`）の `MemoryMappedIO` シート（**確認済み(読解)**）。すべて WO。

| アドレス | 内容 |
|---|---|
| 7FF0h / 7FF1h | SSG レジスタ番号 / 書き込み |
| 7FF2h / 7FF3h | OPL2 アドレス / データ |
| 7FF4h / 7FF5h | OPLL アドレス / データ |
| 7FF6h | I/O Enabler1: b0 = OPLL |
| 7FF7h | SSG の音量 |
| 7FF8h | OPLL の音量 |
| 7FF9h | OPL2 の音量 |
| 7FFAh | SCC の音量 |
| 7FFBh-7FFDh | Reserved |
| 7FFEh | マスター音量 |
| 7FFFh | I/O Enabler2: b0 = OPL2、b1 = SSG、b7 = MSX-TIMER |

利用条件は「RAM Mode=0 か、あるいは BANK1 が ROM バンク (#0-#15) のとき」。

**ミラーは無い**（2026-10-17、hra1129 さんの回答。ユーザー経由）。

### RTL（`d6d16a3`）の窓

**確認済み(読解)**: 同 `y8960_address_decode.v`。

窓は `A15==0 && A[13:5]==9'b11_1111_111` すなわち **7FE0h-7FFFh**、
ミラーが **3FE0h-3FFFh**。書き込み専用。`memory_io_en` が 1 のときのみ有効で、
top では `memory_io_en = ~scc_ma[5] = ~rammode`。
つまり **RAM モードではメモリマップド I/O は消える**。

窓の中の配置は改訂前のもの（SSG 7FEAh、OPL2 7FECh / 7FEEh、DCSG 7FF0h / 7FF1h、
OPLL 7FF2h / 7FF4h、Enabler1 7FF6h、Enabler2 7FFFh）で、音量レジスタは無い。

窓に当たらないメモリアクセス、および窓に当たっても読み出しの場合は SCC に回る
（**確認済み(読解)**: `w_mem_plain` / `w_mio_default_match`）。

## 4. SCC / メガ ROM マッパー

**確認済み(読解)**: `src/ikascc_patch/IKASCC_vrc_s.v`（IKASCC 純正からの patch）、
`src/ikascc_patch/scc_bank.v`。

IKASCC 内蔵マッパーを patch して 2 モードにしたもの。

**互換モード (rammode=0)** — Konami SCC 相当:
- BANK レジスタ: 5000-57FFh(BANK0) / 7000-77FFh(BANK1) / 9000-97FFh(BANK2) / B000-B7FFh(BANK3)。
  **rammode が 1 のときは受け付けない**（`&& !rammode`）
- SCC 音源レジスタ: `bankreg2 == 6'h3F` かつ A[15:11]==10011b、すなわち 9800-9FFFh

**RAM モード (rammode=1)** — 独自:
- モードレジスタ: 4?FBh (? = 8..F、`ablo == FBh` かつ A[15:11]==01001b) の b0
- BANK レジスタ: 4?FCh / 4?FDh / 4?FEh / 4?FFh。**rammode が 0 のときは受け付けない**
- SCC 音源レジスタが追加で `rammode && bankreg1 == 6'h3F` かつ A[15:11]==01111b
  = 7800-7FFFh にも出現
- 書き込みが SRAM まで通る

リセット値は `rammode=0`、`bankreg0..3 = 0,1,2,3`。

### 4.1 バンク番号と rammode が実際に何を決めているか

**確認済み(読解)**: 2026-09-09 に `d6d16a3` を読んだ。効いているのは次の 3 行。

| ファイル | 行の要旨 |
|---|---|
| `ikascc_patch/IKASCC_vrc_s.v` | `o_ROMADDR = { rammode, bankregN[4:0] }` |
| `ikascc_patch/scc_bank.v` | `cpu_address = { scc_ma[17:13], bus_address[12:0] }` |
| 同上 | `cpu_write = w_ram_mode & bus_write`、`w_ram_mode = scc_ma[18]` |

`scc_ma` は `o_ROMADDR` そのものなので、これを合わせると次になる。

- **メモリのアドレスは `bankreg[4:0]` だけで決まる。** 8KB × 32 バンク = 256KB。
  `rammode` はアドレスに寄与しない
- **`rammode` が決めるのは書き込みの可否だけ**（および `memory_io_en = ~scc_ma[5]`
  によるメモリマップド I/O の窓の有無。**確認済み(読解)**: top の当該行）
- **バンク番号による ROM/RAM の区別は無い。** `cpu_write` にバンク番号の分岐が
  一切無いので、RAM モードでは 32 バンクすべてが書ける
- **4000-5FFFh の書き込み保護も無い**（`w_mem_access = bus_valid & ~bus_io` で、
  アドレスによる分岐が無い）
- バンクレジスタは 6bit 書けるが、アドレスに出るのは `[4:0]` の 5bit。
  **bit5 は SCC 音源レジスタの `== 6'h3F` 比較にだけ効く**

メモリマップド I/O の窓は
`memory_io_en & bus_write & (A15==0) & (A[13:5]==9'b111111111)`
（**確認済み(読解)**: `y8960_address_decode.v`）。**書き込みのみ**で、
`rammode=1` のとき窓ごと消える。xlsx の利用条件（§3）はこれと違い、RAM モードでも
BANK1 が ROM バンクなら使える。

## 5. メモリ構成

**確認済み(読解)**: `fpga/.../doc/memory_map.txt`。

- Serial Flash ROM 8MB: 000000h-77FFFFh = FPGA コンフィグ、780000h-7FFFFFh = SRAM 初期イメージ
- Serial SRAM 512KB:
  - 00000h-1FFFFh: BIOS-ROM 8KB × 16 バンク
  - 20000h-3FFFFh: BIOS-RAM 8KB × 16 バンク
  - 40000h-7FFFFh: ADPCM RAM 256KB

SCC マッパーが見るのは 00000h-3FFFFh の 256KB（**確認済み(読解)**:
`scc_bank.v` の `cpu_address` が 18bit）。ADPCM は 18bit アドレスで
40000h 以降を使う（**確認済み(読解)**: `sram_arbiter` のポート幅）。

BIOS-ROM の中身は電源投入時に Flash から SRAM へコピーされる
（**確認済み(読解)**: `system_controller.v` の `sram_initialize` 経路）。
**BIOS ROM イメージ自体はリポジトリに存在しない**。

## 6. 拡張ブロックの仕様

### 6.1 定位と音量の共通の決まり

定位のレジスタ（OPLL 50h-58h、SSG 28h-2Eh、OPL2 F6h-FFh、SCC 9900h-9904h）は、
**1 で左端、128 で中央、255 で右端、既定 128**（**確認済み(読解)**: 各シートの Note 欄）。
ssg シートに貼られた説明図は、**等パワーパンニング**（L = cos θ、R = sin θ、
中央で両側 0.707）を示している。値から θ への写像は図に書かれていない。

**値 0 は xlsx に無い。RTL は 1 と同じ左端として扱う**（**確認済み(読解)**: `history.md` の
2026-10-16 夜の「共通PAN変換テーブル」。定位の表 `src/pan/pan_lut.v` を全ブロックが共有する）。
中央は左右とも 181/256（同 2026-10-19 朝の SCC と ADPCM の項）。

音量のレジスタ（SSG 20h-26h、ミキサー 7FF7h-7FFAh と 7FFEh）は、xlsx では「0-128、128 が最大、
既定 128」。hra1129 さんの回答（2026-10-17、ユーザー経由）は
**0 がミュート、1-127 がゲイン、bit7 が立てば最大**。1-127 の曲線は回答に無い。

### 6.2 OPLLEX (拡張 OPLL)

YM2413 に、**チャンネルごとに**プリセット音色バンクを選ぶ機能と、
チャンネルごとの定位を足したもの。1 回路。直接 I/O は 7Ch/7Dh（OPLL1 と呼ばれている）。

| BANK 値 | 音色セット | 相当チップ |
|---|---|---|
| 0 | OPLL | YM2413 |
| 1 | OPLL-X | YM2423 |
| 2 | OPLL-P | YMF281 |
| 3 | VRC7 | DS1001 |

- **40h-48h**（ch1-9）の b1:b0 が BANK
- **50h-58h**（ch1-9）がステレオ定位
- 10h-48h のレジスタはすべて WO

出典: `doc/spec/Y8960_Specifications.xlsx` の `OPLL-EX` シート（**確認済み(読解)**）、
および madscient/Y8960emu の `doc/Y8960emu_Architecture.md` §3.2（**確認済み(読解)**）。
レジスタ表の見出しはまだ 7Ah/7Bh に触れている。

**リズム音の定位**は、元の ch7-9 の定位をそのまま使う（2026-10-17、hra1129 さんの回答。
ユーザー経由）。YM2413 の割り当てどおり BD が ch7、HH と SD が ch8、TOM と TCY が ch9。

**楽音とリズム音の比率**: 実チップの OPLL は楽音 (MO) とリズム音 (RO) を別端子に出し、
外で混ぜる。OPLLEX はチップ内で混ぜる（ユーザー）。比率は資料に無い。

**RTL 側は未実装**。top が使う `ikaopll_patch/opll.v` は素の IKAOPLL を 2 個並べている
だけで、BANK レジスタも 4 バンクの音色 ROM も定位も入っていない（**確認済み(読解)**）。

音色データの出典は "Copyright free OPLL(x) ROM patches" (David Viens,
Hubert Lamontagne)、CC BY-SA。

### 6.3 OPL2EX (拡張 OPL2)

YM3812 (OPL2) に ADPCM-B を足したもの。1 回路。直接 I/O は C0h/C1h。
レジスタ配置は Y8950 (MSX-AUDIO) と同一で、`07h`-`12h`（`0Dh` / `0Eh` を除く）が
ADPCM-B 系、それ以外は YM3812 に委譲。05h、06h、0Dh、0Eh、13h-1Fh は N/A
（Y8950 のキーボード、DAC などで、廃止または未使用）。
出典: `doc/spec/*.xlsx` の `OPL2+ADPCM` シート、Y8960emu アーキ文書 §3.1（**確認済み(読解)**）。

Y8950 との差（**確認済み(読解)**: 同シート）:

- **OPL2 の波形選択**: E0h-F5h の WS、および TEST レジスタ 01h の b5 = 波形選択
  イネーブル。E0h-F5h の行に「OPL2から追加」と明記
- **F6h-FEh**: ch1-9 のステレオ定位
- **FFh**: ADPCM のステレオ定位

**リズム音**の定位は ch7-9 の定位に従い、楽音と 1 : 1 で混ざる。リズムモードは ch7-9 の
使い方を内部で変えるだけで、音量には影響しない（2026-10-17、hra1129 さんの回答。ユーザー経由）。

**ADPCM は OPL2 の中で混ざる。** ミキサーに ADPCM の音量は無く、ADPCM 自身の音量
（12h）のあとは OPL2 の音量に従う（2026-10-17、同上）。

1Bh の行の Note 欄に「Y8950 EG-CTRL is 12h」とある（`7e45f89` で足された）。Y8950 の
EG-CTRL（ADPCM の音量）が 12h にあるという注記で、上の 12h と一致する。1Bh 自体は N/A の
ままで、なぜこの行に置かれたかは分からない。

**ADPCM のメモリは 256KB の 1 個**（SRAM の 40000h-7FFFFh）。回路が 1 個になったので、
manual §1.3 の「128KB×2ch か 256KB×1 (2ch 共通) を選択可能」は意味を失った。

**ADPCM の ROM は無い**（出典: 2026-09-12 のユーザーからの回答）。
Y8950 はレジスタ `08h` の b0 で ADPCM をサンプル ROM 側に切り替えるが、
Y8960 の ADPCM の後ろには SRAM しかないので、このビットには選ぶ相手が無い。
b1 の 64K モードについては**情報が無い**。

### 6.4 SSG（2 系統）

YM2149 相当の SSG が 2 系統。xlsx（`7e45f89`）の `ssg` シートの配置
（**確認済み(読解)**。2026-10-16 に hra1129 さんが xlsx を正と回答）:

| 範囲 | 内容 | RW |
|---|---|---|
| 00h-0Dh | SSG1 の YM2149 レジスタ | WO |
| 0Eh / 0Fh | SSG1 の GPIO A / B（未接続） | WO |
| 10h-1Dh | SSG2 の YM2149 レジスタ | RW |
| 1Eh / 1Fh | SSG2 の GPIO A / B（GPIO B の下位 4bit は LED） | RW |
| 20h-22h / 24h-26h | SSG1 / SSG2 の ch A-C の音量 | RW |
| 28h-2Ah / 2Ch-2Eh | SSG1 / SSG2 の ch A-C のステレオ定位 | RW |
| 23h, 27h, 2Bh, 2Fh | 未接続 | — |

シートの末尾に「20～EF NA 未接続」の行が残っていて、20h-2Fh と重なる。

**GPIO はセカンダリも機能として有効**（2026-10-16、hra1129 さんの回答。ユーザー経由）。

**2026-08-30 に Discord で決まった YMZ732 の配置（`$00-$1F` が SSG-1、`$20-$3F` が SSG-2、
各系統の `$10-$12` が 4bit パンポット）は採らない。** xlsx が正（2026-10-16）。

AY コアの出力は片極性なので、**定位を掛ける前に無音時レベル（直流成分）を
差し引く**必要がある。省くと直流が定位に漏れる（madscient/EPSGemuEngine のコメントより）。

**RTL（`d6d16a3`）は改訂前**。レジスタポインタは 5bit で **b4 がコア番号**、
音量と定位は無い（**確認済み(読解)**: `ssg_core.v` の `{ core_number, 4'dN }`）。
00h-0Fh が SSG #1（読み出しを駆動しない）、10h-1Fh が SSG #2（読み出しあり。
1Fh の下位 4bit が LED）。

### 6.5 デジタルミキサー

xlsx（`7e45f89`）の `MemoryMappedIO` と `MIXIER` シート（**確認済み(読解)**）:

- 音源ごとの音量が 7FF7h-7FFAh（SSG、OPLL、OPL2、SCC の順。§3）
- マスター音量が 7FFEh。書式は音源ごとの音量と同じ「0: OFF、128: MAX」
- **MMIO のみ**。I/O ポートは無い
- 音量の決まりは §6.1。音源ごとの音量のリセット値は資料に無く、**128（最大）**
  （2026-10-17、hra1129 さんの回答。ユーザー経由）
- マスター音量のリセット値は資料に無く、**128（最大）**（2026-10-18、ユーザー判断）
- マスター音量と音源ごとの音量は、どちらもリニアなゲインで、**単純な積**で掛かる
  （2026-10-18、ユーザーの回答）
- マスター音量は本体の音には掛からない。カートリッジは音声を本体に戻さず、出力が別の線
  であることからの帰結（`implementation-plan.md` §3.7）
- ADPCM の音量は無い。ADPCM は OPL2 に混ざり、OPL2 の音量に従う（§6.3）

RTL には無い（§1）。

### 6.6 MSX-TIMER

4 本のカウンタを持つ独立ブロック。B0h = レジスタ番号、B1h = 値、
B2h = 割り込みフラグ、B3h = カウンタ読み出し
（**確認済み(読解)**: `src/timer/msx_timer.v` の `c_register_index` 他）。
分解能は 0-7 の 8 段。**Base Clock 85.909080MHz (= 3579545 × 24) を
2^(10+2r) で分周したもの**で、11.919578us 〜 195290.369772us
（**確認済み**: `src/timer/doc/msx_timer.xlsx` を展開して
Base Clock と Unit Time の列を読み、式と一致することを確かめた）。

| reso | Unit Time | reso | Unit Time |
|---|---|---|---|
| 0 | 11.919578us | 4 | 3051.412028us |
| 1 | 47.678313us | 5 | 12205.648111us |
| 2 | 190.713252us | 6 | 48822.592443us |
| 3 | 762.853007us | 7 | 195290.369772us |

**同じシートの Count Time 列は分解能ではない。** Unit Time ×（終端値 + 1）で、
シートの例は終端値 5。そこに並ぶ 71.517us 〜 1171742us を分解能と取り違えない。

割り込みは MSX-TIMER と OPL2 内蔵タイマーの 2 系統が
`w_int_n = w_timer_intr_n & w_opl2_intr_n` で OR される（**確認済み(読解)**）。

### 6.7 SCC の定位

xlsx（`80d9682`）の MemoryMappedIO シートに「SCC BANK2-BANK#63」の表が足され、
**9900h-9904h が Ch.A-E の定位**（WO、「RAM Mode=0 の時のみ利用可能」、値の意味は §6.1、
既定 128）になった（**確認済み(読解)**）。同じ表の 9800h-98FFh は標準の SCC の配置のまま。
シート SCC は「MemoryMappedI/O のみ」で中身が無い。

RTL（`80d9682` の `src/ikascc_patch/scc.v`）は次のとおり（**確認済み(読解)**: 同ファイルの
`w_pan_address` / `w_pan_window` / `w_pan_write` / `w_core_cs` の 4 行と、`history.md` の
2026-10-19 朝の項）。

- 定位のアドレスは **A[15:8] = 99h、A[7:0] = 00h-04h の 5 番地だけ**。SCC の窓（BANK2 が 3Fh）が
  出ているときだけ効く。他の region の SCC の窓（§4 の 7800h-7FFFh など）には無い
- **9900h-9904h への書き込みは SCC に渡さない**。IKASCC は A7-A0 しか見ないので、渡すと
  9800h-9804h（Ch.A の波形）に落ちるため。これは RAM モードでも同じ
- **RAM モードでは定位を書けない**（`scc_ma[18]` で止める）。書き込みは定位にも SCC にも届かない
- **9905h 以降と読み出しは従来どおり SCC のミラー**。9900h-9904h を読むと 9800h-9804h が返る
- 等パワーの定位の表を 1 つの乗算器で時分割に掛ける。片側に振り切ったときの振幅は
  従来のモノラル出力と同じ

## 7. 一次情報どうしの食い違い

いずれも**確認済み(読解)**（両方の記述を読み比べた）。
本書は食い違いの事実だけを記録する。どちらを採るかの判断は
`implementation-plan.md` にある。

**出典は 3 系統ではなく 4 系統ある。** 上記 3 つに加えて、
buppu3/openMSX の `y8960` ブランチの既存実装（2026-01 時点の仕様に基づく）が
さらに別の値を持っている。突き合わせ表は `implementation-plan.md` §4.3 にある。

1. **DCSG の I/O アドレス**（3Eh/3Fh と RTL の 7Eh/7Fh）。**DCSG ごと無くなった**（2026-10-16）
2. **OPLL の enable ビットとリセット時の状態**: RTL（`d6d16a3`）は 7FF6h の b0 が
   7Ah 側、b1 が 7Ch 側を開き、リセット時に 7Ah-7Bh が開いている
   （**確認済み(読解)**: `y8960_address_decode.v:115-116, 141, 207-208, 218-219`）。
   xlsx は b0 = OPLL1（7Ch）で、2026-10-16 に 2 番目の OPLL が無くなった。
   openMSX 側は FM-PAC と同じく、b0 で 7Ch-7Dh を開き、リセット直後は閉じる
3. **窓の配置**: RTL は改訂前の配置で、ミラー 3FE0h-3FFFh がある。xlsx は §3 の配置で、
   ミラーは無い（回答）
4. **ROM/RAM バンクの境界**: **出典が 4 つあり、4 つとも違う**
   （**確認済み(読解)**: 2026-09-09 に `d6d16a3` の当該行を読んだ）。

   | 出典 | 記述 |
   |---|---|
   | manual §4 | BANK#0-15 が ROM、#16-31 が RAM |
   | `IKASCC_vrc_s.v` のヘッダコメント | BANK#0-#7 が ROM、#8-#15 が RAM |
   | `scc_bank.v` のコメント | 互換モードは 0-31 が read only、RAM モードは 0-15 が read only で 16-31 が read/write |
   | **RTL の assign** | **バンク番号による分岐が無い。RAM モードなら全 32 バンクが書ける** |

   同じ `IKASCC_vrc_s.v` のヘッダは「BANK0...3 is ROM only」「BANK0 is ROM only」
   とも書いているが、これに当たるコードも無い。§4.1 を見ること。
5. **MMIO の窓が使える条件**: RTL は RAM モードなら窓ごと消す。xlsx は「RAM Mode=0 か、
   BANK1 が ROM バンク (#0-#15)」（§3、§4.1）
6. **BANK0 の出現アドレス**: manual §4 は「4000h-5FFFh と C000h-DFFFh の2か所」。
   BANK1-3 のミラーの有無は manual の図（画像）にあり、テキスト抽出できていない。
   `IKASCC.v` の `i_ABHI` デコードから復元は可能だが**未確認**。
7. **SSG の読み出し**: xlsx は A2h を読み出し専用とし、SSG2 と 20h-2Fh を RW と書く（§2）。
   openMSX 側の実装はカートリッジの読み出しに一切応じない（本体 PSG と衝突するため、
   として 2026-09-09 に決めた）。xlsx に合わせるかは未決

## 8. 未完成であることの確認

- `doc/manual/Y8960_Programmer's_manual.docx` は §5 レジスタ仕様が
  「《記入》」のまま、§3.2-3.6・§6.2・§7.2 が空。**骨組みのみ**。
- RTL（`d6d16a3`）は 2026-10-16 以降の xlsx の改訂を反映していない（§1）。
  OPLLEX の BANK 機能、定位、音量、ミキサーは `d6d16a3` の RTL に無い。`b614b76` 以降の
  RTL には入ったと `history.md` が記録している（§1 の冒頭）
- BIOS ROM イメージが存在しない。
