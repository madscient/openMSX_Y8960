#ifndef Y8960PAN_HH
#define Y8960PAN_HH

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <numbers>

namespace openmsx::y8960 {

struct PanGain { float left, right; };

/** The pan law of the Y8960's per-channel pan registers (OPLL 50h-58h,
  * SSGS 28h-2Eh): 1 is hard left, 128 the centre, 255 hard right, and 0
  * counts as the centre.
  *
  * The specification only gives those anchor values. Between them this is
  * power panning, L = cos(t), R = sin(t) with t running from 0 to pi/2, so
  * the centre sits 3dB down on both sides. (Decided 2026-10-16.)
  */
[[nodiscard]] inline PanGain panGain(uint8_t pan)
{
	if ((pan == 0) || (pan == 128)) {
		// one constant for both sides, so that a centred channel is
		// exactly symmetric rather than cos and sin a rounding apart
		constexpr float c = std::numbers::sqrt2_v<float> / 2.0f;
		return {.left = c, .right = c};
	}
	float t = float(pan - 1) / 254.0f * (std::numbers::pi_v<float> / 2.0f);
	return {.left = std::cos(t), .right = std::sin(t)};
}

/** The gain of a per-channel volume register (SSGS 20h-26h): 0..128,
  * linear, 128 is unity. What 129..255 do is not specified; they count as
  * 128 here. */
[[nodiscard]] inline float volumeGain(uint8_t volume)
{
	return float(std::min<int>(volume, 128)) / 128.0f;
}

} // namespace openmsx::y8960

#endif
