#ifndef Y8960OPL2DEVICE_HH
#define Y8960OPL2DEVICE_HH

#include "MSXDevice.hh"
#include "Y8960AdpcmMemory.hh"
#include "Y8960OPL2.hh"
#include "serialize_meta.hh"

namespace openmsx {

class Y8960OPL2Device final : public MSXDevice
{
public:
	explicit Y8960OPL2Device(const DeviceConfig& config);

	void reset(EmuTime time) override;
	[[nodiscard]] byte readIO(uint16_t port, EmuTime time) override;
	[[nodiscard]] byte peekIO(uint16_t port, EmuTime time) const override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;

	void writePort(bool port, byte value, EmuTime time);

	/** 7FFFh (I/O Enabler2) による直接 I/O ポートの開閉。
	  * メモリマップド I/O からの writePort() はこれに影響されない。 */
	void setIoEnabled(bool enabled) { if (useIoEnabler) ioEnabled = enabled; }

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	/** ADPCM のサンプルメモリは 2 個の OPL2 が 1 個の Y8960-ADPCM-RAM を見る。
	  * どちらの窓かは設定で決まる。分け方を選ぶレジスタが実機で決まったら、
	  * writeIO() から adpcmMemory.setLayout() を呼べばよい。 */
	Y8960AdpcmMemory& adpcmMemory;
	const unsigned adpcmBlock;
	Y8960OPL2 opl2;
	byte registerLatch;
	const bool useIoEnabler;
	bool ioEnabled;
};
SERIALIZE_CLASS_VERSION(Y8960OPL2Device, 1);

} // namespace openmsx

#endif
