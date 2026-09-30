#include "YM2608.hh"

#include "DeviceConfig.hh"
#include "MSXCliComm.hh"
#include "MSXException.hh"
#include "MSXMotherBoard.hh"
#include "serialize.hh"

#include "outer.hh"

namespace openmsx {

// Input clocks per sample of each part, for prescaler 6, 3 and 2
// (the table in ymfm_opn.h, "A note about prescaling and sample rates").
[[nodiscard]] static unsigned fmRate(unsigned prescale)
{
	// 8MHz/144 is not a whole number of Hz; rounding moves the pitch by
	// less than 10 ppm.
	return (YM2608::CLOCK_FREQ + 12 * prescale) / (24 * prescale);
}
[[nodiscard]] static unsigned ssgRate(unsigned prescale)
{
	return YM2608::CLOCK_FREQ / (prescale == 6 ? 32 : prescale == 3 ? 16 : 8);
}

[[nodiscard]] static EmuDuration clocksToDuration(uint64_t clocks)
{
	return EmuDuration(clocks * MAIN_FREQ / YM2608::CLOCK_FREQ);
}

YM2608::YM2608(const std::string& name_, DeviceConfig& config,
               unsigned sampleRamSize, EmuTime time)
	: ResampledSoundDevice(config.getMotherBoard(), name_, "YM2608 (OPNA) FM, rhythm and ADPCM",
	                       1, fmRate(6), true)
	, debuggable(config.getMotherBoard(), getName())
	, chip(static_cast<ymfm::ymfm_interface&>(*this))
	, adpcmRam(config, getName() + " ADPCM RAM", "YM2608 ADPCM sample RAM", sampleRamSize)
	, irq(config.getMotherBoard(), getName() + ".IRQ")
	, timers{{{config.getScheduler(), *this, 0},
	          {config.getScheduler(), *this, 1}}}
	, ssgPart(*this, config)
{
	// The rhythm samples live in a ROM inside the real chip. Its contents are
	// not shipped because their right to be redistributed is unclear;
	// without it the rhythm part is silent but its registers still work.
	if (config.findChild("rom")) {
		try {
			rhythmRom.emplace(getName() + " rhythm ROM", "YM2608 rhythm ROM", config);
		} catch (MSXException& e) {
			config.getCliComm().printWarning(
				"Rhythm ROM for ", getName(), " not loaded, the rhythm part "
				"will be silent: ", e.getMessage());
		}
	}

	reset(time);
	registerSound(config);
}

YM2608::~YM2608()
{
	unregisterSound();
}

void YM2608::clearRam()
{
	adpcmRam.clear(0xFF);
}

void YM2608::reset(EmuTime time)
{
	now = time;
	busyEnd = time;
	for (auto& t : timers) t.cancel();
	chip.reset();
	applyPrescale();
	irq.reset();
	address = 0;
	regs.fill(0);
}

void YM2608::updateStreams(EmuTime time)
{
	updateStream(time);
	ssgPart.updateStream(time);
}

void YM2608::applyPrescale()
{
	auto p = chip.prescale();
	if (p == prescale) return;
	prescale = p;
	// As in SamplePlayer: switching the resampler may drop a few samples.
	setInputRate(fmRate(p));
	createResampler();
	ssgPart.setRate(ssgRate(p));
}

void YM2608::writePort(unsigned port, uint8_t value, EmuTime time)
{
	now = time;
	updateStreams(time);
	// Writes during busy are not dropped. Programs that wait a fixed time
	// instead of polling the busy flag rely on this.
	switch (port & 3) {
	case 0:
		address = value;
		chip.write_address(value);
		applyPrescale();
		break;
	case 1:
		// ymfm ignores this write while the upper address is latched
		if (!(address & 0x100)) regs[address] = value;
		chip.write_data(value);
		break;
	case 2:
		address = 0x100 | value;
		chip.write_address_hi(value);
		applyPrescale();
		break;
	case 3:
		if (address & 0x100) regs[address] = value;
		chip.write_data_hi(value);
		break;
	}
}

uint8_t YM2608::readPort(unsigned port, EmuTime time)
{
	now = time;
	// ADPCM-B status (BRDY, EOS) advances only while samples are generated
	updateStream(time);
	return chip.read(port & 3);
}

uint8_t YM2608::peekPort(unsigned port, EmuTime /*time*/) const
{
	auto& c = const_cast<Chip&>(chip);
	switch (port & 3) {
	case 0: return c.read_status();
	case 1: return c.read_data();
	default:
		// ymfm's reads of the upper half change state (status
		// propagation, ADPCM memory pointer), so they cannot be peeked
		return 0xFF;
	}
}

void YM2608::writeRegister(unsigned reg, uint8_t value, EmuTime time)
{
	auto savedAddress = address;
	if (reg & 0x100) {
		writePort(2, uint8_t(reg), time);
		writePort(3, value, time);
	} else {
		writePort(0, uint8_t(reg), time);
		writePort(1, value, time);
	}
	// Rewriting the latch can touch the prescaler (2Dh-2Fh), but only in
	// a way it was already touched when the program wrote that address.
	writePort((savedAddress & 0x100) ? 2 : 0, uint8_t(savedAddress), time);
}

void YM2608::generateChannels(std::span<float*> bufs, unsigned num)
{
	// Always clock, even when silent: the ADPCM-B status advances only here.
	for (unsigned i = 0; i < num; ++i) {
		int32_t l, r;
		chip.clockFm(l, r);
		bufs[0][2 * i + 0] += float(l);
		bufs[0][2 * i + 1] += float(r);
	}
}


// Chip

void YM2608::Chip::clockFm(int32_t& left, int32_t& right)
{
	clock_fm_and_adpcm();
	left  = m_last_fm.data[0];
	right = m_last_fm.data[1];
}

int32_t YM2608::Chip::clockSsg()
{
	ymfm::ssg_engine::output_data o;
	m_ssg.clock();
	m_ssg.output(o);
	// The same 2/3 mix that ymfm's ssg_resampler applies
	return (o.data[0] + o.data[1] + o.data[2]) * 2 / 3;
}


// SsgPart

YM2608::SsgPart::SsgPart(YM2608& parent_, DeviceConfig& config)
	: ResampledSoundDevice(config.getMotherBoard(), parent_.getName() + " SSG",
	                       "YM2608 (OPNA) SSG", 1, ssgRate(6), false)
	, parent(parent_)
{
	registerSound(config);
}

YM2608::SsgPart::~SsgPart()
{
	unregisterSound();
}

void YM2608::SsgPart::setRate(unsigned rate)
{
	setInputRate(rate);
	createResampler();
}

void YM2608::SsgPart::generateChannels(std::span<float*> bufs, unsigned num)
{
	for (unsigned i = 0; i < num; ++i) {
		bufs[0][i] += float(parent.chip.clockSsg());
	}
}

void YM2608::ymfm_set_timer(uint32_t tnum, int32_t duration_in_clocks)
{
	auto& t = timers[tnum];
	if (duration_in_clocks < 0) {
		t.cancel();
	} else {
		t.schedule(now + clocksToDuration(uint64_t(duration_in_clocks)));
	}
}

void YM2608::timerExpired(unsigned tnum, EmuTime time)
{
	now = time;
	// timer A in CSM mode keys on channel 3
	updateStreams(time);
	m_engine->engine_timer_expired(tnum);
}

void YM2608::ymfm_set_busy_end(uint32_t clocks)
{
	busyEnd = now + clocksToDuration(clocks);
}

bool YM2608::ymfm_is_busy()
{
	return now < busyEnd;
}

void YM2608::ymfm_update_irq(bool asserted)
{
	irq.set(asserted);
}

uint8_t YM2608::ymfm_external_read(ymfm::access_class type, uint32_t addr)
{
	switch (type) {
	case ymfm::ACCESS_ADPCM_A:
		if (rhythmRom && addr < rhythmRom->size()) return (*rhythmRom)[addr];
		// Nibbles 0 and 8 step up and down by the smallest delta, so a
		// missing ROM decodes to (almost) silence instead of a ramp.
		return 0x08;
	case ymfm::ACCESS_ADPCM_B:
		if (adpcmRam.size() == 0) return 0xFF;
		return adpcmRam[addr % adpcmRam.size()];
	default:
		return 0xFF;
	}
}

void YM2608::ymfm_external_write(ymfm::access_class type, uint32_t addr, uint8_t data)
{
	if (type == ymfm::ACCESS_ADPCM_B && adpcmRam.size() != 0) {
		adpcmRam[addr % adpcmRam.size()] = data;
	}
}

std::vector<uint8_t> YM2608::saveChipState()
{
	std::vector<uint8_t> buf;
	ymfm::ymfm_saved_state state(buf, true);
	chip.save_restore(state);
	return buf;
}


// Timer

YM2608::Timer::Timer(Scheduler& scheduler, YM2608& parent_, unsigned tnum_)
	: Schedulable(scheduler), parent(parent_), tnum(tnum_)
{
}

void YM2608::Timer::executeUntil(EmuTime time)
{
	parent.timerExpired(tnum, time);
}

template<typename Archive>
void YM2608::Timer::serialize(Archive& ar, unsigned /*version*/)
{
	ar.template serializeBase<Schedulable>(*this);
}


// Debuggable

YM2608::Debuggable::Debuggable(MSXMotherBoard& motherBoard_, const std::string& name_)
	: SimpleDebuggable(motherBoard_, name_ + " regs", "YM2608 registers, last written values", 0x200)
{
}

uint8_t YM2608::Debuggable::read(unsigned addr, EmuTime /*time*/)
{
	const auto& ym = OUTER(YM2608, debuggable);
	return ym.regs[addr];
}

void YM2608::Debuggable::write(unsigned addr, uint8_t value, EmuTime time)
{
	auto& ym = OUTER(YM2608, debuggable);
	ym.writeRegister(addr, value, time);
}


template<typename Archive>
void YM2608::serialize(Archive& ar, unsigned /*version*/)
{
	ar.serialize("irq",      irq,
	             "timerA",   timers[0],
	             "timerB",   timers[1],
	             "adpcmRam", adpcmRam,
	             "address",  address,
	             "busyEnd",  busyEnd);
	ar.serialize_blob("registers", regs);

	// On load, saving first gives a buffer of the right size to load into.
	auto chipState = saveChipState();
	ar.serialize_blob("chip", std::span{chipState});
	if constexpr (Archive::IS_LOADER) {
		ymfm::ymfm_saved_state state(chipState, false);
		chip.save_restore(state);
		applyPrescale();
	}
}
INSTANTIATE_SERIALIZE_METHODS(YM2608);

} // namespace openmsx
