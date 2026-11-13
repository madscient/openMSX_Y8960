#!/usr/bin/env python3
"""Write one stage of the upstream PR branch for the Y8960 (openMSX/openMSX#2288).

  python <main>/doc/fork/tools/y8960-pr-stage.py <stage 2..10> [--dry]
  python <main>/doc/fork/tools/y8960-pr-stage.py <stage 2..10> --message

Run from the root of the PR worktree. Stage 1 is buppu3's ae8c15509,
cherry-picked unchanged; this writes stages 2 to 10 on top of it.

A stage's own files are taken from SRC (the fork's main). The four
registration files are rebuilt as "SRC minus the lines of later stages",
each added line given to a stage by the class or type name on it. Files of
earlier stages are left as they are, so what a stage adds on the branch
(the tone bank attribution) survives the later ones. SRC must add to the
registration files without removing lines.

--message prints the stage's commit message. y8960-pr-run.sh drives the
whole series.
"""
import re
import subprocess
import sys

SRC, BASE = 'main', 'upstream/master'

NEW = {
    2: ['src/sound/MSXTimer.cc', 'src/sound/MSXTimer.hh'],
    3: ['src/sound/Y8960Pan.hh', 'src/sound/Y8960Mixer.cc', 'src/sound/Y8960Mixer.hh',
        'src/sound/MSXMixer.cc', 'src/sound/MSXMixer.hh'],
    4: ['src/sound/Y8960SsgCore.cc', 'src/sound/Y8960SsgCore.hh', 'src/sound/Y8960SSGS.cc',
        'src/sound/Y8960SSGS.hh', 'src/sound/Y8960SSGSDevice.cc', 'src/sound/Y8960SSGSDevice.hh'],
    5: ['src/sound/YM2413NukeYKTBanked.cc', 'src/sound/YM2413NukeYKTBanked.hh',
        'src/sound/Y8960OPLL.cc', 'src/sound/Y8960OPLL.hh',
        'src/sound/Y8960OPLLDevice.cc', 'src/sound/Y8960OPLLDevice.hh'],
    6: ['src/sound/Y8960OPL2.cc', 'src/sound/Y8960OPL2.hh', 'src/sound/Y8960Adpcm.cc',
        'src/sound/Y8960Adpcm.hh', 'src/sound/Y8960AdpcmMemory.cc', 'src/sound/Y8960AdpcmMemory.hh',
        'src/sound/Y8960OPL2Device.cc', 'src/sound/Y8960OPL2Device.hh'],
    7: ['src/sound/Y8960OPMDevice.cc', 'src/sound/Y8960OPMDevice.hh'],
    8: ['src/sound/Y8960SCC.cc', 'src/sound/Y8960SCC.hh', 'src/imgui/ImGuiSCCViewer.cc'],
    9: ['src/Y8960SystemController.cc', 'src/Y8960SystemController.hh'],
    10: ['src/memory/RomY8960.cc', 'src/memory/RomY8960.hh', 'src/memory/RomFactory.cc',
         'src/memory/RomInfo.cc', 'src/memory/RomTypes.hh', 'share/extensions/HRA_Y8960.xml'],
}
REG = ['src/meson.build', 'build/msvc/openmsx.vcxproj', 'build/msvc/openmsx.vcxproj.filters',
       'src/DeviceFactory.cc']
# First match wins. A line with no key belongs to the stage of the line
# above it (the <Filter> and closing tags in the .filters file).
KEYS = [
    (2, ['MSXTimer', '"MSX-TIMER"']),
    (3, ['Y8960Mixer', 'Y8960Pan', '"Y8960-MIXER"']),
    (4, ['Y8960SsgCore', 'Y8960SSGS', '"Y8960-SSGS"']),
    (5, ['YM2413NukeYKTBanked', 'Y8960OPLL', '"Y8960-OPLL"']),
    (6, ['Y8960Adpcm', 'Y8960OPL2', '"Y8960-OPL2"', '"Y8960-ADPCM-RAM"']),
    (7, ['Y8960OPMDevice', '"Y8960-OPM"']),
    (8, ['Y8960SCC']),
    (9, ['Y8960SystemController', '"Y8960-SYSTEM-CONTROLLER"']),
    (10, ['RomY8960']),
]

