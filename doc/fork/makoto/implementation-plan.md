# Makoto（YM2608 カートリッジ）の実装計画と実行経緯

対象読者: このリポジトリで作業する開発者と AI。決定・却下・訂正を書き足していく。

## 目的

Makoto は YM2608（OPNA）を 1 個載せた MSX 用のサウンドカートリッジである。
これを openMSX の拡張 `Makoto` として足す。
用途は、Makoto 用の拡張 BASIC の回帰試験。試験は openMSX をヘッドレスで走らせ、
レジスタとサンプルメモリをデバッガブルから読んで判定する。

## 利用側との取り決め（外に出る値）

利用側の試験スクリプトはこれらの名前を文字列で持っている。
**変えるときは、先に利用側に知らせる。**

| | 名前 | 中身 |
|---|---|---|
| 拡張 | `Makoto` | `openmsx -ext Makoto -carta <rom>` で使う。I/O だけのデバイスなのでスロットを取らない |
| レジスタのデバッガブル | `Makoto regs` | 512 バイト。`000h`-`0FFh` が表側、`100h`-`1FFh` が裏側。最後に書かれた値 |
| サンプルメモリのデバッガブル | `Makoto ADPCM RAM` | サンプルメモリの全体 |

デバッガブルの名前は、拡張 XML のデバイス `id`（`Makoto`）の後ろに接尾辞を付けて
作っている。**前提**: `share/extensions/Makoto.xml` の `id` が `Makoto` である限り
成立する。

## ハードウェアの前提

| | 内容 | 確度 |
|---|---|---|
| I/O | `14h` 表アドレス（W）／ステータス0（R）、`15h` 表データ（W）／データ（R）、`16h` 裏アドレス（W）／ステータス1（R）、`17h` 裏データ（W）／ADPCM データ（R） | 確認済み（vgmplay-msx `src/drivers/Makoto.asm` の `Makoto_BASE: equ 14H` と各ポートの定義。利用側がソースを読んで確認） |
| クロック | 8MHz | 確認済み（同じファイルの `Makoto_CLOCK: equ 8000000`）。実機の水晶が正確に 8.000MHz かは未確認。upstream PR #2209 の作者も、設計者に 8MHz と確かめたと書いている（伝聞） |
| サンプルメモリ | DRAM、x1 ビット | 容量は未確認。**既定を 256KB にして、`<sampleram>`（KB 単位）で変えられるようにした**。PR #2209 の作者は設計者から 256KB と聞いたと書いている（伝聞） |
| IRQ | `/INT` に出ているか | 未確認。**出ている前提で作った**（Makoto の持ち主の判断）。PR #2209 の作者は設計者から「タイマーの IRQ は直結」と聞いたと書いている（伝聞） |
| リズム音の波形 ROM | チップに内蔵されている | 同梱していない。無ければリズム音は鳴らないが、レジスタは動く。下の「upstream の Makoto（PR #2209）」にあるとおり、SHA1 が GPL のデータと一致した |

## 構成

| ファイル | 役割 |
|---|---|
| `src/sound/MSXMakoto.{hh,cc}` | MSX のデバイス。I/O ポートを受けて `YM2608` に渡すだけ |
| `src/sound/YM2608.{hh,cc}` | ymfm の `ym2608` を包む。FM+リズム+ADPCM のサウンドデバイス（`Makoto`）と SSG のサウンドデバイス（`Makoto SSG`）、タイマー、IRQ、デバッガブル、サンプルメモリ、リズム ROM |
| `src/3rdparty/ymfm/` | ymfm のうち OPN・SSG・ADPCM に要るファイル。BSD-3-Clause（`LICENSE` を同じ場所に置いた） |
| `share/extensions/Makoto.xml` | 拡張の定義 |
| `README`（先頭の節） | エンドユーザー向けの案内。フォークである旨、使い方、リズム ROM の置き方、帰属表示 |
| `doc/fork/makoto/tests/smoke.tcl` | 手で回す検証スクリプト |
| `doc/fork/makoto/tests/rhythm.tcl` | リズム音が鳴るかを録音で見る。ROM の有無で結果が変わる |
| `doc/fork/makoto/tests/bench.tcl` | ホストの CPU 負荷を測る。使い方はファイルの先頭 |
| `doc/fork/makoto/tests/prescale.tcl` + `check-prescale.py` | プリスケーラを切り替えたとき、SSG の音程が追従するかを全体の出力の録音で見る |
| `doc/fork/makoto/tests/native-rate-check.cc` | openMSX の外で、実レートで回した出力と `ym2608::generate()` の出力をサンプル単位で比べる。ビルド方法はファイルの先頭 |
| `doc/fork/makoto/tools/package-release.py` | リリース用の zip を作って中身を検査する |

## 決定

