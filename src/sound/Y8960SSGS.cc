#include "Y8960SSGS.hh"

#include "DeviceConfig.hh"
#include "MSXMotherBoard.hh"
#include "serialize.hh"

#include "outer.hh"
#include "xrange.hh"

#include <algorithm>

namespace openmsx {

// The cores run at the same rate the AY8910 does.
static constexpr int NATIVE_FREQ_INT = 3579545 / 2 / 8;

Y8960SSGS::Y8960SSGS(const std::string& name_, const DeviceConfig& config, EmuTime time)
	: ResampledSoundDevice(config.getMotherBoard(), name_, "Y8960 SSGS",
	                       NUM_CHANNELS, NATIVE_FREQ_INT, true)
	, unit{Y8960SsgCore(name_ + " unit0", config, time),
	       Y8960SsgCore(name_ + " unit1", config, time)}
	, pan{}
	, dc{}
	, debuggable(config.getMotherBoard(), getName())
{
	reset(time);
	registerSound(config);
}

Y8960SSGS::~Y8960SSGS()
{
	unregisterSound();
}

void Y8960SSGS::reset(EmuTime time)
{
	for (auto& u : unit) u.reset(time);
	std::ranges::fill(pan, PAN_CENTER);
	measureDc();
}

void Y8960SSGS::measureDc()
{
	// Generate a single sample with everything silent to find out where the
	// zero level of each channel sits.
	for (auto u : xrange(NUM_UNITS)) {
		std::array<float, CHANNELS_PER_UNIT> sample = {};
		std::array<float*, CHANNELS_PER_UNIT> bufs = {
			&sample[0], &sample[1], &sample[2]};
		unit[u].generateChannels(bufs, 1);
		for (auto c : xrange(CHANNELS_PER_UNIT)) {
			// a nullptr buffer means the core decided the channel is silent
			dc[u * CHANNELS_PER_UNIT + c] = bufs[c] ? sample[c] : 0.0f;
		}
	}
}

// The datasheet does not say how a panpot value maps to left/right levels, so
// this follows the YMZ280B of the same family: both sides open at the centre,
// the opposite side closing linearly as the value moves away, and the two
// extreme steps hard over to one side.
void Y8960SSGS::panGains(uint8_t pan_, float& gainL, float& gainR)
{
	if (pan_ == PAN_CENTER) {
		gainL = 1.0f;
		gainR = 1.0f;
	} else if (pan_ < PAN_CENTER) {
		gainL = 1.0f;
		gainR = (pan_ == 0) ? 0.0f
		                    : float(pan_ - 1) / float(PAN_CENTER - 1);
	} else {
		gainL = float(PAN_MAX - pan_) / float(PAN_MAX - PAN_CENTER);
		gainR = 1.0f;
	}
}

void Y8960SSGS::writeRegister(unsigned reg, uint8_t value, EmuTime time)
{
	if (reg >= 0x40) return; // ADPCM / sequencer area, not used by the Y8960

	updateStream(time);

	unsigned u = (reg >> 5) & 1;
	unsigned sub = reg & 0x1F;
	if ((sub >= 0x10) && (sub <= 0x12)) {
		pan[u * CHANNELS_PER_UNIT + (sub - 0x10)] = value & PAN_MAX;
	} else if (sub <= 0x0D) {
		unit[u].writeRegister(sub, value, time);
	}
	// $0E-$0F do not exist, these parts have no I/O ports
}

uint8_t Y8960SSGS::readRegister(unsigned reg, EmuTime time)
{
	return peekRegister(reg, time);
}

uint8_t Y8960SSGS::peekRegister(unsigned reg, EmuTime time) const
{
	if (reg >= 0x40) return 0xFF;

	unsigned u = (reg >> 5) & 1;
	unsigned sub = reg & 0x1F;
	if ((sub >= 0x10) && (sub <= 0x12)) {
		return pan[u * CHANNELS_PER_UNIT + (sub - 0x10)];
	} else if (sub <= 0x0D) {
		return unit[u].peekRegister(sub, time);
	}
	return 0xFF;
}

float Y8960SSGS::getAmplificationFactorImpl() const
{
	return unit[0].getAmplificationFactor();
}

void Y8960SSGS::generateChannels(std::span<float*> bufs, unsigned num)
{
	// The cores produce mono; collect that first and then spread it over
	// the stereo output with the panpot.
	std::vector<float> scratch(size_t(num) * CHANNELS_PER_UNIT);

	for (auto u : xrange(NUM_UNITS)) {
		std::ranges::fill(scratch, 0.0f);
		std::array<float*, CHANNELS_PER_UNIT> mono = {
			&scratch[0], &scratch[num], &scratch[size_t(2) * num]};
		unit[u].generateChannels(mono, num);

		for (auto c : xrange(CHANNELS_PER_UNIT)) {
			unsigned ch = u * CHANNELS_PER_UNIT + c;
			if (!mono[c]) {
				// silent channel, the core left the buffer alone
				bufs[ch] = nullptr;
				continue;
			}
			float gainL, gainR;
			panGains(pan[ch], gainL, gainR);
			const float* src = &scratch[size_t(c) * num];
			float offset = dc[ch];
			for (auto i : xrange(num)) {
				float v = src[i] - offset;
				bufs[ch][2 * i + 0] += v * gainL;
				bufs[ch][2 * i + 1] += v * gainR;
			}
		}
	}
}

// SimpleDebuggable

Y8960SSGS::Debuggable::Debuggable(MSXMotherBoard& motherBoard_, const std::string& name_)
	: SimpleDebuggable(motherBoard_, name_ + " regs", "Y8960 SSGS", 0x40)
{
}

uint8_t Y8960SSGS::Debuggable::read(unsigned address, EmuTime time)
{
	const auto& ssg = OUTER(Y8960SSGS, debuggable);
	return ssg.peekRegister(address, time);
}

void Y8960SSGS::Debuggable::write(unsigned address, uint8_t value, EmuTime time)
{
	auto& ssg = OUTER(Y8960SSGS, debuggable);
	ssg.writeRegister(address, value, time);
}

template<typename Archive>
void Y8960SSGS::serialize(Archive& ar, unsigned /*version*/)
{
	ar.serialize("unit0", unit[0],
	             "unit1", unit[1],
	             "pan",   pan);
	if constexpr (Archive::IS_LOADER) {
		measureDc();
	}
}
INSTANTIATE_SERIALIZE_METHODS(Y8960SSGS);

} // namespace openmsx
