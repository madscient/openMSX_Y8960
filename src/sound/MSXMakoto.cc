#include "MSXMakoto.hh"

#include "serialize.hh"

namespace openmsx {

MSXMakoto::MSXMakoto(DeviceConfig& config)
	: MSXDevice(config)
	, ym2608(getName(), config,
	         config.getChildDataAsInt("sampleram", 256) * 1024,
	         getCurrentTime())
{
	powerUp(getCurrentTime());
}

void MSXMakoto::powerUp(EmuTime time)
{
	ym2608.clearRam();
	reset(time);
}

void MSXMakoto::reset(EmuTime time)
{
	ym2608.reset(time);
}

byte MSXMakoto::readIO(uint16_t port, EmuTime time)
{
	return ym2608.readPort(port & 3, time);
}

byte MSXMakoto::peekIO(uint16_t port, EmuTime time) const
{
	return ym2608.peekPort(port & 3, time);
}

void MSXMakoto::writeIO(uint16_t port, byte value, EmuTime time)
{
	ym2608.writePort(port & 3, value, time);
}

template<typename Archive>
void MSXMakoto::serialize(Archive& ar, unsigned /*version*/)
{
	ar.template serializeBase<MSXDevice>(*this);
	ar.serialize("YM2608", ym2608);
}
INSTANTIATE_SERIALIZE_METHODS(MSXMakoto);
REGISTER_MSXDEVICE(MSXMakoto, "Makoto");

} // namespace openmsx