# The plgDavid tables are CC BY-SA. The fork keeps that attribution in its
# README, which the PR leaves out, so the PR carries it next to the table.
ATTRIB_FILE = 'src/sound/YM2413NukeYKTBanked.cc'
ATTRIB_ANCHOR = b'constexpr std::array<YM2413::Patch, 15*4> YM2413::m_patches = {\n'
ATTRIB = (b'// The OPLL-X (YM2423), OPLL-P (YMF281) and VRC7 tone banks below come from\n'
          b'// "Copyright free OPLL(x) ROM patches":\n'
          b'//     https://github.com/plgDavid/misc/wiki/Copyright-free-OPLL(x)-ROM-patches\n'
          b'//     (C) David Viens, Hubert Lamontagne\n'
          b'//     Licensed under CC BY-SA.\n')

MSG = {
    2: """MSX-Timer: follow the Y8960 cartridge's current spec

- Register MSX-TIMER with the device factory and give the timer in
  HRA_Y8960.xml an id, so that the extension loads.
- Count at the cartridge's 42.95MHz system clock (3.579545MHz x 12).
  The timer's design sheet gives 85.9MHz, but the cartridge clocks the
  timer with its system clock.
- Make the counters advance and raise their interrupt. The elapsed
  clock was measured from the next sync point rather than from the last
  update, so it was always 0 when the sync point was reached.
- Widen the count arithmetic to 64 bits: a terminal value of 255 at
  resolution 7 needs 256<<24.
- Let the cartridge open and close the I/O ports (I/O Enabler2, 7FFFh
  bit 7). The counters and the interrupt keep running while the ports
  are closed. They are closed after a reset; the mapper that opens them
  comes later in this series.
- A value other than 0-3 written to B3h selects no counter, which then
  reads FFh. Register 3 does not exist and reads 0.
- Savestate version 2 stores whether the ports are open.
- Comments in English; the ones that restated the next line are gone.
""",
    3: """Y8960: add the cartridge's mixer

The Y8960 sound cartridge (by HRA!) has a digital mixer: a volume per
sound block and a master volume, written through memory mapped I/O.
The cartridge does not feed its sound back into the MSX, so the output
setting (<mixer>_output) chooses what is heard: the cartridge, the MSX,
or both mixed.

MSXMixer gets setDeviceGain(), an extra gain per sound device on top of
the device's own amplification and the user's volume and balance. The
mixer's volumes go through it.

Y8960Pan.hh holds the pan law and the volume law that the cartridge's
sound blocks share.

Based on buppu3's implementation.
""",
    4: """Y8960: add the two SSGs

The SSGS block: two YM2149 units behind one 6-bit register number
(00h-0Fh unit 0, 10h-1Fh unit 1), with a volume (20h-26h) and a pan
(28h-2Eh) per channel.

Y8960SsgCore is forked from AY8910 so that Y8960SSGS can mix the two
units into one stereo stream: the pan is per channel, while openMSX
only has a balance per device.
""",
    5: """Y8960: add the OPLL with a tone bank per channel

The OPLL block: a YM2413 where each channel picks one of four preset
tone banks (40h-48h): the YM2413's own, OPLL-X (YM2423), OPLL-P
(YMF281) and VRC7. Each channel also has a pan (50h-58h).

YM2413NukeYKTBanked is YM2413NukeYKT with the four tone banks and a
bank per channel.

The OPLL-X, OPLL-P and VRC7 tone data comes from "Copyright free
OPLL(x) ROM patches" by David Viens and Hubert Lamontagne, licensed
CC BY-SA. The attribution is in YM2413NukeYKTBanked.cc. The Y8960
takes its tone banks from these tables; ymfm carries the same tables,
taken from the same page.

Based on buppu3's implementation.
""",
    6: """Y8960: add the OPL2 with ADPCM

The OPL2 block: an OPL2 with the Y8950's ADPCM-B, a pan per FM channel
(F6h-FEh) and a pan for the ADPCM (FFh). The ADPCM is mixed into the
block's output.

Y8960OPL2 and Y8960Adpcm are copies of Y8950 and Y8950Adpcm. The
ADPCM sample memory (256kB) is a device of its own, Y8960AdpcmMemory,
and PCM_BSY follows the Y8960, which drops it at the end of a one-shot
sample.
""",
    7: """Y8960: add the OPM

The OPM block: openMSX's YM2151 on I/O 7Eh (address) and 7Fh (data;
reading it returns the status).
""",
    8: """Y8960: add the SCC

The cartridge's SCC has a pan register per channel. Y8960SCC is a copy
of SCC cut down to the standard SCC (Mode::Real) and made a stereo
device: SCC is final and keeps its generator private, so it is copied
rather than wrapped. The SCC viewer shows it as well.
""",
    9: """Y8960: add the System Controller

The cartridge's System Controller on I/O 40h-4Fh, as switched I/O
device 80h. Only the identification is emulated: selecting the board
(02h is this cartridge) and a function, each register reading back the
complement of the value that selected it. The Config ROM reader/writer
behind function 01h is not.
""",
    10: """Y8960: add the ROM mapper and the HRA_Y8960 extension

RomY8960 is the cartridge's mapper. It switches 8kB banks of ROM and
RAM, holds the SCC's pan registers (9900h-9904h), and has the memory
mapped I/O through which the cartridge reaches its sound blocks: the
tunnels to the OPLL, OPL2, SSGS and OPM ports, the mixer's volumes,
and the two I/O Enablers that open the blocks' I/O ports.

HRA_Y8960.xml puts the blocks together as an extension.

Based on buppu3's implementation.
""",
}


