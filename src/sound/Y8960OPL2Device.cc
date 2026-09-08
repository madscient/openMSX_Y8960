#include "Y8960OPL2Device.hh"

#include "serialize.hh"

namespace openmsx {

Y8960OPL2Device::Y8960OPL2Device(const DeviceConfig& config)
	: MSXDevice(config)
	, opl2(getName(), config,
	       config.getChildDataAsInt("sampleram", 256) * 1024,
	       getCurrentTime())
	, registerLatch(0)
{
	reset(getCurrentTime());
}

void Y8960OPL2Device::reset(EmuTime time)
{
	opl2.reset(time);
	registerLatch = 0;
	ioEnabled = false;
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
