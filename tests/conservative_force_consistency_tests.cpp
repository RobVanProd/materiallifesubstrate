#include "test_harness.hpp"

#include "mls/conservative_force_consistency_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <map>
#include <numbers>
#include <vector>

namespace {

namespace force =
    mls::experimental::conservative_force_consistency;
namespace constitutive = mls::experimental::constitutive_expressivity;
namespace observation = mls::experimental::mechanical_observability;
using mls::experimental::Matrix3d;
using mls::experimental::Vec3d;
using observation::BondRelation;
using observation::MechanicalPacket;

[[nodiscard]] std::vector<MechanicalPacket> tetrahedron() {
    return {
        {1, 1, {0.0, 0.0, 0.0}, {}},
        {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}},
        {4, 1, {0.0, 0.0, 1.0}, {}},
    };
}

[[nodiscard]] std::vector<BondRelation> k4() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
}

[[nodiscard]] std::vector<constitutive::WeightedRelation> weighted(
    std::span<const BondRelation> relations) {
    std::vector<constitutive::WeightedRelation> result;
    result.reserve(relations.size());
    for (const auto relation : relations) {
        result.push_back({relation, 1.0});
    }
    return result;
}

[[nodiscard]] force::FrozenForceOperator local_model(
    std::span<const MechanicalPacket> reference,
    std::span<const BondRelation> relations, double ratio = 2.0) {
    return force::freeze_symmetric_force_operator(
        constitutive::build_local_collective_energy(
            reference, weighted(relations),
            {.dilatational_coefficient_j_per_m2 = 3.0 * ratio / 20.0,
             .deviatoric_coefficient_j_per_m2 = 0.25}));
}

[[nodiscard]] Matrix3d general_deformation() {
    Matrix3d result{};
    result.value = {{{21.0 / 20.0, 1.0 / 20.0, -1.0 / 40.0},
                     {0.0, 19.0 / 20.0, 1.0 / 25.0},
                     {1.0 / 50.0, 0.0, 11.0 / 10.0}}};
    return result;
}

[[nodiscard]] Matrix3d rational_rotation() {
    Matrix3d result{};
    result.value = {{{1.0 / 9.0, 8.0 / 9.0, 4.0 / 9.0},
                     {8.0 / 9.0, 1.0 / 9.0, -4.0 / 9.0},
                     {-4.0 / 9.0, 4.0 / 9.0, -7.0 / 9.0}}};
    return result;
}

[[nodiscard]] std::vector<MechanicalPacket> transform(
    std::span<const MechanicalPacket> packets, const Matrix3d& map,
    Vec3d translation = {}, double velocity_scale = 1.0) {
    std::vector<MechanicalPacket> result(packets.begin(), packets.end());
    for (auto& packet : result) {
        packet.position_m =
            mls::experimental::multiply(map, packet.position_m) + translation;
        packet.velocity_m_per_s = velocity_scale *
            mls::experimental::multiply(map, packet.velocity_m_per_s);
    }
    return result;
}

[[nodiscard]] double magnitude(Vec3d value) {
    return std::sqrt(mls::experimental::dot(value, value));
}

[[nodiscard]] bool close(double lhs, double rhs, double relative,
                         double absolute = 1.0e-14) {
    return std::abs(lhs - rhs) <=
        std::max(absolute, relative * std::max(std::abs(lhs), std::abs(rhs)));
}

[[nodiscard]] bool close(Vec3d lhs, Vec3d rhs, double relative,
                         double absolute = 1.0e-14) {
    return close(lhs.x, rhs.x, relative, absolute) &&
        close(lhs.y, rhs.y, relative, absolute) &&
        close(lhs.z, rhs.z, relative, absolute);
}

