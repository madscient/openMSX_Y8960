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
	void updateStreams(EmuTime time);
	void applyPrescale();
	[[nodiscard]] std::vector<uint8_t> saveChipState();

	// ym2608::generate() mixes FM+ADPCM and SSG into one stream at a rate
	// that is a multiple of both, repeating or averaging samples. Its
	// protected members let the two parts be clocked separately, each at
	// its own rate, without changing ymfm.
	struct Chip final : ymfm::ym2608 {
		using ym2608::ym2608;
		void clockFm(int32_t& left, int32_t& right);
		[[nodiscard]] int32_t clockSsg();
		[[nodiscard]] unsigned prescale() const { return m_fm.clock_prescale(); }
	};

	// The SSG is a separate stream (mono, at its own rate), so it is a
	// separate sound device.
	struct SsgPart final : ResampledSoundDevice {
		SsgPart(YM2608& parent, DeviceConfig& config);
		~SsgPart();
		void generateChannels(std::span<float*> bufs, unsigned num) override;
		void setRate(unsigned rate);
		using ResampledSoundDevice::updateStream;

		YM2608& parent;
	};

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

	Chip chip;
	Ram adpcmRam;
	std::optional<Rom> rhythmRom;
	IRQHelper irq;
	std::array<Timer, 2> timers;
	SsgPart ssgPart;
	// The rates the two sound devices are constructed with; reset() then
	// finds nothing to change, before the devices are registered.
	unsigned prescale = 6;

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