### ブランチ: `makoto` を upstream から切り、Y8960 のコードを含めない

ユーザーが選んだ。Y8960 対応（`main`）とは別のブランチにし、upstream の上には
Makoto のコードとこの文書だけを載せる。`main` にあるフォークの基盤
（`CLAUDE.md`、`README` のフォーク表記、`doc/fork/` の build・release・tools、
`.gitattributes`）は持ち込まない。ただし `.gitattributes` は後から `main` と同じ
内容にした（下の「リリース」）。また README の先頭の節は、このブランチ用に
書き起こした（下の「エンドユーザー向けの案内」）。

- **前提**: Makoto のビルドに Y8960 が要らない限り成立する
- **失うもの**: push 前の点検器（`check-before-push.sh`）とリリース手順が
  このブランチには無い。push の前の点検は手で行う
- **統合する場合の値段**: `main` と一緒にしたくなったら、`DeviceFactory.cc`、
  `src/meson.build`、`build/msvc/openmsx.vcxproj(.filters)` の 4 ファイルで衝突を
  解く。どれも列挙に 1 行ずつ足した衝突で、機械的に解ける（**推測**: 両ブランチの
  差分がどちらも行の追加だけであることから）。これに加えて `README` の先頭の節が
  両ブランチで違うので、手で 1 つにまとめる

### ymfm を取り込む。ファイル名は `.cc` にする

取り込んだのは ymfm のコミット `81aec25ccbb98f4873a255f7551ac4dadac59b4a`
（2026-07-27）。`ymfm.h`、`ymfm_fm.h`、`ymfm_fm.ipp`、`ymfm_opn.{h,cpp}`、
`ymfm_ssg.{h,cpp}`、`ymfm_adpcm.{h,cpp}` の 9 ファイル。中身は変えていない。

`.cpp` の 3 ファイルは `.cc` に改名した。理由は、Unix 系のビルド
（`build/main.mk`）がソースを `*.cc` のワイルドカードで集めていて、`.cpp` は
黙って落ちること（確認済み: `build/main.mk` の 262 行目）。upstream の imgui も
同じ理由で `.cc` にして取り込んでいる。

### 出力のサンプリングレート: FM と SSG をそれぞれの実レートで出す

`makoto-native-rate` ブランチでの決定（`makoto` は下の旧決定のまま）。
`ym2608::generate()` は使わず、`ym2608` を継承したクラスから protected の
`clock_fm_and_adpcm()`・`m_last_fm`・`m_ssg` を直接回す。ymfm は変えていない。

| プリスケーラ | FM+リズム+ADPCM | SSG |
|---|---|---|
| 6（リセット後） | 8MHz÷144 ≈ 55,556Hz | 8MHz÷32 = 250,000Hz |
| 3 | ÷72 ≈ 111,111Hz | ÷16 = 500,000Hz |
| 2 | ÷48 ≈ 166,667Hz | ÷8 = 1,000,000Hz |

- 理由: `generate()` は FM を出力レートに合わせて同じ値で繰り返す（ZOH）。
  実レートで出せば繰り返しが無くなり、openMSX のリサンプラが直接補間する。
  負荷は MIN と同程度で、MAX の約半分（下の「実レートの試作」）
- 出力は `generate()` とサンプル単位で一致する（確認済み: `native-rate-check.cc`）
- プリスケーラはアドレス `2Dh`-`2Fh` を書いた時点で切り替わる。そのとき両方の
  入力レートを変えて `createResampler()` し直す。`SamplePlayer` と同じく、
  切り替えの瞬間に数サンプルずれる
- FM のレートは整数に丸めている（8MHz÷144 は整数にならない）。音程のずれは 10ppm 未満
- **前提**: ymfm の `ym2608` のこれらのメンバーが protected のままである限り成立する。
  ymfm を上げて private になったら、ymfm に小さな公開関数を足すことになる

旧決定（`makoto`）: ymfm の `OPN_FIDELITY_MIN`（クロック÷48 = 166,666Hz、プリスケーラに
よらず一定）。FM の保持時間はどの fidelity でも FM の 1 周期で同じで、fidelity が
変えるのは SSG の扱いだけ（MIN は SSG 3 サンプルを 2 つに重み付き平均、MAX は
4 回繰り返し）。

### 音声は 2 つのサウンドデバイス

`makoto-native-rate` ブランチでの決定。レートが違うので、FM+リズム+ADPCM
（`Makoto`、ステレオ 1 チャンネル）と SSG（`Makoto SSG`、モノラル 1 チャンネル）を
別のサウンドデバイスにした。音量の設定も別々になる（`Makoto_volume` と
`Makoto SSG_volume`）。**`Makoto SSG` という名前は外に出る値で、まだ確定していない。**

