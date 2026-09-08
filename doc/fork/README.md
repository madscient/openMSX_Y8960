# doc/fork — このフォーク固有の文書

本リポジトリは upstream の openMSX (https://github.com/openMSX/openMSX) の
unofficial fork である。ここには upstream に存在しない、このフォークの
作業に関する文書を置く。

対象読者は開発者。エンドユーザー向けではないので、
`doc/node.mk` の `INSTALL_DOCS` に載せておらず、インストールもされない。

作業時に守る規則は `CLAUDE.md` にまとめてある。

## 文書一覧

| パス | 内容 |
|---|---|
| `CLAUDE.md` | 作業時の規則（ライセンス制約、文書の置き場所、記録の作法） |
| `y8960/` | Y8960 カートリッジのエミュレーション実装 |
| `y8960/hardware-notes.md` | Y8960 のハードウェア仕様の調査結果。出典と確度つき |
| `y8960/implementation-plan.md` | 実装計画・決定・実行経緯 |
| `y8960/tests/` | 手で回す検証スクリプト |
| `build/README.md` | このマシンでのビルド環境。詰まりどころと手順 |

## upstream との関係

| | |
|---|---|
| upstream | https://github.com/openMSX/openMSX |
| 分岐の起点 | `master`（upstream 追従用にそのまま置いてある） |
| 作業ブランチ | `y8960` |
| ライセンス | GPL-2.0-only（upstream と同じ） |

upstream の文書で変更しているのはルートの `README` だけ。
それ以外の変更はコードとビルド定義に限られる。

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
| SSG ×2 | 実装済み（openMSX の `PSG` に `chip_select` を追加） |
| DCSG ×2 | 実装済み（`SNPSG` をそのまま、7Eh / 7Fh） |
| OPLL ×2 | 実装済み（チャンネル別音色バンク付き YM2413） |
| SCC + マッパー | 実装済み（ROM 種別 `Y8960`） |
| MSX-TIMER | 実装済み |
| デジタルミキサー | 実装済み |
| I/O Enabler (7FF6h) | OPLL 分のみ実装済み |
| **OPL2 + ADPCM-B ×2** | **未実装** |
| I/O Enabler2 (7FFFh) | 未実装 |

詳細と残作業は `y8960/implementation-plan.md`。
