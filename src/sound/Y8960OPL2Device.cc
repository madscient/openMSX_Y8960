#include "Y8960OPL2Device.hh"

#include "MSXException.hh"
#include "MSXMotherBoard.hh"
#include "serialize.hh"

#include "narrow.hh"

namespace openmsx {

[[nodiscard]] static Y8960AdpcmMemory& getAdpcmMemory(const DeviceConfig& config)
{
	auto devName = config.getChildData("adpcm_memory", "");
	auto* device = dynamic_cast<Y8960AdpcmMemory*>(
		config.getMotherBoard().findDevice(devName));
	if (!device) {
		throw MSXException("Y8960-OPL2 needs an <adpcm_memory> naming a "
		                   "Y8960-ADPCM-RAM device that is created before it, "
		                   "got '", devName, "'.");
	}
	return *device;
}

[[nodiscard]] static unsigned getAdpcmBlock(const DeviceConfig& config)
{
	int block = config.getChildDataAsInt("adpcm_block", -1);
	if ((block < 0) || (block >= int(Y8960AdpcmMemory::BlockCount))) {
		throw MSXException("Y8960-OPL2 needs an <adpcm_block> of 0..",
		                   Y8960AdpcmMemory::BlockCount - 1, ".");
	}
	return narrow<unsigned>(block);
}

Y8960OPL2Device::Y8960OPL2Device(const DeviceConfig& config)
	: MSXDevice(config)
	, adpcmMemory(getAdpcmMemory(config))
	, adpcmBlock(getAdpcmBlock(config))
	, opl2(getName(), config, adpcmMemory, adpcmBlock, getCurrentTime())
	, registerLatch(0)
	, useIoEnabler(config.getChildDataAsBool("use_io_enabler", true))
	, ioEnabled(!useIoEnabler)
{
	reset(getCurrentTime());
}

void Y8960OPL2Device::reset(EmuTime time)
{
	opl2.reset(time);
	registerLatch = 0;
	ioEnabled = !useIoEnabler;
}

byte Y8960OPL2Device::readIO(uint16_t port, EmuTime time)
{
	if (!ioEnabled) return 0xFF;
	return (port & 1) ? opl2.readReg(registerLatch, time)
	                  : opl2.readStatus(time);
}

byte Y8960OPL2Device::peekIO(uint16_t port, EmuTime time) const
{
	if (!ioEnabled) return 0xFF;
	return (port & 1) ? opl2.peekReg(registerLatch, time)
	                  : opl2.peekStatus(time);
}

void Y8960OPL2Device::writeIO(uint16_t port, byte value, EmuTime time)
{
	if (!ioEnabled) return;
	writePort((port & 1) != 0, value, time);
}

void Y8960OPL2Device::writePort(bool port, byte value, EmuTime time)
{
	if (port) {
		opl2.writeReg(registerLatch, value, time);
	} else {
		registerLatch = value;
	}
}

template<typename Archive>
void Y8960OPL2Device::serialize(Archive& ar, unsigned /*version*/)
{
	ar.template serializeBase<MSXDevice>(*this);
	ar.serialize("opl2",          opl2,
	             "registerLatch", registerLatch,
	             "ioEnabled",     ioEnabled);
}
INSTANTIATE_SERIALIZE_METHODS(Y8960OPL2Device);
REGISTER_MSXDEVICE(Y8960OPL2Device, "Y8960-OPL2");

} // namespace openmsx
