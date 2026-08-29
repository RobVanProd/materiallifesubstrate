#pragma once

#include "mls/transfer_lab.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <string_view>
#include <vector>

namespace mls::experimental::mechanical_observability {

// This lab is read-only kinematics. A packet has no constitutive type, force,
// stiffness, stress, or persistent numerical mode.
struct MechanicalPacket final {
    std::uint64_t id{0};
    // Preserved exactly in the laboratory checkpoint. Kinematic operators do
    // not use mass and therefore cannot turn it into a hidden weighting law.
    std::int64_t mass_quanta{0};
    Vec3d position_m{};
    Vec3d velocity_m_per_s{};

    [[nodiscard]] constexpr bool operator==(
        const MechanicalPacket&) const noexcept = default;
};

// A generic physical relation between two stable packet identities. Endpoint
// order is canonical (first_id < second_id); it is not a spring or force law.
struct BondRelation final {
    std::uint64_t first_id{0};
    std::uint64_t second_id{0};

    [[nodiscard]] constexpr bool operator==(
        const BondRelation&) const noexcept = default;
};

// A generic objective center-anchored four-packet geometric relation. The
// sorted non-center IDs fix the sign convention of the oriented triple volume.
struct VolumeRelation final {
    std::uint64_t center_id{0};
    // Canonical orientation: these IDs are strictly increasing and all differ
    // from center_id. The center itself need not be the smallest ID.
    std::array<std::uint64_t, 3> other_ids{};

    [[nodiscard]] constexpr bool operator==(
        const VolumeRelation&) const noexcept = default;
};

struct MechanicalObservabilityState final {
    double support_radius_m{1.0};
    std::vector<MechanicalPacket> packets{};
    std::vector<BondRelation> bonds{};
    std::vector<VolumeRelation> volumes{};

    [[nodiscard]] constexpr bool operator==(
        const MechanicalObservabilityState&) const noexcept = default;
};

inline constexpr std::uint32_t mechanical_observability_checkpoint_version = 1;

// Canonical little-endian input-only checkpoint. Lookup grids, moments,
// operators, factorizations, and null modes are all deliberately excluded.
[[nodiscard]] std::vector<std::uint8_t> serialize_mechanical_observability_state(
    const MechanicalObservabilityState& state);

[[nodiscard]] MechanicalObservabilityState
deserialize_mechanical_observability_state(
    std::span<const std::uint8_t> checkpoint);

class DenseMatrix final {
public:
    DenseMatrix() = default;
    DenseMatrix(std::size_t row_count, std::size_t column_count);

    [[nodiscard]] std::size_t row_count() const noexcept { return row_count_; }
    [[nodiscard]] std::size_t column_count() const noexcept {
        return column_count_;
    }
    [[nodiscard]] std::span<const double> entries() const noexcept {
        return entries_;
    }
    [[nodiscard]] double operator()(
        std::size_t row, std::size_t column) const;
    double& operator()(std::size_t row, std::size_t column);

