#include "Y8960AdpcmMemory.hh"

#include "serialize.hh"

#include "unreachable.hh"

#include <algorithm>
#include <cassert>

namespace openmsx {

Y8960AdpcmMemory::Y8960AdpcmMemory(const DeviceConfig& config)
	: MSXDevice(config)
	, ram(config, getName(), "Y8960 ADPCM sample RAM", Size)
	, layout(Layout::Shared)
{
}

void Y8960AdpcmMemory::powerUp(EmuTime /*time*/)
{
	ram.clear(0xFF);
}

unsigned Y8960AdpcmMemory::size(unsigned block) const
{
	assert(block < BlockCount);
	switch (layout) {
		using enum Layout;
	case Shared: return Size;
	case First:  return (block == 0) ? Size : 0;
	case Second: return (block == 0) ? 0 : Size;
	case Split:  return Size / 2;
	}
	UNREACHABLE;
}

unsigned Y8960AdpcmMemory::offset(unsigned block) const
{
	return ((layout == Layout::Split) && (block == 1)) ? (Size / 2) : 0;
}

uint8_t Y8960AdpcmMemory::read(unsigned block, unsigned addr) const
{
	if (addr >= size(block)) return 0;
	return ram[offset(block) + addr];
}

void Y8960AdpcmMemory::write(unsigned block, unsigned addr, uint8_t value)
{
	if (addr >= size(block)) return;
	ram.write(offset(block) + addr, value);
}

void Y8960AdpcmMemory::clear(unsigned block)
{
	auto window = ram.getWriteBackdoor().subspan(offset(block), size(block));
	std::ranges::fill(window, 0xFF);
}

static constexpr std::initializer_list<enum_string<Y8960AdpcmMemory::Layout>> layoutInfo = {
	{ "shared", Y8960AdpcmMemory::Layout::Shared },
	{ "first",  Y8960AdpcmMemory::Layout::First  },
	{ "second", Y8960AdpcmMemory::Layout::Second },
	{ "split",  Y8960AdpcmMemory::Layout::Split  },
};
SERIALIZE_ENUM(Y8960AdpcmMemory::Layout, layoutInfo);

template<typename Archive>
void Y8960AdpcmMemory::serialize(Archive& ar, unsigned /*version*/)
{
	ar.template serializeBase<MSXDevice>(*this);
	ar.serialize("ram",    ram,
	             "layout", layout);
}
INSTANTIATE_SERIALIZE_METHODS(Y8960AdpcmMemory);
REGISTER_MSXDEVICE(Y8960AdpcmMemory, "Y8960-ADPCM-RAM");

} // namespace openmsx
