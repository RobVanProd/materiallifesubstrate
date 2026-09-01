#include "mls/relation_geometry_resolution_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <map>
#include <ranges>
#include <stdexcept>

namespace mls::experimental::relation_geometry_resolution {
namespace {

static_assert(sizeof(double) == 8U);
static_assert(std::numeric_limits<double>::digits == 53);
static_assert(std::numeric_limits<double>::is_iec559);

struct DoubleDouble final {
    double hi{0.0};
    double lo{0.0};
};

[[nodiscard]] bool finite(Vec3d value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
        std::isfinite(value.z);
}

[[nodiscard]] DoubleDouble quick_two_sum(double larger, double smaller) noexcept {
    const auto sum = larger + smaller;
    return {sum, smaller - (sum - larger)};
}

[[nodiscard]] DoubleDouble two_sum(double lhs, double rhs) noexcept {
    const auto sum = lhs + rhs;
    const auto rhs_virtual = sum - lhs;
    const auto error = (lhs - (sum - rhs_virtual)) + (rhs - rhs_virtual);
    return {sum, error};
}

[[nodiscard]] DoubleDouble two_difference(double lhs, double rhs) noexcept {
    const auto difference = lhs - rhs;
    const auto rhs_virtual = lhs - difference;
    const auto error = (lhs - (difference + rhs_virtual)) +
        (rhs_virtual - rhs);
    return {difference, error};
}

[[nodiscard]] DoubleDouble normalize(DoubleDouble value) noexcept {
    return quick_two_sum(value.hi, value.lo);
}

[[nodiscard]] DoubleDouble add(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    const auto sum = lhs.hi + rhs.hi;
    const auto virtual_rhs = sum - lhs.hi;
    auto error = (lhs.hi - (sum - virtual_rhs)) +
        (rhs.hi - virtual_rhs);
    error += lhs.lo + rhs.lo;
    return quick_two_sum(sum, error);
}

[[nodiscard]] DoubleDouble negate(DoubleDouble value) noexcept {
    return {-value.hi, -value.lo};
}

[[nodiscard]] DoubleDouble subtract(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    return add(lhs, negate(rhs));
}

[[nodiscard]] DoubleDouble multiply(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    const auto product = lhs.hi * rhs.hi;
    auto error = std::fma(lhs.hi, rhs.hi, -product);
    error += lhs.hi * rhs.lo + lhs.lo * rhs.hi;
    error += lhs.lo * rhs.lo;
    return quick_two_sum(product, error);
}

[[nodiscard]] DoubleDouble divide(
    DoubleDouble numerator, DoubleDouble denominator) {
    if (denominator.hi == 0.0) {
        throw std::domain_error("double-double division by zero");
    }
    const auto first = numerator.hi / denominator.hi;
    auto quotient = DoubleDouble{first, 0.0};
    for (std::size_t iteration = 0; iteration < 2U; ++iteration) {
        const auto residual = subtract(
            numerator, multiply(denominator, quotient));
        const auto correction = residual.hi / denominator.hi;
        quotient = add(quotient, {correction, 0.0});
    }
    return normalize(quotient);
}

[[nodiscard]] DoubleDouble square_root(DoubleDouble value) {
    if (value.hi < 0.0 || (value.hi == 0.0 && value.lo < 0.0)) {
        throw std::domain_error("double-double square root of negative value");
    }
    if (value.hi == 0.0 && value.lo == 0.0) {
        return {};
    }
    auto root = DoubleDouble{std::sqrt(value.hi), 0.0};
    for (std::size_t iteration = 0; iteration < 2U; ++iteration) {
        const auto residual = subtract(value, multiply(root, root));
        const auto denominator = add(root, root);
        root = add(root, divide(residual, denominator));
    }
    return normalize(root);
}

[[nodiscard]] LengthOrder order(DoubleDouble value) noexcept {
    if (value.hi < 0.0 || (value.hi == 0.0 && value.lo < 0.0)) {
        return LengthOrder::shorter;
    }
    if (value.hi > 0.0 || value.lo > 0.0) {
        return LengthOrder::longer;
    }
    return LengthOrder::equal;
}

[[nodiscard]] LengthOrder order(double value) noexcept {
    if (value < 0.0) {
        return LengthOrder::shorter;
    }
    if (value > 0.0) {
        return LengthOrder::longer;
    }
    return LengthOrder::equal;
}

[[nodiscard]] double stable_norm(Vec3d value) noexcept {
    const auto scale =
        std::max({std::abs(value.x), std::abs(value.y), std::abs(value.z)});
    if (scale == 0.0) {
        return 0.0;
    }
    if (!std::isfinite(scale)) {
        return std::numeric_limits<double>::infinity();
    }
    const auto x = value.x / scale;
    const auto y = value.y / scale;
    const auto z = value.z / scale;
    return scale * std::sqrt(x * x + y * y + z * z);
}

[[nodiscard]] bool same_coordinates(Vec3d lhs, Vec3d rhs) noexcept {
    return lhs.x == rhs.x && lhs.y == rhs.y && lhs.z == rhs.z;
}

[[nodiscard]] std::vector<observation::MechanicalPacket> canonical_packets(
    std::span<const observation::MechanicalPacket> packets) {
    std::vector<observation::MechanicalPacket> result(
        packets.begin(), packets.end());
    std::ranges::sort(result, {}, &observation::MechanicalPacket::id);
    for (std::size_t index = 0; index < result.size(); ++index) {
        const auto& packet = result[index];
        if (packet.id == 0U || packet.mass_quanta <= 0 ||
            !finite(packet.position_m) || !finite(packet.velocity_m_per_s) ||
            (index != 0U && result[index - 1U].id == packet.id)) {
            throw std::invalid_argument(
                "resolved force packets must be unique finite positive state");
        }
    }
    return result;
}

[[nodiscard]] std::map<std::uint64_t, std::size_t> packet_lookup(
    std::span<const observation::MechanicalPacket> packets) {
    std::map<std::uint64_t, std::size_t> result;
    for (std::size_t index = 0; index < packets.size(); ++index) {
        result.emplace(packets[index].id, index);
    }
    return result;
}

void validate_packet_correspondence(
    std::span<const observation::MechanicalPacket> reference,
    std::span<const observation::MechanicalPacket> current) {
    if (reference.size() != current.size()) {
        throw std::invalid_argument(
            "reference/current packet counts differ");
    }
    for (std::size_t index = 0; index < reference.size(); ++index) {
        if (reference[index].id != current[index].id ||
            reference[index].mass_quanta != current[index].mass_quanta) {
            throw std::invalid_argument(
                "reference/current packet identities differ");
        }
    }
}

[[nodiscard]] observation::DenseMatrix material_hessian(
    const observation::LinearizedOperator& rigidity,
    const constitutive_expressivity::RelationEnergyOperator& energy_operator) {
    const auto relation_count = rigidity.matrix.row_count();
    const auto coordinate_count = rigidity.matrix.column_count();
    observation::DenseMatrix h_times_r(relation_count, coordinate_count);
    for (std::size_t row = 0; row < relation_count; ++row) {
        for (std::size_t column = 0; column < coordinate_count; ++column) {
            double value = 0.0;
            for (std::size_t inner = 0; inner < relation_count; ++inner) {
                value += energy_operator.h_j_per_m2(row, inner) *
                    rigidity.matrix(inner, column);
            }
            if (!std::isfinite(value)) {
                throw std::overflow_error("resolved material H*R overflow");
            }
            h_times_r(row, column) = value;
        }
    }
    observation::DenseMatrix result(coordinate_count, coordinate_count);
    for (std::size_t row = 0; row < coordinate_count; ++row) {
        for (std::size_t column = 0; column < coordinate_count; ++column) {
            double value = 0.0;
            for (std::size_t relation = 0; relation < relation_count;
                 ++relation) {
                value += rigidity.matrix(relation, row) *
                    h_times_r(relation, column);
            }
            if (!std::isfinite(value)) {
                throw std::overflow_error(
                    "resolved material R^T*H*R overflow");
            }
            result(row, column) = value;
        }
    }
    return result;
}

[[nodiscard]] DoubleDouble exact_offset(double second, double first) noexcept {
    return two_difference(second, first);
}

[[nodiscard]] std::array<DoubleDouble, 3> exact_offset(
    Vec3d second, Vec3d first) noexcept {
    return {exact_offset(second.x, first.x), exact_offset(second.y, first.y),
            exact_offset(second.z, first.z)};
}

[[nodiscard]] DoubleDouble squared_norm(
    const std::array<DoubleDouble, 3>& offset) noexcept {
    DoubleDouble result{};
    for (const auto component : offset) {
        result = add(result, multiply(component, component));
    }
    return normalize(result);
}

[[nodiscard]] DoubleDouble cancellation_resistant_squared_difference(
    const RelationGeometryInput& input) noexcept {
    const std::array current_first{input.current_first_m.x,
                                   input.current_first_m.y,
                                   input.current_first_m.z};
    const std::array current_second{input.current_second_m.x,
                                    input.current_second_m.y,
                                    input.current_second_m.z};
    const std::array reference_first{input.reference_first_m.x,
                                     input.reference_first_m.y,
                                     input.reference_first_m.z};
    const std::array reference_second{input.reference_second_m.x,
                                      input.reference_second_m.y,
                                      input.reference_second_m.z};
    DoubleDouble result{};
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        // (cs-cf)^2-(rs-rf)^2
        // = ((cs-rs)-(cf-rf))*((cs+rs)-(cf+rf)).
        // The first factor preserves semantic endpoint perturbations before a
        // rounded relation subtraction can erase them.  Every addition,
        // subtraction, product residual, and accumulation order is explicit.
        const auto displacement_difference = subtract(
            two_difference(current_second[axis], reference_second[axis]),
            two_difference(current_first[axis], reference_first[axis]));
        const auto offset_sum = subtract(
            two_sum(current_second[axis], reference_second[axis]),
            two_sum(current_first[axis], reference_first[axis]));
        result = add(
            result, multiply(displacement_difference, offset_sum));
    }
    return normalize(result);
}

void validate_input(const RelationGeometryInput& input) {
    if (!finite(input.reference_first_m) ||
        !finite(input.reference_second_m) ||
        !finite(input.current_first_m) ||
        !finite(input.current_second_m) ||
        !(input.frozen_reference_length_m > 0.0) ||
        !std::isfinite(input.frozen_reference_length_m)) {
        throw std::invalid_argument(
            "relation geometry requires finite endpoints and positive l0");
    }
    if (same_coordinates(input.reference_first_m, input.reference_second_m)) {
        throw std::invalid_argument(
            "relation geometry reference endpoints must be noncoincident");
    }
}

[[nodiscard]] Vec3d high_words(
    const std::array<DoubleDouble, 3>& value) noexcept {
    return {value[0].hi, value[1].hi, value[2].hi};
}

[[nodiscard]] Vec3d low_words(
    const std::array<DoubleDouble, 3>& value) noexcept {
    return {value[0].lo, value[1].lo, value[2].lo};
}

} // namespace