[[nodiscard]] std::vector<double> flatten_forces(
    const force::SpatialForceEvaluation& evaluated) {
    std::vector<double> result;
    result.reserve(3U * evaluated.packet_forces.size());
    for (const auto& packet : evaluated.packet_forces) {
        result.push_back(packet.force_n.x);
        result.push_back(packet.force_n.y);
        result.push_back(packet.force_n.z);
    }
    return result;
}

[[nodiscard]] std::vector<MechanicalPacket> displaced(
    std::span<const MechanicalPacket> reference, std::span<const double> u,
    double epsilon) {
    MLS_REQUIRE_EQ(u.size(), 3U * reference.size());
    std::vector<MechanicalPacket> result(reference.begin(), reference.end());
    for (std::size_t index = 0; index < result.size(); ++index) {
        result[index].position_m.x += epsilon * u[3U * index];
        result[index].position_m.y += epsilon * u[3U * index + 1U];
        result[index].position_m.z += epsilon * u[3U * index + 2U];
    }
    return result;
}

[[nodiscard]] std::vector<double> matrix_times(
    const observation::DenseMatrix& matrix, std::span<const double> vector) {
    MLS_REQUIRE_EQ(matrix.column_count(), vector.size());
    std::vector<double> result(matrix.row_count(), 0.0);
    for (std::size_t row = 0; row < matrix.row_count(); ++row) {
        long double value = 0.0L;
        for (std::size_t column = 0; column < matrix.column_count(); ++column) {
            value += static_cast<long double>(matrix(row, column)) *
                vector[column];
        }
        result[row] = static_cast<double>(value);
    }
    return result;
}

[[nodiscard]] double max_difference(
    std::span<const double> lhs, std::span<const double> rhs) {
    MLS_REQUIRE_EQ(lhs.size(), rhs.size());
    double result = 0.0;
    for (std::size_t index = 0; index < lhs.size(); ++index) {
        result = std::max(result, std::abs(lhs[index] - rhs[index]));
    }
    return result;
}

[[nodiscard]] std::vector<double> deterministic_direction(std::size_t count) {
    std::vector<double> result(count);
    long double squared = 0.0L;
    for (std::size_t index = 0; index < count; ++index) {
        const auto signed_index = static_cast<double>(index + 1U);
        result[index] = std::sin(0.731 * signed_index) +
            0.5 * std::cos(0.377 * signed_index);
        squared += static_cast<long double>(result[index]) * result[index];
    }
    const auto inverse_norm = 1.0 / std::sqrt(static_cast<double>(squared));
    for (auto& value : result) {
        value *= inverse_norm;
    }
    return result;
}

} // namespace

