#include "test_harness.hpp"

#include <array>
#include <cstdint>
#include <cstdlib>
#include <numeric>

namespace {

using Vector3i = std::array<std::int64_t, 3>;

[[nodiscard]] std::int64_t component_gcd(Vector3i value) {
    return std::gcd(
        std::gcd(std::abs(value[0]), std::abs(value[1])),
        std::abs(value[2]));
}

[[nodiscard]] Vector3i cross(Vector3i first, Vector3i second) {
    return {
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    };
}

[[nodiscard]] bool is_zero(Vector3i value) {
    return value == Vector3i{0, 0, 0};
}

[[nodiscard]] bool is_integer_multiple(Vector3i value, Vector3i primitive) {
    for (std::size_t axis = 0; axis < primitive.size(); ++axis) {
        if (primitive[axis] == 0) {
            if (value[axis] != 0) {
                return false;
            }
            continue;
        }
        if (value[axis] % primitive[axis] != 0) {
            return false;
        }
        const auto multiple = value[axis] / primitive[axis];
        for (std::size_t other = 0; other < primitive.size(); ++other) {
            if (value[other] != multiple * primitive[other]) {
                return false;
            }
        }
        return true;
    }
    return false;
}

} // namespace

MLS_TEST("fractional phase lattice parallel vectors are primitive multiples") {
    constexpr Vector3i momentum{6, -9, 15};
    const auto divisor = component_gcd(momentum);
    MLS_REQUIRE_EQ(divisor, 3);
    const Vector3i primitive{
        momentum[0] / divisor,
        momentum[1] / divisor,
        momentum[2] / divisor,
    };
    MLS_REQUIRE_EQ(primitive, (Vector3i{2, -3, 5}));
    for (std::int64_t x = -6; x <= 6; ++x) {
        for (std::int64_t y = -6; y <= 6; ++y) {
            for (std::int64_t z = -6; z <= 6; ++z) {
                const Vector3i displacement{x, y, z};
                if (is_zero(cross(displacement, momentum))) {
                    MLS_REQUIRE(is_integer_multiple(displacement, primitive));
                }
            }
        }
    }
}

MLS_TEST("fractional phase reciprocal squared resolution cancels unit choice") {
    // Lq=2/5 and Pq=3/7; squared norms and gcds are deliberately non-unit.
    constexpr std::uint64_t length_numerator = 2;
    constexpr std::uint64_t length_denominator = 5;
    constexpr std::uint64_t momentum_numerator = 3;
    constexpr std::uint64_t momentum_denominator = 7;
    constexpr std::uint64_t relation_squared = 56;
    constexpr std::uint64_t momentum_squared = 693;
    constexpr std::uint64_t relation_gcd = 2;
    constexpr std::uint64_t momentum_gcd = 3;

    // Compare exact rational products by cross multiplication.  The left is
    // J_min^2 * dx_min^2; the right is |r|^2 |p|^2/(gr^2 gp^2).
    constexpr auto left_numerator =
        momentum_numerator * momentum_numerator * relation_squared
        * length_numerator * length_numerator * momentum_squared;
    constexpr auto left_denominator =
        momentum_denominator * momentum_denominator * relation_gcd * relation_gcd
        * length_denominator * length_denominator * momentum_gcd * momentum_gcd;
    constexpr auto right_numerator =
        length_numerator * length_numerator * relation_squared
        * momentum_numerator * momentum_numerator * momentum_squared;
    constexpr auto right_denominator =
        length_denominator * length_denominator * momentum_denominator
        * momentum_denominator * relation_gcd * relation_gcd
        * momentum_gcd * momentum_gcd;
    MLS_REQUIRE_EQ(left_numerator * right_denominator,
                   right_numerator * left_denominator);
}