- SSG は ymfm と同じく 3 声を 2/3 倍して 1 つに混ぜる
- モノラルのデバイスは中央で左右に 1/√2 ずつ出るので、SSG の増幅率に √2 を掛けて、
  FM との音量比を旧実装と揃えた（確認済み: 演奏中の録音の実効値が旧実装と同じ 5094）
- チャンネルが 1 つのデバイスには、0 で初期化されていないバッファが渡る。
  サンプルは加算でなく代入する（`SoundDevice::mixChannels()` のコメント）
- 無音のバッファは `nullptr` で返し、ミキサーのリサンプルを省く。判定はサンプルの
  OR を取るだけにして、分岐を入れない（Wouter が PR で勧めた形）

旧決定（`makoto`）: 1 つのデバイスの 2 チャンネル（チャンネル 1 が FM+リズム+ADPCM の
ステレオ、チャンネル 2 が SSG で左右同じ）。声部ごとに分けるには ymfm を何度も回す
必要があり、見送った。

パンポット（FM `B4h`-`B6h`／`1B4h`-`1B6h`、ADPCM `101h`、リズム `18h`-`1Dh`）は
ymfm が処理する。

### 書き込みはビジー中でも捨てない

ymfm はビジーを記録するだけで書き込みを捨てない。こちらも捨てない。
利用側の ROM はビジーフラグを見ずに固定時間で待つので、捨てる実装だと実機と
違う理由で試験が落ちる。

### ステータスを読む前に音声を生成し直す

ymfm の ADPCM-B の BRDY と EOS、タイマー B の位相は、音声の生成を回したときに
しか進まない。そこで I/O の読み出しとタイマー満了のたびに `updateStream()` で
現在時刻まで生成してから読む。`generateChannels()` は無音でも省略しない。
openMSX のミキサーは消音中も生成を呼ぶ（確認済み: `MSXMixer::updateStream` の
コメントと実装）。
実レート版では、読み出しの前に生成し直すのは FM 側（`Makoto`）だけ。ADPCM-B の
ステータスは FM の刻み（`clock_fm_and_adpcm()`）で進む。書き込みとタイマー満了の
前には両方を生成し直す。無音を `nullptr` で返すようにしても、刻みは省かない。

### デバッガの peek（`debug read ioports`）

`14h` と `15h` は副作用が無いので本物を返す。`16h` と `17h` は ymfm の読み出しが
状態を変える（ステータスの反映、ADPCM メモリのポインタ）ので `FFh` を返す。
本物の値が要るときは Z80 に `IN` させる（`tests/smoke.tcl` がその形）。

### リズム ROM は SHA1 で `systemroms` から拾う。無くても起動する

ユーザーが選んだ。MoonSound の波形 ROM（`share/extensions/moonsound.xml`）と同じく、
`Makoto.xml` の `<rom>` に SHA1 とファイル名を書いておく。利用者は ROM を
`systemroms` の下のどこかに置くだけでよく、openMSX が SHA1 で照合して見つける。
ROM は配布物に含めない。

| | 値 |
|---|---|
| 大きさ | 8192 バイト（ymfm がリズム 6 音に割り当てる範囲 `0000h`-`1FFFh` と一致） |
| SHA1 | `50b6c3e288eaa12ad275d4f323267bb72b0445df` |
| `<filename>` | `ym2608_rhythm.rom`（SHA1 で見つからないときの補助にしか使われない） |

見つからなければ、MoonSound と違って起動は失敗させない。警告を出して、
リズム音だけ鳴らさずに動く（`YM2608.cc` のコンストラクタ）。利用側の試験は
レジスタしか見ないので、ROM の無い環境でも回る。

- **前提**: この SHA1 の吸い出しが出回っているものと同じであること。
  **未確認**（手元の 1 本しか見ていない）。別の吸い出しが見つかったら、
  `<sha1>` を並べて書けばどちらも拾える。値段は XML の 1 行

### エンドユーザー向けの案内は README と XML の説明文

ユーザーが選んだ。`main` と同じく、ルートの `README` の先頭に英語の節を置いた。
フォークである旨、拡張の使い方、リズム ROM の置き方（大きさと SHA1）、
帰属表示（ymfm）を書いてある。`Makoto.xml` の `<description>` にも、
リズム ROM が要ることを一文入れた（openMSX の拡張の一覧に出る）。

upstream の `packagezip.py` は `README` を zip に入れない（`main` の
`doc/fork/release/README.md` の実行経緯に記録がある）ので、デプロイ先で目に
触れるのは XML の説明文だけになる。

### 見送ったもの

- **MSSE（Y8960 カートリッジのバンク切り替えや I/O Enabler）との連携**。
  理由: 利用側の拡張 BASIC は MSSE に参加しない単独の ROM