MLS_TEST("conservative force is exactly the frozen relation gradient") {
    const auto reference = tetrahedron();
    const auto relations = k4();
    const auto model = local_model(reference, relations);
    auto current = transform(reference, general_deformation());
    const Matrix3d velocity_gradient = [] {
        Matrix3d value{};
        value.value = {{{1.0 / 7.0, -1.0 / 11.0, 1.0 / 13.0},
                        {2.0 / 17.0, -1.0 / 19.0, 1.0 / 23.0},
                        {-1.0 / 29.0, 2.0 / 31.0, 1.0 / 37.0}}};
        return value;
    }();
    for (auto& packet : current) {
        packet.velocity_m_per_s = mls::experimental::multiply(
            velocity_gradient, packet.position_m);
        packet.velocity_m_per_s += {1.0 / 5.0, -1.0 / 7.0, 1.0 / 11.0};
    }

    const auto evaluated = force::evaluate_spatial_force(model, current);
    MLS_REQUIRE_EQ(evaluated.status, force::ForceDomainStatus::evaluated);
    MLS_REQUIRE_EQ(evaluated.relation_coordinates.size(), relations.size());
    MLS_REQUIRE_EQ(evaluated.packet_forces.size(), reference.size());
    const auto accepted_energy = constitutive::evaluate_finite_energy(
        model.parent_operator, reference, current);
    MLS_REQUIRE(accepted_energy.finite);
    MLS_REQUIRE(close(evaluated.energy_j, accepted_energy.total_j, 2.0e-13));

    // Independently apply -R^T to the one exported canonical g vector.
    std::vector<double> expected(3U * current.size(), 0.0);
    for (std::size_t coordinate = 0; coordinate < expected.size(); ++coordinate) {
        long double value = 0.0L;
        for (std::size_t relation = 0; relation < relations.size(); ++relation) {
            value -= static_cast<long double>(
                evaluated.current_rigidity.matrix(relation, coordinate)) *
                evaluated.relation_coordinates[relation].conjugate_force_n;
        }
        expected[coordinate] = static_cast<double>(value);
    }
    MLS_REQUIRE(max_difference(flatten_forces(evaluated), expected) < 2.0e-16);

    // Off-diagonal H makes the relation conjugates collective, not springs.
    bool found_collective_coupling = false;
    for (std::size_t row = 0; row < relations.size(); ++row) {
        for (std::size_t column = 0; column < relations.size(); ++column) {
            found_collective_coupling = found_collective_coupling ||
                (row != column &&
                 model.force_operator.h_j_per_m2(row, column) != 0.0);
        }
    }
    MLS_REQUIRE(found_collective_coupling);

    const auto identities = force::evaluate_continuous_identities(
        evaluated, current, {7.0 / 13.0, -5.0 / 11.0, 3.0 / 17.0});
    MLS_REQUIRE(magnitude(identities.total_internal_force_n) < 2.0e-16);
    MLS_REQUIRE(magnitude(identities.torque_about_origin_n_m) < 3.0e-16);
    MLS_REQUIRE(magnitude(identities.torque_about_second_origin_n_m) < 4.0e-16);
    MLS_REQUIRE(std::abs(identities.power_identity_residual_w) < 3.0e-16);
    MLS_REQUIRE(close(
        identities.relation_energy_rate_w, -identities.force_power_w,
        2.0e-14));
}

MLS_TEST("conservative reference tangent joins the accepted linear Hessian") {
    const auto reference = tetrahedron();
    const auto relations = k4();
    const auto model = local_model(reference, relations, 10.0);
    const auto force_at_reference =
        force::evaluate_spatial_force(model, reference);
    MLS_REQUIRE_EQ(
        force_at_reference.status, force::ForceDomainStatus::evaluated);
    MLS_REQUIRE_EQ(force_at_reference.energy_j, 0.0);
    for (const auto& coordinate : force_at_reference.relation_coordinates) {
        MLS_REQUIRE_EQ(coordinate.extension_m, 0.0);
        MLS_REQUIRE_EQ(coordinate.conjugate_force_n, 0.0);
    }
    for (const auto& packet : force_at_reference.packet_forces) {
        MLS_REQUIRE_EQ(packet.force_n, Vec3d{});
    }

    const auto tangent = force::evaluate_spatial_tangent(model, reference);
    MLS_REQUIRE_EQ(tangent.status, force::ForceDomainStatus::evaluated);
    const auto rigidity = observation::build_bond_rigidity_operator(
        reference, relations);
    const auto accepted = constitutive::assemble_packet_energy_hessian(
        rigidity, model.force_operator);
    for (std::size_t row = 0; row < accepted.row_count(); ++row) {
        for (std::size_t column = 0; column < accepted.column_count(); ++column) {
            MLS_REQUIRE_EQ(
                tangent.geometric_energy_hessian_n_per_m(row, column), 0.0);
            MLS_REQUIRE(close(
                tangent.material_energy_hessian_n_per_m(row, column),
                accepted(row, column), 2.0e-15));
            MLS_REQUIRE(close(
                tangent.force_jacobian_n_per_m(row, column),
                -accepted(row, column), 2.0e-15));
        }
    }

    const auto direction = deterministic_direction(3U * reference.size());
    const auto target = matrix_times(tangent.force_jacobian_n_per_m, direction);
    const std::array epsilons{
        std::ldexp(1.0, -6), std::ldexp(1.0, -9),
        std::ldexp(1.0, -12), std::ldexp(1.0, -15),
        std::ldexp(1.0, -18), std::ldexp(1.0, -21)};
    std::vector<double> errors;
    for (const auto epsilon : epsilons) {
        const auto moved = displaced(reference, direction, epsilon);
        auto actual = flatten_forces(force::evaluate_spatial_force(model, moved));
        for (auto& value : actual) {
            value /= epsilon;
        }
        errors.push_back(max_difference(actual, target));
    }
    MLS_REQUIRE(errors[1] < errors[0]);
    MLS_REQUIRE(errors[2] < errors[1]);
    MLS_REQUIRE(errors[3] < errors[2]);
    MLS_REQUIRE(*std::ranges::min_element(errors) < 2.0e-5);
}

