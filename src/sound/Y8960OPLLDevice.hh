#ifndef Y8960OPLLDEVICE_HH
#define Y8960OPLLDEVICE_HH

#include "MSXDevice.hh"
#include "Y8960OPLL.hh"
#include "serialize_meta.hh"

namespace openmsx {

/** The Y8960's OPLL block on its I/O ports. */
class Y8960OPLLDevice final : public MSXDevice
{
public:
	explicit Y8960OPLLDevice(const DeviceConfig& config);

	void reset(EmuTime time) override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;
	void writePort(bool port, byte value, EmuTime time);

	/** 7FF6h (I/O Enabler1) による直接 I/O ポートの開閉。
	  * メモリマップド I/O からの writePort() はこれに影響されない。
	  * 実機もそちらは常に通る（そうでないと I/O を開く手段が無くなる）。 */
	void setIoEnabled(bool enabled) { if (useIoEnabler) ioEnabled = enabled; }

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	Y8960OPLL opll;
	const bool useIoEnabler;
	bool ioEnabled;
};
SERIALIZE_CLASS_VERSION(Y8960OPLLDevice, 1);

} // namespace openmsx

#endif
