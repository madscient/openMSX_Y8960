#include "Y8960Mixer.hh"

#include "DeviceConfig.hh"
#include "MSXException.hh"
#include "MSXMixer.hh"
#include "MSXMotherBoard.hh"
#include "SoundDevice.hh"
#include "XMLElement.hh"
#include "serialize.hh"

#include "StringOp.hh"
#include "stl.hh"
#include "xrange.hh"

#include <algorithm>
#include <cassert>

namespace openmsx {

using Output = Y8960Mixer::Output;

[[nodiscard]] static Output getDefaultOutput(const DeviceConfig& config)
{
	auto value = config.getChildData("default_output", "y8960");
	StringOp::casecmp cmp; // case-insensitive
	if (cmp(value, "y8960")) return Output::Y8960;
	if (cmp(value, "msx"))   return Output::Msx;
	if (cmp(value, "mix"))   return Output::Mix;
	throw MSXException(
		"Illegal default_output in the Y8960 mixer configuration: '", value,
		"', expected 'y8960', 'msx' or 'mix'.");
}

Y8960Mixer::Y8960Mixer(const DeviceConfig& config)
	: MSXDevice(config)
{
	for (const auto* e : config.getXML()->getChildren("channel")) {
		std::string_view idRef = e->getAttributeValue("idref", "");
		if (idRef == "") continue;

		int num = e->getAttributeValueAsInt("num", 0);
		if (num < 0 || num >= ChannelCount) {
			throw MSXException("Invalid channel number(", num, ") device '", idRef, "'");
		}

		channelDevices[num].push_back(idRef);
	}

	// Report a channel that names something which is not a sound device
	// here, rather than leaving it silently unmixed.
	auto& mixer = getMotherBoard().getMSXMixer();
	for (const auto& devices : channelDevices) {
		for (std::string_view device : devices) {
			if (!mixer.findDevice(device)) {
				throw MSXException("Unknown sound device '", device,
				                   "' in the Y8960 mixer configuration.");
			}
		}
	}

	outputSetting = std::make_unique<EnumSetting<Output>>(
		getCommandController(), getName() + "_output",
		"Which sound output to listen to: the Y8960's own, the MSX's, or both.",
		getDefaultOutput(config),
		EnumSetting<Output>::Map{
			{"y8960", Output::Y8960},
			{"msx",   Output::Msx  },
			{"mix",   Output::Mix  }});
	outputSetting->attach(*this);

	reset(getCurrentTime());
}

Y8960Mixer::~Y8960Mixer()
{
	outputSetting->detach(*this);

	// Hand every device back at unity. Without this, removing the cartridge
	// while listening to its output alone would leave the MSX muted.
	auto& mixer = getMotherBoard().getMSXMixer();
	for (const auto& info : mixer.getDeviceInfos()) {
		mixer.setDeviceGain(info.device->getName(), 1.0f, 1.0f);
	}
}

void Y8960Mixer::reset(EmuTime /*time*/)
{
	registerLatch = 0;
	std::ranges::fill(regs, 0);

	masterGain = Gain{.left = 1.0f, .right = 1.0f};
	std::ranges::fill(channelGain, Gain{.left = 1.0f, .right = 1.0f});

	applyAllGains();
}

byte Y8960Mixer::readIO(uint16_t port, EmuTime time)
{
	return peekIO(port, time);
}

byte Y8960Mixer::peekIO(uint16_t port, EmuTime /*time*/) const
{
	if ((port & 1) == 0) return registerLatch;
	return (registerLatch < RegCount) ? regs[registerLatch] : 0xFF;
}

void Y8960Mixer::writeIO(uint16_t port, byte value, EmuTime /*time*/)
{
	// The register layout is not specified, so this stores and nothing more.
	if ((port & 1) == 0) {
		registerLatch = value;
	} else if (registerLatch < RegCount) {
		regs[registerLatch] = value;
	}
}

void Y8960Mixer::setChannelGain(int channel, float left, float right)
{
	assert(channel >= 0 && channel < ChannelCount);
	channelGain[channel] = Gain{.left = left, .right = right};
	applyAllGains();
}

void Y8960Mixer::setMasterGain(float left, float right)
{
	masterGain = Gain{.left = left, .right = right};
	applyAllGains();
}

std::optional<int> Y8960Mixer::findChannel(std::string_view name) const
{
	for (auto ch : xrange(ChannelCount)) {
		if (contains(channelDevices[ch], name)) return ch;
	}
	return {};
}

void Y8960Mixer::applyAllGains()
{
	// Silencing one of the two outputs is a gain of zero on the devices
	// behind it. The cartridge's own devices are the ones its channels
	// name; whatever else is registered belongs to the MSX.
	auto output = outputSetting->getEnum();
	float y8960Gain = (output != Output::Msx)   ? 1.0f : 0.0f;
	float msxGain   = (output != Output::Y8960) ? 1.0f : 0.0f;

	auto& mixer = getMotherBoard().getMSXMixer();
	for (const auto& info : mixer.getDeviceInfos()) {
		std::string_view name = info.device->getName();
		if (auto channel = findChannel(name)) {
			const auto& g = channelGain[*channel];
			mixer.setDeviceGain(name, g.left  * masterGain.left  * y8960Gain,
			                          g.right * masterGain.right * y8960Gain);
		} else {
			mixer.setDeviceGain(name, msxGain, msxGain);
		}
	}
}

void Y8960Mixer::update(const Setting& /*setting*/) noexcept
{
	applyAllGains();
}

template<typename Archive>
void Y8960Mixer::serialize(Archive& ar, unsigned version)
{
	ar.template serializeBase<MSXDevice>(*this);
	if (ar.versionAtLeast(version, 2)) {
		ar.serialize("regs",          regs,
		             "registerLatch", registerLatch);
	}
}
INSTANTIATE_SERIALIZE_METHODS(Y8960Mixer);
REGISTER_MSXDEVICE(Y8960Mixer, "Y8960MIXER");

} // namespace openmsx