std::string_view path_name(GeometryPath path) noexcept {
    switch (path) {
    case GeometryPath::frozen_binary64:
        return "frozen_binary64";
    case GeometryPath::cancellation_resistant_binary64:
        return "cancellation_resistant_binary64";
    case GeometryPath::transient_double_double:
        return "transient_double_double";
    }
    return "unknown";
}

std::string_view status_name(GeometryStatus status) noexcept {
    switch (status) {
    case GeometryStatus::evaluated:
        return "evaluated";
    case GeometryStatus::coincident_relation:
        return "coincident_relation";
    case GeometryStatus::unresolved_noncoincident:
        return "unresolved_noncoincident";
    }
    return "unknown";
}

std::string_view order_name(LengthOrder value) noexcept {
    switch (value) {
    case LengthOrder::shorter:
        return "shorter";
    case LengthOrder::equal:
        return "equal";
    case LengthOrder::longer:
        return "longer";
    }
    return "unknown";
}

RelationGeometryEvaluation evaluate_relation_geometry(
    const RelationGeometryInput& input, GeometryPath path) {
    validate_input(input);
    RelationGeometryEvaluation result{};
    result.path = path;
    result.coordinate_coincident =
        same_coordinates(input.current_first_m, input.current_second_m);

    if (path == GeometryPath::transient_double_double) {
        const auto reference_offset = exact_offset(
            input.reference_second_m, input.reference_first_m);
        const auto current_offset = exact_offset(
            input.current_second_m, input.current_first_m);
        result.reference_offset_m = high_words(reference_offset);
        result.reference_offset_low_m = low_words(reference_offset);
        result.current_offset_m = high_words(current_offset);
        result.current_offset_low_m = low_words(current_offset);
        const auto reference_squared = squared_norm(reference_offset);
        const auto current_squared = squared_norm(current_offset);
        // Direct subtraction of two double-double squared norms still has
        // only about 106 bits of relative precision.  It cannot retain a
        // subnormal endpoint perturbation beside an O(1) reference norm.
        // Preserve the exact algebraic coordinate with the independently
        // factored endpoint-bit numerator, then divide by the DD norm sum.
        const auto squared_difference =
            cancellation_resistant_squared_difference(input);
        result.squared_distance_difference_m2 = squared_difference.hi;
        result.squared_distance_difference_low_m2 = squared_difference.lo;
        if (result.coordinate_coincident) {
            result.status = GeometryStatus::coincident_relation;
            return result;
        }
        const auto reference_length = square_root(reference_squared);
        const auto current_length = square_root(current_squared);
        if (current_length.hi == 0.0) {
            result.status = GeometryStatus::unresolved_noncoincident;
            return result;
        }
        const auto extension = divide(
            squared_difference, add(current_length, reference_length));
        result.current_length_m = current_length.hi;
        result.current_length_low_m = current_length.lo;
        result.extension_m = extension.hi;
        result.extension_low_m = extension.lo;
        result.exact_length_order = order(extension);
        std::array<DoubleDouble, 3> direction{};
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            direction[axis] = divide(current_offset[axis], current_length);
        }
        result.direction_first_to_second = high_words(direction);
        result.direction_low = low_words(direction);
        if (!finite(result.direction_first_to_second)) {
            throw std::overflow_error(
                "transient relation direction is nonfinite");
        }
        result.status = GeometryStatus::evaluated;
        return result;
    }

    result.reference_offset_m =
        input.reference_second_m - input.reference_first_m;
    result.current_offset_m = input.current_second_m - input.current_first_m;
    if (!finite(result.reference_offset_m) || !finite(result.current_offset_m)) {
        throw std::overflow_error("binary64 relation offset overflow");
    }
    const auto current_length = stable_norm(result.current_offset_m);
    if (result.coordinate_coincident) {
        result.status = GeometryStatus::coincident_relation;
        return result;
    }
    if (current_length == 0.0) {
        result.status = GeometryStatus::unresolved_noncoincident;
        return result;
    }
    if (!std::isfinite(current_length)) {
        throw std::overflow_error("binary64 relation length overflow");
    }
    result.current_length_m = current_length;
    result.direction_first_to_second = {
        result.current_offset_m.x / current_length,
        result.current_offset_m.y / current_length,
        result.current_offset_m.z / current_length};
    if (!finite(result.direction_first_to_second)) {
        throw std::overflow_error("binary64 relation direction overflow");
    }

    if (path == GeometryPath::frozen_binary64) {
        result.extension_m =
            current_length - input.frozen_reference_length_m;
        result.exact_length_order = order(result.extension_m);
        result.squared_distance_difference_m2 =
            current_length * current_length -
            input.frozen_reference_length_m *
                input.frozen_reference_length_m;
    } else {
        const auto numerator =
            cancellation_resistant_squared_difference(input);
        const auto denominator =
            current_length + input.frozen_reference_length_m;
        if (!(denominator > 0.0) || !std::isfinite(denominator)) {
            throw std::overflow_error(
                "rationalized extension denominator is invalid");
        }
        const auto extension = divide(numerator, {denominator, 0.0});
        result.extension_m = extension.hi;
        result.extension_low_m = extension.lo;
        result.squared_distance_difference_m2 = numerator.hi;
        result.squared_distance_difference_low_m2 = numerator.lo;
        result.exact_length_order = order(numerator);
    }
    if (!std::isfinite(result.extension_m) ||
        !std::isfinite(result.squared_distance_difference_m2)) {
        throw std::overflow_error("relation extension evaluation overflow");
    }
    result.status = GeometryStatus::evaluated;
    return result;
}