- **ステータス0 のバス衝突（実機ではミュージックモジュールとぶつかる）の再現**。
  理由: 利用側の ROM は `14h` を読まない
- **ADPCM の ROM モードと x8 ビット DRAM の削除**。ymfm が持っているので残した。
  利用側は使わない
- **声部ごとのチャンネル分け**。理由は上の「音声は 2 つのサウンドデバイス」の旧決定

## upstream の Makoto（PR #2209）

upstream に、別の作者（maxiwamoto）による Makoto の PR がある
（https://github.com/openMSX/openMSX/pull/2209）。2026-09-29 の時点では open で、
Wouter Vermaelen がレビュー中。取り込まれれば upstream の `Makoto` と
このブランチの `Makoto` が並ぶことになる。

### 比較（2026-09-29、PR の head `6db5b2a64` を読んで比べた）

| | PR #2209 | このブランチ |
|---|---|---|
| ymfm | 同じ版（`81aec25`）に独自の改変 4 件（声部ごとの出力、副作用の無い peek、実効レジスタの読み書き、キャッシュの初期化） | 改変なし |
| 生成レート | `OPN_FIDELITY_MAX`（1MHz） | `OPN_FIDELITY_MIN`（約 167kHz） |
| チャンネル | 16 声部 | 2 |
| リズム音 | libvgm の再構成データ（GPL-2.0-or-later）を内蔵 | `systemroms` から SHA1 で拾う |
| レジスタのデバッガブル | `Makoto registers`（実効値） | `Makoto regs`（最後に書いた値） |
| `16h`/`17h` の peek | 実際の値 | `FFh` |
| サンプル RAM | `std::array`。デバッガブルは無い | `Ram`（`Makoto ADPCM RAM`） |

ポート、クロック、RAM 容量、IRQ 直結、タイマーを 2 つの `Schedulable` で持つこと、
ビジー中の書き込みを捨てないことは共通。

**リズム音データの SHA1 が一致した**（確認済み: PR の
`src/3rdparty/ym2608/README.openmsx` に書かれた SHA1 と、`Makoto.xml` の `<sha1>` が
どちらも `50b6c3e2…`）。手元の ROM は libvgm の再構成データと同一ということになる。
ライセンスの表示だけを見れば GPL-2.0-or-later は openMSX の GPL-2.0-only と両立するが、
**同梱しないと決めた**（2026-09-29、ユーザー判断）。理由: チップ内蔵のデータを
libvgm が独自に配っているだけに見え、そのデータを再配布してよいという根拠が
確かめられない。上の「リズム ROM は SHA1 で…」の決定はそのまま。
**前提**: データの出所と再配布の権利が確かめられない限り成立する。変えるときの値段は、
`Makoto.xml` と `YM2608.cc` のリズム ROM まわり、`package-release.py` の検査、README の案内の 4 か所を直すこと。
加えて、同梱するならデータのライセンス文も入れる

### 利用側への影響

PR がこのまま取り込まれると、デバッガブルの名前が「利用側との取り決め」と違う
（`Makoto regs` ではなく `Makoto registers`、`Makoto ADPCM RAM` は無い）。
利用側が upstream 版に乗り換えるときは、試験スクリプトの名前を書き換えることになる。

### PR に提案したこと

ユーザーの承認を得て、2026-09-29 に PR にコメントした
（https://github.com/openMSX/openMSX/pull/2209#issuecomment-5884649363）。

1. **サンプル RAM を `Ram` にする。** PR の `std::array` は、XML のセーブステートでは
   `CollectionSaver` で 1 要素ずつ `<item>` になる。リバースのスナップショットでは
   memcpy 1 回だが、`serialize_blob` を通らないので `DeltaBlock` の差分圧縮が効かず、
   毎回 256KiB がまるごと積まれる（openMSX の `serialize_core.hh` と `serialize.hh` を
   読んだ見立て。**未計測**）。`Ram` なら両方で `serialize_blob` になり、デバッガブルも付く
2. **下の「ymfm の挙動」1〜3 を実機で確かめてもらう。** PR の ymfm は ADPCM に
   `peek()` を足しただけで、該当箇所はこのブランチと同じ（確認済み: 両方の
   `ymfm_adpcm` を差分し、`ymfm_opn` の `m_flag_control(0x1c)` を見た）

見送った提案: **生成レートを下げる件**（Wouter は 1MHz のコストを気にしている）。
理由: CPU 負荷も音質も比べておらず、出す根拠が無い。
→ 2026-09-30 に CPU 負荷は測った（下の「生成レートの負荷」）。音質は比べていない。
  ユーザーの承認を得て、我々の実装での参考値であることを冒頭に断ったうえで PR に投稿した
  （https://github.com/openMSX/openMSX/pull/2209#issuecomment-5894597882）

### 生成レートの負荷（2026-09-30、確認済み）

