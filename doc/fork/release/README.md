# リリース

GitHub の Releases にこのフォークのビルドを出すための決まりと手順。
対象読者は開発者。

## 1. 決めたこと（2026-09-15）

| 項目 | 値 | 理由と前提 |
|---|---|---|
| タグ名 | `<upstream の版>-y8960.<n>`。初回は `21.0-y8960.1` | ユーザー判断。upstream の `RELEASE_xx_x` と衝突しない。`<upstream の版>` は `build/version.py` の `packageVersionNumber`。`main` は 21.0 以降の開発版に載っているので、厳密には 21.0 そのものではない |
| タグの種類 | **lightweight**（`gh release create` に作らせる） | annotated にすると `git describe` に拾われ、`build/version.py` が `y8960.1` から数字を取れずに例外で止まる（**確認済み**: 使い捨てリポジトリで annotated タグを付けて `git describe` が `21.0-y8960.1` を返すことを見て、その文字列を `extractGitRevision` / `extractNumberFromGitRevision` と同じ正規表現に通した）。lightweight なら describe は失敗し、ビルドは `unknown` で通る（**確認済み**: 同じリポジトリで lightweight タグを付けて describe が終了コード 128） |
| exe の版表示 | 触らない。`21.0-unknown` になる | ユーザー判断。`build/version.py` に接尾辞を足すと、upstream が版を上げるたびに同じ行でリベースが衝突する。**前提**: `git describe` が失敗する限り成立する。つまり、フォークのタグに annotated を使わず、upstream の annotated タグ（`RELEASE_21_0` など）もローカルに取り込まないこと。upstream のタグが見えると版表示は `21.0-<数>-g<hash>` の形になる（**確認済み**: upstream のタグを取り込んだクローンで `git describe --dirty` が返した `RELEASE_21_0-530-g…` を、`extractGitRevision` / `extractNumberFromGitRevision` と同じ正規表現に通した。ビルドはしていない）。取り込まないための設定は `doc/fork/README.md` の「upstream のタグは取り込まない」。取り込んでしまったことは `check-before-push.sh` の 7 が知らせる |
| 種別 | Pre-release | ユーザー判断。ハードウェア自体が WIP で挙動が変わる前提 |
| リリースノート | 英語 | ユーザー判断。ルートの `README` と揃える |
| 配布物 | Windows x64 のバイナリ zip 1 本 | このフォークでビルド実績があるのが Windows x64 だけ |
| 入れないもの | `CLAUDE.md` と `doc/fork/` | ユーザー判断（開発者・AI 向けの文書）。下の §2 |

### 見送ったもの

- **MSI** — 見送った。理由: WiX が要り、このフォークで試していない。
  足すなら `build/package-windows/packagemsi.py` を使う
- **pdb の zip** — 見送った。理由: pdb が 120MB を超え、利用者の多くには要らない。
  クラッシュ報告を受けるようになったら付ける。`packagezip.py` が
  `derived/x64-VC-Release/package-windows/` に作るので、やり直しは添付 1 つ

### 2026-10-12 に決めたこと

- **Makoto（YM2608 カートリッジ）だけを載せた版は、このフォークからは出さない**
  （ユーザー判断）。Makoto は upstream に入ったので、`main` のビルドにそのまま含まれる。
  以前の `21.0-makoto.1` と `21.0-makoto.2` は消してある
- **次のリリース（`21.0-y8960.2`）は、upstream の issue #2238 の返事を待ってから出す**
  （ユーザー判断）。upstream の Makoto は YM2608 のリズム音のデータをソースに内蔵していて、
  ビルドすればバイナリにも入る。このデータを配ってよいかを upstream に尋ねている
  （https://github.com/openMSX/openMSX/issues/2238 。経緯は `doc/fork/makoto/README.md` の §5）。
  ソースは upstream をそのまま運ぶものとして、`main` に push してある。
  **前提**: 返事が出るまでの判断。返事の内容によって、そのまま出すか、データを外して
  出すかを決め直す。外す場合の値段は調べていない
  - 返事は「外部 ROM として扱う PR を出してくれれば取り込む」で、その PR を出した
    （https://github.com/openMSX/openMSX/pull/2239 ）。取り込まれた後に追従すれば、
    データはこのフォークのソースとバイナリからも外れる。リリースはそれを待つ
  - 2026-10-12 に取り込まれた（upstream の `c596782ad`）。2026-10-13 に `main` を追従させた
    （`doc/fork/y8960/implementation-plan.md` §8）。データはこのフォークのソースからも外れた

## 2. 開発文書を配布物から外す仕組み

配布物は 2 種類あり、外す仕組みが違う。

| 配布物 | 仕組み |
|---|---|
| バイナリ zip | upstream の `packagezip.py` は `doc/node.mk` の `INSTALL_DOCS` と `doc/manual` しか入れないので、元々入らない。`doc/fork/tools/package-release.py` が出来た zip の中身を検査し、入っていたら失敗する |
| ソースアーカイブ | GitHub がタグから自動で作る。ルートの `.gitattributes` に `export-ignore` を書いてある |