MLS_TEST("conservative finite tangent includes symmetric geometric response") {
    const auto reference = tetrahedron();
    const auto relations = k4();
    const auto model = local_model(reference, relations, 1.0 / 3.0);
    const auto current = transform(reference, general_deformation());
    const auto tangent = force::evaluate_spatial_tangent(model, current);
    MLS_REQUIRE_EQ(tangent.status, force::ForceDomainStatus::evaluated);
    MLS_REQUIRE(force::maximum_asymmetry(
                    tangent.material_energy_hessian_n_per_m) < 2.0e-16);
    MLS_REQUIRE(force::maximum_asymmetry(
                    tangent.geometric_energy_hessian_n_per_m) < 2.0e-16);
    MLS_REQUIRE(force::maximum_asymmetry(
                    tangent.total_energy_hessian_n_per_m) < 3.0e-16);
    double geometric_norm = 0.0;
    for (std::size_t row = 0; row < tangent.packet_ids.size() * 3U; ++row) {
        for (std::size_t column = 0; column < tangent.packet_ids.size() * 3U;
             ++column) {
            const auto expected =
                tangent.material_energy_hessian_n_per_m(row, column) +
                tangent.geometric_energy_hessian_n_per_m(row, column);
            MLS_REQUIRE_EQ(
                tangent.total_energy_hessian_n_per_m(row, column), expected);
            MLS_REQUIRE_EQ(
                tangent.force_jacobian_n_per_m(row, column), -expected);
            geometric_norm = std::max(
                geometric_norm,
                std::abs(tangent.geometric_energy_hessian_n_per_m(row, column)));
        }
    }
    MLS_REQUIRE(geometric_norm > 1.0e-4);

    // Binary64 finite differences are a diagnostic only; the analytic
    // derivative above is the production object.
    constexpr auto step = 1.0e-6;
    const auto dof_count = 3U * current.size();
    for (std::size_t column = 0; column < dof_count; ++column) {
        std::vector<double> basis(dof_count, 0.0);
        basis[column] = 1.0;
        const auto plus = flatten_forces(force::evaluate_spatial_force(
            model, displaced(current, basis, step)));
        const auto minus = flatten_forces(force::evaluate_spatial_force(
            model, displaced(current, basis, -step)));
        for (std::size_t row = 0; row < dof_count; ++row) {
            const auto numeric = (plus[row] - minus[row]) / (2.0 * step);
            MLS_REQUIRE(close(
                numeric, tangent.force_jacobian_n_per_m(row, column),
                3.0e-9, 3.0e-10));
        }
    }
}

