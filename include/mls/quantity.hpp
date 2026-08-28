#pragma once

#include <compare>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <type_traits>

namespace mls {

using Scalar = std::int64_t;

namespace detail {

[[nodiscard]] constexpr Scalar checked_add(Scalar lhs, Scalar rhs) {
    if ((rhs > 0 && lhs > std::numeric_limits<Scalar>::max() - rhs) ||
        (rhs < 0 && lhs < std::numeric_limits<Scalar>::min() - rhs)) {
        throw std::overflow_error("MLS integer addition overflow");
    }
    return static_cast<Scalar>(lhs + rhs);
}

[[nodiscard]] constexpr Scalar checked_subtract(Scalar lhs, Scalar rhs) {
    if ((rhs < 0 && lhs > std::numeric_limits<Scalar>::max() + rhs) ||
        (rhs > 0 && lhs < std::numeric_limits<Scalar>::min() + rhs)) {
        throw std::overflow_error("MLS integer subtraction overflow");
    }
    return static_cast<Scalar>(lhs - rhs);
}

[[nodiscard]] constexpr Scalar checked_multiply(Scalar lhs, Scalar rhs) {
    if (lhs == 0 || rhs == 0) {
        return 0;
    }
    if ((lhs == -1 && rhs == std::numeric_limits<Scalar>::min()) ||
        (rhs == -1 && lhs == std::numeric_limits<Scalar>::min())) {
        throw std::overflow_error("MLS integer multiplication overflow");
    }
    if (lhs > 0) {
        if ((rhs > 0 && lhs > std::numeric_limits<Scalar>::max() / rhs) ||
            (rhs < 0 && rhs < std::numeric_limits<Scalar>::min() / lhs)) {
            throw std::overflow_error("MLS integer multiplication overflow");
        }
    } else if ((rhs > 0 && lhs < std::numeric_limits<Scalar>::min() / rhs) ||
               (rhs < 0 && lhs < std::numeric_limits<Scalar>::max() / rhs)) {
        throw std::overflow_error("MLS integer multiplication overflow");
    }
    return static_cast<Scalar>(lhs * rhs);
}

} // namespace detail

// Quantity stores an exact number of caller-defined fixed-point quanta. Unit
// scales belong in WorldConfig/ElementCatalog, never in hidden conversions.
template <typename DimensionTag>
class Quantity final {
public:
    constexpr Quantity() = default;

    [[nodiscard]] static constexpr Quantity from_raw(Scalar value) noexcept {
        return Quantity(value);
    }

    [[nodiscard]] constexpr Scalar raw() const noexcept { return value_; }

    constexpr Quantity& operator+=(Quantity rhs) {
        value_ = detail::checked_add(value_, rhs.value_);
        return *this;
    }

    constexpr Quantity& operator-=(Quantity rhs) {
        value_ = detail::checked_subtract(value_, rhs.value_);
        return *this;
    }

    [[nodiscard]] friend constexpr Quantity operator+(Quantity lhs, Quantity rhs) {
        lhs += rhs;
        return lhs;
    }

    [[nodiscard]] friend constexpr Quantity operator-(Quantity lhs, Quantity rhs) {
        lhs -= rhs;
        return lhs;
    }

    [[nodiscard]] friend constexpr Quantity operator-(Quantity value) {
        if (value.value_ == std::numeric_limits<Scalar>::min()) {
            throw std::overflow_error("MLS quantity negation overflow");
        }
        return Quantity::from_raw(static_cast<Scalar>(-value.value_));
    }

    [[nodiscard]] friend constexpr Quantity operator*(Quantity value, Scalar factor) {
        return Quantity::from_raw(detail::checked_multiply(value.value_, factor));
    }

    [[nodiscard]] friend constexpr Quantity operator*(Scalar factor, Quantity value) {
        return value * factor;
    }

    [[nodiscard]] friend constexpr Quantity operator/(Quantity value, Scalar divisor) {
        if (divisor == 0) {
            throw std::domain_error("MLS quantity division by zero");
        }
        if (value.value_ == std::numeric_limits<Scalar>::min() && divisor == -1) {
            throw std::overflow_error("MLS quantity division overflow");
        }
        return Quantity::from_raw(static_cast<Scalar>(value.value_ / divisor));
    }

    [[nodiscard]] constexpr auto operator<=>(const Quantity&) const noexcept = default;

private:
    explicit constexpr Quantity(Scalar value) noexcept : value_(value) {}

    Scalar value_{0};
};

struct LengthDimension;
struct MassDimension;
struct TimeDimension;
struct VelocityDimension;
struct MomentumDimension;
struct EnergyDimension;
struct TemperatureDimension;
struct HeatCapacityDimension;

using Length = Quantity<LengthDimension>;
using Mass = Quantity<MassDimension>;
using Time = Quantity<TimeDimension>;
using Velocity = Quantity<VelocityDimension>;
using Momentum = Quantity<MomentumDimension>;
using Energy = Quantity<EnergyDimension>;
using Temperature = Quantity<TemperatureDimension>;
using HeatCapacity = Quantity<HeatCapacityDimension>;

template <typename QuantityType>
struct Vector3 final {
    QuantityType x{};
    QuantityType y{};
    QuantityType z{};

    constexpr Vector3& operator+=(const Vector3& rhs) {
        const auto next_x = x + rhs.x;
        const auto next_y = y + rhs.y;
        const auto next_z = z + rhs.z;
        x = next_x;
        y = next_y;
        z = next_z;
        return *this;
    }

    constexpr Vector3& operator-=(const Vector3& rhs) {
        const auto next_x = x - rhs.x;
        const auto next_y = y - rhs.y;
        const auto next_z = z - rhs.z;
        x = next_x;
        y = next_y;
        z = next_z;
        return *this;
    }

    [[nodiscard]] friend constexpr Vector3 operator+(Vector3 lhs, const Vector3& rhs) {
        lhs += rhs;
        return lhs;
    }

    [[nodiscard]] friend constexpr Vector3 operator-(Vector3 lhs, const Vector3& rhs) {
        lhs -= rhs;
        return lhs;
    }

    [[nodiscard]] friend constexpr Vector3 operator-(const Vector3& value) {
        return {-value.x, -value.y, -value.z};
    }

    [[nodiscard]] constexpr auto operator<=>(const Vector3&) const noexcept = default;
};

using Position3 = Vector3<Length>;
using Velocity3 = Vector3<Velocity>;
using Momentum3 = Vector3<Momentum>;

[[nodiscard]] constexpr bool is_nonnegative(Energy value) noexcept {
    return value.raw() >= 0;
}

[[nodiscard]] constexpr bool is_nonnegative(Mass value) noexcept {
    return value.raw() >= 0;
}

[[nodiscard]] constexpr bool is_nonnegative(HeatCapacity value) noexcept {
    return value.raw() >= 0;
}

} // namespace mls
