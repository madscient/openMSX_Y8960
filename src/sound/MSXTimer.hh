#ifndef MSXTIMER_HH
#define MSXTIMER_HH

#include "DynamicClock.hh"
#include "EmuTime.hh"
#include "IRQHelper.hh"
#include "Schedulable.hh"

#include <array>
#include <cstdint>
#include <string>

namespace openmsx {

class MSXMotherBoard;

/** The MSX-TIMER of HRA!'s Y8960: four counters that count up to a terminal
  * value, each with its interrupt, behind four ports:
  *   0: register index (bits 3-2 the counter, bits 1-0 its register)
  *   1: register data
  *   2: interrupt flags, bit n for counter n; writing 1 clears a flag
  *   3: write: which counter port 3 reads (0-3, anything else none);
  *      read: that counter's count, 0xFF for none
  * The registers of a counter:
  *   0: bit 0 repeat, bits 6-4 resolution, bit 7 interrupt enable
  *   1: terminal value
  *   2: bit 0 counting, writing bit 1 clears the count
  *   3: not there, reads 0
  */
class MSXTimer
{
public:
	// The timer's design sheet gives 85.9MHz, but the cartridge clocks it
	// with its 42.95MHz system clock.
	static constexpr unsigned CLOCK_FREQ = 3579545 * 12;

	MSXTimer(MSXMotherBoard& motherBoard, const std::string& name);

	void reset(EmuTime time);
	[[nodiscard]] uint8_t readPort(unsigned port, EmuTime time);
	[[nodiscard]] uint8_t peekPort(unsigned port, EmuTime time) const;
	void writePort(unsigned port, uint8_t value, EmuTime time);

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	class Counter final : public Schedulable {
	public:
		Counter(MSXTimer& timer, Scheduler& scheduler);

		void reset(EmuTime time);
		[[nodiscard]] uint8_t peekReg(unsigned reg) const;
		void writeReg(unsigned reg, uint8_t value, EmuTime time);
		void clearFlag(EmuTime time);
		void sync(EmuTime time);
		[[nodiscard]] uint8_t peekCount(EmuTime time) const;
		[[nodiscard]] bool peekFlag(EmuTime time) const;
		[[nodiscard]] bool flag() const { return ended; }
		[[nodiscard]] bool interrupt() const { return ended && intEnable; }

		template<typename Archive>
		void serialize(Archive& ar, unsigned version);

	private:
		void executeUntil(EmuTime time) override;
		[[nodiscard]] unsigned shift() const { return 10 + 2 * resolution; }
		[[nodiscard]] uint8_t count(uint64_t t) const { return uint8_t(t >> shift()); }
		void advance(uint64_t& t, bool& end, bool& on, uint64_t elapsed) const;
		void schedule();

		MSXTimer& timer;
		DynamicClock clock{EmuTime::zero()};
		uint64_t ticks = 0; // since the count was last cleared
		uint8_t terminal = 0;
		uint8_t resolution = 0;
		bool repeat = false;
		bool intEnable = false;
		bool counting = false;
		bool ended = false;
	};

	void updateIrq();

	std::array<Counter, 4> counters;
	IRQHelper irq;
	uint8_t index = 0;
	uint8_t select = 0; // 4: none
};

} // namespace openmsx

#endif