ResolvedForceEvaluation evaluate_resolved_spatial_force(
    const conservative_force_consistency::FrozenForceOperator& frozen_operator,
    std::span<const observation::MechanicalPacket> reference_packets,
    std::span<const observation::MechanicalPacket> current_packets,
    GeometryPath path) {
    // Reuse the accepted reference evaluation as an immutable-integrity guard
    // for the parent/force operator pairing.  Candidate geometry never enters
    // this call and the accepted implementation remains untouched.
    const auto accepted_reference =
        conservative_force_consistency::evaluate_spatial_force(
            frozen_operator, reference_packets);
    if (accepted_reference.status !=
        conservative_force_consistency::ForceDomainStatus::evaluated) {
        throw std::invalid_argument(
            "frozen operator does not evaluate on its reference packets");
    }

    const auto reference = canonical_packets(reference_packets);
    const auto current = canonical_packets(current_packets);
    validate_packet_correspondence(reference, current);
    const auto reference_lookup = packet_lookup(reference);
    const auto current_lookup = packet_lookup(current);
    const auto& energy_operator = frozen_operator.force_operator;
    const auto relation_count = energy_operator.relations.size();
    if (energy_operator.reference_lengths_m.size() != relation_count ||
        energy_operator.h_j_per_m2.row_count() != relation_count ||
        energy_operator.h_j_per_m2.column_count() != relation_count) {
        throw std::invalid_argument(
            "resolved force operator dimensions disagree");
    }

    std::vector<RelationGeometryEvaluation> geometries;
    geometries.reserve(relation_count);
    for (std::size_t index = 0; index < relation_count; ++index) {
        const auto relation = energy_operator.relations[index];
        if (!reference_lookup.contains(relation.first_id) ||
            !reference_lookup.contains(relation.second_id) ||
            !current_lookup.contains(relation.first_id) ||
            !current_lookup.contains(relation.second_id)) {
            throw std::invalid_argument(
                "resolved force relation endpoint is absent");
        }
        const auto& reference_first =
            reference[reference_lookup.at(relation.first_id)];
        const auto& reference_second =
            reference[reference_lookup.at(relation.second_id)];
        const auto& current_first =
            current[current_lookup.at(relation.first_id)];
        const auto& current_second =
            current[current_lookup.at(relation.second_id)];
        auto geometry = evaluate_relation_geometry(
            {.reference_first_m = reference_first.position_m,
             .reference_second_m = reference_second.position_m,
             .current_first_m = current_first.position_m,
             .current_second_m = current_second.position_m,
             .frozen_reference_length_m =
                 energy_operator.reference_lengths_m[index]},
            path);
        if (geometry.status != GeometryStatus::evaluated) {
            ResolvedForceEvaluation failure{};
            failure.status = geometry.status == GeometryStatus::coincident_relation
                ? ResolvedForceStatus::coincident_relation
                : ResolvedForceStatus::unresolved_noncoincident;
            failure.failed_relation_index = index;
            failure.failed_relation = relation;
            return failure;
        }
        geometries.push_back(std::move(geometry));
    }

    std::vector<double> conjugate(relation_count, 0.0);
    for (std::size_t row = 0; row < relation_count; ++row) {
        for (std::size_t column = 0; column < relation_count; ++column) {
            conjugate[row] += energy_operator.h_j_per_m2(row, column) *
                geometries[column].extension_m;
        }
        if (!std::isfinite(conjugate[row])) {
            throw std::overflow_error("resolved relation conjugate overflow");
        }
    }
    double energy_twice = 0.0;
    for (std::size_t index = 0; index < relation_count; ++index) {
        energy_twice += geometries[index].extension_m * conjugate[index];
    }
    if (!std::isfinite(energy_twice)) {
        throw std::overflow_error("resolved relation energy overflow");
    }

    ResolvedForceEvaluation result{};
    result.status = ResolvedForceStatus::evaluated;
    result.energy_j = 0.5 * energy_twice;
    result.current_rigidity.kind =
        observation::ObservableKind::central_bond_length_rate;
    result.current_rigidity.matrix =
        observation::DenseMatrix(relation_count, 3U * current.size());
    result.current_rigidity.packet_ids.reserve(current.size());
    for (const auto& packet : current) {
        result.current_rigidity.packet_ids.push_back(packet.id);
    }
    std::vector<Vec3d> accumulated(current.size());
    result.relation_coordinates.reserve(relation_count);
    for (std::size_t index = 0; index < relation_count; ++index) {
        const auto relation = energy_operator.relations[index];
        const auto first = current_lookup.at(relation.first_id);
        const auto second = current_lookup.at(relation.second_id);
        const auto direction = geometries[index].direction_first_to_second;
        const auto relation_force = conjugate[index] * direction;
        accumulated[first] += relation_force;
        accumulated[second] += -relation_force;
        result.relation_coordinates.push_back(
            {index, relation, geometries[index], conjugate[index]});
        const std::array components{direction.x, direction.y, direction.z};
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            result.current_rigidity.matrix(index, 3U * first + axis) =
                -components[axis];
            result.current_rigidity.matrix(index, 3U * second + axis) =
                components[axis];
        }
    }
    result.packet_forces.reserve(current.size());
    for (std::size_t index = 0; index < current.size(); ++index) {
        if (!finite(accumulated[index])) {
            throw std::overflow_error("resolved packet force overflow");
        }
        result.packet_forces.push_back(
            {current[index].id, accumulated[index]});
    }
    return result;
}

