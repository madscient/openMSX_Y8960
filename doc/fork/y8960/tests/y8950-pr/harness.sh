#!/bin/sh
# usage: PR=<PR の worktree> WORK=<作業用> harness.sh on|off
# Type::Y8960 を試すための差し込み。コミットしない。
#   on : $PR/src/sound/MSXAudio.cc を $WORK/MSXAudio.cc.orig に退避し、設定の <y8960test>true</y8960test> で
#        Type::Y8960 を選ぶように書き換える。$WORK/user/extensions/audio-y8960test.xml（デバイス名 "Y8960 test"）を書く
#   off: 退避のコピーから MSXAudio.cc を戻す（git checkout は使わない。ほかの未コミットの変更ごと消えるため）
# on の後に build.sh で組み、exe を控えてから off にする。
cd "${PR:?}" || exit 99
case "$1" in
on)
	cp src/sound/MSXAudio.cc "${WORK:?}/MSXAudio.cc.orig" || exit 98
	sed -i -b 's/getCurrentTime(), \*periphery, Y8950::Type::Y8950)/getCurrentTime(), *periphery, config.getChildDataAsBool("y8960test", false) ? Y8950::Type::Y8960 : Y8950::Type::Y8950)/' src/sound/MSXAudio.cc
	grep -q y8960test src/sound/MSXAudio.cc || { echo "patch did not apply"; exit 97; }
	mkdir -p "$WORK/user/extensions"
	sed 's/<MSX-AUDIO id="Generic MSX-Audio">/<MSX-AUDIO id="Y8960 test">\n      <y8960test>true<\/y8960test>/' share/extensions/audio.xml \
		> "$WORK/user/extensions/audio-y8960test.xml"
	echo "harness on"
	;;
off)
	cp "${WORK:?}/MSXAudio.cc.orig" src/sound/MSXAudio.cc || exit 96
	grep -q y8960test src/sound/MSXAudio.cc && { echo "restore failed"; exit 95; }
	echo "harness off"
	;;
*)
	echo "usage: harness.sh on|off"; exit 2
	;;
esac