MLS_TEST("conservative force is objective covariant label free and dimensioned") {
    const auto reference = tetrahedron();
    const auto relations = k4();
    const auto model = local_model(reference, relations, 2.0);
    const auto current = transform(reference, general_deformation());
    const auto baseline = force::evaluate_spatial_force(model, current);
    const auto rotation = rational_rotation();
    const auto rotated = transform(
        current, rotation, {7.0 / 13.0, -5.0 / 11.0, 3.0 / 17.0});
    const auto rotated_force = force::evaluate_spatial_force(model, rotated);
    MLS_REQUIRE(close(rotated_force.energy_j, baseline.energy_j, 3.0e-13));
    for (std::size_t index = 0; index < baseline.packet_forces.size(); ++index) {
        MLS_REQUIRE(close(
            rotated_force.packet_forces[index].force_n,
            mls::experimental::multiply(
                rotation, baseline.packet_forces[index].force_n),
            5.0e-13));
    }

    constexpr auto scale = 2.0;
    const auto scaled_reference =
        transform(reference, scale * Matrix3d::identity());
    const auto scaled_current = transform(current, scale * Matrix3d::identity());
    const auto scaled_model = local_model(scaled_reference, relations, 2.0);
    const auto scaled_force =
        force::evaluate_spatial_force(scaled_model, scaled_current);
    MLS_REQUIRE(close(
        scaled_force.energy_j, scale * scale * baseline.energy_j, 3.0e-13));
    for (std::size_t index = 0; index < baseline.packet_forces.size(); ++index) {
        MLS_REQUIRE(close(
            scaled_force.packet_forces[index].force_n,
            scale * baseline.packet_forces[index].force_n, 5.0e-13));
    }
    const auto baseline_tangent = force::evaluate_spatial_tangent(model, current);
    const auto scaled_tangent =
        force::evaluate_spatial_tangent(scaled_model, scaled_current);
    for (std::size_t row = 0;
         row < baseline_tangent.total_energy_hessian_n_per_m.row_count(); ++row) {
        for (std::size_t column = 0;
             column < baseline_tangent.total_energy_hessian_n_per_m.column_count();
             ++column) {
            MLS_REQUIRE(close(
                scaled_tangent.total_energy_hessian_n_per_m(row, column),
                baseline_tangent.total_energy_hessian_n_per_m(row, column),
                8.0e-13));
        }
    }

    // Packet and relation order/endpoints are presentation only.
    auto permuted_current = current;
    std::ranges::reverse(permuted_current);
    const auto permuted_force =
        force::evaluate_spatial_force(model, permuted_current);
    MLS_REQUIRE_EQ(permuted_force.packet_forces, baseline.packet_forces);
    MLS_REQUIRE_EQ(
        permuted_force.relation_coordinates, baseline.relation_coordinates);

    std::vector<std::size_t> reverse_coordinates(relations.size());
    for (std::size_t index = 0; index < relations.size(); ++index) {
        reverse_coordinates[index] = relations.size() - 1U - index;
    }
    auto relation_permuted = force::permute_relation_coordinates(
        model, reverse_coordinates);
    for (auto& relation : relation_permuted.parent_operator.relations) {
        std::swap(relation.first_id, relation.second_id);
    }
    for (auto& relation : relation_permuted.force_operator.relations) {
        std::swap(relation.first_id, relation.second_id);
    }
    const auto coordinate_force =
        force::evaluate_spatial_force(relation_permuted, current);
    MLS_REQUIRE_EQ(
        coordinate_force.packet_forces.size(), baseline.packet_forces.size());
    for (std::size_t index = 0;
         index < coordinate_force.packet_forces.size(); ++index) {
        MLS_REQUIRE_EQ(
            coordinate_force.packet_forces[index].packet_id,
            baseline.packet_forces[index].packet_id);
        MLS_REQUIRE(close(
            coordinate_force.packet_forces[index].force_n,
            baseline.packet_forces[index].force_n, 3.0e-13));
    }
    for (std::size_t new_index = 0; new_index < relations.size(); ++new_index) {
        const auto old_index = reverse_coordinates[new_index];
        MLS_REQUIRE(close(
            coordinate_force.relation_coordinates[new_index].conjugate_force_n,
            baseline.relation_coordinates[old_index].conjugate_force_n,
            3.0e-13));
    }

    const std::map<std::uint64_t, std::uint64_t> renaming{
        {1, 40}, {2, 10}, {3, 30}, {4, 20}};
    auto renamed_reference = reference;
    auto renamed_current = current;
    for (auto& packet : renamed_reference) {
        packet.id = renaming.at(packet.id);
    }
    for (auto& packet : renamed_current) {
        packet.id = renaming.at(packet.id);
    }
    auto renamed_weighted = weighted(relations);
    std::ranges::reverse(renamed_weighted);
    for (auto& entry : renamed_weighted) {
        entry.relation.first_id = renaming.at(entry.relation.first_id);
        entry.relation.second_id = renaming.at(entry.relation.second_id);
        std::swap(entry.relation.first_id, entry.relation.second_id);
    }
    const auto renamed_model = force::freeze_symmetric_force_operator(
        constitutive::build_local_collective_energy(
            renamed_reference, renamed_weighted,
            {.dilatational_coefficient_j_per_m2 = 3.0 * 2.0 / 20.0,
             .deviatoric_coefficient_j_per_m2 = 0.25}));
    const auto renamed_force =
        force::evaluate_spatial_force(renamed_model, renamed_current);
    MLS_REQUIRE(close(renamed_force.energy_j, baseline.energy_j, 3.0e-13));
    std::map<std::uint64_t, Vec3d> semantic;
    for (const auto& packet : renamed_force.packet_forces) {
        const auto original = std::ranges::find_if(
            renaming, [&](const auto& entry) { return entry.second == packet.packet_id; });
        MLS_REQUIRE(original != renaming.end());
        semantic.emplace(original->first, packet.force_n);
    }
    for (const auto& packet : baseline.packet_forces) {
        MLS_REQUIRE(close(semantic.at(packet.packet_id), packet.force_n, 3.0e-13));
    }
}

