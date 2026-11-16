#ifndef Y8960CARTRIDGE_HH
#define Y8960CARTRIDGE_HH

#include "RomBlocks.hh"

#include "Ram.hh"
#include "Y8960.hh"

#include <array>
#include <cstdint>

namespace openmsx {

/** HRA!'s Y8960 sound cartridge: a Konami SCC style mapper with 128kB of RAM
  * next to the ROM, and memory mapped registers that reach its Y8960.
  */
class Y8960Cartridge final : public Rom8kBBlocks
{
public:
	Y8960Cartridge(const DeviceConfig& config, Rom&& rom);

	void powerUp(EmuTime time) override;
	void reset(EmuTime time) override;
	[[nodiscard]] byte peekMem(uint16_t address, EmuTime time) const override;
	[[nodiscard]] byte readMem(uint16_t address, EmuTime time) override;
	[[nodiscard]] const byte* getReadCacheLine(uint16_t address) const override;
	void writeMem(uint16_t address, byte value, EmuTime time) override;
	[[nodiscard]] byte* getWriteCacheLine(uint16_t address) override;

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	[[nodiscard]] uint8_t getBank(unsigned region) const { return bankReg[region - 2]; }
	[[nodiscard]] bool isRamRegion(unsigned region) const;
	[[nodiscard]] bool isSccRegion(unsigned region) const;
	[[nodiscard]] bool isSccAddress(uint16_t address) const;
	[[nodiscard]] bool isMmioVisible() const;
	[[nodiscard]] unsigned getRamAddress(uint16_t address) const;
	void setBank(unsigned region, uint8_t value);
	void writeMmio(uint16_t address, byte value, EmuTime time);

private:
	Y8960 y8960;
	Ram ram;
	std::array<uint8_t, 4> bankReg = {0, 1, 2, 3};
	bool ramEnabled = false;
};

} // namespace openmsx

#endif
