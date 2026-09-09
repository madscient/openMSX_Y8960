#include "Y8960Mixer.hh"

#include "DeviceConfig.hh"
#include "MSXException.hh"
#include "MSXMotherBoard.hh"
#include "XMLElement.hh"
#include "serialize.hh"

#include "StringOp.hh"
#include "xrange.hh"

#include <algorithm>
#include <cassert>

namespace openmsx {

using OutputSelect = MSXMixer::OutputSelect;

[[nodiscard]] static OutputSelect getDefaultOutput(const DeviceConfig& config)
{
	auto value = config.getChildData("default_output", "y8960");
	StringOp::casecmp cmp; // case-insensitive
	if (cmp(value, "y8960")) return OutputSelect::EXTERNAL;
	if (cmp(value, "msx"))   return OutputSelect::INTERNAL;
	if (cmp(value, "mix"))   return OutputSelect::BOTH;
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

	outputSetting = std::make_unique<EnumSetting<OutputSelect>>(
		getCommandController(), getName() + "_output",
		"Which sound output to listen to: the Y8960's own, the MSX's, or both.",
		getDefaultOutput(config),
		EnumSetting<OutputSelect>::Map{
			{"y8960", OutputSelect::EXTERNAL},
			{"msx",   OutputSelect::INTERNAL},
			{"mix",   OutputSelect::BOTH    }});
	outputSetting->attach(*this);

	reset(getCurrentTime());
}

Y8960Mixer::~Y8960Mixer()
{
	outputSetting->detach(*this);
	getMotherBoard().getMSXMixer().selectOutput(OutputSelect::INTERNAL);
}

void Y8960Mixer::reset(EmuTime /*time*/)
{
	updateSelector();

	registerLatch = 0;
	std::ranges::fill(regs, 0);

	masterGain = Gain{.left = 1.0f, .right = 1.0f};
	std::ranges::fill(channelGain, Gain{.left = 1.0f, .right = 1.0f});

	for (const auto& devices : channelDevices) {
		for (std::string_view device : devices) {
			getMotherBoard().getMSXMixer().setExternal(device, true);
		}
	}
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
	applyGain(channel);
}

void Y8960Mixer::setMasterGain(float left, float right)
{
	masterGain = Gain{.left = left, .right = right};
	applyAllGains();
}

void Y8960Mixer::applyGain(int channel)
{
	const auto& g = channelGain[channel];
	for (std::string_view device : channelDevices[channel]) {
		getMotherBoard().getMSXMixer().setDeviceGain(
			device, g.left * masterGain.left, g.right * masterGain.right);
	}
}

void Y8960Mixer::applyAllGains()
{
	for (auto ch : xrange(ChannelCount)) applyGain(ch);
}

void Y8960Mixer::updateSelector()
{
	getMotherBoard().getMSXMixer().selectOutput(outputSetting->getEnum());
}

void Y8960Mixer::update(const Setting& /*setting*/) noexcept
{
	updateSelector();
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
