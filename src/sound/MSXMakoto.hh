#ifndef MSXMAKOTO_HH
#define MSXMAKOTO_HH

#include "MSXDevice.hh"
#include "YM2608.hh"

namespace openmsx {

/** Makoto: a sound cartridge with one YM2608 (OPNA) on four I/O ports. */
class MSXMakoto final : public MSXDevice
{
public:
	explicit MSXMakoto(DeviceConfig& config);

	void powerUp(EmuTime time) override;
	void reset(EmuTime time) override;
	[[nodiscard]] byte readIO(uint16_t port, EmuTime time) override;
	[[nodiscard]] byte peekIO(uint16_t port, EmuTime time) const override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	YM2608 ym2608;
};

} // namespace openmsx

#endif
