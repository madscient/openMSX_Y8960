# doc/fork — このフォーク固有の文書

## このディレクトリの規則

本リポジトリは upstream の openMSX (https://github.com/openMSX/openMSX) の
unofficial fork である。

**upstream に存在しない、このフォーク固有の文書はすべて `doc/fork/` 配下に置く。**
`doc/` 直下や `doc/internal/` は upstream の文書が入る階層なので、そこには置かない。
こうしておくと upstream の変更を取り込むときに衝突しないし、
どれがフォークの成果物かが階層だけで分かる。

対象読者は開発者と AI であり、エンドユーザーではない。
`doc/node.mk` の `INSTALL_DOCS` に載せないので、インストールされない。

## 内容

| ディレクトリ | 内容 |
|---|---|
| `y8960/` | Y8960 カートリッジのエミュレーション実装 |
| `build/` | このマシンでのビルド環境の構築手順と経緯 |
