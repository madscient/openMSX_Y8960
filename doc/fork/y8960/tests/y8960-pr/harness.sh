#!/bin/sh
# usage: PR=<PR worktree> WORK=<work dir> harness.sh on|off
# A hook to try YM2413::Type::Y8960 before any device uses it. Never committed.
#   on : saves $PR/src/sound/MSXMusic.cc as $WORK/MSXMusic.cc.orig and makes the
#        config's <y8960test>true</y8960test> pick Type::Y8960. Writes
#        $WORK/user/extensions/fmpac-y8960test.xml (device "Y8960 test").
#   off: puts MSXMusic.cc back from the saved copy (not git checkout, which
#        would also drop the uncommitted change under test)
# Build after "on", keep the exe, then "off".
cd "${PR:?}" || exit 99
case "$1" in
on)
	cp src/sound/MSXMusic.cc "${WORK:?}/MSXMusic.cc.orig" || exit 98
	sed -i -b 's/, ym2413(getName(), config)$/, ym2413(getName(), config, config.getChildDataAsBool("y8960test", false) ? YM2413::Type::Y8960 : YM2413::Type::YM2413)/' src/sound/MSXMusic.cc
	grep -q y8960test src/sound/MSXMusic.cc || { echo "patch did not apply"; exit 97; }
	mkdir -p "$WORK/user/extensions"
	sed 's/<FMPAC id="Panasoft SW-M004 FMPAC">/<FMPAC id="Y8960 test">\n          <y8960test>true<\/y8960test>/' share/extensions/fmpac.xml \
		> "$WORK/user/extensions/fmpac-y8960test.xml"
	grep -q y8960test "$WORK/user/extensions/fmpac-y8960test.xml" || { echo "extension not written"; exit 96; }
	echo "harness on"
	;;
off)
	cp "${WORK:?}/MSXMusic.cc.orig" src/sound/MSXMusic.cc || exit 95
	grep -q y8960test src/sound/MSXMusic.cc && { echo "restore failed"; exit 94; }
	echo "harness off"
	;;
*)
	echo "usage: harness.sh on|off"; exit 2
	;;
esac
