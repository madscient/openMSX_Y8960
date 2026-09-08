#include "Y8960SSGDevice.hh"

#include "serialize.hh"

namespace openmsx {

Y8960SSGDevice::Y8960SSGDevice(const DeviceConfig& config)
	: MSXDevice(config)
	, ssg(getName(), config, getCurrentTime())
	, registerLatch(0)
{
	reset(getCurrentTime());
}

void Y8960SSGDevice::reset(EmuTime time)
{
	ssg.reset(time);
	registerLatch = 0;
	ioEnabled = false;
}

byte Y8960SSGDevice::readIO(uint16_t port, EmuTime time)
{
	if (!ioEnabled) return 0xFF;
	// only the read port returns anything, as on the PSG
	return ((port & 3) == 2) ? ssg.readRegister(registerLatch, time) : 0xFF;
}

byte Y8960SSGDevice::peekIO(uint16_t port, EmuTime time) const
{
	if (!ioEnabled) return 0xFF;
	return ((port & 3) == 2) ? ssg.peekRegister(registerLatch, time) : 0xFF;
}

void Y8960SSGDevice::writeIO(uint16_t port, byte value, EmuTime time)
{
	if (!ioEnabled) return;
	writePort((port & 3) == 1, value, time);
}

void Y8960SSGDevice::writePort(bool port, byte value, EmuTime time)
{
	if (port) {
		ssg.writeRegister(registerLatch, value, time);
	} else {
		registerLatch = value & 0x3F;
	}
}

template<typename Archive>
void Y8960SSGDevice::serialize(Archive& ar, unsigned /*version*/)
{
	ar.template serializeBase<MSXDevice>(*this);
	ar.serialize("ssg",           ssg,
	             "registerLatch", registerLatch,
	             "ioEnabled",     ioEnabled);
}
INSTANTIATE_SERIALIZE_METHODS(Y8960SSGDevice);
REGISTER_MSXDEVICE(Y8960SSGDevice, "Y8960-SSG");

} // namespace openmsx
