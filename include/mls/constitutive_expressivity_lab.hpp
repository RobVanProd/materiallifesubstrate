#pragma once

#include "mls/mechanical_observability_lab.hpp"

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace mls::experimental::constitutive_expressivity {

namespace observation = mechanical_observability;

// ConstitutiveExpressivity is a read-only energy experiment. None of the
// types in this header are authoritative packet state, and no function
// integrates motion or applies a force to World.
struct WeightedRelation final {
    observation::BondRelation relation{};
    // Dimensionless, positive finite quadrature/influence weight. It is
    // explicit constitutive data and is never inferred from stable IDs.
    double weight{1.0};

    [[nodiscard]] constexpr bool operator==(
        const WeightedRelation&) const noexcept = default;
};

struct PairRelationCoefficient final {
    observation::BondRelation relation{};
    // H diagonal entry in J/m^2, so 0.5*h*extension^2 is joules.
    double h_j_per_m2{1.0};

    [[nodiscard]] constexpr bool operator==(
        const PairRelationCoefficient&) const noexcept = default;
};

struct RelationExtensionState final {
    // Canonical semantic order; independent of packet/relation input order.
    std::vector<observation::BondRelation> relations{};
    std::vector<double> reference_lengths_m{};
    std::vector<double> extensions_m{};
};

struct PacketDisplacement final {
    std::uint64_t packet_id{0};
    Vec3d displacement_m{};

    [[nodiscard]] constexpr bool operator==(
        const PacketDisplacement&) const noexcept = default;
};

// Actual current length minus actual reference length. Only packet centers and
// retained distance relations participate. This is the finite objective path.
[[nodiscard]] RelationExtensionState evaluate_finite_relation_extensions(
    std::span<const observation::MechanicalPacket> reference_packets,
    std::span<const observation::MechanicalPacket> current_packets,
    std::span<const observation::BondRelation> relations);

// R*u using the inherited unit-direction central-distance rigidity operator.
[[nodiscard]] RelationExtensionState evaluate_linearized_relation_extensions(
    std::span<const observation::MechanicalPacket> reference_packets,
    std::span<const PacketDisplacement> displacements_by_id,
    std::span<const observation::BondRelation> relations);

enum class EnergyFamily : std::uint8_t {
    pair_separable,
    local_incident_collective,
    dense_global_diagnostic,
};

struct LocalCollectiveContribution final {
    std::uint64_t packet_id{0};
    std::size_t incident_relation_count{0};
    // m_i=sum_e w_e*l_e^2 [m^2]. This active-family value is reported and
    // never replaced by a surface/bulk correction.
    double weighted_length_moment_m2{0.0};
    double maximum_incident_length_m{0.0};
    // Each matrix is in the global canonical relation coordinate order.
    observation::DenseMatrix dilatational_h_j_per_m2{};
    observation::DenseMatrix deviatoric_h_j_per_m2{};
    // Local Gram factors used for nonnegative sum-of-squares evaluation.
    observation::DenseMatrix dilatational_factor_sqrt_j_per_m{};
    observation::DenseMatrix deviatoric_factor_sqrt_j_per_m{};
};

struct RelationEnergyOperator final {
    EnergyFamily family{EnergyFamily::pair_separable};
    std::vector<observation::BondRelation> relations{};
    std::vector<double> reference_lengths_m{};
    // E=0.5*e^T*H*e. H is symmetric experimental constitutive data, not
    // persistent packet state.
    observation::DenseMatrix h_j_per_m2{};
    // Explicit Gram factor H=L^T L [sqrt(J)/m]. It permits direct singular
    // analysis of L*R without forming the normal-equation packet Hessian.
    observation::DenseMatrix factor_sqrt_j_per_m{};
    std::vector<LocalCollectiveContribution> local_contributions{};
    // Maximum center-to-neighbor reference length in any local family. A
    // local collective H may couple two relations only when they share a
    // packet.
    double locality_radius_m{0.0};
    std::size_t nonlocal_off_diagonal_count{0};
};

// Pair/bond-like negative control: H=diag(h_e), h_e>0. Parameter entries may
// arrive in any order or endpoint orientation and are canonicalized by the
// physical endpoint identities.
[[nodiscard]] RelationEnergyOperator build_pair_separable_energy(
    std::span<const observation::MechanicalPacket> reference_packets,
    std::span<const PairRelationCoefficient> coefficients);

struct LocalCollectivePolicy final {
    // Positive coefficients in J/m^2. For each packet i:
    // q_i=sum w*l*e, m_i=sum w*l^2, d_i=q_i/m_i,
    // E_i=0.5*A*q_i^2/m_i + 0.5*B*sum w*(e-d_i*l)^2.
    double dilatational_coefficient_j_per_m2{1.0};
    double deviatoric_coefficient_j_per_m2{1.0};
};

// Ordinary-state-based/LPS-style distance-only collective evaluator. Every
// local scalar and extension state is rebuilt from the reference/current
// relation geometry. No deformation gradient, persistent dilatation, tensor,
// history, force, or time state exists.
[[nodiscard]] RelationEnergyOperator build_local_collective_energy(
    std::span<const observation::MechanicalPacket> reference_packets,
    std::span<const WeightedRelation> relations,
    const LocalCollectivePolicy& policy);

struct LocalEnergyValue final {
    std::uint64_t packet_id{0};
    double dilatational_j{0.0};
    double deviatoric_j{0.0};
    double total_j{0.0};
};

struct EnergyEvaluation final {
    double total_j{0.0};
    double dilatational_j{0.0};
    double deviatoric_j{0.0};
    bool finite{false};
    std::vector<LocalEnergyValue> local{};
};

[[nodiscard]] EnergyEvaluation evaluate_energy(
    const RelationEnergyOperator& energy_operator,
    const RelationExtensionState& extensions);

[[nodiscard]] EnergyEvaluation evaluate_finite_energy(
    const RelationEnergyOperator& energy_operator,
    std::span<const observation::MechanicalPacket> reference_packets,
    std::span<const observation::MechanicalPacket> current_packets);

// K=R^T H R in packet-displacement coordinates. This is an algebraic Hessian
// diagnostic only; it is not exposed through an authoritative force API.
[[nodiscard]] observation::DenseMatrix assemble_packet_energy_hessian(
    const observation::BondOperator& rigidity,
    const RelationEnergyOperator& energy_operator);

// L*R is the direct energy-observability operator. It is the preferred rank
// diagnostic because K=R^T*L^T*L*R squares the condition number.
[[nodiscard]] observation::LinearizedOperator
assemble_energy_factor_times_rigidity(
    const observation::BondOperator& rigidity,
    const RelationEnergyOperator& energy_operator);

[[nodiscard]] double maximum_symmetry_residual(
    const observation::DenseMatrix& matrix) noexcept;

} // namespace mls::experimental::constitutive_expressivity
