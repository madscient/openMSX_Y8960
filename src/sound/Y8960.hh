#ifndef Y8960_HH
#define Y8960_HH

#include "AY8910.hh"
#include "SCC.hh"
#include "Y8950.hh"
#include "Y8950Periphery.hh"
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

	// OPL2 with ADPCM: port 0 address (write) and status (read), port 1 data
	[[nodiscard]] uint8_t readOpl2(bool port, EmuTime time);
	[[nodiscard]] uint8_t peekOpl2(bool port, EmuTime time) const;
	void writeOpl2(bool port, uint8_t value, EmuTime time);

	// SSGS, two SSGs behind one pair of ports: port 0 address, port 1 data.
	// 00h-0Fh is SSG 0, 10h-1Fh SSG 1, 20h-2Fh the volume and pan of their
	// channels.
	void writeSsg(bool port, uint8_t value, EmuTime time);

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

	// nothing on the OPL2's general purpose I/O
	struct NoPeriphery final : Y8950Periphery {
		void write(uint4_t outputs, uint4_t values, EmuTime time) override;
		[[nodiscard]] uint4_t read(EmuTime time) override;
	} noPeriphery;
	Y8950 opl2;
	uint8_t opl2Latch = 0;
	std::array<AY8910, 2> ssg;
	uint8_t ssgLatch = 0;

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
