#ifndef Y8950ADPCM_HH
#define Y8950ADPCM_HH

#include "Clock.hh"
#include "Schedulable.hh"
#include "TrackedRam.hh"
#include "serialize_meta.hh"

#include <cstdint>

namespace openmsx {

class DeviceConfig;

/** What Y8950Adpcm needs from the chip that owns it.
  * The Y8960's OPL2 block has the same status register as the Y8950, so it
  * can host this same ADPCM implementation without duplicating it.
  */
class Y8950Status
{
public:
	// Bitmask for register 0x04
	static constexpr int R04_ST1          = 0x01; // Timer1 Start
	static constexpr int R04_ST2          = 0x02; // Timer2 Start
	static constexpr int R04_MASK_BUF_RDY = 0x08; // Mask 'Buffer Ready'
	static constexpr int R04_MASK_EOS     = 0x10; // Mask 'End of sequence'
	static constexpr int R04_MASK_T2      = 0x20; // Mask Timer2 flag
	static constexpr int R04_MASK_T1      = 0x40; // Mask Timer1 flag
	static constexpr int R04_IRQ_RESET    = 0x80; // IRQ RESET

	// Bitmask for status register
	static constexpr int STATUS_PCM_BSY = 0x01;
	static constexpr int STATUS_EOS     = R04_MASK_EOS;
	static constexpr int STATUS_BUF_RDY = R04_MASK_BUF_RDY;
	static constexpr int STATUS_T2      = R04_MASK_T2;
	static constexpr int STATUS_T1      = R04_MASK_T1;

	virtual void setStatus(uint8_t flags) = 0;
	virtual void resetStatus(uint8_t flags) = 0;
	[[nodiscard]] virtual uint8_t peekRawStatus() const = 0;

protected:
	~Y8950Status() = default;
};

class Y8950Adpcm final : public Schedulable
{
public:
	Y8950Adpcm(Y8950Status& host, const DeviceConfig& config,
	           const std::string& name, unsigned sampleRam);

	void clearRam();
	void reset(EmuTime time);
	[[nodiscard]] bool isMuted() const;
	void writeReg(uint8_t rg, uint8_t data, EmuTime time);
	[[nodiscard]] uint8_t readReg(uint8_t rg, EmuTime time);
	[[nodiscard]] uint8_t peekReg(uint8_t rg, EmuTime time) const;
	[[nodiscard]] int calcSample();
	void sync(EmuTime time);
	void resetStatus();

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	// This data is updated while playing
	struct PlayData {
		unsigned memPtr;
		unsigned nowStep;
		int out;
		int output;
		int diff;
		int nextLeveling;
		int sampleStep;
		uint8_t adpcm_data;
	};

	// Schedulable
	void executeUntil(EmuTime time) override;

	void schedule();
	void restart(PlayData& pd) const;

	[[nodiscard]] bool isPlaying() const;
	void writeData(uint8_t data);
	[[nodiscard]] uint8_t peekReg(uint8_t rg) const;
	[[nodiscard]] uint8_t readData();
	[[nodiscard]] uint8_t peekData() const;
	void writeMemory(unsigned memPtr, uint8_t value);
	[[nodiscard]] uint8_t readMemory(unsigned memPtr) const;
	[[nodiscard]] int calcSample(bool doEmu);

private:
	Y8950Status& host;
	TrackedRam ram;

	// copy/pasted from Y8950.hh
	static constexpr int CLOCK_FREQ     = 3579545;
	static constexpr int CLOCK_FREQ_DIV = 72;
	Clock<CLOCK_FREQ, CLOCK_FREQ_DIV> clock;

	PlayData emu; // used for emulator behaviour (read back of sample data)
	PlayData aud; // used by audio generation thread

	unsigned startAddr;
	unsigned stopAddr;
	unsigned addrMask;
	int volume = 0;
	int volumeWStep;
	int readDelay;
	int delta;
	uint8_t reg7;
	uint8_t reg15;
	bool romBank;
};
SERIALIZE_CLASS_VERSION(Y8950Adpcm, 2);

} // namespace openmsx

#endif
