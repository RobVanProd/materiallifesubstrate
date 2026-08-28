#pragma once

#include "mls/world.hpp"

#include <cstdint>
#include <span>
#include <vector>

namespace mls {

inline constexpr std::uint32_t canonical_checkpoint_format_version = 2;
// Version of the authoritative transition laws/state interpretation, separate
// from the byte-layout version above. Any change that can alter continuation
// from identical authoritative state must increment this value.
inline constexpr std::uint32_t authoritative_physics_abi_version = 1;

// Canonical, versioned little-endian restart image for authoritative World
// state. The sparse grid is rebuilt, and packet event history is intentionally
// omitted because neither is authoritative or read by physical transitions.
[[nodiscard]] std::vector<std::uint8_t> serialize_canonical_checkpoint(const World& world);

// Rejects corrupt, truncated, unsupported, noncanonical, or invariant-violating
// checkpoint bytes. Successful decoding reconstructs exact deterministic state.
[[nodiscard]] World deserialize_canonical_checkpoint(
    std::span<const std::uint8_t> checkpoint);

} // namespace mls