Wouter が PR の作者に頼んだ測り方（拡張なしを基準に、無音、演奏中）に合わせて、
このブランチの `YM2608` で fidelity だけを変えて測った。MED と MAX は `FIDELITY` と
`INPUT_RATE` を書き換えた一時ビルドで、ソースは戻してある。

条件: Win10 機、`tests/bench.tcl`、C-BIOS_MSX2+、`renderer none`、`throttle off`、
`sound_driver sdl`、起動後 10 秒から 120 秒ぶんを計時、各 5 回を交互に実行。
「演奏中」は FM 6 声（アルゴリズム 7、TL 0）と SSG 3 声（音量 15）を鳴らしっぱなし。
録音で確かめた（ピーク 12386、無音側は 0）。

| | 実時間の平均 | 拡張なしからの増分 | 実時間で動かしたときのコア 1 本に対する割合 |
|---|---|---|---|
| 拡張なし | 858ms | — | — |
| MIN（約 167kHz）無音 | 3970ms | 3112ms | 2.6% |
| MED（約 333kHz）無音 | 4884ms | 4026ms | 3.4% |
| MAX（1MHz）無音 | 7801ms | 6943ms | 5.8% |
| MIN 演奏中 | 5546ms | 4688ms | 3.9% |
| MED 演奏中 | 6193ms | 5335ms | 4.4% |
| MAX 演奏中 | 9622ms | 8764ms | 7.3% |

- 割合は「増分 ÷ 120 秒」。CPU によって変わるので、比（MAX 無音は MIN 無音の約 2.2 倍）の
  方が他のマシンにも持っていける
- 増分には ymfm の生成とリサンプルの両方が入っていて、分けて測ってはいない
- このブランチは 2 チャンネルで声部ごとの処理が無い。PR の実装で同じ比になるかは**未検証**
- デプロイ済みの `21.0-makoto.2` でも無音の MIN を測り、同じ水準だった（sdl で 3773ms、
  拡張なし 802ms）
- 無音でも `generate()` は止められない（ADPCM-B のステータスが進まなくなる。
  上の「ステータスを読む前に音声を生成し直す」）

### Wouter の実レート案の試作（2026-09-30、`makoto-native-rate`）

Wouter は PR で、FM+ADPCM を 55.6kHz のステレオ、SSG を 250kHz のモノラルの 2 本に
分ければ、ZOH が無くなって速くもなると提案した（欠点として ymfm の変更が増えることを
挙げている）。このブランチで試作した。

- **ymfm を変えずにできた**（上の「出力のサンプリングレート」）
- 提案が触れていないプリスケーラの切り替えは、入力レートの切り替えで追従できた
  （確認済み: `prescale.tcl` で 976.6 / 1953.1 / 3906.2Hz がどれも誤差 0.1% 未満。
  SSG の切り替えを外した版では p3 と p2 が 977Hz のまま落ちる）
- 負荷（確認済み）: Win11 機、`bench.tcl`、条件は上の「生成レートの負荷」と同じ。
  拡張なしからの増分の平均（5 回）

  | | 無音 | 演奏中 |
  |---|---|---|
  | MIN（1 回目 / 2 回目） | 1896 / 1963ms | 2831 / 2881ms |
  | MAX（1 回目） | 3763ms | 4808ms |
  | 実レート（1 回目 / 2 回目） | 1961 / 1842ms | 2966 / 2931ms |
  | 実レート＋無音のスキップ（2 回目） | 1394ms | 2784ms |

  実レートだけでは MIN と誤差の範囲（2 回で順位が入れ替わった）。無音のスキップを
  足すと無音時に MIN より約 3 割軽い。MAX とは同じ回で測っていないが、MAX の
  約 4 割以下。Win10 機での以前の数字とは直接比べない
- 無音のときに残る負荷は、ymfm が FM と SSG を実レートで回し続ける分と見ている
  （**推測**: リサンプルはスキップされているので。切り分けて測ってはいない）
- 見つけた不具合 2 件（修正済み）: 1 チャンネルのデバイスでの加算（出力が発散した）と、
  モノラル化による SSG の 3dB 低下。**`record_channels` による録音ではどちらも
  見えなかった。** 録音するチャンネルは 0 で初期化された別のバッファを通るため。
  試験は全体の出力を録音する形にした
- 未検証: リズム ROM がある場合の発音（手元に ROM が無い）、セーブステートの
  保存と読み込み、実行中にプリスケーラを切り替えたときの切り替わりの瞬間の音

## ymfm の挙動で、実機と違うかもしれない点

1〜3 は ymfm の挙動として走らせて確かめた（2026-09-22、`smoke.tcl` と
同じ形の使い捨てスクリプトで確認）。4 はソースを読んだだけ。
**実機との突き合わせはしていない。**
実機がこのとおりかは未確認。利用側の試験が落ちたら、まずここを疑う。

