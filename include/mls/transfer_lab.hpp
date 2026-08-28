#pragma once

#include <array>
#include <compare>
#include <cstdint>
#include <map>
#include <span>
#include <string_view>
#include <vector>

namespace mls::experimental {

// TransferLab is a deterministic binary64 experiment. SI suffixes make its
// dimensioned values explicit; it is not an authoritative World transition.
struct Vec3d final {
    double x{0.0};
    double y{0.0};
    double z{0.0};

    [[nodiscard]] constexpr auto operator<=>(const Vec3d&) const noexcept = default;
};

struct Matrix3d final {
    std::array<std::array<double, 3>, 3> value{};

    [[nodiscard]] static constexpr Matrix3d zero() noexcept { return {}; }
    [[nodiscard]] static constexpr Matrix3d identity() noexcept {
        Matrix3d result{};
        result.value[0][0] = 1.0;
        result.value[1][1] = 1.0;
        result.value[2][2] = 1.0;
        return result;
    }

    [[nodiscard]] constexpr auto operator<=>(const Matrix3d&) const noexcept = default;
};

[[nodiscard]] Vec3d operator+(Vec3d lhs, Vec3d rhs) noexcept;
[[nodiscard]] Vec3d operator-(Vec3d lhs, Vec3d rhs) noexcept;
[[nodiscard]] Vec3d operator-(Vec3d value) noexcept;
[[nodiscard]] Vec3d operator*(double scalar, Vec3d value) noexcept;
[[nodiscard]] Vec3d operator*(Vec3d value, double scalar) noexcept;
[[nodiscard]] Vec3d operator/(Vec3d value, double scalar);
Vec3d& operator+=(Vec3d& lhs, Vec3d rhs) noexcept;

[[nodiscard]] double dot(Vec3d lhs, Vec3d rhs) noexcept;
[[nodiscard]] Vec3d cross(Vec3d lhs, Vec3d rhs) noexcept;
[[nodiscard]] double norm(Vec3d value) noexcept;
[[nodiscard]] Vec3d multiply(const Matrix3d& matrix, Vec3d vector) noexcept;
[[nodiscard]] Matrix3d multiply(const Matrix3d& lhs, const Matrix3d& rhs) noexcept;
[[nodiscard]] Matrix3d transpose(const Matrix3d& matrix) noexcept;
[[nodiscard]] Matrix3d outer(Vec3d lhs, Vec3d rhs) noexcept;
[[nodiscard]] Matrix3d operator+(const Matrix3d& lhs, const Matrix3d& rhs) noexcept;
[[nodiscard]] Matrix3d operator*(double scalar, const Matrix3d& matrix) noexcept;
[[nodiscard]] double frobenius_norm(const Matrix3d& matrix) noexcept;

enum class TransferCandidate : std::uint8_t {
    pic,
    apic,
    flip_diagnostic,
};

[[nodiscard]] std::string_view candidate_name(TransferCandidate candidate) noexcept;

struct TransferParticle final {
    std::uint64_t id{0};
    // Mass is exact in the experimental particle state. The conversion to kg
    // is declared by TransferConfig and only the grid workspace uses binary64.
    std::int64_t mass_quanta{0};
    Vec3d position_m{};
    Vec3d velocity_m_per_s{};
    // Numerical APIC auxiliary, in inverse seconds. It is not physical packet
    // spin, stored energy, or an authoritative MLS ledger channel.
    Matrix3d affine_velocity_per_s{};

    [[nodiscard]] constexpr bool operator==(const TransferParticle&) const noexcept = default;
};

struct TransferConfig final {
    double grid_spacing_m{1.0};
    Vec3d grid_origin_m{};
    double kg_per_mass_quantum{1.0};

    [[nodiscard]] constexpr bool operator==(const TransferConfig&) const noexcept = default;
};

struct GridIndex final {
    std::int64_t x{0};
    std::int64_t y{0};
    std::int64_t z{0};

    [[nodiscard]] constexpr auto operator<=>(const GridIndex&) const noexcept = default;
};

struct KernelSample final {
    GridIndex index{};
    Vec3d node_position_m{};
    Vec3d node_offset_from_particle_m{};
    double weight{0.0};
};

struct GridNode final {
    double mass_kg{0.0};
    Vec3d momentum_kg_m_per_s{};
    Vec3d velocity_m_per_s{};
    // FLIP compares an explicitly updated grid velocity against this value.
    // With no modeled update in this lab the two values remain identical.
    Vec3d velocity_before_update_m_per_s{};

    [[nodiscard]] constexpr bool operator==(const GridNode&) const noexcept = default;
};

struct TransferGrid final {
    TransferConfig config{};
    std::map<GridIndex, GridNode> nodes{};
};

struct TransferTotals final {
    double mass_kg{0.0};
    Vec3d linear_momentum_kg_m_per_s{};
    // Center-only orbital angular momentum is the MLS point-packet quantity.
    Vec3d center_orbital_kg_m2_per_s{};
    // Affine terms are reported independently and never close a physical
    // ledger. APIC literature's augmented total is center + affine.
    Vec3d affine_auxiliary_kg_m2_per_s{};
    Vec3d augmented_angular_kg_m2_per_s{};
    double center_kinetic_j{0.0};
    double affine_auxiliary_kinetic_j{0.0};
    double augmented_kinetic_j{0.0};
};

struct TransferCycle final {
    std::vector<TransferParticle> particles{};
    TransferGrid grid{};
    TransferTotals particle_before{};
    TransferTotals grid_after_p2g{};
    TransferTotals particle_after{};
    std::int64_t exact_mass_quanta_before{0};
    std::int64_t exact_mass_quanta_after{0};
    // These are numerical diagnostics, not physical energy channels.
    double p2g_numerical_energy_residual_j{0.0};
    double roundtrip_numerical_energy_residual_j{0.0};
};

// Tensor-product quadratic B-spline support. On the complete unbounded stencil
// it has partition of unity, first-moment reproduction, and D=(h^2/4)I.
[[nodiscard]] std::vector<KernelSample> quadratic_bspline_samples(
    Vec3d particle_position_m, const TransferConfig& config);

[[nodiscard]] TransferGrid particle_to_grid(
    std::span<const TransferParticle> particles,
    const TransferConfig& config,
    TransferCandidate candidate);

[[nodiscard]] std::vector<TransferParticle> grid_to_particles(
    std::span<const TransferParticle> particles_before,
    const TransferGrid& grid,
    TransferCandidate candidate);

// Diagnostic-only external grid delta for FLIP probes. It deliberately does
// not claim a modeled force or energy source.
void add_diagnostic_grid_velocity_delta(TransferGrid& grid, Vec3d delta_m_per_s);

[[nodiscard]] TransferTotals particle_totals(
    std::span<const TransferParticle> particles, const TransferConfig& config);
[[nodiscard]] TransferTotals grid_totals(const TransferGrid& grid);
[[nodiscard]] std::int64_t exact_particle_mass_quanta(
    std::span<const TransferParticle> particles);

[[nodiscard]] TransferCycle transfer_cycle(
    std::span<const TransferParticle> particles,
    const TransferConfig& config,
    TransferCandidate candidate);

} // namespace mls::experimental
