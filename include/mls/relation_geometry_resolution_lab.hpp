#pragma once

#include "mls/conservative_force_consistency_lab.hpp"

#include <cstdint>
#include <limits>
#include <span>
#include <string_view>
#include <vector>

namespace mls::experimental::relation_geometry_resolution {

namespace observation = mechanical_observability;

// Read-only arithmetic paths for the accepted central-distance coordinate.
// No value in this namespace is authoritative packet or relation state.
enum class GeometryPath : std::uint8_t {
    frozen_binary64,
    cancellation_resistant_binary64,
    transient_double_double,
};

[[nodiscard]] std::string_view path_name(GeometryPath path) noexcept;

enum class GeometryStatus : std::uint8_t {
    evaluated,
    coincident_relation,
    unresolved_noncoincident,
};

[[nodiscard]] std::string_view status_name(GeometryStatus status) noexcept;

enum class LengthOrder : std::int8_t {
    shorter = -1,
    equal = 0,
    longer = 1,
};

[[nodiscard]] std::string_view order_name(LengthOrder order) noexcept;

struct RelationGeometryInput final {
    Vec3d reference_first_m{};
    Vec3d reference_second_m{};
    Vec3d current_first_m{};
    Vec3d current_second_m{};
    // This is the accepted operator's frozen binary64 l0.  The reference
    // endpoint bits are also mandatory so cancellation-resistant paths can
    // evaluate the same real-arithmetic distance difference independently.
    double frozen_reference_length_m{0.0};
};

struct RelationGeometryEvaluation final {
    GeometryPath path{GeometryPath::frozen_binary64};
    GeometryStatus status{GeometryStatus::unresolved_noncoincident};
    bool coordinate_coincident{false};
    Vec3d reference_offset_m{};
    Vec3d current_offset_m{};
    // In Path C these are the low words of transient double-double offsets.
    // They are evidence diagnostics and are never persistent physical state.
    Vec3d reference_offset_low_m{};
    Vec3d current_offset_low_m{};
    double current_length_m{0.0};
    double current_length_low_m{0.0};
    double extension_m{0.0};
    double extension_low_m{0.0};
    Vec3d direction_first_to_second{};
    Vec3d direction_low{};
    double squared_distance_difference_m2{0.0};
    double squared_distance_difference_low_m2{0.0};
    LengthOrder exact_length_order{LengthOrder::equal};

    [[nodiscard]] constexpr bool operator==(
        const RelationGeometryEvaluation&) const noexcept = default;
};

// Evaluate only relation geometry.  Malformed/nonfinite input throws.  Exact
// coordinate coincidence fails closed.  A path that cannot form a direction
// for distinct endpoint bit patterns returns unresolved_noncoincident rather
// than inventing a direction or relabeling the state as exact coincidence.
[[nodiscard]] RelationGeometryEvaluation evaluate_relation_geometry(
    const RelationGeometryInput& input, GeometryPath path);

enum class ResolvedForceStatus : std::uint8_t {
    evaluated,
    coincident_relation,
    unresolved_noncoincident,
};

struct ResolvedRelationForceCoordinate final {
    std::size_t relation_index{0};
    observation::BondRelation relation{};
    RelationGeometryEvaluation geometry{};
    double conjugate_force_n{0.0};
};

struct ResolvedForceEvaluation final {
    ResolvedForceStatus status{ResolvedForceStatus::unresolved_noncoincident};
    double energy_j{std::numeric_limits<double>::quiet_NaN()};
    std::vector<ResolvedRelationForceCoordinate> relation_coordinates{};
    std::vector<conservative_force_consistency::PacketForce> packet_forces{};
    observation::LinearizedOperator current_rigidity{};
    std::size_t failed_relation_index{
        std::numeric_limits<std::size_t>::max()};
    observation::BondRelation failed_relation{};
};

// Parallel read-only force assembly using the frozen accepted H and a named
// relation-geometry path.  The accepted evaluator remains unchanged.
[[nodiscard]] ResolvedForceEvaluation evaluate_resolved_spatial_force(
    const conservative_force_consistency::FrozenForceOperator& energy_operator,
    std::span<const observation::MechanicalPacket> reference_packets,
    std::span<const observation::MechanicalPacket> current_packets,
    GeometryPath path);

struct ResolvedTangentEvaluation final {
    ResolvedForceStatus status{ResolvedForceStatus::unresolved_noncoincident};
    std::vector<std::uint64_t> packet_ids{};
    observation::DenseMatrix material_energy_hessian_n_per_m{};
    observation::DenseMatrix geometric_energy_hessian_n_per_m{};
    observation::DenseMatrix total_energy_hessian_n_per_m{};
    observation::DenseMatrix force_jacobian_n_per_m{};
    std::size_t failed_relation_index{
        std::numeric_limits<std::size_t>::max()};
    observation::BondRelation failed_relation{};
};

[[nodiscard]] ResolvedTangentEvaluation evaluate_resolved_spatial_tangent(
    const conservative_force_consistency::FrozenForceOperator& energy_operator,
    std::span<const observation::MechanicalPacket> reference_packets,
    std::span<const observation::MechanicalPacket> current_packets,
    GeometryPath path);

} // namespace mls::experimental::relation_geometry_resolution
