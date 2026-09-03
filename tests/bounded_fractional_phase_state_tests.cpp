#include "test_harness.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <utility>

namespace {

constexpr std::int32_t minimum_leading_exponent = -16382;
constexpr std::int32_t maximum_leading_exponent = 16383;

template <std::size_t SignificandBits>
struct CanonicalDyadic final {
    static_assert(SignificandBits > 0U);
    static_assert(SignificandBits % 8U == 0U);
    static_assert(SignificandBits <= 65535U);

    static constexpr std::size_t significand_bytes = SignificandBits / 8U;
    static constexpr std::size_t serialized_bytes = 5U + significand_bytes;

    bool negative{};
    std::int32_t leading_exponent{};
    std::array<std::uint8_t, significand_bytes> significand{};

    [[nodiscard]] bool is_zero() const {
        return std::ranges::all_of(significand, [](std::uint8_t byte) { return byte == 0U; });
    }

    void validate() const {
        if (is_zero()) {
            if (negative || leading_exponent != 0) {
                throw std::invalid_argument("zero must have positive sign and exponent zero");
            }
            return;
        }
        if (leading_exponent < minimum_leading_exponent ||
            leading_exponent > maximum_leading_exponent) {
            throw std::out_of_range("finite dyadic exponent is outside the frozen range");
        }
        if ((significand.front() & UINT8_C(0x80)) == 0U) {
            throw std::invalid_argument("nonzero significand must have exactly the declared precision");
        }
    }

    [[nodiscard]] std::array<std::uint8_t, serialized_bytes> serialize() const {
        validate();
        std::array<std::uint8_t, serialized_bytes> bytes{};
        bytes[0] = negative ? UINT8_C(1) : UINT8_C(0);
        constexpr auto precision = static_cast<std::uint16_t>(SignificandBits);
        bytes[1] = static_cast<std::uint8_t>(precision & UINT16_C(0x00ff));
        bytes[2] = static_cast<std::uint8_t>(precision >> 8U);

        const auto exponent_word = leading_exponent >= 0
            ? static_cast<std::uint16_t>(leading_exponent)
            : static_cast<std::uint16_t>(INT32_C(65536) + leading_exponent);
        bytes[3] = static_cast<std::uint8_t>(exponent_word & UINT16_C(0x00ff));
        bytes[4] = static_cast<std::uint8_t>(exponent_word >> 8U);
        std::copy(significand.begin(), significand.end(), bytes.begin() + 5);
        return bytes;
    }

    [[nodiscard]] static CanonicalDyadic deserialize(
        const std::array<std::uint8_t, serialized_bytes>& bytes) {
        if (bytes[0] > 1U) {
            throw std::invalid_argument("sign byte must be zero or one");
        }
        const auto precision = static_cast<std::uint16_t>(
            static_cast<std::uint16_t>(bytes[1]) |
            static_cast<std::uint16_t>(static_cast<std::uint16_t>(bytes[2]) << 8U));
        if (precision != SignificandBits) {
            throw std::invalid_argument("serialized precision does not match the state profile");
        }
        const auto exponent_word = static_cast<std::uint16_t>(
            static_cast<std::uint16_t>(bytes[3]) |
            static_cast<std::uint16_t>(static_cast<std::uint16_t>(bytes[4]) << 8U));
        const auto exponent = exponent_word <= UINT16_C(0x7fff)
            ? static_cast<std::int32_t>(exponent_word)
            : static_cast<std::int32_t>(exponent_word) - INT32_C(65536);

        CanonicalDyadic value{};
        value.negative = bytes[0] != 0U;
        value.leading_exponent = exponent;
        std::copy(bytes.begin() + 5, bytes.end(), value.significand.begin());
        value.validate();
        return value;
    }

    friend bool operator==(const CanonicalDyadic&, const CanonicalDyadic&) = default;
};

template <std::size_t SignificandBits>
[[nodiscard]] std::array<std::uint8_t, SignificandBits / 8U> sample_significand() {
    std::array<std::uint8_t, SignificandBits / 8U> result{};
    result.front() = UINT8_C(0x80);
    result.back() = static_cast<std::uint8_t>(result.back() | UINT8_C(0x25));
    return result;
}

template <std::size_t SignificandBits>
void require_size_contract(
    std::size_t expected_component,
    std::size_t expected_phase_payload,
    std::size_t expected_packet) {
    constexpr auto component = CanonicalDyadic<SignificandBits>::serialized_bytes;
    constexpr auto phase_payload = 6U * component;
    constexpr auto packet = 16U + phase_payload; // uint64 packet ID plus int64 mass.
    MLS_REQUIRE_EQ(component, expected_component);
    MLS_REQUIRE_EQ(phase_payload, expected_phase_payload);
    MLS_REQUIRE_EQ(packet, expected_packet);
}

class Rational final {
public:
    constexpr Rational(std::int64_t numerator = 0, std::int64_t denominator = 1)
        : numerator_(numerator), denominator_(denominator) {
        if (denominator_ == 0) {
            throw std::invalid_argument("zero rational denominator");
        }
        if (denominator_ < 0) {
            numerator_ = -numerator_;
            denominator_ = -denominator_;
        }
        const auto numerator_magnitude = numerator_ < 0 ? -numerator_ : numerator_;
        const auto divisor = std::gcd(numerator_magnitude, denominator_);
        numerator_ /= divisor;
        denominator_ /= divisor;
    }

