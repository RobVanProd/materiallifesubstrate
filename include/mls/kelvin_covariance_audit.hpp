#pragma once

#include "mls/mechanical_observability_lab.hpp"

#include <cstddef>
#include <span>
#include <vector>

namespace mls::experimental::kelvin_covariance_audit {

namespace observation = mechanical_observability;

// Orthonormal Kelvin map in the frozen order
// xx, yy, zz, sqrt(2)xy, sqrt(2)xz, sqrt(2)yz.  The returned 6x6 matrix K
// satisfies kelvin(Q E Q^T) = K kelvin(E).
[[nodiscard]] observation::DenseMatrix kelvin_rotation(
    const Matrix3d& proper_rotation);

// Geometry-only similarity used by this read-only audit.  Position becomes
// s*Q*x+t, support becomes s*H, and the operator input coordinates transform
// as v'=Q*v (no physical velocity scaling is hidden in the geometry map).
[[nodiscard]] std::vector<observation::MechanicalPacket>
transform_packet_geometry(
    std::span<const observation::MechanicalPacket> packets,
    const Matrix3d& proper_rotation, Vec3d translation_m, double scale);

// Constructs (1/s) K_N R T_N^T directly from the raw base operator.
[[nodiscard]] observation::DenseMatrix expected_transformed_operator(
    const observation::DenseMatrix& base,
    const Matrix3d& proper_rotation, double scale);

// One rotationally invariant scalar per complete six-row packet block.  This
// is a diagnostic coordinate map only; it is not a candidate or physical law.
struct BlockNormalization final {
    observation::DenseMatrix normalized{};
    std::vector<double> block_norms{};
    bool complete{false};
    std::size_t first_invalid_block{0};
};

[[nodiscard]] BlockNormalization normalize_kelvin_blocks(
    const observation::DenseMatrix& matrix);

[[nodiscard]] double normalized_frobenius_difference(
    const observation::DenseMatrix& actual,
    const observation::DenseMatrix& reference);

// Deterministic direct one-sided-Jacobi diagnostic spectrum, descending and
// including the complete min(rows,columns) tail.  It does not form normal
// equations, set a rank, or discard a mode; nonfinite input/nonconvergence
// fails closed.
[[nodiscard]] std::vector<double> singular_values(
    const observation::DenseMatrix& matrix);

[[nodiscard]] double normalized_spectrum_difference(
    std::span<const double> actual, std::span<const double> reference,
    double actual_scale = 1.0);

struct OrthogonalityDiagnostics final {
    double q_residual{0.0};
    double determinant_residual{0.0};
    double kelvin_residual{0.0};
};

[[nodiscard]] OrthogonalityDiagnostics diagnose_orthogonality(
    const Matrix3d& proper_rotation,
    const observation::DenseMatrix& kelvin);

struct RowNormalizationCounterexample final {
    double raw_spectrum_delta{0.0};
    double row_normalized_spectrum_delta{0.0};
    double raw_transform_residual{0.0};
    bool row_normalizations_complete{false};
};

// Uses an actual 3-D Kelvin rotation and an anisotropic diagonal raw operator.
// Orthogonal output mixing preserves its raw spectrum but independent scalar
// row normalization generally does not.
[[nodiscard]] RowNormalizationCounterexample
kelvin_row_normalization_counterexample(const Matrix3d& proper_rotation);

} // namespace mls::experimental::kelvin_covariance_audit
