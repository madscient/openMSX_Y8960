#include "Y8960SSGSDevice.hh"

#include "CassettePort.hh"
#include "JoystickPort.hh"
#include "LedStatus.hh"
#include "MSXException.hh"
#include "MSXMotherBoard.hh"
#include "RenShaTurbo.hh"
#include "serialize.hh"

#include "StringOp.hh"
#include "stl.hh"

namespace openmsx {

[[nodiscard]] static byte getKeyboardLayout(const Y8960SSGSDevice& device)
{
	auto value = device.getDeviceConfig().getChildData("keyboardlayout", "50on");
	StringOp::casecmp cmp; // case-insensitive
	if (cmp(value, "50on")) {
		return 0x00;
	} else if (cmp(value, "jis")) {
		return 0x40;
	}
	throw MSXException(
		"Illegal keyboard layout configuration in '", device.getName(),
		"' device configuration: '", value,
		"', expected 'jis' or '50on'.");
}

Y8960SSGSDevice::Y8960SSGSDevice(const DeviceConfig& config)
	: MSXDevice(config)
	, readable(config.getChildDataAsBool("readable", false))
	, useIoEnabler(config.getChildDataAsBool("use_io_enabler", true))
	, gpio(config.getChildDataAsBool("gpio", false))
	, cassette(getMotherBoard().getCassettePort())
	, renShaTurbo(getMotherBoard().getRenShaTurbo())
	, ports(generate_array<2>([&](auto i) { return &getMotherBoard().getJoystickPort(unsigned(i)); }))
	, keyLayout(gpio ? getKeyboardLayout(*this) : byte(0))
	, registerLatch(0)
	, ioEnabled(!useIoEnabler)
	, ssgs(getName(), config, getCurrentTime(),
	       gpio ? static_cast<AY8910Periphery*>(this) : nullptr)
{
	reset(getCurrentTime());
}

Y8960SSGSDevice::~Y8960SSGSDevice()
{
	powerDown(EmuTime::dummy());
}

void Y8960SSGSDevice::reset(EmuTime time)
{
	ssgs.reset(time);
	registerLatch = 0;
	ioEnabled = !useIoEnabler;
}

void Y8960SSGSDevice::powerDown(EmuTime /*time*/)
{
	if (gpio) {
		getLedStatus().setLed(LedStatus::KANA, false);
	}
}

byte Y8960SSGSDevice::readIO(uint16_t port, EmuTime time)
{
	if (!readable || !ioEnabled) return 0xFF;
	// only the read port returns anything, as on the PSG
	return ((port & 3) == 2) ? ssgs.readRegister(registerLatch, time) : 0xFF;
}

byte Y8960SSGSDevice::peekIO(uint16_t port, EmuTime time) const
{
	if (!readable || !ioEnabled) return 0xFF;
	return ((port & 3) == 2) ? ssgs.peekRegister(registerLatch, time) : 0xFF;
}

void Y8960SSGSDevice::writeIO(uint16_t port, byte value, EmuTime time)
{
	if (!ioEnabled) return;
	writePort((port & 3) == 1, value, time);
}

void Y8960SSGSDevice::writePort(bool port, byte value, EmuTime time)
{
	if (port) {
		ssgs.writeRegister(registerLatch, value, time);
	} else {
		registerLatch = value & 0x3F;
	}
}

byte Y8960SSGSDevice::readA(EmuTime time)
{
	byte joystick = ports[selectedPort]->read(time) |
	                ((renShaTurbo.getSignal(time)) ? 0x10 : 0x00);
	byte cassetteInput = cassette.cassetteIn(time) ? 0x80 : 0x00;
	return joystick | keyLayout | cassetteInput;
}

void Y8960SSGSDevice::writeB(byte value, EmuTime time)
{
	byte val0 =  (value & 0x03)       | ((value & 0x10) >> 2);
	byte val1 = ((value & 0x0C) >> 2) | ((value & 0x20) >> 3);
	ports[0]->write(val0, time);
	ports[1]->write(val1, time);
	selectedPort = (value & 0x40) >> 6;

	if ((prev ^ value) & 0x80) {
		getLedStatus().setLed(LedStatus::KANA, !(value & 0x80));
	}
	prev = value;
}

template<typename Archive>
void Y8960SSGSDevice::serialize(Archive& ar, unsigned version)
{
	ar.template serializeBase<MSXDevice>(*this);
	// The tag is part of the savestate format, so it stays "ssg" even though
	// the member no longer is.
	ar.serialize("ssg",           ssgs,
	             "registerLatch", registerLatch,
	             "ioEnabled",     ioEnabled);
	if (ar.versionAtLeast(version, 2) && gpio) {
		byte portB = prev;
		ar.serialize("portB", portB);
		if constexpr (Archive::IS_LOADER) {
			writeB(portB, getCurrentTime());
		}
		// selectedPort is derived from portB
	}
}
INSTANTIATE_SERIALIZE_METHODS(Y8960SSGSDevice);
REGISTER_MSXDEVICE(Y8960SSGSDevice, "Y8960-SSGS");

} // namespace openmsx
