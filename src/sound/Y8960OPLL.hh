#ifndef Y8960OPLL_HH
#define Y8960OPLL_HH

#include "MSXDevice.hh"
#include "YM2413.hh"
#include "serialize_meta.hh"

namespace openmsx {

class Y8960OPLL final : public MSXDevice
{
public:
	explicit Y8960OPLL(DeviceConfig& config);

	void reset(EmuTime time) override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;
	void writePort(bool port, byte value, EmuTime time);

	/** 7FF6h (I/O Enabler1) による直接 I/O ポートの開閉。
	  * メモリマップド I/O からの writePort() はこれに影響されない。
	  * 実機もそちらは常に通る（そうでないと I/O を開く手段が無くなる）。 */
	void setIoEnabled(bool enabled) { if (useIoEnabler) ioEnabled = enabled; }

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);
protected:
	YM2413 ym2413;
	const bool useIoEnabler;
	bool ioEnabled;
};
SERIALIZE_CLASS_VERSION(Y8960OPLL, 4);

} // namespace openmsx

#endif