1. **フラグマスク `110h` のリセット値は `1Ch` で、EOS・BRDY・ZERO がステータス1 に
   出ない。** `110h` を書き換えるまで BRDY は 0 のまま。
   確認済み: `110h` を書かずに読んだら BRDY は 8 回とも 0、`00h` を書くと
   8 回とも 1（ステータス1 は `08h`）
2. **ADPCM-B の記録で、終了アドレスの最後の 1 バイトが書かれない。**
   `adpcm_b_channel::write` は書く前に `at_end()` を見て、最後のバイトの位置なら
   書かずに EOS を立てる。x1 ビット DRAM では、終了アドレス `E` に対して
   `((E+1)<<2)-1` 番地がそれに当たる。
   確認済み: 終了アドレス `0000h` で `A1 A2 A3 A4` を書くと、RAM は `A1 A2 A3 FF`
3. **ADPCM-B の CPU からの読み出しは、limit アドレスで 0 番地に戻る。**
   戻るのは limit の最後のバイトを読む**前**なので、そのバイトは読めない。
   確認済み: limit `0000h` で `B1`-`B8` を書いて読むと `B1 B2 B3 B1 B2 B3 B1 B2`。
   limit（`10Ch`/`10Dh`）を大きくしておけば起きない（`smoke.tcl` は `FFFFh` にしている）
4. **ADPCM-B の EOS と BRDY は、ステータス1 を読んだときにしか IRQ に反映されない。**
   `read_status_hi()` の中で `set_reset_status()` している（ソースを読んだだけで、
   **未検証**）。タイマー A/B の IRQ はそれとは別で、満了した時点で立つ

## 動かし方

ビルドは `main` と同じ手順（`main` の `doc/fork/build/README.md`）。
openMSX の起動も同じで、`OPENMSX_SYSTEM_DATA` を作業ツリーの `share/` に向けると、
ビルドし直さずに `share/extensions/Makoto.xml` が読まれる。

```sh
OPENMSX_SYSTEM_DATA="$(pwd)/share" \
OPENMSX_USER_DATA="$(pwd)/derived/openmsx-user" \
MAKOTO_TEST_OUT="$(pwd)/derived/makoto-smoke.txt" \
  ./derived/x64-VC-Release/install/openmsx.exe \
  -machine C-BIOS_MSX2+ -ext Makoto -script doc/fork/makoto/tests/smoke.tcl
```

結果は `MAKOTO_TEST_OUT` のファイルに `PASS`/`FAIL` の行で出る。最後の行が
`failures 0` なら全部通っている。

## デプロイ

利用側のハーネスは、環境変数が指すフォルダの `openmsx.exe` を使う。
Makoto 版には専用のフォルダを用意する（置き場所はマシンごとに違うので、ここには書かない）。
`main` の配布物と同じく、upstream の `packagezip.py` で zip を作ってそのフォルダに展開する。

```sh
PYTHONPATH=build py build/package-windows/packagezip.py x64 Release NOCATAPULT
# derived/x64-VC-Release/package-windows/openmsx-<版>-windows-vc-x64-bin.zip ができる
```

zip の中身は `openmsx.exe`、`share/`、`doc/`、`codec/`。展開は上書きになる。
zip に無いもの（Catapult、利用者が置いた `share/systemroms/` の中身）は残る。

展開したら、`OPENMSX_SYSTEM_DATA` を外し、`OPENMSX_USER_DATA` を使い捨ての場所に
向けて、デプロイ先の exe で `smoke.tcl` を走らせる。

## リリース

`main` のリリース手順（`main` の `doc/fork/release/README.md`）に倣う。
zip は `doc/fork/makoto/tools/package-release.py <タグ名>` で作る。upstream の
`packagezip.py` を呼んだあと、次の 2 つを足して中身を検査する。

- `README` → `README.txt`
- **ymfm のライセンス文** `src/3rdparty/ymfm/LICENSE` → `doc/ymfm-LICENSE.txt`。
  BSD 3-Clause の第 2 条は、バイナリの再配布に著作権表示・条件・免責事項を
  含めることを求める。upstream の `packagezip.py` はこれを入れない

**フォークが `src/3rdparty/` に足したライブラリには、ライセンス文の同梱先を
`EXTRA_FILES` に書く。** 書いていないライブラリがあるとスクリプトは zip を作らずに
止まる（upstream/master に無いディレクトリを数えて判定する）。確認済み: ymfm の行を
抜いた写しで走らせると `no license in EXTRA_FILES` で終了コード 1。

手順:

