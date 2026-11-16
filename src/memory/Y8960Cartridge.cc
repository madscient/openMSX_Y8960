// HRA!'s Y8960 sound cartridge.
//
// Mapper: four 8kB regions at 0x4000-0xBFFF, each with a bank register.
//   The hardware keeps the low 6 bits of a bank number:
//     0-15   ROM
//     16-31  RAM (read-only unless in RAM mode)
//     32-62  the same as 0-30
//     63     SCC registers in the upper 2kB of the region (0x1800-0x1FFF).
//            Only 0x9800-0x9FFF is where a Konami SCC has them.
//   0x4000-0x7FFF is mirrored at 0xC000-0xFFFF, 0x8000-0xBFFF at 0x0000-0x3FFF.
//
// Bank registers:
//   Normal mode: 0x5000-0x57FF, 0x7000-0x77FF, 0x9000-0x97FF, 0xB000-0xB7FF.
//   RAM mode:    0x48FC-0x48FF, mirrored every 0x100 up to 0x4FFF. RAM in
//                0x6000-0xBFFF is writable; 0x4000-0x5FFF holds these
//                registers and shows no SCC.
//   0x48FB (mirrored the same way) bit 0 selects RAM mode.
//
// SCC pan: 0x9900-0x9904, channel A-E, while 0x9800-0x9FFF shows the SCC.
//   Writes there don't reach the SCC; reads and the rest of 0x99xx do.
//
// Memory mapped registers, write-only but for 0x7FFF, at 0x7FE0-0x7FFF while
// 0x6000-0x7FFF shows neither RAM nor the SCC:
//   0x7FF0/0x7FF1 SSG address/data
//   0x7FF2/0x7FF3 OPL2 address/data
//   0x7FF4/0x7FF5 OPLL address/data
//   0x7FF6 I/O Enabler1: bit 0 opens the OPLL ports
//   0x7FF7 SSG volume   0x7FF8 OPLL volume   0x7FF9 OPL2 volume
//   0x7FFA SCC volume   0x7FFD OPM volume    0x7FFE master volume
//   0x7FFB/0x7FFC OPM address/data, in between the volumes
//   0x7FFF I/O Enabler2, readable: bit 0 opens the OPL2 ports, bit 1 the
//          SSG's, bit 2 the OPM's, bit 7 the MSX-TIMER's
//
// I/O ports, all closed after reset like the FM-PAC's:
//   0x7C/0x7D OPLL address/data (write-only)
//   0x7E/0x7F OPM address and data/status (the status on 0x7F only)
//   0xA0/0xA1 SSG address/data (write-only), shared with the MSX's own PSG
//   0xB0-0xB3 MSX-TIMER. Its counters and interrupt run on while the ports
//             are closed: the enable bit only gates the address decoding.
//   0xC0/0xC1 OPL2 address and status/data

#include "Y8960Cartridge.hh"

#include "CacheLine.hh"
#include "MSXCPUInterface.hh"
#include "serialize.hh"

#include "xrange.hh"

