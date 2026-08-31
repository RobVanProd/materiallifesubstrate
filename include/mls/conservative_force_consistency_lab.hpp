#pragma once

#include "mls/constitutive_expressivity_lab.hpp"

#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <string_view>
#include <vector>

namespace mls::experimental::conservative_force_consistency {

namespace constitutive = constitutive_expressivity;
namespace observation = mechanical_observability;

// This namespace contains a read-only spatial derivative experiment. It does
// not install forces in World, integrate motion, or create authoritative
// packet state. The constitutive operator, topology, and reference lengths are
// consumed as frozen input and are never inferred from the current geometry.
enum class ForceDomainStatus : std::uint8_t {
    evaluated,
    coincident_relation,
};

[[nodiscard]] std::string_view status_name(ForceDomainStatus status) noexcept;

struct RelationForceCoordinate final {
    // Index and relation are exactly the frozen RelationEnergyOperator
    // coordinate. No force-specific reordering of H is permitted.
    std::size_t relation_index{0};
    observation::BondRelation relation{};
    double reference_length_m{0.0};
    double current_length_m{0.0};
    double extension_m{0.0};
    // g_a=(H*e)_a [N]. It is computed once before spatial assembly and may
    // depend on extensions of other incident relations.
    double conjugate_force_n{0.0};
    Vec3d direction_first_to_second{};

    [[nodiscard]] constexpr bool operator==(
        const RelationForceCoordinate&) const noexcept = default;
};

struct PacketForce final {
    std::uint64_t packet_id{0};
    Vec3d force_n{};

    [[nodiscard]] constexpr bool operator==(
        const PacketForce&) const noexcept = default;
};

struct FrozenForceOperator final {
    // Parent is retained byte-for-byte for traceability. force_operator differs
    // only in H: each off-diagonal unordered pair is averaged once and mirrored
    // exactly, while diagonals are copied. The bounded binary64 pair-average
    // representation error is audited; no diagonal/eigenvalue regularisation,
    // current-state input, or constitutive rebuild occurs.
    constitutive::RelationEnergyOperator parent_operator{};
    constitutive::RelationEnergyOperator force_operator{};
    double maximum_parent_h_magnitude_j_per_m2{0.0};
    double maximum_correction_j_per_m2{0.0};
    double correction_tolerance_j_per_m2{0.0};
};

[[nodiscard]] FrozenForceOperator freeze_symmetric_force_operator(
    const constitutive::RelationEnergyOperator& parent_operator);

struct SpatialForceEvaluation final {
    ForceDomainStatus status{ForceDomainStatus::coincident_relation};
    // Valid only when status==evaluated. A domain failure deliberately leaves
    // every potentially actionable output empty and energy_j non-finite.
    double energy_j{std::numeric_limits<double>::quiet_NaN()};
    std::vector<RelationForceCoordinate> relation_coordinates{};
    std::vector<PacketForce> packet_forces{};
    observation::LinearizedOperator current_rigidity{};
    // Populated only for coincident_relation.
    std::size_t failed_relation_index{
        std::numeric_limits<std::size_t>::max()};
    observation::BondRelation failed_relation{};
};

// Explicitly applies a relation-coordinate permutation. new_to_old[new] gives
// the source coordinate. Relations, reference lengths, H rows/columns, and
// every stored factor/local block are transformed together. This helper is
// the only supported way to move H to a different coordinate order.
[[nodiscard]] FrozenForceOperator permute_relation_coordinates(
    const FrozenForceOperator& energy_operator,
    std::span<const std::size_t> new_to_old);

// On the explicit noncoincident domain, evaluate
//   e_a=|x_j-x_i|-l_a^0, U=0.5*e^T*H*e, g=H*e,
//   f_i+=g_a*n_a, f_j-=g_a*n_a.
// H, reference lengths, relation topology, and canonical relation order come
// only from energy_operator. Malformed data throw; exact coincidence returns
// a structured, output-empty domain failure before any force is assembled.
[[nodiscard]] SpatialForceEvaluation evaluate_spatial_force(
    const FrozenForceOperator& energy_operator,
    std::span<const observation::MechanicalPacket> current_packets);

struct ContinuousForceIdentities final {
    Vec3d total_internal_force_n{};
    Vec3d torque_about_origin_n_m{};
    Vec3d torque_about_second_origin_n_m{};
    // dU/dt=g dot (R*v) and sum_p f_p dot v_p=-dU/dt [W].
    double relation_energy_rate_w{0.0};
    double force_power_w{0.0};
    double power_identity_residual_w{0.0};
};

// Uses current packet velocities only as a virtual-velocity probe. It does not
// advance time or mutate any state.
[[nodiscard]] ContinuousForceIdentities evaluate_continuous_identities(
    const SpatialForceEvaluation& force,
    std::span<const observation::MechanicalPacket> current_packets,
    Vec3d second_origin_m);

struct SpatialTangentEvaluation final {
    ForceDomainStatus status{ForceDomainStatus::coincident_relation};
    std::vector<std::uint64_t> packet_ids{};
    // d^2U/dx^2 = R^T H R + sum_a g_a*d^2|r_a|/dx^2 [N/m].
    observation::DenseMatrix material_energy_hessian_n_per_m{};
    observation::DenseMatrix geometric_energy_hessian_n_per_m{};
    observation::DenseMatrix total_energy_hessian_n_per_m{};
    // df/dx=-d^2U/dx^2. This is a read-only derivative diagnostic.
    observation::DenseMatrix force_jacobian_n_per_m{};
    std::size_t failed_relation_index{
        std::numeric_limits<std::size_t>::max()};
    observation::BondRelation failed_relation{};
};

// Analytic finite tangent. At reference e=g=0 the geometric term is zero and
// the material term reduces to the accepted R_0^T H R_0 Hessian. No
// nonsymmetric or direction-frozen approximation is substituted.
[[nodiscard]] SpatialTangentEvaluation evaluate_spatial_tangent(
    const FrozenForceOperator& energy_operator,
    std::span<const observation::MechanicalPacket> current_packets);

[[nodiscard]] double maximum_asymmetry(
    const observation::DenseMatrix& matrix) noexcept;

} // namespace mls::experimental::conservative_force_consistency
