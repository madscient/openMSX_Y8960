#ifndef Y8960SSGS_HH
#define Y8960SSGS_HH

#include "ResampledSoundDevice.hh"
#include "Y8960SsgCore.hh"

#include "EmuTime.hh"
#include "SimpleDebuggable.hh"

#include <array>
#include <cstdint>
#include <span>
#include <string>

namespace openmsx {

class AY8910Periphery;

/** The SSGS block of the Y8960: two YM2149 units with a panpot per channel.
  *
  * Register map, same as the YMZ705 (SSGS) and YMZ732 (SSGS2):
  *
  *   $00-$1F  unit 0        $20-$3F  unit 1
  *
  * and within a unit:
  *
  *   $00-$0D  YM2149 registers
  *   $0E-$0F  absent, unless the primary unit carries the GPIO
  *   $10-$12  4 bit panpot for channel A, B and C
  *
  * $40 and up is the ADPCM and sequencer area of those parts, which the Y8960
  * does not use.
  *
  * This is one stereo sound device rather than two mono ones because the
  * panpot is per channel, while openMSX only has a balance per device.
  */
class Y8960SSGS final : public ResampledSoundDevice
{
public:
	static constexpr unsigned NUM_UNITS = 2;
	static constexpr unsigned CHANNELS_PER_UNIT = 3;
	static constexpr unsigned NUM_CHANNELS = NUM_UNITS * CHANNELS_PER_UNIT;

	/** Highest panpot value; the register is 4 bits on the 705 and 732. */
	static constexpr uint8_t PAN_MAX = 15;
	static constexpr uint8_t PAN_CENTER = (PAN_MAX + 1) / 2;

	/** @param periphery what the primary unit's GPIO drives, or nullptr for
	  *                   a block without one. */
	Y8960SSGS(const std::string& name, const DeviceConfig& config, EmuTime time,
	          AY8910Periphery* periphery = nullptr);
	~Y8960SSGS();

	void reset(EmuTime time);
	void writeRegister(unsigned reg, uint8_t value, EmuTime time);
	[[nodiscard]] uint8_t readRegister(unsigned reg, EmuTime time);
	[[nodiscard]] uint8_t peekRegister(unsigned reg, EmuTime time) const;

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	// SoundDevice
	void generateChannels(std::span<float*> bufs, unsigned num) override;
	[[nodiscard]] float getAmplificationFactorImpl() const override;

	static void panGains(uint8_t pan, float& gainL, float& gainR);
	void measureDc();
	[[nodiscard]] bool isGpioReg(unsigned unit_, unsigned sub) const;

private:
	std::array<Y8960SsgCore, NUM_UNITS> unit;
	const bool hasGpio;
	std::array<uint8_t, NUM_CHANNELS> pan;

	/** The core's output is unipolar, so a silent channel does not sit at
	  * zero. That offset has to come off before the panpot is applied,
	  * otherwise the DC leaks into the stereo image. */
	std::array<float, NUM_CHANNELS> dc;

	struct Debuggable final : SimpleDebuggable {
		Debuggable(MSXMotherBoard& motherBoard, const std::string& name);
		[[nodiscard]] uint8_t read(unsigned address, EmuTime time) override;
		void write(unsigned address, uint8_t value, EmuTime time) override;
	} debuggable;
};

} // namespace openmsx

#endif
