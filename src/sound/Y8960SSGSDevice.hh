#ifndef Y8960SSGSDEVICE_HH
#define Y8960SSGSDEVICE_HH

#include "MSXDevice.hh"
#include "Y8960SSGS.hh"
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
class Y8960SSGSDevice final : public MSXDevice
{
public:
	explicit Y8960SSGSDevice(const DeviceConfig& config);

	void reset(EmuTime time) override;
	[[nodiscard]] byte readIO(uint16_t port, EmuTime time) override;
	[[nodiscard]] byte peekIO(uint16_t port, EmuTime time) const override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;

	void writePort(bool port, byte value, EmuTime time);

	/** カートリッジ版はリードに反応しない。A0h-A2h は本体 PSG と重なっており、
	  * 読み出しに応じると本体と衝突するため。本体内蔵版は既存の PSG を
	  * 置き換えるので読み書きの両方に応じる。
	  * XML の <readable> で切り替える (既定はカートリッジ版)。 */

	/** 7FFFh (I/O Enabler2) bit 4. */
	void setIoEnabled(bool enabled) { if (useIoEnabler) ioEnabled = enabled; }

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	Y8960SSGS ssg;
	byte registerLatch;
	const bool readable;
	const bool useIoEnabler;
	bool ioEnabled;
};
SERIALIZE_CLASS_VERSION(Y8960SSGSDevice, 1);

} // namespace openmsx

#endif
