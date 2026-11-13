#!/bin/sh
# Build stages <first>..<last> of the upstream PR branch for the Y8960
# (openMSX/openMSX#2288): per stage, write the files, commit, build, and
# check that the extension loads. Stops at the first failure.
#
#   sh <main>/doc/fork/tools/y8960-pr-run.sh <first> <last> <user data dir>
#
# Run from the root of the PR worktree, with the branch at stage <first>-1.
# <user data dir> needs the C-BIOS machines (see doc/fork/build/README.md).
# Logs go next to the worktree: ../pr-cNN-openmsx.log, ../pr-cNN-testconfig.log
#
# Setting the branch up, from the root of the fork's main worktree:
#   git worktree add -b y8960 derived/pr upstream/master
#   cp -r derived/3rdparty derived/pr/derived/3rdparty   # saves the download
#   cd derived/pr && git cherry-pick ae8c15509            # stage 1, buppu3's
#   sh ../../doc/fork/tools/y8960-pr-run.sh 2 10 <user data dir>
# Redoing from stage k after main changed: git reset --hard to the commit of
# stage k-1, then run k..10.
#
# -testconfig prints nothing when the extension fails to load, it only exits
# with 1. CLAUDE.md section 5 has how to get the message.
set -u
D=$(cd "$(dirname "$0")" && pwd)
USERDIR=$(cd "$3" && pwd)
EXE=derived/x64-VC-Release/install/openmsx.exe
PATH="$PATH:/c/Program Files (x86)/Microsoft Visual Studio/Installer"
MSBUILD=$(vswhere.exe -latest -products "*" -requires Microsoft.Component.MSBuild -find "MSBuild/**/Bin/MSBuild.exe" | head -1)
# The reasons for the toolset and vcpkg options are in doc/fork/build/README.md.
OPTS="-nologo -m -p:Configuration=Release -p:Platform=x64 -p:PlatformToolset=v145 -p:VcpkgEnabled=false"

if [ ! -d derived/x64-VC-Release/3rdParty ]; then
	"$MSBUILD" $OPTS build/3rdparty/3rdparty.sln > ../pr-3rdparty.log 2>&1
	r=$?
	echo "3rdparty exit=$r"
	[ $r -eq 0 ] || exit 1
fi

for k in $(seq "$1" "$2"); do
	kk=$(printf '%02d' "$k")
	echo "##### stage $k"
	python "$D/y8960-pr-stage.py" "$k" || exit 1
	git add -A src share build || exit 1
	git status --short
	python "$D/y8960-pr-stage.py" "$k" --message > ../pr-msg.txt || exit 1
	git commit -q -F ../pr-msg.txt || exit 1
	git log --format='%h %an | %s' -1
	# The build goes to a file, not a pipe, so that its exit code is the one seen.
	"$MSBUILD" $OPTS build/msvc/openmsx.sln > "../pr-c$kk-openmsx.log" 2>&1
	r=$?
	echo "openmsx exit=$r"
	[ $r -eq 0 ] || exit 1
	OPENMSX_SYSTEM_DATA="$(pwd)/share" OPENMSX_USER_DATA="$USERDIR" \
		timeout 120 "$EXE" -testconfig -machine C-BIOS_MSX2+ -ext HRA_Y8960 > "../pr-c$kk-testconfig.log" 2>&1
	r=$?
	echo "testconfig exit=$r"
	[ $r -eq 0 ] || exit 1
done
echo "all done"
