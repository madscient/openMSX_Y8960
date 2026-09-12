# doc/fork — このフォーク固有の文書

本リポジトリは upstream の openMSX (https://github.com/openMSX/openMSX) の
unofficial fork である。ここには upstream に存在しない、このフォークの
作業に関する文書を置く。

対象読者は開発者。エンドユーザー向けではないので、
`doc/node.mk` の `INSTALL_DOCS` に載せておらず、インストールもされない。

作業時に守る規則はリポジトリのルートの `CLAUDE.md` にまとめてある。

## 文書一覧

| パス | 内容 |
|---|---|
| `y8960/` | Y8960 カートリッジのエミュレーション実装 |
| `y8960/hardware-notes.md` | Y8960 のハードウェア仕様の調査結果。出典と確度つき |
| `y8960/implementation-plan.md` | 実装計画・決定・実行経緯 |
| `y8960/tests/` | 手で回す検証スクリプト |
| `build/README.md` | ビルド環境。マシンごとの詰まりどころと手順 |
| `retrospective.md` | 振り返り。失敗の原因と、入れた対策 |
| `tools/` | push 前点検と文書整合の検査スクリプト |

## upstream との関係

| | |
|---|---|
| upstream | https://github.com/openMSX/openMSX（remote 名 `upstream`） |
| 作業ブランチ | `main` |
| `origin/master` | 分岐の起点の記録。追従には使わない |
| ライセンス | GPL-2.0-only（upstream と同じ） |

upstream の文書で変更しているのはルートの `README` だけ。
それ以外の変更はコードとビルド定義に限られる。

### 追従はリベースで行う

`main` は upstream のある一点の直系の子孫として保ち、マージコミットを作らない。
`main` が今どこに載っているかは `git merge-base main upstream/master` で取れるので、
この文書には書かない。

リベースを選ぶ理由は、**衝突する面を先に機械で判定できる**こと。upstream と
フォークがそれぞれ触ったファイルの集合を比べ、重なりが空ならリベースは黙って通る。
重なったときはリベースが衝突で止まるので、気づかないまま壊れる余地がない。

**前提**: フォークの変更が upstream の変更と別のファイルに収まる限り、この判定が
効く。同じファイルに入るようになったら、止まった衝突を手で解くことになる。

```sh
git fetch upstream master
base=$(git merge-base main upstream/master)

# 触ったファイルの重なりを見る。出力が空なら衝突しない
comm -12 <(git diff --name-only $base upstream/master | sort) \
         <(git diff --name-only $base main | sort)

git rebase --onto upstream/master $base main

# フォークのコミットがそのまま載ったか。全行が "=" になること
git range-diff $base..ORIG_HEAD upstream/master..main
```

載せ替えると `main` の履歴が変わるので、`origin/main` へは
`git push --force-with-lease origin main` で進める。
push の前に `doc/fork/tools/check-before-push.sh` を通すこと。

**載せ替えたらビルドし直す。** upstream が触ったファイルによっては再ビルドの範囲が
広い。手順は `doc/fork/build/README.md`。

## 外部リポジトリ

本リポジトリには取り込んでいない情報源。

| リポジトリ | 役割 | 扱い |
|---|---|---|
| [hra1129/Y8960_Cartridge](https://github.com/hra1129/Y8960_Cartridge) | Y8960 の**一次仕様**（FPGA RTL + docx/xlsx）。WIP | 仕様の参照元。**コードもデータも取り込まない**（非商用ライセンスで GPL と非互換） |
| [buppu3/openMSX](https://github.com/buppu3/openMSX) | `y8960` ブランチに Y8960 実装。GPL | Y8960 分の 15 コミットを cherry-pick 済み。V9968 は取り込んでいない |
| [madscient/Y8960emu](https://github.com/madscient/Y8960emu) | OPLLEX / OPL2EX の別実装（ymfm ベース）。MIT | 設計の参照と挙動の突き合わせ用。コアは移植しない |
| [madscient/EPSGemuEngine](https://github.com/madscient/EPSGemuEngine) | SSG/EPSG の別実装。MIT + BSD-3 | 参照のみ |

## Y8960 の実装状況

| ブロック | 状態 |
|---|---|
| SSGS (YMZ705/732 相当) ×1 | 実装済み。内部に YM2149 相当の SSG が 2 系統（計 6ch）+ チャンネルごとの 4bit パンポット。カートリッジ版はライトオンリー |
| DCSG ×2 | 実装済み（`SN76489` を載せた `Y8960-DCSG`、3Eh / 3Fh） |
| OPLL ×2 | 実装済み（チャンネル別音色バンク付き YM2413） |
| SCC + マッパー | 実装済み（ROM 種別 `Y8960`）。バンクメモリは RTL と差があり**保留中** |
| MSX-TIMER | 実装済み（B0h-B3h。hra1129 さん確定）。割り込みが CPU に届くことを実測済み |
| デジタルミキサー | 音源ごとの左右ゲインと全体の左右ゲインの器のみ。**B6h-B7h はゲインに繋いでいない**（レジスタアレイの中身が未定のため） |
| 出力の切り替え | 実装済み。`y8960-mixer_output` で y8960 / msx / mix |
| OPL2 + ADPCM-B ×2 | 実装済み（OPL2 波形選択つき）。ADPCM の発音を実測済み |
| I/O Enabler (7FF6h) | 実装済み（OPLL 用の 2 ビット） |
| I/O Enabler2 (7FFFh) | 実装済み（OPL2 b0/b1、DCSG b2/b3、SSGS b4、タイマー b7） |
| メモリマップド I/O のトンネル | 実装済み（7FEAh-7FF5h。窓を `rammode` で閉じるのは未実装） |
| カートリッジ版 / 本体内蔵版の切り替え | 実装済み（I/O イネーブラー、MMIO トンネル、SSGS のリード、SSGS の GPIO の 4 点） |

詳細と残作業は `y8960/implementation-plan.md`。
