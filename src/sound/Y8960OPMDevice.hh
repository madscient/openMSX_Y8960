#ifndef Y8960OPMDEVICE_HH
#define Y8960OPMDEVICE_HH

#include "MSXDevice.hh"
#include "YM2151.hh"
#include "serialize_meta.hh"

namespace openmsx {

/** Y8960 の OPM (YM2151)。直接 I/O は 7Eh = アドレス、7Fh = データ。
  * 7Fh を読むとステータスが返る。7Eh の読み出しには応じない。 */
class Y8960OPMDevice final : public MSXDevice
{
public:
	explicit Y8960OPMDevice(const DeviceConfig& config);

	void reset(EmuTime time) override;
	[[nodiscard]] byte readIO(uint16_t port, EmuTime time) override;
	[[nodiscard]] byte peekIO(uint16_t port, EmuTime time) const override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;

	void writePort(bool port, byte value, EmuTime time);

	/** 7FFFh (I/O Enabler2) による直接 I/O ポートの開閉。
	  * メモリマップド I/O からの writePort() はこれに影響されない。 */
	void setIoEnabled(bool enabled) { ioEnabled = enabled; }
	[[nodiscard]] bool isIoEnabled() const { return ioEnabled; }

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	YM2151 ym2151;
	byte registerLatch;
	bool ioEnabled;
};
SERIALIZE_CLASS_VERSION(Y8960OPMDevice, 1);

} // namespace openmsx

#endif
