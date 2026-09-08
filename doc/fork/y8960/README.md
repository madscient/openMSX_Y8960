# Y8960 エミュレーション実装 — 文書の役割

このディレクトリは、Y8960 カートリッジのエミュレーションを openMSX に
追加する作業のための文書を置く。Y8960 対応は upstream には存在しない独自機能である。

ディレクトリの位置と対象読者の規則は `doc/fork/README.md` を参照。

## 文書一覧

| 文書 | 役割 | 対象読者 |
|---|---|---|
| `README.md` (本書) | 文書の役割の記録・索引 | 開発者/AI |
| `hardware-notes.md` | Y8960 ハードウェア仕様の調査結果。一次情報の出典と確度つき | 開発者/AI |
| `implementation-plan.md` | 実装計画・決定事項・実行経緯 | 開発者/AI |

`implementation-plan.md` が作業計画と経緯を記録する文書である。
セッションをまたぐ引き継ぎ情報・見送った判断はすべてここに書く。

## 外部リポジトリの位置づけ

以下は本リポジトリには取り込んでいない外部の情報源である。
文書もコードもコピーしていない（2026-09-08 時点）。

| リポジトリ | 役割 | 本作業での扱い |
|---|---|---|
| hra1129/Y8960_Cartridge | Y8960 の**一次仕様**（FPGA RTL + docx/xlsx 仕様書）。WIP | 仕様の参照元。`hardware-notes.md` に要約を転記 |
| madscient/Y8960emu | OPLLEX / OPL2EX の別実装（ymfm ベース、FmEngineApi DLL）。MIT | 設計の参照。コアは移植しない（理由は `implementation-plan.md`） |
| madscient/EPSGemuEngine | SSG/EPSG の別実装（MAME ay8910 ベース）。MIT + BSD-3 | 参照のみ。openMSX の `AY8910` を使うため移植しない |

コードを取り込む段になったら、取り込み元・版・ライセンスをこの表に追記すること。