namespace openmsx {

static constexpr unsigned ROM_BANKS = 16;
static constexpr unsigned RAM_BANKS = 16;
static constexpr uint8_t SCC_BANK = 0x3F;

Y8960Cartridge::Y8960Cartridge(const DeviceConfig& config, Rom&& rom_)
	: Rom8kBBlocks(config, std::move(rom_))
	, y8960(getName(), config, getCurrentTime())
	, ram(config, getName() + " RAM", "Y8960 RAM", RAM_BANKS * 0x2000)
{
	powerUp(getCurrentTime());
}

Y8960Cartridge::~Y8960Cartridge()
{
	writeIoEnabler1(0);
	writeIoEnabler2(0);
}

void Y8960Cartridge::powerUp(EmuTime time)
{
	y8960.powerUp(time);
	reset(time);
}

void Y8960Cartridge::reset(EmuTime time)
{
	writeIoEnabler1(0);
	writeIoEnabler2(0);
	ramEnabled = false;
	for (auto region : xrange(2u, 6u)) {
		setBank(region, uint8_t(region - 2));
	}
	y8960.reset(time);
}

bool Y8960Cartridge::isRamRegion(unsigned region) const
{
	auto bank = getBank(region) & 0x3F;
	return (bank != SCC_BANK) && (bank & 0x10);
}

bool Y8960Cartridge::isSccRegion(unsigned region) const
{
	if (ramEnabled && (region == 2)) return false;
	return (getBank(region) & 0x3F) == SCC_BANK;
}

bool Y8960Cartridge::isSccAddress(uint16_t address) const
{
	return (0x4000 <= address) && (address < 0xC000) &&
	       ((address & 0x1800) == 0x1800) && isSccRegion(address >> 13);
}

bool Y8960Cartridge::isMmioVisible() const
{
	// 0x7FE0-0x7FFF lies inside the SCC registers of the same region
	if (ramEnabled && isRamRegion(3)) return false;
	return !isSccRegion(3);
}

bool Y8960Cartridge::isIoEnabler2(uint16_t address) const
{
	return (address == 0x7FFF) && isMmioVisible();
}

unsigned Y8960Cartridge::getRamAddress(uint16_t address) const
{
	return (getBank(address >> 13) & 0x0F) * 0x2000 + (address & 0x1FFF);
}

void Y8960Cartridge::setBank(unsigned region, uint8_t value)
{
	bankReg[region - 2] = value;
	auto block = value % ROM_BANKS;
	setRom(region, block);
	if (region < 4) {
		setRom(region + 4, block); // 0x4000-0x7FFF at 0xC000-0xFFFF
	} else {
		setRom(region - 4, block); // 0x8000-0xBFFF at 0x0000-0x3FFF
	}
	// After setRom(), which points the CPU's read cache at the ROM block:
	// the region may show RAM, or the SCC in its upper 2kB.
	invalidateDeviceRWCache(region << 13, 0x2000);
}

byte Y8960Cartridge::peekMem(uint16_t address, EmuTime time) const
{
	if (isIoEnabler2(address)) {
		return ioEnabler2;
	} else if (isSccAddress(address)) {
		return y8960.peekScc(uint8_t(address), time);
	} else if (isRamRegion(address >> 13)) {
		return ram[getRamAddress(address)];
	} else {
		return Rom8kBBlocks::peekMem(address, time);
	}
}

byte Y8960Cartridge::readMem(uint16_t address, EmuTime time)
{
	if (isIoEnabler2(address)) {
		return ioEnabler2;
	} else if (isSccAddress(address)) {
		return y8960.readScc(uint8_t(address), time);
	} else if (isRamRegion(address >> 13)) {
		return ram[getRamAddress(address)];
	} else {
		return Rom8kBBlocks::readMem(address, time);
	}
}

const byte* Y8960Cartridge::getReadCacheLine(uint16_t address) const
{
	if (isIoEnabler2(address | CacheLine::LOW)) {
		return nullptr;
	} else if (isSccAddress(address)) {
		return nullptr;
	} else if (isRamRegion(address >> 13)) {
		return &ram[getRamAddress(address)];
	} else {
		return Rom8kBBlocks::getReadCacheLine(address);
	}
}

void Y8960Cartridge::writeMem(uint16_t address, byte value, EmuTime time)
{
	if ((address < 0x4800) || (address >= 0xC000)) return;

	if (isSccAddress(address)) {
		if ((0x9900 <= address) && (address <= 0x9904)) {
			y8960.writeSccPan(address - 0x9900, value, time);
		} else {
			y8960.writeScc(uint8_t(address), value, time);
		}
		return;
	}

	if (ramEnabled && (address >= 0x6000) && isRamRegion(address >> 13)) {
		ram[getRamAddress(address)] = value;
	}

	if (isMmioVisible()) {
		writeMmio(address, value, time);
	}

	if ((address & 0xF8FF) == 0x48FB) {
		bool newRamEnabled = value & 1;
		if (newRamEnabled != ramEnabled) {
			ramEnabled = newRamEnabled;
			invalidateDeviceRWCache(0x4000, 0x8000);
		}
	}

	if (!ramEnabled && ((address & 0x1800) == 0x1000)) {
		auto region = unsigned(address >> 13);
		if (value != getBank(region)) setBank(region, value);
	} else if (ramEnabled && ((address & 0xF8FC) == 0x48FC)) {
		auto region = unsigned(address & 3) + 2;
		if (value != getBank(region)) setBank(region, value);
	}
}

void Y8960Cartridge::writeMmio(uint16_t address, byte value, EmuTime time)
{
	using enum Y8960::Block;
	switch (address) {
	case 0x7FF0: case 0x7FF1: y8960.writeSsg (address & 1, value, time); break;
	case 0x7FF2: case 0x7FF3: y8960.writeOpl2(address & 1, value, time); break;
	case 0x7FF4: case 0x7FF5: y8960.writeOpll(address & 1, value, time); break;
	case 0x7FF6: writeIoEnabler1(value); break;
	case 0x7FF7: y8960.writeVolume(SSG,  value, time); break;
	case 0x7FF8: y8960.writeVolume(OPLL, value, time); break;
	case 0x7FF9: y8960.writeVolume(OPL2, value, time); break;
	case 0x7FFA: y8960.writeVolume(SCC,  value, time); break;
	case 0x7FFB: y8960.writeOpm(false, value, time); break;
	case 0x7FFC: y8960.writeOpm(true,  value, time); break;
	case 0x7FFD: y8960.writeVolume(OPM,  value, time); break;
	case 0x7FFE: y8960.writeMasterVolume(value, time); break;
	case 0x7FFF: writeIoEnabler2(value); break;
	default: break;
	}
}

void Y8960Cartridge::writeIoEnabler1(uint8_t value)
{
	value &= 0x01;
	if (value != ioEnabler1) {
		if (value) {
			getCPUInterface().register_IO_Out_range(0x7C, 2, this);
		} else {
			getCPUInterface().unregister_IO_Out_range(0x7C, 2, this);
		}
	}
	ioEnabler1 = value;
}

void Y8960Cartridge::writeIoEnabler2(uint8_t value)
{
	value &= 0x87;
	auto changed = value ^ ioEnabler2;
	auto& cpu = getCPUInterface();
	if (changed & 0x01) {
		if (value & 0x01) {
			cpu.register_IO_InOut_range(0xC0, 2, this);
		} else {
			cpu.unregister_IO_InOut_range(0xC0, 2, this);
		}
	}
	if (changed & 0x02) {
		if (value & 0x02) {
			cpu.register_IO_Out_range(0xA0, 2, this);
		} else {
			cpu.unregister_IO_Out_range(0xA0, 2, this);
		}
	}
	if (changed & 0x04) {
		if (value & 0x04) {
			cpu.register_IO_InOut_range(0x7E, 2, this);
		} else {
			cpu.unregister_IO_InOut_range(0x7E, 2, this);
		}
	}
	if (changed & 0x80) {
		if (value & 0x80) {
			cpu.register_IO_InOut_range(0xB0, 4, this);
		} else {
			cpu.unregister_IO_InOut_range(0xB0, 4, this);
		}
	}
	ioEnabler2 = value;
}

byte Y8960Cartridge::readIO(uint16_t port, EmuTime time)
{
	switch (port & 0xFF) {
	case 0x7E: case 0x7F: return y8960.readOpm(port & 1);
	case 0xB0: case 0xB1: case 0xB2: case 0xB3: return y8960.readTimer(port & 3, time);
	case 0xC0: case 0xC1: return y8960.readOpl2(port & 1, time);
	default: return 0xFF;
	}
}

byte Y8960Cartridge::peekIO(uint16_t port, EmuTime time) const
{
	switch (port & 0xFF) {
	case 0x7E: case 0x7F: return y8960.readOpm(port & 1);
	case 0xB0: case 0xB1: case 0xB2: case 0xB3: return y8960.peekTimer(port & 3, time);
	case 0xC0: case 0xC1: return y8960.peekOpl2(port & 1, time);
	default: return 0xFF;
	}
}

void Y8960Cartridge::writeIO(uint16_t port, byte value, EmuTime time)
{
	switch (port & 0xFF) {
	case 0x7C: case 0x7D: y8960.writeOpll(port & 1, value, time); break;
	case 0x7E: case 0x7F: y8960.writeOpm (port & 1, value, time); break;
	case 0xA0: case 0xA1: y8960.writeSsg (port & 1, value, time); break;
	case 0xB0: case 0xB1: case 0xB2: case 0xB3: y8960.writeTimer(port & 3, value, time); break;
	case 0xC0: case 0xC1: y8960.writeOpl2(port & 1, value, time); break;
	default: break;
	}
}

byte* Y8960Cartridge::getWriteCacheLine(uint16_t address)
{
	if ((address < 0x4800) || (address >= 0xC000)) {
		return unmappedWrite.data();
	} else if (address < 0x5000) {
		return nullptr; // RAM mode registers
	} else if ((address & CacheLine::HIGH) == 0x7F00) {
		return nullptr; // memory mapped registers
	} else if (isSccAddress(address)) {
		return nullptr;
	} else if ((address & 0x1800) == 0x1000) {
		return nullptr; // bank registers
	} else if (ramEnabled && (address >= 0x6000) && isRamRegion(address >> 13)) {
		return &ram[getRamAddress(address)];
	} else {
		return unmappedWrite.data();
	}
}

template<typename Archive>
void Y8960Cartridge::serialize(Archive& ar, unsigned /*version*/)
{
	ar.template serializeBase<Rom8kBBlocks>(*this);
	ar.serialize("y8960",      y8960,
	             "ram",        ram,
	             "bankReg",    bankReg,
	             "ramEnabled", ramEnabled);
	// through the setters, which register the ports that are open
	auto enabler1 = ioEnabler1;
	auto enabler2 = ioEnabler2;
	ar.serialize("ioEnabler1", enabler1,
	             "ioEnabler2", enabler2);
	if constexpr (Archive::IS_LOADER) {
		writeIoEnabler1(enabler1);
		writeIoEnabler2(enabler2);
	}
}
INSTANTIATE_SERIALIZE_METHODS(Y8960Cartridge);
REGISTER_MSXDEVICE(Y8960Cartridge, "Y8960Cartridge");

} // namespace openmsx
