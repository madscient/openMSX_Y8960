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

# フォークが自分で書いたもの。全文を見てよい。
ownpaths="CLAUDE.md doc/fork"

# push する差分の追加行を "ファイル: 内容" で出す。
#
# 作業ツリー全体を見ると upstream のファイルまで対象に入る。そこには
# 導出した語にたまたま部分一致する英文があり、こちらが書いていない行で
# 止まる。範囲を出す差分に絞れば、当たった行は必ず自分が足した行になる。
added_lines() {
	git diff -U0 $range -- $paths | awk '
		/^\+\+\+ /{ f = substr($0, 7); next }
		/^\+/{ print f ": " substr($0, 2) }
	'
}

# 追加行の照合を grep ではなく awk で行う。Git for Windows の grep は
# -i と -F を併用すると UTF-8 の入力で異常終了する（-F 単独なら通る）。
# git grep は自前実装なので影響を受けない。
# 語は小文字で渡すこと。突き合わせは tolower() で行う。
match_terms() {
	awk -v terms="$1" '
		BEGIN { n = split(terms, t, " ") }
		{
			low = tolower($0)
			for (i = 1; i <= n; i++) if (index(low, t[i])) { print; next }
		}
	'
}

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
terms=""
add_fixed() {
	# 短すぎる語は一般語に当たるので採らない
	[ ${#1} -ge 5 ] || return 0
	fixed="$fixed -e $1"
	terms="$terms $(printf '%s' "$1" | tr 'A-Z' 'a-z')"
}
add_fixed "${USERNAME:-}"
add_fixed "${USER:-}"
add_fixed "${COMPUTERNAME:-}"

# ROM の置き場所はジャンクションのリンク先から取る。区切りは両方の形で見る。
# リンクは名前を決め打ちにせず systemroms 直下を全部見る。ROM 置き場は
# 複数あることがあり、名前を 1 つに固定すると足したリンクを見落とす。
for romlink in derived/openmsx-user/systemroms/*; do
	[ -e "$romlink" ] || continue
	romdir=$(python -c "import os,sys;print(os.path.realpath(sys.argv[1]))" "$romlink" 2>/dev/null)
	[ -n "${romdir:-}" ] || continue
	add_fixed "$romdir"
	add_fixed "$(printf '%s' "$romdir" | tr '\\' '/')"
done

if [ -z "$fixed" ]; then
	echo "  導出できた語が無い（環境変数もジャンクションも見つからない）"
else
	hits=$(
		{
			added_lines | match_terms "$terms"
			git grep -I -n -i -F $fixed -- $ownpaths 2>/dev/null
		} 2>/dev/null
	)
	if [ -n "$hits" ]; then
		printf '%s\n' "$hits" | sed 's/^/  /'
		echo "  NG: ローカル固有の文字列が混ざっている"
		fail=1
	else
		echo "  OK"
	fi
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
homehits=$(
	{
		added_lines | awk 'tolower($0) ~ /:[\/\\]users[\/\\]/'
		git grep -I -n -i -e ":[/\]Users[/\]" -- $ownpaths 2>/dev/null
	} 2>/dev/null
)
if [ -n "$homehits" ]; then
	printf '%s\n' "$homehits" | sed 's/^/  /'
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