    friend constexpr Rational operator+(Rational left, Rational right) {
        return {
            left.numerator_ * right.denominator_ + right.numerator_ * left.denominator_,
            left.denominator_ * right.denominator_,
        };
    }

    friend constexpr Rational operator-(Rational left, Rational right) {
        return {
            left.numerator_ * right.denominator_ - right.numerator_ * left.denominator_,
            left.denominator_ * right.denominator_,
        };
    }

    friend constexpr Rational operator-(Rational value) {
        return {-value.numerator_, value.denominator_};
    }

    friend constexpr Rational operator*(Rational left, Rational right) {
        return {
            left.numerator_ * right.numerator_,
            left.denominator_ * right.denominator_,
        };
    }

    friend constexpr bool operator==(Rational, Rational) = default;

private:
    std::int64_t numerator_{};
    std::int64_t denominator_{1};
};

using Vector3q = std::array<Rational, 3>;

[[nodiscard]] constexpr Vector3q operator+(Vector3q left, Vector3q right) {
    return {left[0] + right[0], left[1] + right[1], left[2] + right[2]};
}

[[nodiscard]] constexpr Vector3q operator-(Vector3q left, Vector3q right) {
    return {left[0] - right[0], left[1] - right[1], left[2] - right[2]};
}

[[nodiscard]] constexpr Vector3q operator-(Vector3q value) {
    return {-value[0], -value[1], -value[2]};
}

[[nodiscard]] constexpr Vector3q scale(Vector3q value, Rational factor) {
    return {factor * value[0], factor * value[1], factor * value[2]};
}

[[nodiscard]] constexpr Vector3q cross(Vector3q left, Vector3q right) {
    return {
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    };
}

constexpr Vector3q zero_vector{};

} // namespace

MLS_TEST("bounded fractional phase serialization has fixed registered sizes") {
    require_size_contract<64>(13U, 78U, 94U);
    require_size_contract<96>(17U, 102U, 118U);
    require_size_contract<128>(21U, 126U, 142U);
    require_size_contract<192>(29U, 174U, 190U);
    require_size_contract<256>(37U, 222U, 238U);
}

MLS_TEST("bounded fractional phase serialization is canonical") {
    using Component = CanonicalDyadic<96>;
    const Component value{true, -13, sample_significand<96>()};
    const auto bytes = value.serialize();

    MLS_REQUIRE_EQ(bytes.size(), 17U);
    MLS_REQUIRE_EQ(bytes[0], UINT8_C(1));
    MLS_REQUIRE_EQ(bytes[1], UINT8_C(96));
    MLS_REQUIRE_EQ(bytes[2], UINT8_C(0));
    MLS_REQUIRE_EQ(bytes[3], UINT8_C(0xf3));
    MLS_REQUIRE_EQ(bytes[4], UINT8_C(0xff));
    MLS_REQUIRE_EQ(bytes[5], UINT8_C(0x80));
    MLS_REQUIRE_EQ(bytes.back(), UINT8_C(0x25));
    MLS_REQUIRE_EQ(Component::deserialize(bytes), value);

    const Component zero{};
    const auto zero_bytes = zero.serialize();
    MLS_REQUIRE_EQ(Component::deserialize(zero_bytes), zero);
    MLS_REQUIRE_EQ(zero_bytes[0], UINT8_C(0));
    MLS_REQUIRE_EQ(zero_bytes[3], UINT8_C(0));
    MLS_REQUIRE_EQ(zero_bytes[4], UINT8_C(0));
    MLS_REQUIRE(std::ranges::all_of(
        zero_bytes.begin() + 5, zero_bytes.end(), [](std::uint8_t byte) { return byte == 0U; }));

    auto signed_zero = zero_bytes;
    signed_zero[0] = UINT8_C(1);
    MLS_REQUIRE_THROWS(std::invalid_argument, Component::deserialize(signed_zero));

    auto stale_zero_exponent = zero_bytes;
    stale_zero_exponent[3] = UINT8_C(1);
    MLS_REQUIRE_THROWS(std::invalid_argument, Component::deserialize(stale_zero_exponent));

    auto invalid_sign = bytes;
    invalid_sign[0] = UINT8_C(2);
    MLS_REQUIRE_THROWS(std::invalid_argument, Component::deserialize(invalid_sign));

    auto wrong_precision = bytes;
    wrong_precision[1] = UINT8_C(64);
    MLS_REQUIRE_THROWS(std::invalid_argument, Component::deserialize(wrong_precision));

    auto denormalized = bytes;
    denormalized[5] = UINT8_C(0x40);
    MLS_REQUIRE_THROWS(std::invalid_argument, Component::deserialize(denormalized));
}

