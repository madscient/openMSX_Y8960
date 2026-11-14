#!/bin/sh
# usage: PR=<PR の worktree の根> build.sh <ログの絶対パス>
# PR の worktree を Release で組む。終了コードは msbuild のもの。ログの最後の行に exit= と秒数を書く。
# ログは worktree の下か短いパスに置く（長いパスの下でのビルドは 260 字の制限で落ちる。doc/fork/build/README.md）。
cd "${PR:?set PR to the PR worktree}" || exit 99
PATH="$PATH:/c/Program Files (x86)/Microsoft Visual Studio/Installer"
MSBUILD=$(vswhere.exe -latest -products "*" -requires Microsoft.Component.MSBuild -find "MSBuild/**/Bin/MSBuild.exe" | head -1)
OPTS="-nologo -m -p:Configuration=Release -p:Platform=x64 -p:PlatformToolset=v145 -p:VcpkgEnabled=false"
start=$(date +%s)
"$MSBUILD" $OPTS build/msvc/openmsx.sln > "$1" 2>&1
rc=$?
end=$(date +%s)
echo "exit=$rc seconds=$((end - start))" >> "$1"
exit $rc
