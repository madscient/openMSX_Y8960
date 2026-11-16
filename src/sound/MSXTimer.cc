#include "MSXTimer.hh"

#include "MSXMotherBoard.hh"
#include "serialize.hh"

#include <algorithm>

namespace openmsx {

MSXTimer::MSXTimer(MSXMotherBoard& motherBoard, const std::string& name)
	: counters{Counter(*this, motherBoard.getScheduler()), Counter(*this, motherBoard.getScheduler()),
	           Counter(*this, motherBoard.getScheduler()), Counter(*this, motherBoard.getScheduler())}
	, irq(motherBoard, name + ".IRQ")
{
}

void MSXTimer::reset(EmuTime time)
{
	for (auto& c : counters) c.reset(time);
	index = 0;
	select = 0;
	irq.reset();
}

uint8_t MSXTimer::readPort(unsigned port, EmuTime time)
{
	switch (port & 3) {
	case 1: case 2: case 3:
		for (auto& c : counters) c.sync(time);
		updateIrq();
		break;
	}
	return peekPort(port, time);
}

uint8_t MSXTimer::peekPort(unsigned port, EmuTime time) const
{
	switch (port & 3) {
	case 0:
		return index;
	case 1:
		return counters[(index >> 2) & 3].peekReg(index & 3);
	case 2: {
		uint8_t flags = 0;
		for (unsigned i = 0; i < 4; ++i) {
			if (counters[i].peekFlag(time)) flags |= uint8_t(1 << i);
		}
		return flags;
	}
	default:
		return (select < 4) ? counters[select].peekCount(time) : 0xFF;
	}
}

void MSXTimer::writePort(unsigned port, uint8_t value, EmuTime time)
{
	switch (port & 3) {
	case 0:
		index = value;
		break;
	case 1:
		counters[(index >> 2) & 3].writeReg(index & 3, value, time);
		break;
	case 2:
		for (unsigned i = 0; i < 4; ++i) {
			if (value & (1 << i)) counters[i].clearFlag(time);
		}
		break;
	case 3:
		select = (value & 0xFC) ? 4 : value;
		break;
	}
	updateIrq();
}

void MSXTimer::updateIrq()
{
	bool any = std::ranges::any_of(counters, &Counter::interrupt);
	if (any) {
		irq.set();
	} else {
		irq.reset();
	}
}


MSXTimer::Counter::Counter(MSXTimer& timer_, Scheduler& scheduler)
	: Schedulable(scheduler)
	, timer(timer_)
{
	clock.setFreq(CLOCK_FREQ);
}

void MSXTimer::Counter::reset(EmuTime time)
{
	removeSyncPoint();
	clock.reset(time);
	ticks = 0;
	terminal = resolution = 0;
	repeat = intEnable = counting = ended = false;
}

uint8_t MSXTimer::Counter::peekReg(unsigned reg) const
{
	switch (reg) {
	case 0: return uint8_t((repeat ? 0x01 : 0) | (resolution << 4) | (intEnable ? 0x80 : 0));
	case 1: return terminal;
	case 2: return counting;
	default: return 0;
	}
}

void MSXTimer::Counter::writeReg(unsigned reg, uint8_t value, EmuTime time)
{
	sync(time);
	switch (reg) {
	case 0:
		repeat = value & 1;
		resolution = (value >> 4) & 7;
		intEnable = value & 0x80;
		break;
	case 1:
		terminal = value;
		break;
	case 2:
		counting = value & 1;
		if (value & 2) ticks = 0;
		break;
	}
	schedule();
}

void MSXTimer::Counter::clearFlag(EmuTime time)
{
	sync(time);
	ended = false;
	schedule();
}

// The count ends on the last clock of the unit in which it reaches the
// terminal value, or of the current unit if it is past it already. A
// repeating counter starts again from 0, the others stop there.
void MSXTimer::Counter::advance(uint64_t& t, bool& end, bool& on, uint64_t elapsed) const
{
	while (on && elapsed) {
		uint64_t boundary = uint64_t(std::max(count(t), terminal) + 1) << shift();
		uint64_t step = std::min(boundary - t, elapsed);
		t += step;
		elapsed -= step;
		if (t == boundary) {
			end = true;
			if (repeat) {
				t = 0;
			} else {
				t = boundary - 1;
				on = false;
			}
		}
	}
}

void MSXTimer::Counter::sync(EmuTime time)
{
	advance(ticks, ended, counting, clock.getTicksTill(time));
	clock.advance(time);
}

uint8_t MSXTimer::Counter::peekCount(EmuTime time) const
{
	uint64_t t = ticks;
	bool end = ended;
	bool on = counting;
	advance(t, end, on, clock.getTicksTill(time));
	return count(t);
}

bool MSXTimer::Counter::peekFlag(EmuTime time) const
{
	uint64_t t = ticks;
	bool end = ended;
	bool on = counting;
	advance(t, end, on, clock.getTicksTill(time));
	return end;
}

void MSXTimer::Counter::schedule()
{
	removeSyncPoint();
	if (counting) {
		uint64_t boundary = uint64_t(std::max(count(ticks), terminal) + 1) << shift();
		setSyncPoint(clock + (boundary - ticks));
	}
}

void MSXTimer::Counter::executeUntil(EmuTime time)
{
	sync(time);
	schedule();
	timer.updateIrq();
}

template<typename Archive>
void MSXTimer::Counter::serialize(Archive& ar, unsigned /*version*/)
{
	ar.template serializeBase<Schedulable>(*this);
	ar.serialize("clock",      clock,
	             "ticks",      ticks,
	             "terminal",   terminal,
	             "resolution", resolution,
	             "repeat",     repeat,
	             "intEnable",  intEnable,
	             "counting",   counting,
	             "ended",      ended);
}

template<typename Archive>
void MSXTimer::serialize(Archive& ar, unsigned /*version*/)
{
	ar.serialize("counter0", counters[0],
	             "counter1", counters[1],
	             "counter2", counters[2],
	             "counter3", counters[3],
	             "irq",      irq,
	             "index",    index,
	             "select",   select);
}
INSTANTIATE_SERIALIZE_METHODS(MSXTimer);

} // namespace openmsx