ResolvedTangentEvaluation evaluate_resolved_spatial_tangent(
    const conservative_force_consistency::FrozenForceOperator& frozen_operator,
    std::span<const observation::MechanicalPacket> reference_packets,
    std::span<const observation::MechanicalPacket> current_packets,
    GeometryPath path) {
    const auto force = evaluate_resolved_spatial_force(
        frozen_operator, reference_packets, current_packets, path);
    if (force.status != ResolvedForceStatus::evaluated) {
        ResolvedTangentEvaluation failure{};
        failure.status = force.status;
        failure.failed_relation_index = force.failed_relation_index;
        failure.failed_relation = force.failed_relation;
        return failure;
    }
    ResolvedTangentEvaluation result{};
    result.status = ResolvedForceStatus::evaluated;
    result.packet_ids = force.current_rigidity.packet_ids;
    result.material_energy_hessian_n_per_m = material_hessian(
        force.current_rigidity, frozen_operator.force_operator);
    const auto coordinate_count = force.current_rigidity.matrix.column_count();
    result.geometric_energy_hessian_n_per_m =
        observation::DenseMatrix(coordinate_count, coordinate_count);
    const auto current = canonical_packets(current_packets);
    const auto lookup = packet_lookup(current);
    for (const auto& coordinate : force.relation_coordinates) {
        const auto first = lookup.at(coordinate.relation.first_id);
        const auto second = lookup.at(coordinate.relation.second_id);
        const auto direction = coordinate.geometry.direction_first_to_second;
        const std::array n{direction.x, direction.y, direction.z};
        const auto radius = coordinate.geometry.current_length_m;
        if (!(radius > 0.0)) {
            throw std::overflow_error(
                "resolved tangent radius is not positive");
        }
        for (std::size_t row_axis = 0; row_axis < 3U; ++row_axis) {
            for (std::size_t column_axis = 0; column_axis < 3U;
                 ++column_axis) {
                const auto identity =
                    row_axis == column_axis ? 1.0 : 0.0;
                const auto projector =
                    (identity - n[row_axis] * n[column_axis]) / radius;
                const auto contribution =
                    coordinate.conjugate_force_n * projector;
                const auto first_row = 3U * first + row_axis;
                const auto second_row = 3U * second + row_axis;
                const auto first_column = 3U * first + column_axis;
                const auto second_column = 3U * second + column_axis;
                result.geometric_energy_hessian_n_per_m(
                    first_row, first_column) += contribution;
                result.geometric_energy_hessian_n_per_m(
                    second_row, second_column) += contribution;
                result.geometric_energy_hessian_n_per_m(
                    first_row, second_column) -= contribution;
                result.geometric_energy_hessian_n_per_m(
                    second_row, first_column) -= contribution;
            }
        }
    }
    result.total_energy_hessian_n_per_m =
        observation::DenseMatrix(coordinate_count, coordinate_count);
    result.force_jacobian_n_per_m =
        observation::DenseMatrix(coordinate_count, coordinate_count);
    for (std::size_t row = 0; row < coordinate_count; ++row) {
        for (std::size_t column = 0; column < coordinate_count; ++column) {
            const auto total =
                result.material_energy_hessian_n_per_m(row, column) +
                result.geometric_energy_hessian_n_per_m(row, column);
            if (!std::isfinite(total)) {
                throw std::overflow_error("resolved force tangent overflow");
            }
            result.total_energy_hessian_n_per_m(row, column) = total;
            result.force_jacobian_n_per_m(row, column) = -total;
        }
    }
    return result;
}

} // namespace mls::experimental::relation_geometry_resolution
