# このフォークで作業するときの規則

本リポジトリは upstream の openMSX (https://github.com/openMSX/openMSX) の
unofficial fork である。**本書は upstream には無い、このフォーク固有のファイル。**
事実関係と文書の索引は `doc/fork/README.md` を見ること。

## 1. 持ち込んではいけないもの

openMSX は **GPL-2.0-only**（`meson.build` の `license` 宣言）。
次はライセンスが非互換なので、**コードもデータも取り込まない**。

- **hra1129/Y8960_Cartridge の FPGA ソースと図表。**
  そのライセンスは条項 3 で「書面による事前の許可なしに販売、および
  商業的な製品や活動に使用しないこと」を課している。
  非商用制限は GPL と両立しない

`doc/fork/y8960/hardware-notes.md` は**読解した事実の記述**であって、コードや文章の
複製ではない。仕様を参照するのは構わないが、この線を越えない。

## 2. 落としてはいけない帰属表示

`src/sound/YM2413NukeYKTBanked.cc` の OPLL-X / OPLL-P / VRC7 音色データは
"Copyright free OPLL(x) ROM patches" (David Viens / Hubert Lamontagne) 由来で、
**CC BY-SA なので帰属表示が要る**（出所は 2026-09-09 に確認済み）。
表示はルートの `README` にある。このファイルを整理するときも消さない。

## 3. 文書をどこに置くか

**フォーク固有の文書は `doc/fork/` 配下に置き、upstream の文書はなるべく触らない。**
`doc/` 直下や `doc/internal/` は upstream の文書が入る階層なので、そこには足さない。
upstream を取り込むときに衝突せず、どれがフォークの成果物かが階層で分かる。

- `CLAUDE.md`（本書、リポジトリのルート）— AI 向けの規則
- `doc/fork/README.md` — 人間向けの情報リソース。事実と索引
- `doc/fork/<主題>/` — 主題ごとの文書

### 例外: ルートの `README`

**`README` だけは upstream のものに追記する。** GitHub のフロントページであり、
ここに集約する理由がある。置くのは次の 2 つ。

- **フォークである旨** — upstream ではないこと、何が足してあるか、報告先。
  無いと利用者が upstream と取り違える
- **帰属表示**（§2）。目に触れない場所に置いても意味がない

`doc/authors.txt` は upstream のクレジット一覧なので**触らない**。
フォーク側のクレジットは `README` に集める。

コードとビルド定義（`src/`, `build/`, `share/`）は、機能追加に必要な範囲で
upstream のファイルを変更してよい。「なるべく触らない」の対象外。

## 4. 作業の記録

主題ごとに作業計画と実行経緯の文書を持ち、決定・却下・訂正はその都度書く。
Y8960 なら `doc/fork/y8960/implementation-plan.md`。口頭で終えない。

主張には確度を併記する。走らせて確かめたなら**確認済み**とその手段を、
作っただけなら**未検証**、出典を示せないなら**推測**と根拠を一行。

## 5. openMSX を走らせるとき

**ウィンドウを出さない。** テストやスモークテストで openmsx.exe を起動するときは、
Tcl スクリプトの**先頭**に必ず次の 2 行を置く。

```tcl
set renderer none
set sound_driver null
```

設定が効く前にウィンドウが作られてしまうので、位置が先頭であることに意味がある。

理由は、ウィンドウが出るとキーボード入力を奪い、**人間の並行作業と衝突して
事故になる**こと。実際にウィンドウが出ないことは、プロセスの MainWindowHandle が
0 になることで確認できる。`renderer none` でも `recordChannel` による WAV 録音は
成立するので、音を測るテストも書ける。

`-testconfig` は構成を検証して終了するだけなのでウィンドウを作らない。

## 6. ビルド

このマシン固有の詰まりどころが `doc/fork/build/README.md` にある。
msbuild には `-p:PlatformToolset=v145 -p:VcpkgEnabled=false` が要る。
理由もそちらに書いてある。