MLS_TEST("conservative collapse path stays explicit and coincidence fails closed") {
    const auto reference = tetrahedron();
    const auto relations = k4();
    const auto model = local_model(reference, relations, 10.0);
    double previous_geometric = 0.0;
    for (const auto exponent : std::array{0, -4, -8, -12, -16, -20, -24, -28, -32}) {
        auto compressed = reference;
        const auto ratio = std::ldexp(1.0, exponent);
        compressed[1].position_m = {ratio, 0.0, 0.0};
        const auto evaluated = force::evaluate_spatial_force(model, compressed);
        MLS_REQUIRE_EQ(evaluated.status, force::ForceDomainStatus::evaluated);
        MLS_REQUIRE_EQ(evaluated.relation_coordinates.front().current_length_m,
                       ratio);
        const auto tangent = force::evaluate_spatial_tangent(model, compressed);
        MLS_REQUIRE_EQ(tangent.status, force::ForceDomainStatus::evaluated);
        double geometric = 0.0;
        for (const auto value :
             tangent.geometric_energy_hessian_n_per_m.entries()) {
            MLS_REQUIRE(std::isfinite(value));
            geometric = std::max(geometric, std::abs(value));
        }
        if (exponent < 0) {
            MLS_REQUIRE(geometric >= previous_geometric);
        }
        previous_geometric = geometric;
        auto adjacent = compressed;
        adjacent[1].position_m.x = std::nextafter(
            ratio, std::numeric_limits<double>::infinity());
        const auto adjacent_evaluated =
            force::evaluate_spatial_force(model, adjacent);
        MLS_REQUIRE(adjacent_evaluated.relation_coordinates.front().current_length_m !=
                    evaluated.relation_coordinates.front().current_length_m);
    }

    auto coincident = reference;
    coincident[1].position_m = coincident[0].position_m;
    const auto failure = force::evaluate_spatial_force(model, coincident);
    MLS_REQUIRE_EQ(
        failure.status, force::ForceDomainStatus::coincident_relation);
    MLS_REQUIRE_EQ(failure.failed_relation_index, std::size_t{0});
    MLS_REQUIRE_EQ(failure.failed_relation, (BondRelation{1, 2}));
    MLS_REQUIRE(std::isnan(failure.energy_j));
    MLS_REQUIRE(failure.relation_coordinates.empty());
    MLS_REQUIRE(failure.packet_forces.empty());
    MLS_REQUIRE_EQ(failure.current_rigidity.matrix.row_count(), std::size_t{0});
    const auto tangent_failure =
        force::evaluate_spatial_tangent(model, coincident);
    MLS_REQUIRE_EQ(
        tangent_failure.status, force::ForceDomainStatus::coincident_relation);
    MLS_REQUIRE_EQ(
        tangent_failure.total_energy_hessian_n_per_m.row_count(),
        std::size_t{0});
    MLS_REQUIRE_THROWS(
        std::domain_error,
        force::evaluate_continuous_identities(failure, coincident, {}));
}

