#pragma once

#include "mls/world.hpp"

#include <cstdint>
#include <span>
#include <vector>

namespace mls {

inline constexpr std::uint32_t canonical_checkpoint_format_version = 1;

// Canonical, versioned little-endian restart image for authoritative World
// state. The sparse grid is rebuilt, and packet event history is intentionally
// omitted because neither is authoritative or read by physical transitions.
[[nodiscard]] std::vector<std::uint8_t> serialize_canonical_checkpoint(const World& world);

// Rejects corrupt, truncated, unsupported, noncanonical, or invariant-violating
// checkpoint bytes. Successful decoding reconstructs exact deterministic state.
[[nodiscard]] World deserialize_canonical_checkpoint(
    std::span<const std::uint8_t> checkpoint);

} // namespace mls
