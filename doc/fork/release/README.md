# リリース

GitHub の Releases にこのフォークのビルドを出すための決まりと手順。
対象読者は開発者。

## 1. 決めたこと（2026-09-15）

| 項目 | 値 | 理由と前提 |
|---|---|---|
| タグ名 | `<upstream の版>-y8960.<n>`。初回は `21.0-y8960.1` | ユーザー判断。upstream の `RELEASE_xx_x` と衝突しない。`<upstream の版>` は `build/version.py` の `packageVersionNumber`。`main` は 21.0 以降の開発版に載っているので、厳密には 21.0 そのものではない |
| タグの種類 | **lightweight**（`gh release create` に作らせる） | annotated にすると `git describe` に拾われ、`build/version.py` が `y8960.1` から数字を取れずに例外で止まる（**確認済み**: 使い捨てリポジトリで annotated タグを付けて `git describe` が `21.0-y8960.1` を返すことを見て、その文字列を `extractGitRevision` / `extractNumberFromGitRevision` と同じ正規表現に通した）。lightweight なら describe は失敗し、ビルドは `unknown` で通る（**確認済み**: 同じリポジトリで lightweight タグを付けて describe が終了コード 128） |
| exe の版表示 | 触らない。`21.0-unknown` になる | ユーザー判断。`build/version.py` に接尾辞を足すと、upstream が版を上げるたびに同じ行でリベースが衝突する。**前提**: フォークのタグに annotated を使わない限り成立する |
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
3. スモークテスト。`-testconfig -machine C-BIOS_MSX2+ -ext HRA_Y8960` が終了コード 0
4. `py doc/fork/tools/package-release.py <タグ名>`
5. リリースを作る。タグは付けずに `--target` でコミットを指し、GitHub に作らせる

   ```sh
   gh release create <タグ名> --repo madscient/openMSX_Y8960 \
     --target <コミット SHA> --prerelease --title "<タイトル>" \
     --notes-file <ノート> \
     derived/x64-VC-Release/package-windows/openmsx-<タグ名>-windows-vc-x64-bin.zip
   ```

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