1. `-t:Rebuild` で全体をビルドし直す
2. `py doc/fork/makoto/tools/package-release.py <タグ名>`
3. zip を `derived/` の下に展開し、`OPENMSX_SYSTEM_DATA` を外し、ユーザーデータを
   使い捨ての場所に向けて、`tests/smoke.tcl` と `tests/rhythm.tcl`（ROM ありと無し）を
   走らせる
4. `makoto` を push し、`gh release create <タグ名> --draft --prerelease --target <完全な SHA>`
   でドラフトを作る。中身を見てから `--draft=false` で公開する
5. `git fetch origin tag <タグ名>` して `git cat-file -t <タグ名>` が `commit` であることを見る

| 項目 | 値 | 理由と前提 |
|---|---|---|
| タグ名 | `21.0-makoto.<n>`。初回は `21.0-makoto.1` | ユーザー判断。`main` の `21.0-y8960.<n>` と同じ形 |
| タグの種類 | lightweight（`gh release create` に作らせる） | annotated だと `build/version.py` がビルド中に止まる（`main` で確認済みの事情） |
| 種別 | Pre-release | ユーザー判断。実機との突き合わせをしていない |
| 配布物 | Windows x64 のバイナリ zip 1 本 | |
| 入れるもの | `README.txt`、`doc/GPL.txt`、`doc/ymfm-LICENSE.txt` | 帰属表示とライセンス文。検査の必須項目 |
| 入れないもの | リズム ROM | 再配布してよいという根拠が確かめられない（「upstream の Makoto（PR #2209）」を参照）。zip の全ファイルの SHA1 がリズム ROM と一致しないことを検査する |

**ソースアーカイブから `doc/fork/` を外す。** `main` と同じ `export-ignore` の行を
`.gitattributes` に置いた（`main` と行まで揃えてあるので、統合しても衝突しない）。
`21.0-makoto.1` はこの変更の前のコミットなので、そのソースアーカイブには
`doc/fork/makoto/` が入っている。次のリリースから外れる。

## 実行経緯

### 2026-09-22

- `makoto` ブランチを upstream/master（`a5450eb92`）から作成
- ymfm を取り込み、`YM2608` と `MSXMakoto` を実装。拡張 XML と検証スクリプトを追加
- **Release ビルドが通ることを確認（確認済み）**。`main` のビルド済み成果物からの
  差分ビルドで 0 エラー / 125 警告 / 14 分 48 秒。新しく書いた `YM2608.cc` と
  `MSXMakoto.cc` の警告は 0。ymfm からは C4100（未使用の引数）などが出る
- **`smoke.tcl` が全項目通ることを確認（確認済み）**。`failures 0`。
  ウィンドウが出ないことも確認した（`MainWindowHandle` を 0.5 秒おきに 4 回とって、
  すべて 0）
  - BRDY の項目は、`110h` を書く前は 8 回とも 0 で落ちていた。
    この項目は壊れていれば落ちることになる
  - 読み出しの項目は、RAM の初期値 `FFh` と違う値の並びを比べている。
    読み出しの経路が壊れていれば一致しない
- 上の「ymfm の挙動」の 1〜3 を走らせて確かめた
- **未検証**: タイマー A の IRQ が CPU に届くこと。ステータス0 のフラグが立つことと、
  `27h` で消えることまでは確かめた
- ~~**未検証**: リズム ROM を与えたときの発音。ROM が手元に無い~~ → 下で確認済み
- **未検証**: セーブステートの保存と読み込み
- 専用のデプロイ先へ zip（750 ファイル）を展開。展開した `openmsx.exe` がビルドしたものと
  同一であることを `cmp` で確認。**デプロイ先の exe と `share/` で `smoke.tcl` が全項目
  通ることを確認（確認済み）**。`failures 0`、ウィンドウは出ていない
- 3 コミットに分けてコミット。`main` の `check-before-push.sh` を範囲だけ
  `upstream/master..HEAD` に替えて走らせ、1〜4（著者、trailer、ローカル固有の文字列、
  作業ツリー）が通ることを確認（確認済み）。5 と 6 はこのブランチに
  `upstream-touched.txt` と `check-docs.py` が無いので NG になる。5 が挙げた
  変更済みの upstream のファイルは `DeviceFactory.cc`、`src/meson.build`、
  `build/msvc/openmsx.vcxproj(.filters)` の 4 つで、上の「統合する場合の値段」と一致する
- リズム ROM の扱いを決めた（上の「リズム ROM は SHA1 で…」）。`README` に
  エンドユーザー向けの節を足した
- **リズム ROM を `systemroms` に置くと SHA1 で見つかり、リズム音が鳴ることを確認
  （確認済み）**。`tests/rhythm.tcl` でバスドラムを鳴らし、チャンネル 1 を 0.3 秒
  録音した。振幅の最大値は ROM ありで 15284、ROM 無しで 12。ROM 無しでも起動は
  終了コード 0。使い捨てのユーザーデータを 2 つ作り、片方の `systemroms` にだけ
  ROM を複製して比べた
