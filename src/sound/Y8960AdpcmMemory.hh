#ifndef Y8960ADPCMMEMORY_HH
#define Y8960ADPCMMEMORY_HH

#include "MSXDevice.hh"
#include "TrackedRam.hh"
#include "serialize_meta.hh"

#include <cstdint>

namespace openmsx {

/** The ADPCM sample memory that the Y8960's two OPL2 blocks divide between
  * them.
  *
  * The cartridge has one 256kB region of SRAM for ADPCM (40000h-7FFFFh of the
  * serial SRAM) and both OPL2 blocks address it, so the memory is a device of
  * its own that the blocks refer to instead of something either block owns.
  * The manual offers 256kB shared by both blocks or 128kB each; giving all
  * 256kB to one block is the remaining pair of cases.
  *
  * **Nothing selects between the four.** The register that would is in
  * neither the RTL nor the register tables, so setLayout() is never called
  * and the memory stays shared. Wiring it up once the hardware decides is a
  * matter of calling setLayout() from wherever that register lands.
  */
class Y8960AdpcmMemory final : public MSXDevice
{
public:
	/** How the memory is divided between block 0 and block 1. */
	enum class Layout : uint8_t {
		Shared, // all of it to both blocks; each sees the other's writes
		First,  // all of it to block 0, nothing to block 1
		Second, // nothing to block 0, all of it to block 1
		Split,  // half to each block
	};

	static constexpr unsigned Size = 256 * 1024;
	static constexpr unsigned BlockCount = 2;

	explicit Y8960AdpcmMemory(const DeviceConfig& config);

	void powerUp(EmuTime time) override;

	/** The memory as one OPL2 block sees it. How much a block can reach and
	  * where its window starts both follow the layout. Addresses at or past
	  * size() read as 0 and writes to them are dropped, which is what a real
	  * chip does where the address space is wider than the memory behind it. */
	[[nodiscard]] unsigned size(unsigned block) const;
	[[nodiscard]] uint8_t read(unsigned block, unsigned addr) const;
	void write(unsigned block, unsigned addr, uint8_t value);
	void clear(unsigned block);

	void setLayout(Layout newLayout) { layout = newLayout; }
	[[nodiscard]] Layout getLayout() const { return layout; }

	template<typename Archive>
	void serialize(Archive& ar, unsigned version);

private:
	[[nodiscard]] unsigned offset(unsigned block) const;

	TrackedRam ram;
	Layout layout;
};
SERIALIZE_CLASS_VERSION(Y8960AdpcmMemory, 1);

} // namespace openmsx

#endif
