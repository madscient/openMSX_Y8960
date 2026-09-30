// Checks that driving ymfm's YM2608 at its native rates (one FM+ADPCM
// sample per FM clock, one SSG sample per SSG clock) yields the same
// samples that ym2608::generate() repeats or averages into its fixed
// output rate. ymfm itself is not modified: the FM and SSG steps are
// reached through protected members of a subclass.
//
// Build (MSVC, from the repository root):
//   cl /nologo /O2 /std:c++20 /EHsc /Isrc/3rdparty/ymfm
//      doc/fork/makoto/tests/native-rate-check.cc
//      src/3rdparty/ymfm/ymfm_opn.cc src/3rdparty/ymfm/ymfm_ssg.cc
//      src/3rdparty/ymfm/ymfm_adpcm.cc
// Prints one line per comparison and "RESULT: ALL MATCH" or "RESULT: MISMATCH".
// With --control, the native side skips the writes that start ADPCM-B
// (100h), key the rhythm (10h) and set SSG volume A (08h); every comparison
// must then report mismatches, which shows that ADPCM, rhythm and SSG are
// really part of what is compared.

#include "ymfm_opn.h"

#include <cstdint>
#include <cstdio>
#include <functional>
#include <string_view>
#include <vector>

namespace {

bool control = false;

struct Memory final : ymfm::ymfm_interface {
	std::vector<uint8_t> rom = std::vector<uint8_t>(0x2000);
	std::vector<uint8_t> ram = std::vector<uint8_t>(0x40000);
	Memory() {
		// Deterministic non-trivial nibbles so ADPCM-A/B actually move.
		uint32_t x = 12345;
		for (auto& b : rom) { x = x * 1103515245 + 12345; b = uint8_t(x >> 16); }
		for (auto& b : ram) { x = x * 1103515245 + 12345; b = uint8_t(x >> 16); }
	}
	uint8_t ymfm_external_read(ymfm::access_class type, uint32_t addr) override {
		if (type == ymfm::ACCESS_ADPCM_A) return rom[addr % rom.size()];
		if (type == ymfm::ACCESS_ADPCM_B) return ram[addr % ram.size()];
		return 0xff;
	}
	void ymfm_external_write(ymfm::access_class type, uint32_t addr, uint8_t data) override {
		if (type == ymfm::ACCESS_ADPCM_B) ram[addr % ram.size()] = data;
	}
};

struct Native final : ymfm::ym2608 {
	using ym2608::ym2608;
	void fm(int32_t& l, int32_t& r) {
		clock_fm_and_adpcm();
		l = m_last_fm.data[0];
		r = m_last_fm.data[1];
	}
	int32_t ssg() {
		ymfm::ssg_engine::output_data o;
		m_ssg.clock();
		m_ssg.output(o);
		return o.data[0] + o.data[1] + o.data[2];
	}
	uint32_t prescale() const { return m_fm.clock_prescale(); }
};

// generate() mixes the three SSG voices with a 2/3 factor
// (ssg_resampler<..., MixTo1=true>::write_to_output); openMSX applies that
// factor as the SSG device's amplification instead.
int32_t mixed(int32_t sum) { return sum * 2 / 3; }

void write(ymfm::ym2608& c, unsigned reg, uint8_t val) {
	unsigned hi = (reg & 0x100) ? 2 : 0;
	c.write(hi + 0, uint8_t(reg));
	c.write(hi + 1, val);
}

// The register program; 'at' is in FM samples and is always even, so
// that it also falls on a whole SSG sample at every prescale (FM:SSG
// clock ratio is 9:2 at prescale 6 and 3, and 6:1 at prescale 2).
struct Event { uint32_t at; unsigned reg; uint8_t val; };

std::vector<Event> program(uint8_t prescaleReg) {
	std::vector<Event> ev;
	auto w = [&](uint32_t at, unsigned reg, uint8_t val) { ev.push_back({at, reg, val}); };
	w(0, prescaleReg, 0);
	w(0, 0x29, 0x80);                        // 6-channel mode
	for (unsigned bank : {0x000u, 0x100u}) {
		for (unsigned ch = 0; ch < 3; ++ch) {
			for (unsigned op : {0u, 4u, 8u, 12u}) {
				w(0, bank + 0x30 + op + ch, 0x01);  // DT/MUL
				w(0, bank + 0x40 + op + ch, 0x08);  // TL
				w(0, bank + 0x50 + op + ch, 0x1f);  // AR
				w(0, bank + 0x60 + op + ch, 0x05);  // DR
				w(0, bank + 0x80 + op + ch, 0x2f);  // SL/RR
			}
			w(0, bank + 0xb0 + ch, uint8_t(ch * 2 + 1)); // FB/ALG
			w(0, bank + 0xb4 + ch, 0xc0);                // L+R
			w(0, bank + 0xa4 + ch, uint8_t(0x20 + ch));  // block/fnum hi
			w(0, bank + 0xa0 + ch, uint8_t(0x69 + 16 * ch));
		}
	}
	for (uint8_t k : {0x00, 0x01, 0x02, 0x04, 0x05, 0x06}) w(2, 0x28, uint8_t(0xf0 | k));
	// SSG: two tones, one noise+envelope voice
	w(2, 0x00, 0x40); w(2, 0x01, 0x01);
	w(2, 0x02, 0x7f); w(2, 0x03, 0x00);
	w(2, 0x04, 0x10); w(2, 0x05, 0x00);
	w(2, 0x06, 0x05);
	w(2, 0x07, 0x1c);                         // tones A,B; tone+noise C
	w(2, 0x08, 0x0f); w(2, 0x09, 0x0c); w(2, 0x0a, 0x10);
	w(2, 0x0b, 0x80); w(2, 0x0c, 0x00); w(2, 0x0d, 0x0e);
	// rhythm: all six, full level
	w(4, 0x11, 0x3f);
	for (unsigned r = 0x18; r <= 0x1d; ++r) w(4, r, 0xdf);
	w(4, 0x10, 0x3f);
	// ADPCM-B from sample RAM
	w(6, 0x101, 0xc0);
	w(6, 0x102, 0x00); w(6, 0x103, 0x00);
	w(6, 0x104, 0xff); w(6, 0x105, 0x0f);
	w(6, 0x10c, 0xff); w(6, 0x10d, 0xff);
	w(6, 0x109, 0x00); w(6, 0x10a, 0x40);
	w(6, 0x10b, 0xff);
	w(6, 0x100, 0xa0);
	// changes while running
	w(20000, 0x28, 0x01);                     // key off ch 2
	w(30000, 0x0a, 0x0f); w(30000, 0x06, 0x1f);
	w(40000, 0x10, 0x05);                     // re-key two rhythm sounds
	w(50000, 0x28, 0xf1);
	w(60000, 0x10a, 0x80);                    // ADPCM-B faster
	w(70000, 0x0d, 0x0a);
	return ev;
}

// Reference: generate() at a fixed output rate. For each FM sample k the
// reference emits 'fmRep' outputs; for each SSG sample m it emits
// 'ssgRep' outputs (only used when the SSG is repeated, i.e. MAX).
struct Totals { uint64_t fmCompared = 0, fmMismatch = 0, fmNonZero = 0;
                uint64_t ssgCompared = 0, ssgMismatch = 0, ssgNonZero = 0; };

Totals run(uint8_t prescaleReg, ymfm::opn_fidelity fidelity, bool compareSsg,
           uint32_t fmSamples) {
	Memory refMem, natMem;
	ymfm::ym2608 ref(refMem);
	Native nat(natMem);
	ref.set_fidelity(fidelity);
	ref.reset();
	nat.reset();

	auto events = program(prescaleReg);
	size_t next = 0;
	auto applyUpTo = [&](uint32_t k) {
		while (next < events.size() && events[next].at == k) {
			write(ref, events[next].reg, events[next].val);
			unsigned reg = events[next].reg;
			if (!(control && (reg == 0x100 || reg == 0x10 || reg == 0x08))) {
				write(nat, reg, events[next].val);
			}
			++next;
		}
	};

	Totals t;
	std::vector<ymfm::ym2608::output_data> out;
	std::vector<int32_t> refSsg;  // data[2] of every reference output
	std::vector<int32_t> natSsg;
	unsigned ssgRep = 0;
	for (uint32_t k = 0; k < fmSamples; ++k) {
		unsigned pre = nat.prescale();
		unsigned ssgClk = pre == 6 ? 32 : pre == 3 ? 16 : 8;  // master clocks per SSG sample
		unsigned outClk = fidelity == ymfm::OPN_FIDELITY_MAX ? 8
		                : fidelity == ymfm::OPN_FIDELITY_MED ? 24 : 48;
		if (compareSsg) {
			// SSG samples that start before this FM sample see the old registers
			ssgRep = ssgClk / outClk;
			while (natSsg.size() * ssgRep < refSsg.size()) natSsg.push_back(mixed(nat.ssg()));
		}
		applyUpTo(k);
		pre = nat.prescale();
		unsigned fmClk = pre * 24;                       // master clocks per FM sample
		unsigned rep = fmClk / outClk;
		int32_t l, r;
		nat.fm(l, r);
		out.resize(rep);
		ref.generate(out.data(), rep);
		for (auto& o : out) {
			++t.fmCompared;
			if (o.data[0] != l || o.data[1] != r) ++t.fmMismatch;
			refSsg.push_back(o.data[2]);
		}
		if (l || r) ++t.fmNonZero;
	}
	if (compareSsg) {
		for (size_t m = 0; (m + 1) * ssgRep <= refSsg.size(); ++m) {
			if (m == natSsg.size()) natSsg.push_back(mixed(nat.ssg()));
			for (unsigned i = 0; i < ssgRep; ++i) {
				++t.ssgCompared;
				if (refSsg[m * ssgRep + i] != natSsg[m]) ++t.ssgMismatch;
			}
			if (natSsg[m]) ++t.ssgNonZero;
		}
	}
	return t;
}

} // namespace

