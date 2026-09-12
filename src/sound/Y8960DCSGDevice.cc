#include "Y8960DCSGDevice.hh"

#include "serialize.hh"

namespace openmsx {

Y8960DCSGDevice::Y8960DCSGDevice(const DeviceConfig& config)
	: MSXDevice(config)
	, dcsg(getName(), config)
	, useIoEnabler(config.getChildDataAsBool("use_io_enabler", true))
	, ioEnabled(!useIoEnabler)
{
	reset(getCurrentTime());
}

void Y8960DCSGDevice::reset(EmuTime time)
{
	dcsg.reset(time);
	ioEnabled = !useIoEnabler;
}

void Y8960DCSGDevice::writeIO(uint16_t /*port*/, byte value, EmuTime time)
{
	if (!ioEnabled) return;
	writePort(value, time);
}

void Y8960DCSGDevice::writePort(byte value, EmuTime time)
{
	dcsg.write(value, time);
}

template<typename Archive>
void Y8960DCSGDevice::serialize(Archive& ar, unsigned /*version*/)
{
	ar.template serializeBase<MSXDevice>(*this);
	ar.serialize("dcsg",      dcsg,
	             "ioEnabled", ioEnabled);
}
INSTANTIATE_SERIALIZE_METHODS(Y8960DCSGDevice);
REGISTER_MSXDEVICE(Y8960DCSGDevice, "Y8960-DCSG");

} // namespace openmsx
