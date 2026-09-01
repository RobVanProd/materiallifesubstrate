#pragma once

#include "mls/conservative_force_consistency_lab.hpp"

#include <cstdint>
#include <string_view>

namespace mls::experimental::relation_geometry_resolution {

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

} // namespace mls::experimental::relation_geometry_resolution