def git(*args):
    return subprocess.run(['git', *args], capture_output=True, check=True).stdout


def classify(line):
    s = line.decode('utf-8')
    for g, keys in KEYS:
        if any(key in s for key in keys):
            return g
    return None


def added_lines(path):
    """{1-based line number in SRC: stage} for the lines SRC adds over BASE."""
    out = git('diff', '-U0', BASE, SRC, '--', path).decode('utf-8')
    src_lines = git('cat-file', 'blob', f'{SRC}:{path}').splitlines(keepends=True)
    result = {}
    for m in re.finditer(r'^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', out, re.M):
        removed = int(m.group(1)) if m.group(1) is not None else 1
        assert removed == 0, f'{path}: SRC removes lines, not a pure insertion'
        start = int(m.group(2))
        count = int(m.group(3)) if m.group(3) is not None else 1
        group = None
        for n in range(start, start + count):
            g = classify(src_lines[n - 1])
            if g is None:
                assert group is not None, f'{path}:{n}: no stage for {src_lines[n - 1]!r}'
                g = group
            group = g
            result[n] = g
    return src_lines, result


def write(path, data, dry):
    if not dry:
        with open(path, 'wb') as f:
            f.write(data)


def main():
    k = int(sys.argv[1])
    opt = sys.argv[2] if len(sys.argv) > 2 else ''
    assert k in NEW, 'stage must be 2..10'
    if opt == '--message':
        sys.stdout.write(MSG[k])
        return
    dry = opt == '--dry'

    for path in NEW[k]:
        write(path, git('cat-file', 'blob', f'{SRC}:{path}'), dry)
        print('would write' if dry else 'wrote', path)

    if k == 2:
        # buppu3's extension names no id for the timer, and openMSX requires
        # one. Use the id the fork's extension gives it.
        xml = 'share/extensions/HRA_Y8960.xml'
        data = open(xml, 'rb').read()
        old, new = b'<MSX-TIMER>', b'<MSX-TIMER id="y8960-timer">'
        assert data.count(old) == 1, 'timer element not found exactly once'
        write(xml, data.replace(old, new), dry)
        print('timer id given in', xml)

    if k == 5:
        data = open(ATTRIB_FILE, 'rb').read() if not dry else git('cat-file', 'blob', f'{SRC}:{ATTRIB_FILE}')
        assert data.count(ATTRIB_ANCHOR) == 1, 'tone table not found exactly once'
        assert ATTRIB not in data, 'attribution already there'
        write(ATTRIB_FILE, data.replace(ATTRIB_ANCHOR, ATTRIB + ATTRIB_ANCHOR), dry)
        print('attribution added to', ATTRIB_FILE)

    for path in REG:
        src_lines, added = added_lines(path)
        keep = [line for n, line in enumerate(src_lines, 1) if added.get(n, 0) <= k]
        write(path, b''.join(keep), dry)
        print(f'{path}: {sum(1 for g in added.values() if g <= k)} of {len(added)} added lines')
        if dry:
            for n in sorted(added):
                if added[n] == k:
                    print(f'   +{k} {src_lines[n - 1].decode().rstrip()}')


main()
