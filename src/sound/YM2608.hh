#ifndef YM2608_HH
#define YM2608_HH

#include "ResampledSoundDevice.hh"

#include "EmuTime.hh"
#include "IRQHelper.hh"
#include "Ram.hh"
#include "Rom.hh"
#include "Schedulable.hh"
#include "SimpleDebuggable.hh"

#include "3rdparty/ymfm/ymfm_opn.h"

#include <array>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <vector>

namespace openmsx {

class DeviceConfig;

class YM2608 final : private ResampledSoundDevice, private ymfm::ymfm_interface
{
public:
	static constexpr unsigned CLOCK_FREQ = 8000000;

	YM2608(const std::string& name, DeviceConfig& config,
	       unsigned sampleRamSize, EmuTime time);
	~YM2608();

	void clearRam();
	void reset(EmuTime time);

	// 'port' is A1:A0 of the chip, the same layout as ymfm::ym2608::read/write
	void writePort(unsigned port, uint8_t value, EmuTime time);
	[[nodiscard]] uint8_t readPort(unsigned port, EmuTime time);
	[[nodiscard]] uint8_t peekPort(unsigned port, EmuTime time) const;

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	// SoundDevice
	void generateChannels(std::span<float*> bufs, unsigned num) override;

	// ymfm_interface
	void ymfm_set_timer(uint32_t tnum, int32_t duration_in_clocks) override;
	void ymfm_set_busy_end(uint32_t clocks) override;
	bool ymfm_is_busy() override;
	void ymfm_update_irq(bool asserted) override;
	uint8_t ymfm_external_read(ymfm::access_class type, uint32_t address) override;
	void ymfm_external_write(ymfm::access_class type, uint32_t address, uint8_t data) override;

	void writeRegister(unsigned reg, uint8_t value, EmuTime time);
	void timerExpired(unsigned tnum, EmuTime time);
	[[nodiscard]] std::vector<uint8_t> saveChipState();

	struct Timer final : Schedulable {
		Timer(Scheduler& scheduler, YM2608& parent, unsigned tnum);
		void schedule(EmuTime time) { removeSyncPoint(); setSyncPoint(time); }
		void cancel() { removeSyncPoint(); }
		void executeUntil(EmuTime time) override;
		template<typename Archive>
		void serialize(Archive& ar, unsigned version);

		YM2608& parent;
		const unsigned tnum;
	};

	struct Debuggable final : SimpleDebuggable {
		Debuggable(MSXMotherBoard& motherBoard, const std::string& name);
		[[nodiscard]] uint8_t read(unsigned address, EmuTime time) override;
		void write(unsigned address, uint8_t value, EmuTime time) override;
	} debuggable;

	ymfm::ym2608 chip;
	Ram adpcmRam;
	std::optional<Rom> rhythmRom;
	IRQHelper irq;
	std::array<Timer, 2> timers;

	std::vector<ymfm::ym2608::output_data> outputBuffer;

	// ymfm calls back into this object without passing the time along
	EmuTime now = EmuTime::zero();
	EmuTime busyEnd = EmuTime::zero();

	// ymfm keeps one address latch for both register arrays; this is a
	// copy of it, so that the debuggable can put it back after a write
	uint16_t address = 0;
	std::array<uint8_t, 0x200> regs;
};

} // namespace openmsx

#endif
