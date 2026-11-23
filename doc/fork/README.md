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
| `y8960/` | Y8960 カートリッジの調査、試験、計画。実装は upstream のもの（下の「Y8960 の実装」） |
| `y8960/hardware-notes.md` | Y8960 のハードウェア仕様の調査結果。出典と確度つき |
| `y8960/implementation-plan.md` | 実装計画・決定・実行経緯 |
| `y8960/tests/` | 手で回す検証スクリプト |
| `makoto/README.md` | Makoto（YM2608）の独自実装を持っていた間に分かったこと。実装は upstream のものを使う |
| `build/README.md` | ビルド環境。マシンごとの詰まりどころと手順 |
| `release/README.md` | GitHub Releases に出すときの決まりと手順 |
| `retrospective.md` | 振り返り。失敗の原因と、入れた対策 |
| `tools/` | push 前点検、文書整合の検査、リリース用 zip の作成スクリプト。`y8960-pr-*` は、フォーク独自の実装を最初の PR の段に分けて組んだスクリプトで、その実装が在る `main`（下の「Y8960 の実装」のマージより前）でだけ動く |
| `upstream-touched.txt` | 変更してよい upstream のファイルの一覧と理由。点検器が突き合わせる |
| `LICENSE` | 道具（スクリプトと、それが読む音列）のライセンス。MIT。例外と対象外の文書は冒頭に書いてある |

## upstream との関係

| | |
|---|---|
| upstream | https://github.com/openMSX/openMSX（remote 名 `upstream`） |
| 作業ブランチ | `main` |
| `origin/master` | 分岐の起点の記録。追従には使わない |
| ライセンス | GPL-2.0-only（upstream と同じ） |

upstream のファイルで変更しているのは、ルートの `README` と `.gitattributes`
（本ディレクトリと `CLAUDE.md` をソースアーカイブから外す）、それに上流への PR に出す直しを
先に持つ `src/memory/Y8960Cartridge.cc` と `src/sound/Y8950Adpcm.cc`。ほかのコードとビルド定義は upstream と同じ。
一覧は `upstream-touched.txt`。

### 追従はマージで行う

`main` には upstream の `master` をマージで取り込む。`main` の履歴は書き換えないので、
`origin/main` へは通常の push で進み、記録に書いた SHA は `main` から辿れ続ける。

理由は、フォークの変更が upstream のコードに無いこと。重なりうるのはルートの `README` と
`.gitattributes` だけで、取り込みはほとんどの回で衝突しない。リベースにすると、
そのたびに force-push と、ほかのマシンの手元の合わせ直しが要る。

**前提**: フォークが upstream のコードを変えない限り成立する。変えるようになったら、
衝突の解き方とあわせて見直す。

```sh
git fetch upstream master

# 取り込む前に衝突を見る。1 行目はマージ結果のツリー。衝突があれば 2 行目から
# そのファイル名が出て、終了コードが 1 になる
git merge-tree --write-tree --name-only main upstream/master

git merge upstream/master

# フォークの差が想定どおりか。doc/fork/ を除いて CLAUDE.md・README・.gitattributes の 3 つだけが出ること
git diff --name-only upstream/master main | grep -v '^doc/fork/'
```

push の前に `doc/fork/tools/check-before-push.sh` を通すこと。

**取り込んだらビルドし直す。** upstream が触ったファイルによっては再ビルドの範囲が
広い。手順は `doc/fork/build/README.md`。

### upstream のタグは取り込まない

upstream の `RELEASE_xx_x` は annotated タグで、ローカルに在ると `git describe` が
成功し、exe の版表示が `<版>-unknown`（`<版>` は `build/version.py` の `packageVersionNumber`）の
形でなくなる（`doc/fork/release/README.md` §1）。

| fetch の形 | upstream のタグ |
|---|---|
| `git fetch upstream master`（ブランチ名を付ける） | 取らない |
| `git fetch upstream`（ブランチ名なし） | 取る。全ブランチのリモート追跡ブランチも作る |
| `remote.upstream.tagOpt` を `--no-tags` にした上での `git fetch upstream` | 取らない |

（**確認済み**: git 2.52 で、設定の無いリモートに `git fetch --dry-run` を 3 通り走らせ、
`[new tag]` の行が出るかを見た）

クローンを作ったら、一度 `git config remote.upstream.tagOpt --no-tags` を設定しておく。
この設定はクローンごとで、リポジトリには入らない。設定の無いクローンで取り込んで
しまったことは、`check-before-push.sh` の 7 が `git describe` の成功で知らせる。

## 外部リポジトリ

本リポジトリには取り込んでいない情報源。

| リポジトリ | 役割 | 扱い |
|---|---|---|
| [hra1129/Y8960_Cartridge](https://github.com/hra1129/Y8960_Cartridge) | Y8960 の**一次仕様**（FPGA RTL + docx/xlsx）。WIP | 仕様の参照元。**コードもデータも取り込まない**（非商用ライセンスで GPL と非互換） |
| [buppu3/openMSX](https://github.com/buppu3/openMSX) | `y8960` ブランチに Y8960 実装。GPL | Y8960 分の 15 コミットを cherry-pick し、フォーク独自の実装の土台にした（履歴に残っているのは 14 件。1 件は取り消した変更で、追従のときに空になった）。今の `main` のコードには残っていない。MSX-TIMER は upstream の `Y8960Cartridge` に `Co-authored-by` 付きで入った。V9968 は取り込んでいない |
| [madscient/Y8960emu](https://github.com/madscient/Y8960emu) | OPLLEX / OPL2EX の別実装（ymfm ベース）。MIT | 設計の参照と挙動の突き合わせ用。コアは移植しない |
| [madscient/EPSGemuEngine](https://github.com/madscient/EPSGemuEngine) | SSG/EPSG の別実装。MIT + BSD-3 | 参照のみ |

## Y8960 の実装

実装は upstream のもの。ROM 種別 `Y8960Cartridge`（`src/memory/Y8960Cartridge.{hh,cc}`）が
マッパー、SCC、ミキサー、各音源、MSX-TIMER、System Controller を持ち、OPLL は `YM2413` の
`Type::Y8960`（`src/sound/YM2413NukeYKT.*`）を使う。拡張は `share/extensions/HRA_Y8960.xml`。

フォーク独自の実装（音源ごとのデバイスと ROM 種別 `Y8960`）は、upstream を取り込んだ
マージ `ff829bc46` の 1 番目の親 `5b23a057b` までの `main` にある。外から見える違い:

- OPLL のバンク 1〜3（OPLL-X・OPLL-P・VRC7）の音色表は Nuked-OPLL のもの。ハードウェアの音色の
  出典は plgDavid の表（`y8960/hardware-notes.md` §6.2）なので、ハードウェアとは違う音になる
- 出力の切り替え（設定 `y8960-mixer_output`）が無い。本体の音は消さずに混ぜる
- デバイスは `Y8960Cartridge` の 1 つで、デバッガブルとプローブの名前が違う。試験が使う名前の
  対応は `y8960/tests/y8960-pr/runall.sh` の冒頭の置き換えにある

DCSG と、OPLL / OPL2 の 2 番目の回路は、2026-10-16 の仕様変更で無くなった。
本体内蔵版は別のハードウェアになるので、このフォークはカートリッジ版だけを扱う。

詳細と残作業は `y8960/implementation-plan.md`。
