#include "test_harness.hpp"

#include "mls/kelvin_covariance_audit.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace {

namespace audit = mls::experimental::kelvin_covariance_audit;
namespace observation = mls::experimental::mechanical_observability;
using mls::experimental::Matrix3d;
using mls::experimental::Vec3d;
using observation::MechanicalPacket;

[[nodiscard]] Matrix3d rational_rotation() {
    Matrix3d result{};
    result.value = {{{1.0 / 9.0, 8.0 / 9.0, 4.0 / 9.0},
                     {8.0 / 9.0, 1.0 / 9.0, -4.0 / 9.0},
                     {-4.0 / 9.0, 4.0 / 9.0, -7.0 / 9.0}}};
    return result;
}

[[nodiscard]] std::vector<MechanicalPacket> cube() {
    std::vector<MechanicalPacket> result;
    std::uint64_t id = 1;
    for (int z = 0; z < 2; ++z) {
        for (int y = 0; y < 2; ++y) {
            for (int x = 0; x < 2; ++x) {
                result.push_back({id++, 1,
                    {static_cast<double>(x), static_cast<double>(y),
                     static_cast<double>(z)}, {}});
            }
        }
    }
    return result;
}

[[nodiscard]] double tolerance(
    const observation::DenseMatrix& matrix, const double factor) {
    return factor * static_cast<double>(std::max({std::size_t{6},
        matrix.row_count(), matrix.column_count()})) *
        std::numeric_limits<double>::epsilon();
}

} // namespace

MLS_TEST("Kelvin raw corrected-gradient operator obeys similarity law") {
    const auto rotation = rational_rotation();
    const auto kelvin = audit::kelvin_rotation(rotation);
    const auto orthogonality =
        audit::diagnose_orthogonality(rotation, kelvin);
    MLS_REQUIRE(orthogonality.q_residual <=
        8192.0 * 6.0 * std::numeric_limits<double>::epsilon());
    MLS_REQUIRE(orthogonality.determinant_residual <=
        8192.0 * 6.0 * std::numeric_limits<double>::epsilon());
    MLS_REQUIRE(orthogonality.kelvin_residual <=
        16384.0 * 6.0 * std::numeric_limits<double>::epsilon());

    const auto packets = cube();
    constexpr double support = 2.0;
    const auto base = observation::build_corrected_local_gradient(
        packets, {.support_radius_m = support});
    MLS_REQUIRE_EQ(base.status, observation::OperatorBuildStatus::built);

    constexpr double scale = 0.5;
    const auto transformed_packets = audit::transform_packet_geometry(
        packets, rotation, {0.37, -0.29, 0.41}, scale);
    const auto transformed = observation::build_corrected_local_gradient(
        transformed_packets, {.support_radius_m = scale * support});
    MLS_REQUIRE_EQ(
        transformed.status, observation::OperatorBuildStatus::built);
    const auto expected = audit::expected_transformed_operator(
        base.symmetric_gradient.matrix, rotation, scale);
    MLS_REQUIRE(audit::normalized_frobenius_difference(
        transformed.symmetric_gradient.matrix, expected) <=
        tolerance(expected, 32768.0));

    const auto base_spectrum =
        audit::singular_values(base.symmetric_gradient.matrix);
    const auto transformed_spectrum =
        audit::singular_values(transformed.symmetric_gradient.matrix);
    MLS_REQUIRE(audit::normalized_spectrum_difference(
        transformed_spectrum, base_spectrum, scale) <=
        tolerance(expected, 65536.0));
}

MLS_TEST("Kelvin block scalar is covariant but scalar row scaling is not") {
    const auto rotation = rational_rotation();
    const auto packets = cube();
    constexpr double support = 2.0;
    constexpr double scale = 2.0;
    const auto base = observation::build_corrected_local_gradient(
        packets, {.support_radius_m = support});
    const auto transformed_packets = audit::transform_packet_geometry(
        packets, rotation, {0.37, -0.29, 0.41}, scale);
    const auto transformed = observation::build_corrected_local_gradient(
        transformed_packets, {.support_radius_m = scale * support});
    MLS_REQUIRE_EQ(base.status, observation::OperatorBuildStatus::built);
    MLS_REQUIRE_EQ(
        transformed.status, observation::OperatorBuildStatus::built);

    const auto base_blocks =
        audit::normalize_kelvin_blocks(base.symmetric_gradient.matrix);
    const auto transformed_blocks =
        audit::normalize_kelvin_blocks(transformed.symmetric_gradient.matrix);
    MLS_REQUIRE(base_blocks.complete);
    MLS_REQUIRE(transformed_blocks.complete);
    const auto expected = audit::expected_transformed_operator(
        base_blocks.normalized, rotation, 1.0);
    MLS_REQUIRE(audit::normalized_frobenius_difference(
        transformed_blocks.normalized, expected) <=
        tolerance(expected, 65536.0));

    const auto counterexample =
        audit::kelvin_row_normalization_counterexample(rotation);
    MLS_REQUIRE(counterexample.row_normalizations_complete);
    MLS_REQUIRE(counterexample.raw_transform_residual == 0.0);
    MLS_REQUIRE(counterexample.raw_spectrum_delta <=
        65536.0 * 6.0 * std::numeric_limits<double>::epsilon());
    MLS_REQUIRE(counterexample.row_normalized_spectrum_delta > 1.0e-3);
    MLS_REQUIRE(counterexample.row_normalized_spectrum_delta >
        1000.0 * 65536.0 * 6.0 *
            std::numeric_limits<double>::epsilon());
}

MLS_TEST("Kelvin covariance audit rejects invalid transformations and blocks") {
    auto reflection = Matrix3d::identity();
    reflection.value[0][0] = -1.0;
    MLS_REQUIRE_THROWS(
        std::invalid_argument, audit::kelvin_rotation(reflection));
    MLS_REQUIRE_THROWS(std::invalid_argument,
        audit::transform_packet_geometry(
            cube(), Matrix3d::identity(), {}, 0.0));

    observation::DenseMatrix invalid_rows(5U, 3U);
    MLS_REQUIRE_THROWS(std::invalid_argument,
        audit::normalize_kelvin_blocks(invalid_rows));

    observation::DenseMatrix zero_block(6U, 3U);
    const auto normalized = audit::normalize_kelvin_blocks(zero_block);
    MLS_REQUIRE(!normalized.complete);
    MLS_REQUIRE_EQ(normalized.first_invalid_block, std::size_t{0});
}
