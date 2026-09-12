#ifndef Y8960DCSGDEVICE_HH
#define Y8960DCSGDEVICE_HH

#include "MSXDevice.hh"
#include "Y8960DCSG.hh"
#include "serialize_meta.hh"

namespace openmsx {

/** The Y8960's DCSG block on its I/O port.
  *
  * One DCSG per instance. The chip latches everything through a single
  * write-only register, so the block occupies one port and the two circuits
  * are told apart by the address bit below it: 3Eh / 7FF0h reach the first,
  * 3Fh / 7FF1h the second.
  */
class Y8960DCSGDevice final : public MSXDevice
{
public:
	explicit Y8960DCSGDevice(const DeviceConfig& config);

	void reset(EmuTime time) override;
	void writeIO(uint16_t port, byte value, EmuTime time) override;

	void writePort(byte value, EmuTime time);

	/** 7FFFh (I/O Enabler2) bit 2 / bit 3 による直接 I/O ポートの開閉。
	  * メモリマップド I/O からの writePort() はこれに影響されない。
	  * 実機もそちらは常に通る（そうでないと I/O を開く手段が無くなる）。 */
	void setIoEnabled(bool enabled) { if (useIoEnabler) ioEnabled = enabled; }

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	Y8960DCSG dcsg;
	const bool useIoEnabler;
	bool ioEnabled;
};
SERIALIZE_CLASS_VERSION(Y8960DCSGDevice, 1);

} // namespace openmsx

#endif
