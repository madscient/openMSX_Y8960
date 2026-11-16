#ifndef Y8960_HH
#define Y8960_HH

#include "SCC.hh"
#include "YM2413.hh"

#include "EmuTime.hh"
#include "SimpleDebuggable.hh"

#include <array>
#include <cstdint>
#include <string>

namespace openmsx {

class DeviceConfig;
class MSXMotherBoard;

/** The sound part of HRA!'s Y8960: its sound chips and its digital mixer.
  * How a CPU reaches them (ports, memory mapped registers, enable bits) is
  * up to whatever holds this, such as Y8960Cartridge.
  */
class Y8960
{
public:
	/** The blocks of the digital mixer, each with its own volume register. */
	enum class Block : uint8_t { SSG, OPLL, OPL2, SCC, OPM, NUM };

	Y8960(const std::string& name, const DeviceConfig& config, EmuTime time);

	void powerUp(EmuTime time);
	void reset(EmuTime time);

	// SCC, decoding the low 8 address bits like the SCC itself
	[[nodiscard]] uint8_t readScc(uint8_t address, EmuTime time);
	[[nodiscard]] uint8_t peekScc(uint8_t address, EmuTime time) const;
	void writeScc(uint8_t address, uint8_t value, EmuTime time);
	void writeSccPan(unsigned channel, uint8_t value, EmuTime time);

	// OPLL: port 0 address, port 1 data
	void writeOpll(bool port, uint8_t value, EmuTime time);

	// digital mixer
	void writeVolume(Block block, uint8_t value, EmuTime time);
	void writeMasterVolume(uint8_t value, EmuTime time);

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	void writeMixer(unsigned reg, uint8_t value, EmuTime time);
	void applyVolume(Block block, EmuTime time);
	void applyPan(unsigned reg, EmuTime time);
	void applyAll(EmuTime time);

private:
	MSXMotherBoard& motherBoard;
	SCC scc;
	YM2413 opll;
	uint8_t opllLatch = 0;

	// the registers of the digital mixer, laid out as in Y8960.cc
	std::array<uint8_t, 0x2E> mixer{};

	struct Debuggable final : SimpleDebuggable {
		Debuggable(MSXMotherBoard& motherBoard, const std::string& name);
		[[nodiscard]] uint8_t read(unsigned address) override;
		void write(unsigned address, uint8_t value, EmuTime time) override;
	} debuggable;
};

} // namespace openmsx

#endif
