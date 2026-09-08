# Y8960 エミュレーション実装 — 文書の役割

Y8960 カートリッジのエミュレーションを openMSX に追加する作業のための文書。
Y8960 対応は upstream には存在しない独自機能である。

実装状況の一覧と外部リポジトリとの関係は `doc/fork/README.md`、
作業時の規則はルートの `CLAUDE.md` にある。

## 文書一覧

| 文書 | 役割 |
|---|---|
| `README.md` (本書) | 文書の役割の記録・索引 |
| `hardware-notes.md` | Y8960 ハードウェア仕様の調査結果。一次情報の出典と確度つき |
| `implementation-plan.md` | 実装計画・決定事項・実行経緯 |
| `tests/opll-enabler.tcl` | OPLL I/O Enabler (7FF6h) の回帰テスト |
| `tests/opl2-waveform.tcl` | OPL2 波形選択 (E0h-F5h) の回帰テスト。WAV を書き出す |
| `tests/check-opl2-waveform.py` | 上記 WAV の判定 |
| `tests/ssgs-panpot.tcl` | SSGS のパンポットと 2 系統の分離の回帰テスト |
| `tests/check-ssgs-panpot.py` | 上記 WAV の判定 |
| `tests/ssgs-write-only.tcl` | SSGS がリードに反応しないことの回帰テスト |

`implementation-plan.md` が作業計画と経緯を記録する文書である。
セッションをまたぐ引き継ぎ情報・見送った判断・訂正はすべてここに書く。

## 取り込み元

Y8960 の実装本体は buppu3/openMSX の `y8960` ブランチ由来で、
そのうち Y8960 分の 15 コミットを cherry-pick したもの（GPL、著者情報は保持）。
経緯は `implementation-plan.md` §3.0。

一次仕様である hra1129/Y8960_Cartridge からは**何も取り込んでいない**。
`hardware-notes.md` は RTL と仕様書を読解した結果の記述であって、複製ではない。
理由はルートの `CLAUDE.md` §1。
