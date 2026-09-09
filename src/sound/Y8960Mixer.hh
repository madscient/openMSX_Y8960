#ifndef Y8960MIXER_HH
#define Y8960MIXER_HH

#include "EnumSetting.hh"
#include "MSXDevice.hh"
#include "MSXMixer.hh"
#include "serialize_meta.hh"

#include <array>
#include <memory>
#include <string_view>
#include <vector>

namespace openmsx {

/** The Y8960's sound output and its digital mixer.
  *
  * The cartridge does **not** feed its audio back into the MSX; the two
  * outputs are separate wires and whoever owns the machine either switches
  * between them or mixes them. That choice is the output setting below.
  * The cartridge defaults to its own output alone, a built-in Y8960 to the
  * mix, because there is only one output to hear in that case.
  *
  * The mixer proper takes a left/right gain per sound chip and one overall
  * gain, and applies both to the Y8960's own devices.
  *
  * **Nothing drives those gains.** The hardware block does not exist yet and
  * its registers are unspecified, so B6h-B7h only stores what is written to
  * it and every gain stays at unity. Wiring them up is a matter of calling
  * setChannelGain() / setMasterGain() from writeIO() once the register layout
  * is known.
  */
class Y8960Mixer final : public MSXDevice, private Observer<Setting>
{
public:
	static constexpr int ChannelCount = 10;
	static constexpr int RegCount = ChannelCount * 2;

	explicit Y8960Mixer(const DeviceConfig& config);
	~Y8960Mixer() override;

	void reset(EmuTime time) override;
	[[nodiscard]] byte readIO(uint16_t port, EmuTime time) override;
	[[nodiscard]] byte peekIO(uint16_t port, EmuTime time) const override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;

	/** 音源チップ 1 個ぶんの左右ゲイン。0.0 が無音、1.0 が素通り。 */
	void setChannelGain(int channel, float left, float right);

	/** Y8960 の音源すべてに掛かるゲイン。0.0 が無音、1.0 が素通り。 */
	void setMasterGain(float gain);

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	struct Gain { float left, right; };

	void applyGain(int channel);
	void applyAllGains();
	void updateSelector();
	void update(const Setting& setting) noexcept override;

private:
	std::array<std::vector<std::string_view>, ChannelCount> channelDevices;
	std::array<Gain, ChannelCount> channelGain;
	float masterGain;
	std::array<byte, RegCount> regs;
	byte registerLatch;
	std::unique_ptr<EnumSetting<MSXMixer::OutputSelect>> outputSetting;
};
SERIALIZE_CLASS_VERSION(Y8960Mixer, 2);

} // namespace openmsx

#endif