**`.gitattributes` の効き目は GitHub 側で確かめる。** `git archive` での確認は
手元の git の挙動であって、GitHub のアーカイブ生成が同じ属性を読む保証ではない。
§3 の手順 6 で毎回見る。

## 3. 手順

リポジトリのルートで行う。ビルドの詳細は `doc/fork/build/README.md`。

1. `sh doc/fork/tools/check-before-push.sh` を通し、`main` を push する
2. **`-t:Rebuild` で**全体をビルドし直す。インクリメンタルビルドは
   `MSB8065`（カスタムビルドの出力が作られていない）の警告を出したまま
   何もコンパイルせずに終わることがあり、exe がコミットと一致する保証にならない
3. `py doc/fork/tools/package-release.py <タグ名>`
4. 配布物そのものでスモークテストをする。zip を `derived/` の下に展開し、
   `OPENMSX_SYSTEM_DATA` を外して `OPENMSX_USER_DATA` を使い捨ての場所に向ける。
   `-testconfig -machine C-BIOS_MSX2+ -ext HRA_Y8960` が終了コード 0 で、
   `doc/fork/y8960/tests/` のテストも通ること。
   深いディレクトリに展開すると、C-BIOS の長いファイル名が Windows のパス長の
   上限に当たって展開が落ちる
5. リリースをドラフトで作る。タグは付けずに `--target` でコミットを指し、
   公開時に GitHub に作らせる。**`--target` は完全な SHA で渡す。**
   短縮形は `target_commitish is invalid` で弾かれる

   ```sh
   gh release create <タグ名> --repo madscient/openMSX_Y8960 --draft \
     --target "$(git rev-parse <コミット>)" --prerelease --title "<タイトル>" \
     --notes-file <ノート> \
     derived/x64-VC-Release/package-windows/openmsx-<タグ名>-windows-vc-x64-bin.zip
   ```

   ノートを確かめてから `gh release edit <タグ名> --repo madscient/openMSX_Y8960 --draft=false` で公開する
6. ソースアーカイブを落として、`CLAUDE.md` と `doc/fork/` が無いことを見る
7. `git fetch origin tag <タグ名>` して `git cat-file -t <タグ名>` が `commit`
   （lightweight）であることを見る

## 4. 実行経緯

### 2026-09-15 — 21.0-y8960.1

- 手元の exe は最新コミットより前のビルドだった。インクリメンタルビルドは
  3 秒で何もせずに終わったので、`-t:Rebuild` にした（§3 の手順 2）
- ルートの `README` が実装に追いついていなかった（OPL2 を未実装と書いていた）。
  書き直した
- upstream の zip にはルートの `README` が入らず、CC BY-SA の帰属表示が
  配布物から落ちることが分かった。`package-release.py` で `README.txt` として足す
- `.gitattributes` の `export-ignore` を GitHub のアーカイブで確かめた
  （**確認済み**: push したコミットの tarball を API で取得し、`CLAUDE.md` と
  `doc/fork/` に当たるパスが 0 件。1 つ前のコミットの tarball では 37 件）
- `-t:Rebuild`: 0 エラー / 79 警告 / 25 分 04 秒、`LNK4286` 0 件
- `package-release.py` の検査が効くことを確かめた（**確認済み**: 禁止に
  `README.txt`、必須に実在しないファイルを差し込んで走らせ、両方 NG で終了コード 1、
  zip は消えた）。zip は 751 ファイル / 8,332,928 バイト
- 展開した zip でスモークテスト（**確認済み**）。`-testconfig` が終了コード 0
  （存在しない拡張を渡すと 1 になることも見た）。`adpcm-play.tcl` +
  `check-adpcm-play.py` が peak 5543 / 385.9Hz / 停止時 0 で、これまでの記録と同じ
- `gh release create` の `--target` に短縮 SHA を渡して 422 で弾かれた。
  完全な SHA でドラフトを作った（§3 の手順 5）
- ユーザーがドラフトを確認し、公開した。公開後に確かめたこと（すべて**確認済み**）
  - タグは lightweight: `git cat-file -t 21.0-y8960.1` が `commit`、指す先は `b62d5c56c`
  - タグのソースアーカイブ（zip と tar.gz の両方）に `CLAUDE.md` と `doc/fork/` が 0 件。
    `README` とソース、拡張の XML は入っている
  - Releases から落とした zip の sha256 が手元の zip と一致

### 2026-10-18 — 21.0-y8960.2

- 対象は `ce8fc1024`（ミキサーのマスター音量まで）。`main` と origin が一致していることを見てから進めた
- `-t:Rebuild`: 0 エラー / 83 警告 / 33 分 23 秒、`LNK4286` 0 件
- zip は 755 ファイル / 8,437,945 バイト。`CLAUDE.md` と `doc/fork/` は 0 件
- 展開した zip でスモークテスト（**確認済み**）。`-testconfig` が終了コード 0
  （存在しない拡張を渡すと 1）。`doc/fork/y8960/tests/` の 20 本がすべて期待どおりで、
  目で見るテスト 5 本の出力は開発用ビルドの出力とバイト単位で同一
