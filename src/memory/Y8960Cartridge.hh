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
	~Y8960Cartridge() override;

	void powerUp(EmuTime time) override;
	void reset(EmuTime time) override;
	[[nodiscard]] byte peekMem(uint16_t address, EmuTime time) const override;
	[[nodiscard]] byte readMem(uint16_t address, EmuTime time) override;
	[[nodiscard]] const byte* getReadCacheLine(uint16_t address) const override;
	void writeMem(uint16_t address, byte value, EmuTime time) override;
	[[nodiscard]] byte* getWriteCacheLine(uint16_t address) override;
	[[nodiscard]] byte readIO(uint16_t port, EmuTime time) override;
	[[nodiscard]] byte peekIO(uint16_t port, EmuTime time) const override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	[[nodiscard]] uint8_t getBank(unsigned region) const { return bankReg[region - 2]; }
	[[nodiscard]] bool isRamRegion(unsigned region) const;
	[[nodiscard]] bool isSccRegion(unsigned region) const;
	[[nodiscard]] bool isSccAddress(uint16_t address) const;
	[[nodiscard]] bool isMmioVisible() const;
	[[nodiscard]] bool isIoEnabler2(uint16_t address) const;
	[[nodiscard]] unsigned getRamAddress(uint16_t address) const;
	void setBank(unsigned region, uint8_t value);
	void writeMmio(uint16_t address, byte value, EmuTime time);
	void writeIoEnabler1(uint8_t value);
	void writeIoEnabler2(uint8_t value);

private:
	Y8960 y8960;
	Ram ram;
	std::array<uint8_t, 4> bankReg = {0, 1, 2, 3};
	bool ramEnabled = false;
	uint8_t ioEnabler1 = 0;
	uint8_t ioEnabler2 = 0;
};

} // namespace openmsx

#endif