MLS_TEST("conservative force does not fabricate the missing edge mechanism") {
    const auto reference = tetrahedron();
    auto relations = k4();
    relations.pop_back();
    const auto model = local_model(reference, relations, 2.0);
    const auto rigidity = observation::build_bond_rigidity_operator(
        reference, relations);
    const auto diagnosed = observation::diagnose_mechanical_observability(
        rigidity.linearized, reference);
    MLS_REQUIRE_EQ(diagnosed.nonrigid_nullity, std::size_t{1});
    std::vector<double> mechanism(3U * reference.size(), 0.0);
    for (std::size_t row = 0; row < mechanism.size(); ++row) {
        mechanism[row] = diagnosed.nonrigid_nullspace_basis(row, 0U);
    }
    double previous = std::numeric_limits<double>::infinity();
    for (const auto exponent : std::array{-8, -12, -16, -20}) {
        const auto epsilon = std::ldexp(1.0, exponent);
        const auto current = displaced(reference, mechanism, epsilon);
        const auto evaluated = force::evaluate_spatial_force(model, current);
        const auto values = flatten_forces(evaluated);
        double scaled = 0.0;
        for (const auto value : values) {
            scaled = std::max(scaled, std::abs(value) / epsilon);
        }
        MLS_REQUIRE(scaled < previous);
        previous = scaled;
    }
}

MLS_TEST("conservative force rejects malformed frozen coordinate data") {
    const auto reference = tetrahedron();
    const auto relations = k4();
    auto model = local_model(reference, relations);
    model.force_operator.h_j_per_m2(0U, 1U) += 1.0;
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        force::evaluate_spatial_force(model, reference));
    model = local_model(reference, relations);
    model.force_operator.h_j_per_m2(0U, 1U) += 1.0;
    model.force_operator.h_j_per_m2(1U, 0U) += 1.0;
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        force::evaluate_spatial_force(model, reference));
    model = local_model(reference, relations);
    model.force_operator.relations[1] = model.force_operator.relations[0];
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        force::evaluate_spatial_force(model, reference));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        force::permute_relation_coordinates(
            local_model(reference, relations),
            std::array<std::size_t, 6>{0, 1, 2, 3, 4, 4}));
    model = local_model(reference, relations);
    model.force_operator.reference_lengths_m[0] = 0.0;
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        force::evaluate_spatial_force(model, reference));
    model = local_model(reference, relations);
    std::swap(model.parent_operator.relations[0],
              model.parent_operator.relations[1]);
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        force::evaluate_spatial_force(model, reference));
    model = local_model(reference, relations);
    model.parent_operator.locality_radius_m *= 2.0;
    model.force_operator.locality_radius_m *= 2.0;
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        force::evaluate_spatial_force(model, reference));
    model = local_model(reference, relations);
    model.parent_operator.local_contributions[0]
        .maximum_incident_length_m *= 2.0;
    model.force_operator.local_contributions[0]
        .maximum_incident_length_m *= 2.0;
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        force::evaluate_spatial_force(model, reference));
}