- リリースノートは 1 版の構成から大きく変わったので書き直した。1 版向けのソフトは
  音源の構成とメモリマップド I/O の番地が変わったので直す必要がある、と明記した
- ドラフトを作ったところで止め（ユーザーの指示）、ユーザーの了承を得て公開した。公開後に確かめたこと
  （すべて**確認済み**）
  - タグは lightweight: `git cat-file -t 21.0-y8960.2` が `commit`、指す先は `ce8fc1024`
  - タグのソースアーカイブ（zip と tar.gz の両方。各 2543 ファイル）に `CLAUDE.md` と `doc/fork/` が 0 件。
    `README` と `HRA_Y8960.xml` は入っている。同じ数え方で `doc/manual/` は 20 件当たるので、0 件は
    パターンの書き損じではない
  - Releases から落とした zip の sha256 が手元の zip と一致

### 2026-10-21 — 21.0-y8960.3

- 対象は `e2286a505`（OPM の追加まで）。前回からの変更は SCC の定位、定位の値 0 を左端に、OPM。
  `main` を push し、origin と一致していることを見てから進めた
- `-t:Rebuild`: 0 エラー / 83 警告 / 31 分 09 秒、`LNK4286` 0 件
- zip は 755 ファイル / 8,445,904 バイト。sha256 は `0eae9a5f…5717`
- 展開した zip でスモークテスト（**確認済み**）。`-testconfig` が終了コード 0（存在しない拡張を渡すと 1）。
  `doc/fork/y8960/tests/` の 20 本がすべて期待どおりで、目で見るテスト 5 本の出力は開発用ビルドの出力と
  バイト単位で同一
- 既存拡張の `-testconfig` のうち `Panasonic_FS-CA1` だけが使い捨てのユーザーデータで 1 を返した。
  ROM が要る拡張で、ROM は開発用のユーザーデータにしか無い（**確認済み**: 同じ exe に開発用の
  ユーザーデータを与えると 0、前回の exe に使い捨てのユーザーデータを与えると 1）。配布物の問題ではない
- リリースノートは前回の構成を引き継ぎ、変更点と、OPM の busy を持たない制限を足した
- ドラフトを作ったところで止めた（ユーザーの指示は「リリース準備」）
- **ユーザーの指示で、リリースノートに基にしたハードウェアの版と差分を足した。** 基にしたのは
  hra1129/Y8960_Cartridge の v0.9.2（`hardware-notes.md` の冒頭の表）。差分として挙げたのは次の 9 つで、
  根拠はすべて `6437a0d` の RTL か `history.md` を読んだもの（**確認済み(読解)**）
  - MMIO の窓を常に出す / リセット直後に OPLL と SSG のポートが開いている（どちらも hra1129 さんが
    v0.9.2 の不具合と回答。`hardware-notes.md` §3、§7）
  - SCC の窓の出方と 7900h-7904h の定位 / BANK#63 の SCC の窓の外（未定義。v0.9.2 は FFh）
  - SSG の 2 系統目が A2h から読める（`dual_ssg.v` の `ssg_core1` が `builtin = 1'b1`）
  - OPM の書き込みキュー・`/WAIT`・busy
  - ROM と RAM を別の空間として持つこと。v0.9.2 が 256KB の 1 空間であることは `d6d16a3` で読んだもので、
    `6437a0d` では読み直していない（**推測**: その後の `history.md` にメモリの構成を変えた記録が無い）
  - System Controller（40h-4Fh、`device_id` 02h）を持たないこと、BIOS ROM を含まないこと
  - 音源のコアと、音源どうしの相対音量が RTL 由来でないこと
- 既知の制限から「実機が無い」を外し、「実機と比べていない」にした。v0.9.2 は FPGA に書き込まれている
  （`history.md` の 2026-10-20 23:12 の項）
- ルートの `README` の既知の制限は直していない。zip の `README.txt` は `e2286a505` の `README` なので、
  直すとリリースが指すコミットと食い違う
- ユーザーの了承を得て公開した。公開後に確かめたこと（すべて**確認済み**）
  - タグは lightweight: `git cat-file -t 21.0-y8960.3` が `commit`、指す先は `e2286a505`
  - タグのソースアーカイブ（zip と tar.gz の両方。ファイルだけを数えて各 2461 件）に `CLAUDE.md` と
    `doc/fork/` が 0 件。`README`、`HRA_Y8960.xml`、`Y8960OPMDevice` は入っている。同じ数え方で
    `doc/manual/` は 19 件当たるので、0 件はパターンの書き損じではない
  - Releases から落とした zip の sha256 が手元の zip と一致