    [[nodiscard]] bool operator==(const DenseMatrix&) const noexcept = default;

private:
    std::size_t row_count_{0};
    std::size_t column_count_{0};
    std::vector<double> entries_{};
};

enum class ObservableKind : std::uint8_t {
    corrected_local_symmetric_gradient,
    central_bond_length_rate,
    oriented_volume_rate,
    enriched_bond_and_volume,
};

[[nodiscard]] std::string_view observable_name(ObservableKind kind) noexcept;

struct LinearizedOperator final {
    DenseMatrix matrix{};
    // Defines the three-column blocks of matrix, independent of input order.
    std::vector<std::uint64_t> packet_ids{};
    ObservableKind kind{ObservableKind::corrected_local_symmetric_gradient};
};

enum class OperatorBuildStatus : std::uint8_t {
    built,
    empty,
    singular_local_moment,
    ill_conditioned_local_moment,
    numerical_failure,
};

[[nodiscard]] std::string_view status_name(OperatorBuildStatus status) noexcept;

struct CorrectedGradientPolicy final {
    double support_radius_m{1.0};
    double condition_number_max{1.0e10};
};

struct LocalMomentDiagnostic final {
    std::uint64_t packet_id{0};
    std::size_t neighbor_count{0};
    Matrix3d moment_m2{};
    double smallest_eigenvalue_m2{0.0};
    double largest_eigenvalue_m2{0.0};
    double condition_number{0.0};
    // The inverse is accepted only when this independently evaluated product
    // residual satisfies the frozen 4096*3*epsilon64 gate.
    double inverse_residual_normalized{
        std::numeric_limits<double>::infinity()};
    double inverse_residual_tolerance{
        4096.0 * 3.0 * std::numeric_limits<double>::epsilon()};
    bool inverse_accepted{false};
    OperatorBuildStatus status{OperatorBuildStatus::empty};
};

struct CorrectedGradientOperator final {
    OperatorBuildStatus status{OperatorBuildStatus::empty};
    // Six rows per packet: xx, yy, zz, sqrt(2)xy, sqrt(2)xz,
    // sqrt(2)yz. Entries have units m^-1 and output has units s^-1.
    LinearizedOperator symmetric_gradient{};
    // Nine rows per packet in row-major tensor order. This is retained only
    // for the affine-reproduction diagnostic.
    DenseMatrix full_gradient{};
    std::vector<LocalMomentDiagnostic> local_moments{};
};

// First-order corrected local particle gradient. Neighbor eligibility and all
// weights derive only from packet positions and the dimensioned support
// radius. No grid state participates.
[[nodiscard]] CorrectedGradientOperator build_corrected_local_gradient(
    std::span<const MechanicalPacket> packets,
    const CorrectedGradientPolicy& policy);

struct BondOperator final {
    LinearizedOperator linearized{};
    std::vector<BondRelation> relations{};
    std::vector<double> lengths_m{};
};

// The row for edge (i,j) is [-n_ij^T,+n_ij^T], the Jacobian of
// |x_j-x_i|. It is an objective observable, not a constitutive force.
[[nodiscard]] BondOperator build_bond_rigidity_operator(
    std::span<const MechanicalPacket> packets,
    std::span<const BondRelation> relations);

struct VolumeOperator final {
    LinearizedOperator linearized{};
    std::vector<VolumeRelation> relations{};
    std::vector<double> oriented_volumes_m3{};
};

// The observable is det(x_j-x_i,x_k-x_i,x_l-x_i). Its derivative is
// objective under proper rigid motion and introduces no force or penalty.
[[nodiscard]] VolumeOperator build_oriented_volume_operator(
    std::span<const MechanicalPacket> packets,
    std::span<const VolumeRelation> relations);

// Frozen candidate-D topology rule. For every center with at least three
// incident bond neighbors, choose the sorted neighbor triple maximizing the
// registered objective area score, with stable-ID lexicographic ties. A
// center whose maximum score is zero emits no tuple.
[[nodiscard]] std::vector<VolumeRelation> select_oriented_volume_relations(
    std::span<const MechanicalPacket> packets,
    std::span<const BondRelation> bonds);

// Empty volumes are a valid candidate-C state. Every tuple in a nonempty D
// state must equal the selector's canonical choice for its center, with at
// most one tuple per center. This permits explicit registered subsets while
// rejecting arbitrary, multiple-per-center, and nonincident tuples.
void validate_selected_oriented_volume_relations(
    std::span<const MechanicalPacket> packets,
    std::span<const BondRelation> bonds,
    std::span<const VolumeRelation> volumes);

[[nodiscard]] LinearizedOperator combine_relational_operators(
    const BondOperator& bonds, const VolumeOperator& volumes);

// Applies an operator after matching packets by stable ID. The result uses
// matrix row order and the packet input may be arbitrarily permuted.
[[nodiscard]] std::vector<double> apply_operator(
    const LinearizedOperator& linearized,
    std::span<const MechanicalPacket> packets);

// Applies the nine-component corrected-gradient operator and returns one
// row-major tensor per canonical packet ID.
[[nodiscard]] std::vector<Matrix3d> evaluate_full_local_gradients(
    const CorrectedGradientOperator& corrected,
    std::span<const MechanicalPacket> packets);

struct RowNormalization final {
    DenseMatrix normalized{};
    std::vector<double> row_norms{};
    bool complete{false};
    std::size_t first_invalid_row{0};
};

// Nonzero row scaling preserves the exact kernel while making mixed-unit
// relation rows suitable for a numerical rank diagnostic. No row is dropped.
[[nodiscard]] RowNormalization normalize_operator_rows(
    const DenseMatrix& matrix);

struct RankPolicy final {
    std::size_t maximum_rows{4096};
    std::size_t maximum_columns{2048};
    double roundoff_safety_factor{512.0};
    double ambiguity_factor{8.0};
    double residual_safety_factor{4096.0};
};

enum class RankStatus : std::uint8_t {
    analyzed,
    empty,
    size_limit,
    invalid_rows,
    ambiguous,
    numerical_failure,
};

[[nodiscard]] std::string_view status_name(RankStatus status) noexcept;

struct RankDiagnostics final {
    RankStatus status{RankStatus::empty};
    std::size_t row_count{0};
    std::size_t column_count{0};
    std::size_t rank{0};
    std::size_t nullity{0};
    double threshold{0.0};
    double ambiguity_lower{0.0};
    double ambiguity_upper{0.0};
    bool rank_is_certified{false};
    bool basis_complete{false};
    double normalized_null_residual{0.0};
    std::vector<double> accepted_pivot_magnitudes{};
    std::vector<double> diagonal_magnitudes{};
    std::vector<std::size_t> column_permutation{};
    // Columns are a deterministic orthonormal numerical basis of ker(R).
    DenseMatrix nullspace_basis{};
};

[[nodiscard]] RankDiagnostics diagnose_rank_and_nullspace(
    const DenseMatrix& row_normalized_operator,
    const RankPolicy& policy = {});

struct RigidMotionSubspace final {
    std::vector<std::uint64_t> packet_ids{};
    // Raw columns are tx,ty,tz,rx,ry,rz about the packet centroid.
    DenseMatrix generators{};
    DenseMatrix orthonormal_basis{};
    std::size_t rank{0};
};

[[nodiscard]] RigidMotionSubspace build_rigid_motion_subspace(
    std::span<const MechanicalPacket> packets);

struct ObservabilityDiagnostics final {
    RankStatus status{RankStatus::empty};
    RankDiagnostics operator_rank{};
    RigidMotionSubspace rigid{};
    bool rigid_subspace_in_kernel{false};
    double normalized_rigid_residual{0.0};
    std::size_t nonrigid_nullity{0};
    bool kernel_equals_rigid_subspace{false};
    // Resolved kernel directions after removing the rigid projection.
    DenseMatrix nonrigid_nullspace_basis{};
    double normalized_nonrigid_residual{0.0};
    double rigid_orthogonality_residual{0.0};
};

[[nodiscard]] ObservabilityDiagnostics diagnose_mechanical_observability(
    const LinearizedOperator& linearized,
    std::span<const MechanicalPacket> packets,
    const RankPolicy& policy = {});

[[nodiscard]] std::vector<MechanicalPacket> with_affine_velocity(
    std::span<const MechanicalPacket> packets,
    const Matrix3d& gradient_per_s,
    Vec3d intercept_m_per_s);

[[nodiscard]] std::vector<double> expected_affine_bond_rates_m_per_s(
    std::span<const MechanicalPacket> packets,
    std::span<const BondRelation> relations,
    const Matrix3d& gradient_per_s);

[[nodiscard]] std::vector<double> expected_affine_volume_rates_m3_per_s(
    std::span<const MechanicalPacket> packets,
    std::span<const VolumeRelation> relations,
    const Matrix3d& gradient_per_s);

// A read-only similarity transform used for covariance/objectivity tests.
// Q must be a proper rotation and scale must be positive. Position becomes
// scale*Q*x+t and velocity becomes scale*Q*v.
[[nodiscard]] std::vector<MechanicalPacket> similarity_transform_packets(
    std::span<const MechanicalPacket> packets,
    const Matrix3d& proper_rotation,
    Vec3d translation_m,
    double scale);

[[nodiscard]] bool is_proper_rotation(
    const Matrix3d& matrix, double tolerance = 1.0e-12) noexcept;

struct FiniteRelationComparison final {
    double maximum_bond_absolute_error_m{0.0};
    double maximum_bond_relative_error{0.0};
    double maximum_volume_absolute_error_m3{0.0};
    double maximum_volume_relative_error{0.0};
    bool finite{true};
};

// Compares actual lengths and oriented triple volumes. It does not use a
// linearized operator or infer an energy.
[[nodiscard]] FiniteRelationComparison compare_finite_relations(
    std::span<const MechanicalPacket> reference,
    std::span<const MechanicalPacket> transformed,
    std::span<const BondRelation> bonds,
    std::span<const VolumeRelation> volumes);

} // namespace mls::experimental::mechanical_observability
