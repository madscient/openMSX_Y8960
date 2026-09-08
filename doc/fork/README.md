# doc/fork — このフォーク固有の文書

## このディレクトリの規則

本リポジトリは upstream の openMSX (https://github.com/openMSX/openMSX) の
unofficial fork である。

**フォーク固有の文書は `doc/fork/` 配下に置き、upstream の文書はなるべく触らない。**
`doc/` 直下や `doc/internal/` は upstream の文書が入る階層なので、そこには足さない。
こうしておくと upstream を取り込むときに衝突しないし、
どれがフォークの成果物かが階層だけで分かる。

`doc/fork/` の対象読者は開発者と AI であり、エンドユーザーではない。
`doc/node.mk` の `INSTALL_DOCS` に載せないので、インストールされない。

### 例外: ルートの `README`

**`README` だけは upstream のものに追記する。** GitHub のフロントページになるため、
ここに集約する理由がある。次の 2 つを置く。

- **フォークである旨** — upstream ではないこと、何が足してあるか、
  問題の報告先。これが無いと利用者が upstream と取り違える
- **帰属表示** — CC BY-SA の OPLL(x) 音色データなど、
  再頒布に伴って表示が要るもの。目に触れない場所に置くと意味がない

`doc/authors.txt` は upstream のクレジット一覧なので**触らない**。
フォーク側のクレジットは `README` に集める。

コードとビルド定義（`src/`, `build/`, `share/`）は、機能追加に必要な範囲で
upstream のファイルを変更する。ここは「なるべく触らない」の対象外。

## 内容

| ディレクトリ | 内容 |
|---|---|
| `y8960/` | Y8960 カートリッジのエミュレーション実装 |
| `build/` | このマシンでのビルド環境の構築手順と経緯 |

## 取り込んではいけないもの

openMSX は **GPL-2.0-only** である（`meson.build` の `license` 宣言）。
以下はライセンスが非互換なので、**コードもデータも本リポジトリに持ち込まない**。

- **hra1129/Y8960_Cartridge の FPGA ソースと図表**。
  そのライセンスは条項 3 で「書面による事前の許可なしに販売、および
  商業的な製品や活動に使用しないこと」を課している。
  非商用制限は GPL と両立しない。
  `y8960/hardware-notes.md` は**読解した事実の記述**であって、
  コードや文章の複製ではない。この線を越えないこと

帰属表示が要るものは README に書いてある。特に
`src/sound/YM2413NukeYKTBanked.cc` の OPLL-X / OPLL-P / VRC7 音色データは
"Copyright free OPLL(x) ROM patches" (David Viens / Hubert Lamontagne) 由来で、
CC BY-SA なので帰属表示を落とせない。**出所は確認済み**（2026-09-09）。
