#ifndef Y8960SSGDEVICE_HH
#define Y8960SSGDEVICE_HH

#include "MSXDevice.hh"
#include "Y8960SSG.hh"
#include "serialize_meta.hh"

namespace openmsx {

/** The Y8960's SSGS block on its I/O ports.
  *
  *   base+0  write the register number
  *   base+1  write the register
  *   base+2  read the register
  *
  * Same layout as the MSX PSG, but the register number is 6 bits wide here
  * because there are two units.
  */
class Y8960SSGDevice final : public MSXDevice
{
public:
	explicit Y8960SSGDevice(const DeviceConfig& config);

	void reset(EmuTime time) override;
	[[nodiscard]] byte readIO(uint16_t port, EmuTime time) override;
	[[nodiscard]] byte peekIO(uint16_t port, EmuTime time) const override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;

	void writePort(bool port, byte value, EmuTime time);

	/** 7FFFh (I/O Enabler2) bit 4. */
	void setIoEnabled(bool enabled) { ioEnabled = enabled; }

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	Y8960SSG ssg;
	byte registerLatch;
	bool ioEnabled = false;
};
SERIALIZE_CLASS_VERSION(Y8960SSGDevice, 1);

} // namespace openmsx

#endif
