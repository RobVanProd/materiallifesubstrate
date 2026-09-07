#pragma once
#include <array>
#include <cstdint>
#include <iosfwd>
#include <string>
#include <vector>

// Research-only. Deliberately not included in mls.hpp or connected to World.
namespace mls::kernel_parity {
struct B96 {
  std::array<std::uint8_t, 17> wire{};
};
static_assert(sizeof(B96) == 17);
struct Packet {
  std::uint64_t id{};
  std::int64_t mass{};
  std::array<B96, 3> x{}, p{};
};
struct State {
  std::int64_t time{};
  std::vector<Packet> packets;
};
// Isolated text protocol: model and initial state only, never reference
// outputs.
int run(std::istream &input, std::ostream &output);
} // namespace mls::kernel_parity