MLS_TEST("bounded fractional phase exponent range fails closed") {
    using Component = CanonicalDyadic<128>;
    const auto significand = sample_significand<128>();
    const Component minimum{false, minimum_leading_exponent, significand};
    const Component maximum{true, maximum_leading_exponent, significand};
    const auto minimum_bytes = minimum.serialize();
    const auto maximum_bytes = maximum.serialize();
    MLS_REQUIRE_EQ(Component::deserialize(minimum_bytes), minimum);
    MLS_REQUIRE_EQ(Component::deserialize(maximum_bytes), maximum);

    const Component underflow{false, minimum_leading_exponent - 1, significand};
    const Component overflow{false, maximum_leading_exponent + 1, significand};
    MLS_REQUIRE_THROWS(std::out_of_range, underflow.serialize());
    MLS_REQUIRE_THROWS(std::out_of_range, overflow.serialize());

    auto encoded_underflow = minimum_bytes;
    encoded_underflow[3] = UINT8_C(0x01); // -16383 as a little-endian signed word.
    encoded_underflow[4] = UINT8_C(0xc0);
    MLS_REQUIRE_THROWS(std::out_of_range, Component::deserialize(encoded_underflow));

    auto encoded_overflow = maximum_bytes;
    encoded_overflow[3] = UINT8_C(0x00); // +16384 as a little-endian signed word.
    encoded_overflow[4] = UINT8_C(0x40);
    MLS_REQUIRE_THROWS(std::out_of_range, Component::deserialize(encoded_overflow));
}

MLS_TEST("bounded pair residuals exactly account for momentum and angular momentum") {
    const Vector3q position_i{Rational{7, 3}, Rational{-5, 4}, Rational{11, 6}};
    const Vector3q position_j{Rational{-2, 5}, Rational{13, 7}, Rational{-3, 2}};
    const Vector3q momentum_i{Rational{2, 9}, Rational{-5, 11}, Rational{7, 8}};
    const Vector3q momentum_j{Rational{-4, 13}, Rational{3, 10}, Rational{-1, 6}};
    const auto separation = position_i - position_j;
    const auto ideal_impulse = scale(separation, Rational{5, 13});
    MLS_REQUIRE_EQ(cross(separation, ideal_impulse), zero_vector);

    const Vector3q error_i{Rational{1, 64}, Rational{-3, 128}, Rational{5, 256}};
    const Vector3q error_j{Rational{-1, 32}, Rational{1, 256}, Rational{7, 512}};
    const auto applied_i = ideal_impulse + error_i;
    const auto applied_j = -ideal_impulse + error_j;

    const auto momentum_before = momentum_i + momentum_j;
    const auto momentum_after = (momentum_i + applied_i) + (momentum_j + applied_j);
    MLS_REQUIRE_EQ(momentum_after - momentum_before, error_i + error_j);

    const auto angular_before =
        cross(position_i, momentum_i) + cross(position_j, momentum_j);
    const auto angular_after =
        cross(position_i, momentum_i + applied_i) +
        cross(position_j, momentum_j + applied_j);
    const auto expected_angular_residual =
        cross(position_i, error_i) + cross(position_j, error_j);
    MLS_REQUIRE_EQ(angular_after - angular_before, expected_angular_residual);
}

MLS_TEST("bounded equal and opposite rounding preserves momentum but exposes transverse torque") {
    const Vector3q position_i{Rational{5, 2}, Rational{-7, 3}, Rational{4, 5}};
    const Vector3q position_j{Rational{-1, 4}, Rational{2, 7}, Rational{-9, 8}};
    const auto separation = position_i - position_j;
    const auto ideal_impulse = scale(separation, Rational{-7, 19});
    const Vector3q rounding_error{
        Rational{1, 1024}, Rational{-3, 2048}, Rational{5, 4096}};
    const auto rounded_impulse = ideal_impulse + rounding_error;
    const auto applied_i = rounded_impulse;
    const auto applied_j = -rounded_impulse;

    MLS_REQUIRE_EQ(applied_i + applied_j, zero_vector);
    MLS_REQUIRE_EQ(
        cross(position_i, applied_i) + cross(position_j, applied_j),
        cross(separation, rounding_error));
    MLS_REQUIRE_EQ(cross(separation, rounded_impulse), cross(separation, rounding_error));
}