int main(int argc, char** argv) {
	control = argc > 1 && std::string_view(argv[1]) == "--control";
	struct Case { const char* name; uint8_t reg; ymfm::opn_fidelity fid; bool ssg; };
	const Case cases[] = {
		{"prescale 6, MAX (FM + SSG)", 0x2d, ymfm::OPN_FIDELITY_MAX, true},
		{"prescale 6, MED (FM only)",  0x2d, ymfm::OPN_FIDELITY_MED, false},
		{"prescale 6, MIN (FM only)",  0x2d, ymfm::OPN_FIDELITY_MIN, false},
		{"prescale 2, MAX (FM + SSG)", 0x2f, ymfm::OPN_FIDELITY_MAX, true},
	};
	bool ok = true;
	for (const auto& c : cases) {
		auto t = run(c.reg, c.fid, c.ssg, 80000);
		std::printf("%-28s FM %llu compared, %llu mismatch, %llu non-zero FM samples",
		            c.name, (unsigned long long)t.fmCompared,
		            (unsigned long long)t.fmMismatch, (unsigned long long)t.fmNonZero);
		if (c.ssg) {
			std::printf("; SSG %llu compared, %llu mismatch, %llu non-zero SSG samples",
			            (unsigned long long)t.ssgCompared,
			            (unsigned long long)t.ssgMismatch, (unsigned long long)t.ssgNonZero);
		}
		std::printf("\n");
		if (t.fmMismatch || t.ssgMismatch || !t.fmNonZero || (c.ssg && !t.ssgNonZero)) ok = false;
	}
	std::printf("RESULT: %s\n", ok ? "ALL MATCH" : "MISMATCH");
	return ok ? 0 : 1;
}
