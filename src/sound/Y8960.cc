#include "Y8960.hh"

#include "DeviceConfig.hh"
#include "DummyAY8910Periphery.hh"
#include "MSXMotherBoard.hh"
#include "serialize.hh"

#include "outer.hh"
#include "xrange.hh"

#include <cmath>
#include <numbers>

namespace openmsx {

// The registers of the digital mixer, which is also the layout of the
// "<name> mixer" debuggable:
//   0x00-0x04  volume of SSG, OPLL, OPL2, SCC, OPM
//   0x05       master volume
//   0x06-0x0E  OPLL pan, channel 1-9            (OPLL 50h-58h)
//   0x0F-0x18  OPL2 pan, channel 1-9 and ADPCM  (OPL2 F6h-FFh)
//   0x19-0x1D  SCC pan, channel A-E
//   0x1E-0x2D  SSG 20h-2Fh: volume (20h-22h, 24h-26h) and pan (28h-2Ah,
//              2Ch-2Eh) of channel A-C of both SSGs; 23h, 27h, 2Bh and 2Fh
//              are not connected and stay 0
static constexpr unsigned VOLUME   = 0x00;
static constexpr unsigned MASTER   = 0x05;
static constexpr unsigned OPLL_PAN = 0x06;
static constexpr unsigned OPL2_PAN = 0x0F;
static constexpr unsigned SCC_PAN  = 0x19;
static constexpr unsigned SSG_REGS = 0x1E;

[[nodiscard]] static constexpr bool isSsgConnected(unsigned reg)
{
	return (reg & 3) != 3;
}

// The NukeYKT core puts the rhythm out as HH, TOM, BD, SD, TC, after the 9
// melodic channels. Each takes the pan of the channel it sounds on: BD 7,
// HH and SD 8, TOM and TC 9.
static constexpr std::array<uint8_t, 5> OPLL_RHYTHM_CHANNEL = {7, 8, 6, 7, 8};

// Y8950 puts the rhythm out as BD, SD, CYM, HH, TOM, then the ADPCM. The
// rhythm takes the pans of channels 7-9 like the OPLL's, the ADPCM its own.
static constexpr std::array<uint8_t, 6> OPL2_RHYTHM_CHANNEL = {6, 7, 8, 7, 8, 9};

// The levels of the blocks relative to each other, measured on the cartridge
// with all volume registers at their maximum. The config's <volume> is the
// level of the OPM, the loudest.
static constexpr std::array<float, size_t(Y8960::Block::NUM)> BLOCK_LEVEL = {
	15003.0f / 30000.0f, // SSG
	 7009.0f / 30000.0f, // OPLL
	 7433.0f / 30000.0f, // OPL2
	 7509.0f / 30000.0f, // SCC
	1.0f,                // OPM
};

struct PanGain { float left, right; };

// The pan registers: 1 is hard left, 128 the centre, 255 hard right, and 0
// is hard left like 1. The specification only gives those points; in between
// this is constant power, so the centre is 3dB down on both sides.
[[nodiscard]] static PanGain panGain(uint8_t pan)
{
	if (pan == 128) {
		// exactly symmetric, rather than cos() and sin() a rounding apart
		constexpr float c = std::numbers::sqrt2_v<float> / 2.0f;
		return {.left = c, .right = c};
	}
	if (pan == 0) pan = 1;
	float t = float(pan - 1) / 254.0f * (std::numbers::pi_v<float> / 2.0f);
	return {.left = std::cos(t), .right = std::sin(t)};
}

// The volume registers: 0 mutes, 1-127 is linear in steps of 1/128, and any
// value with bit 7 set is unity. 128 is the documented maximum.
[[nodiscard]] static float volumeGain(uint8_t volume)
{
	return (volume & 0x80) ? 1.0f : float(volume) / 128.0f;
}

Y8960::Y8960(const std::string& name, const DeviceConfig& config, EmuTime time)
	: motherBoard(config.getMotherBoard())
	, scc(name + " SCC", config, time, SCC::Mode::Real)
	, opll(name + " OPLL", config, YM2413::Type::Y8960)
	, opl2(name + " OPL2", config, 256 * 1024, time, noPeriphery, Y8950::Type::Y8960)
	, ssg{AY8910(name + " SSG 0", DummyAY8910Periphery::instance(), config, time, AY8910::Type::YM2149),
	      AY8910(name + " SSG 1", DummyAY8910Periphery::instance(), config, time, AY8910::Type::YM2149)}
	, debuggable(motherBoard, name)
{
	scc.enableSetChannelFactors();
	opll.enableSetChannelFactors();
	opl2.enableSetChannelFactors();
	for (auto& s : ssg) s.enableSetChannelFactors();
}

void Y8960::NoPeriphery::write(uint4_t /*outputs*/, uint4_t /*values*/, EmuTime /*time*/)
{
}

uint4_t Y8960::NoPeriphery::read(EmuTime /*time*/)
{
	return 15;
}

void Y8960::powerUp(EmuTime time)
{
	scc.powerUp(time);
	opl2.clearRam();
}

void Y8960::reset(EmuTime time)
{
	scc.reset(time);
	opll.reset(time);
	opllLatch = 0;
	opl2.reset(time);
	opl2Latch = 0;
	for (auto& s : ssg) s.reset(time);
	ssgLatch = 0;
	for (auto reg : xrange(VOLUME, MASTER + 1)) mixer[reg] = 0x80;
	for (auto reg : xrange(OPLL_PAN, SSG_REGS)) mixer[reg] = 128;
	for (auto r : xrange(0x10u)) {
		mixer[SSG_REGS + r] = !isSsgConnected(r) ? 0 : (r < 8) ? 0x80 : 128;
	}
	applyAll(time);
}

uint8_t Y8960::readScc(uint8_t address, EmuTime time)
{
	return scc.readMem(address, time);
}

uint8_t Y8960::peekScc(uint8_t address, EmuTime time) const
{
	return scc.peekMem(address, time);
}

void Y8960::writeScc(uint8_t address, uint8_t value, EmuTime time)
{
	scc.writeMem(address, value, time);
}

void Y8960::writeSccPan(unsigned channel, uint8_t value, EmuTime time)
{
	if (channel < 5) writeMixer(SCC_PAN + channel, value, time);
}

void Y8960::writeOpll(bool port, uint8_t value, EmuTime time)
{
	if (!port) {
		opllLatch = value;
	} else if ((0x50 <= opllLatch) && (opllLatch <= 0x58)) {
		writeMixer(OPLL_PAN + opllLatch - 0x50, value, time);
	}
	// the YM2413 sees the pan writes as well, and ignores them
	opll.writePort(port, value, time);
}

// Unlike a Y8950, the data port reads back only the ADPCM data (0Fh).
uint8_t Y8960::readOpl2(bool port, EmuTime time)
{
	if (!port) return opl2.readStatus(time);
	return (opl2Latch == 0x0F) ? opl2.readReg(opl2Latch, time) : 0xFF;
}

uint8_t Y8960::peekOpl2(bool port, EmuTime time) const
{
	if (!port) return opl2.peekStatus(time);
	return (opl2Latch == 0x0F) ? opl2.peekReg(opl2Latch, time) : 0xFF;
}

void Y8960::writeOpl2(bool port, uint8_t value, EmuTime time)
{
	if (!port) {
		opl2Latch = value;
		return;
	}
	if (opl2Latch >= 0xF6) {
		writeMixer(OPL2_PAN + opl2Latch - 0xF6, value, time);
	}
	// the Y8950 sees the pan writes as well, and ignores them
	opl2.writeReg(opl2Latch, value, time);
}

void Y8960::writeSsg(bool port, uint8_t value, EmuTime time)
{
	if (!port) {
		ssgLatch = value & 0x3F; // 40h-FFh are 00h-3Fh again
	} else if (ssgLatch < 0x20) {
		ssg[ssgLatch >> 4].writeRegister(ssgLatch & 0x0F, value, time);
	} else if (ssgLatch < 0x30) {
		writeMixer(SSG_REGS + ssgLatch - 0x20, value, time);
	}
}

void Y8960::writeVolume(Block block, uint8_t value, EmuTime time)
{
	writeMixer(VOLUME + unsigned(block), value, time);
}

void Y8960::writeMasterVolume(uint8_t value, EmuTime time)
{
	writeMixer(MASTER, value, time);
}

void Y8960::writeMixer(unsigned reg, uint8_t value, EmuTime time)
{
	if (reg >= SSG_REGS && !isSsgConnected(reg - SSG_REGS)) return;
	mixer[reg] = value;
	if (reg < MASTER) {
		applyVolume(Block(reg - VOLUME), time);
	} else if (reg == MASTER) {
		for (auto b : xrange(size_t(Block::NUM))) applyVolume(Block(b), time);
	} else {
		applyPan(reg, time);
	}
}

void Y8960::applyVolume(Block block, EmuTime time)
{
	float gain = BLOCK_LEVEL[size_t(block)]
	           * volumeGain(mixer[VOLUME + unsigned(block)]) * volumeGain(mixer[MASTER]);
	switch (block) {
	case Block::SSG:  for (auto& s : ssg) s.setSoftwareVolume(gain, time); break;
	case Block::OPLL: opll.setSoftwareVolume(gain, time); break;
	case Block::OPL2: opl2.setSoftwareVolume(gain, time); break;
	case Block::SCC:  scc .setSoftwareVolume(gain, time); break;
	default: break;
	}
}

void Y8960::applyPan(unsigned reg, EmuTime time)
{
	if (reg >= SSG_REGS) {
		// 20h-27h volume, 28h-2Fh pan; bit 2 the SSG, bits 1-0 its channel
		auto r = (reg - SSG_REGS) & 7;
		if (!isSsgConnected(r)) return;
		auto pan = panGain(mixer[SSG_REGS + 8 + r]);
		float vol = volumeGain(mixer[SSG_REGS + r]);
		ssg[r >> 2].setChannelFactors(r & 3, pan.left * vol, pan.right * vol, time);
		return;
	}
	auto [left, right] = panGain(mixer[reg]);
	if ((OPLL_PAN <= reg) && (reg < OPLL_PAN + 9)) {
		auto ch = reg - OPLL_PAN;
		opll.setChannelFactors(ch, left, right, time);
		for (auto i : xrange(unsigned(OPLL_RHYTHM_CHANNEL.size()))) {
			if (OPLL_RHYTHM_CHANNEL[i] == ch) {
				opll.setChannelFactors(9 + i, left, right, time);
			}
		}
	} else if ((OPL2_PAN <= reg) && (reg < OPL2_PAN + 10)) {
		auto ch = reg - OPL2_PAN;
		if (ch < 9) opl2.setChannelFactors(ch, left, right, time);
		for (auto i : xrange(unsigned(OPL2_RHYTHM_CHANNEL.size()))) {
			if (OPL2_RHYTHM_CHANNEL[i] == ch) {
				opl2.setChannelFactors(9 + i, left, right, time);
			}
		}
	} else if ((SCC_PAN <= reg) && (reg < SCC_PAN + 5)) {
		scc.setChannelFactors(reg - SCC_PAN, left, right, time);
	}
}

void Y8960::applyAll(EmuTime time)
{
	for (auto b : xrange(size_t(Block::NUM))) applyVolume(Block(b), time);
	for (auto reg : xrange(OPLL_PAN, unsigned(mixer.size()))) applyPan(reg, time);
}


Y8960::Debuggable::Debuggable(MSXMotherBoard& motherBoard_, const std::string& name_)
	: SimpleDebuggable(motherBoard_, name_ + " mixer", "Y8960 digital mixer", 0x2E)
{
}

uint8_t Y8960::Debuggable::read(unsigned address)
{
	const auto& y8960 = OUTER(Y8960, debuggable);
	return y8960.mixer[address];
}

void Y8960::Debuggable::write(unsigned address, uint8_t value, EmuTime time)
{
	auto& y8960 = OUTER(Y8960, debuggable);
	y8960.writeMixer(address, value, time);
}


template<typename Archive>
void Y8960::serialize(Archive& ar, unsigned /*version*/)
{
	ar.serialize("scc",       scc,
	             "opll",      opll,
	             "opllLatch", opllLatch,
	             "opl2",      opl2,
	             "opl2Latch", opl2Latch,
	             "ssg0",      ssg[0],
	             "ssg1",      ssg[1],
	             "ssgLatch",  ssgLatch,
	             "mixer",     mixer);
	if constexpr (Archive::IS_LOADER) {
		// the sound devices don't keep their software volume and channel
		// factors in a savestate
		applyAll(motherBoard.getCurrentTime());
	}
}
INSTANTIATE_SERIALIZE_METHODS(Y8960);

} // namespace openmsx
