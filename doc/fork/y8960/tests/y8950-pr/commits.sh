#!/bin/sh
# usage: PR=<PR の worktree> WORK=<作業用> commits.sh <段> [<段> ...]
# 段ごとに、$WORK/snap-<段>/ のファイルを $PR/src/sound に置いてコミットし、コミットごとに組む。本文は $WORK/messages.txt の
# 「=== <段>」の節（split_msg.py が msg-<段>.txt に分ける）。exe は $WORK/exe/c<段>.exe に控える。
# 写しに入れるのは、どの段にも同じ組のファイル（変えないものは upstream のまま）。upstream に出すコミットなので trailer は付けない。
HERE=$(cd "$(dirname "$0")" && pwd)
cd "${PR:?}" || exit 99
py "$HERE/split_msg.py" "${WORK:?}/messages.txt" || exit 98
for x in "$@"; do
	files=$(cd "$WORK/snap-$x" && ls)
	for f in $files; do cp "$WORK/snap-$x/$f" "src/sound/$f" || exit 97; done
	for f in $files; do git add "src/sound/$f" || exit 96; done
	git commit -q -F "$WORK/msg-$x.txt" || { echo "commit $x failed"; exit 95; }
	git log --oneline -1
	sh "$HERE/build.sh" "$WORK/build-c$x.log"
	tail -1 "$WORK/build-c$x.log"
	tail -1 "$WORK/build-c$x.log" | grep -q '^exit=0 ' || { echo "build $x failed"; exit 94; }
	mkdir -p "$WORK/exe"
	cp derived/x64-VC-Release/install/openmsx.exe "$WORK/exe/c$x.exe" || exit 93
done
git status --short
echo DONE