- **`21.0-makoto.1` を Pre-release として公開**。対象は `736b65cb4`
  - `-t:Rebuild` で全体をビルドし直した。0 エラー / 141 警告 / 44 分 33 秒。
    `LNK4286` は 0 件
  - zip は 751 エントリ。`doc/fork/` が無いこと、`README.txt`・`openmsx.exe`・
    `share/extensions/Makoto.xml`・`doc/GPL.txt` があること、リズム ROM と同じ SHA1 の
    ファイルが無いことを検査した
  - **zip を `derived/` の下に展開し、そのバイナリで確認（確認済み）**。
    `OPENMSX_SYSTEM_DATA` を外し、ユーザーデータは使い捨て。`smoke.tcl` は
    `failures 0`、`rhythm.tcl` の振幅の最大値は ROM 無しで 12、ROM ありで 15284。
    ウィンドウは出ていない
  - ドラフトで作り、Pre-release・対象コミット・添付の大きさ（8,287,633 バイト）が
    手元と一致することを見てから公開した。タグが lightweight であることを
    `git cat-file -t` で確認
- `.gitattributes` に `main` と同じ `export-ignore` の行を足した。`git archive` で
  `doc/fork/` の項目が 0 件になることを確認（確認済み）。変更前のコミット
  （`736b65cb4`）では 6 件出るので、この確かめ方は違いを見分けられる
- GitHub が生成するアーカイブ（`gh api repos/.../tarball/<SHA>`）でも確認（確認済み）。
  `9afaabd86` では `doc/fork/` が 0 件、`736b65cb4` では 5 件。どちらにも
  `src/sound/YM2608.cc` は入っている
- `21.0-makoto.1` の zip に ymfm のライセンス文が入っていないことが分かった。
  ユーザー判断で、`21.0-makoto.2` を出して `.1` はドラフトに戻す。
  zip の作成をスクリプトにしてリポジトリに入れ、ライセンス文を必須項目にした
  （上の「リリース」）。README の Credits から同梱先を指すようにした
- **`21.0-makoto.2` を Pre-release として公開**。対象は `a7525c0b5`
  - `-t:Rebuild` で 0 エラー / 141 警告 / 37 分 38 秒。`LNK4286` は 0 件
  - `package-release.py` で zip を作成（752 エントリ、検査 OK）。
    `doc/ymfm-LICENSE.txt` が `src/3rdparty/ymfm/LICENSE` と同一であることを確認
  - **展開した zip で確認（確認済み）**。`smoke.tcl` は `failures 0`、`rhythm.tcl` は
    ROM 無しで 12、ROM ありで 15284。ウィンドウは出ていない
  - ドラフトで作って中身を見てから公開。タグは lightweight（`git cat-file -t` が `commit`）
- `21.0-makoto.1` をドラフトに戻した。タグ `21.0-makoto.1` はリモートに残っている

### 2026-09-29

- upstream に Makoto の PR #2209 があることを知り、このブランチと比べた
  （上の「upstream の Makoto（PR #2209）」）。リズム ROM の SHA1 が、PR が内蔵している
  libvgm の再構成データ（GPL-2.0-or-later）の SHA1 と一致した
- ユーザーの承認を得て、PR にサンプル RAM と ymfm の挙動 1〜3 についてコメントした
- リズム ROM は引き続き同梱しないと決めた（ユーザー判断）。`src/sound/YM2608.cc` の
  コメントにあった、配らない理由（「著作物だから」）を同じ理由に書き直した

### 2026-09-30

- PR #2209 のその後のレビューを読んだ。サンプル RAM の件は Wouter が作者に取り込みを
  頼んだ。PR の head は `6db5b2a64` のまま
- 生成レートごとの CPU 負荷を測った（上の「生成レートの負荷」）。`tests/bench.tcl` を追加
- ユーザーの承認を得て `makoto` を push し、測定結果を PR に投稿した
- Wouter が ZOH と 1MHz の負荷について懸念を書き、FM+ADPCM と SSG を実レートの
  2 本に分ける案を出した。ユーザーの指示でこれを `makoto-native-rate` ブランチで
  試作した（上の「Wouter の実レート案の試作」）。`makoto` と配布物は変えていない
- ユーザーから、SSG を openMSX の既存の PSG（`AY8910`）に置き換える案が出た。
  ymfm には SSG を外部の実装に差し替える `ssg_override` がある。ただし `AY8910` は
  クロックが MSX の値（3579545÷2）で固定されていて、プリスケーラ 6 の 2MHz にも、
  プリスケーラによる切り替えにも合わない。クロックを設定できるようにする変更が
  upstream のファイルに要る。**未着手**
