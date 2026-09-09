#include "Y8960DCSGDevice.hh"

#include "serialize.hh"

namespace openmsx {

Y8960DCSGDevice::Y8960DCSGDevice(const DeviceConfig& config)
	: MSXDevice(config)
	, sn76489(getName(), config)
	, useIoEnabler(config.getChildDataAsBool("use_io_enabler", true))
	, ioEnabled(!useIoEnabler)
{
	reset(getCurrentTime());
}

void Y8960DCSGDevice::reset(EmuTime time)
{
	sn76489.reset(time);
	ioEnabled = !useIoEnabler;
}

void Y8960DCSGDevice::writeIO(uint16_t /*port*/, byte value, EmuTime time)
{
	if (!ioEnabled) return;
	writePort(value, time);
}

void Y8960DCSGDevice::writePort(byte value, EmuTime time)
{
	sn76489.write(value, time);
}

template<typename Archive>
void Y8960DCSGDevice::serialize(Archive& ar, unsigned /*version*/)
{
	ar.template serializeBase<MSXDevice>(*this);
	ar.serialize("sn76489",   sn76489,
	             "ioEnabled", ioEnabled);
}
INSTANTIATE_SERIALIZE_METHODS(Y8960DCSGDevice);
REGISTER_MSXDEVICE(Y8960DCSGDevice, "Y8960-DCSG");

} // namespace openmsx
