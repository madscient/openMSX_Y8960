#ifndef Y8960SSGSDEVICE_HH
#define Y8960SSGSDEVICE_HH

#include "AY8910Periphery.hh"
#include "MSXDevice.hh"
#include "Y8960SSGS.hh"
#include "serialize_meta.hh"

#include <array>

namespace openmsx {

class CassettePortInterface;
class RenShaTurbo;
class JoystickPortIf;

/** The Y8960's SSGS block on its I/O ports.
  *
  *   base+0  write the register number
  *   base+1  write the register
  *   base+2  read the register
  *
  * Same layout as the MSX PSG, but the register number is 6 bits wide here
  * because there are two units.
  */
class Y8960SSGSDevice final : public MSXDevice, public AY8910Periphery
{
public:
	explicit Y8960SSGSDevice(const DeviceConfig& config);
	~Y8960SSGSDevice() override;

	void reset(EmuTime time) override;
	void powerDown(EmuTime time) override;
	[[nodiscard]] byte readIO(uint16_t port, EmuTime time) override;
	[[nodiscard]] byte peekIO(uint16_t port, EmuTime time) const override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;

	void writePort(bool port, byte value, EmuTime time);

	/** カートリッジ版はリードに反応しない。A0h-A2h は本体 PSG と重なっており、
	  * 読み出しに応じると本体と衝突するため。本体内蔵版は既存の PSG を
	  * 置き換えるので読み書きの両方に応じる。
	  * XML の <readable> で切り替える (既定はカートリッジ版)。
	  * <io> の type も広げないと readIO() まで来ないので注意。 */

	/** 7FFFh (I/O Enabler2) bit 4. */
	void setIoEnabled(bool enabled) { if (useIoEnabler) ioEnabled = enabled; }

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	// AY8910Periphery: port A input, port B output. The built-in Y8960
	// stands in for the machine's PSG, so this is the PSG's wiring.
	[[nodiscard]] byte readA(EmuTime time) override;
	void writeB(byte value, EmuTime time) override;

private:
	const bool readable;
	const bool useIoEnabler;
	const bool gpio;
	CassettePortInterface& cassette;
	RenShaTurbo& renShaTurbo;
	std::array<JoystickPortIf*, 2> ports;
	int selectedPort = 0;
	byte prev = 255;
	const byte keyLayout; // 0x40 or 0x00
	byte registerLatch;
	bool ioEnabled;
	Y8960SSGS ssgs; // must come after everything it is handed above
};
SERIALIZE_CLASS_VERSION(Y8960SSGSDevice, 2);

} // namespace openmsx

#endif
