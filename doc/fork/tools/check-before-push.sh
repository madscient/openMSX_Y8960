#!/bin/sh
# push する前の点検。fork に push したオブジェクトは親リポジトリから
# SHA で辿れて後から消せないので、出す前に見る。
#
#   sh doc/fork/tools/check-before-push.sh
#
# 終了コード 0 なら push してよい。
#
# 探す語をこのファイルに書かないこと。ユーザー名・マシン名・ROM の置き場所は
# まさに漏らしたくないものであり、検査器に平文で書けば検査器が漏洩源になる。
# 実行時に環境とジャンクションのリンク先から組み立てる。
# 副産物として、どのマシンでも書き換えずに効く。

set -u
fail=0
range="origin/main..HEAD"
paths="CLAUDE.md README doc src share build"

echo "== 1. 著者とコミッタ =="
ids=$(git log --format='%an <%ae>%n%cn <%ce>' $range | sort -u)
if [ -z "$ids" ]; then
	echo "  push するコミットが無い"
else
	echo "$ids" | sed 's/^/  /'
fi

echo "== 2. コミットメッセージの trailer =="
if git log --format='%b' $range | grep -i "example.invalid"; then
	echo "  NG: 不正な trailer"
	fail=1
else
	echo "  OK"
fi

echo "== 3-1. ローカル固有の文字列（環境から導出、固定文字列で照合）=="
fixed=""
add_fixed() {
	# 短すぎる語は一般語に当たるので採らない
	[ ${#1} -ge 5 ] && fixed="$fixed -e $1"
}
add_fixed "${USERNAME:-}"
add_fixed "${USER:-}"
add_fixed "${COMPUTERNAME:-}"

# ROM の置き場所はジャンクションのリンク先から取る。区切りは両方の形で見る。
romlink="derived/openmsx-user/systemroms/local"
if [ -e "$romlink" ]; then
	romdir=$(python -c "import os,sys;print(os.path.realpath(sys.argv[1]))" "$romlink" 2>/dev/null)
	if [ -n "${romdir:-}" ]; then
		add_fixed "$romdir"
		add_fixed "$(printf '%s' "$romdir" | tr '\\' '/')"
	fi
fi

if [ -z "$fixed" ]; then
	echo "  導出できた語が無い（環境変数もジャンクションも見つからない）"
elif git grep -I -n -i -F $fixed -- $paths 2>/dev/null; then
	echo "  NG: ローカル固有の文字列が混ざっている"
	fail=1
else
	echo "  OK"
fi

echo "== 3-2. ホームディレクトリの絶対パス（一般形）=="
# 3-1 は今のマシンの語しか知らないので、別マシンで書かれたものは捕まらない。
# 誰の名前も要らない形で網を張っておく。
#
# Program Files のような標準の導入先は個人情報を含まないので対象にしない。
# 対象はこのフォークが書いた場所だけ。upstream の doc/manual には
# 説明のためのホームディレクトリ例があり、それは事故ではない。
#
# 説明文に例示パスを書かないこと。検査器が自分に当たる。
if git grep -I -n -i -e ":[/\]Users[/\]" \
	-- CLAUDE.md README doc/fork src share build 2>/dev/null; then
	echo "  NG: ホームディレクトリの絶対パスが混ざっている"
	fail=1
else
	echo "  OK"
fi

echo "== 4. 作業ツリー =="
if [ -n "$(git status --porcelain)" ]; then
	git status --short | sed 's/^/  /'
	echo "  NG: 未コミットの変更がある"
	fail=1
else
	echo "  OK"
fi

echo "== 5. 文書の整合 =="
if python doc/fork/tools/check-docs.py; then
	:
else
	fail=1
fi

echo
if [ $fail -eq 0 ]; then
	echo "OK: push してよい"
else
	echo "NG: 上を直してから push する"
fi
exit $fail
