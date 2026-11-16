#ifndef Y8960CARTRIDGE_HH
#define Y8960CARTRIDGE_HH

#include "RomBlocks.hh"

#include "MSXSwitchedDevice.hh"
#include "Ram.hh"
#include "Y8960.hh"

#include <array>
#include <cstdint>
#include <optional>

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
	/** The System Controller, on I/O 40h-4Fh as switched I/O id 80h. 41h
	  * selects a board by its id (02h is this cartridge) and 42h a function
	  * (01h is the Config ROM reader/writer); each reads back the complement
	  * of what selected it. Only this identification is emulated: the Config
	  * ROM reader/writer behind 43h-47h reads FFh and takes no writes.
	  * The hardware forgets the selection when 40h is written with anything
	  * but 80h. The device switch doesn't tell a switched device that it was
	  * deselected, so here the selection lasts until 41h is written again or
	  * a reset.
	  */
	struct SystemController final : MSXSwitchedDevice {
		explicit SystemController(MSXMotherBoard& motherBoard);
		void reset();
		[[nodiscard]] uint8_t readSwitchedIO(uint16_t port, EmuTime time) override;
		[[nodiscard]] uint8_t peekSwitchedIO(uint16_t port, EmuTime time) const override;
		void writeSwitchedIO(uint16_t port, uint8_t value, EmuTime time) override;
		template<typename Archive>
		void serialize(Archive& ar, unsigned version);

		bool boardSelected = false;
		bool romFunction = false;
	};

	Y8960 y8960;
	// a part of its own, so that a cartridge can go without one
	std::optional<SystemController> systemController;
	Ram ram;
	std::array<uint8_t, 4> bankReg = {0, 1, 2, 3};
	bool ramEnabled = false;
	uint8_t ioEnabler1 = 0;
	uint8_t ioEnabler2 = 0;
};

} // namespace openmsx

#endif
