#include "mls/physical_support.hpp"

#include <compare>
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace mls {
namespace {

struct WideUnsigned final {
    std::uint64_t high{0};
    std::uint64_t low{0};

    [[nodiscard]] constexpr auto operator<=>(const WideUnsigned&) const noexcept = default;
};

// Portable exact 64 x 64 -> 128 multiplication, decomposed into 32-bit limbs.
[[nodiscard]] constexpr WideUnsigned multiply_wide(
    const std::uint64_t left, const std::uint64_t right) noexcept {
    constexpr std::uint64_t mask = UINT64_C(0xffffffff);
    const auto left_low = left & mask;
    const auto left_high = left >> 32U;
    const auto right_low = right & mask;
    const auto right_high = right >> 32U;

    auto product = left_low * right_low;
    const auto result_low_limb = product & mask;
    auto carry = product >> 32U;

    product = left_high * right_low + carry;
    auto middle = product & mask;
    const auto result_high_limb = product >> 32U;

    product = left_low * right_high + middle;
    carry = product >> 32U;
    const auto low = (product << 32U) + result_low_limb;
    const auto high = left_high * right_high + result_high_limb + carry;
    return {high, low};
}

[[nodiscard]] constexpr bool add_wide(
    WideUnsigned& accumulator, const WideUnsigned addend) noexcept {
    const auto previous_low = accumulator.low;
    accumulator.low += addend.low;
    const std::uint64_t carry = accumulator.low < previous_low ? 1U : 0U;
    if (addend.high > std::numeric_limits<std::uint64_t>::max() - accumulator.high ||
        carry > std::numeric_limits<std::uint64_t>::max() - accumulator.high - addend.high) {
        return false;
    }
    accumulator.high += addend.high + carry;
    return true;
}

[[nodiscard]] constexpr std::uint64_t unsigned_distance(
    const Scalar left, const Scalar right) noexcept {
    if (left >= right) {
        return static_cast<std::uint64_t>(left) - static_cast<std::uint64_t>(right);
    }
    return static_cast<std::uint64_t>(right) - static_cast<std::uint64_t>(left);
}

} // namespace

bool within_spherical_support(
    const Position3& first, const Position3& second, const Length interaction_radius) {
    if (interaction_radius.raw() <= 0) {
        throw std::invalid_argument("interaction radius must be positive");
    }
    const auto radius = static_cast<std::uint64_t>(interaction_radius.raw());
    const auto dx = unsigned_distance(first.x.raw(), second.x.raw());
    const auto dy = unsigned_distance(first.y.raw(), second.y.raw());
    const auto dz = unsigned_distance(first.z.raw(), second.z.raw());

    // This early rejection both saves work and bounds every following square.
    if (dx > radius || dy > radius || dz > radius) {
        return false;
    }

    auto squared_distance = multiply_wide(dx, dx);
    if (!add_wide(squared_distance, multiply_wide(dy, dy)) ||
        !add_wide(squared_distance, multiply_wide(dz, dz))) {
        // A mathematical overflow means the sum is larger than any legal
        // radius squared in the signed-Scalar reference domain.
        return false;
    }
    return squared_distance <= multiply_wide(radius, radius);
}

} // namespace mls
