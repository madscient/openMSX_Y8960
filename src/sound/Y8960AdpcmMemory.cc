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
	, blocks{{{*this, 0}, {*this, 1}}}
{
}

Y8950AdpcmRam& Y8960AdpcmMemory::getBlock(unsigned index)
{
	assert(index < BlockCount);
	return blocks[index];
}

void Y8960AdpcmMemory::powerUp(EmuTime /*time*/)
{
	ram.clear(0xFF);
}

Y8960AdpcmMemory::Block::Block(Y8960AdpcmMemory& memory_, unsigned index_)
	: memory(memory_)
	, index(index_)
{
}

unsigned Y8960AdpcmMemory::Block::size() const
{
	switch (memory.layout) {
		using enum Layout;
	case Shared: return Size;
	case First:  return (index == 0) ? Size : 0;
	case Second: return (index == 0) ? 0 : Size;
	case Split:  return Size / 2;
	}
	UNREACHABLE;
}

unsigned Y8960AdpcmMemory::Block::offset() const
{
	return ((memory.layout == Layout::Split) && (index == 1)) ? (Size / 2) : 0;
}

uint8_t Y8960AdpcmMemory::Block::read(unsigned addr) const
{
	if (addr >= size()) return 0;
	return memory.ram[offset() + addr];
}

void Y8960AdpcmMemory::Block::write(unsigned addr, uint8_t value)
{
	if (addr >= size()) return;
	memory.ram.write(offset() + addr, value);
}

void Y8960AdpcmMemory::Block::clear()
{
	auto window = memory.ram.getWriteBackdoor().subspan(offset(), size());
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
