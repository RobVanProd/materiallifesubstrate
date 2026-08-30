#pragma once

#include "mls/mechanical_observability_lab.hpp"

#include <cstddef>
#include <cstdint>
#include <span>
#include <string_view>
#include <vector>

namespace mls::experimental::relational_observability_confirmation {

namespace observation = mechanical_observability;

// Frozen binary64 gates from the Relational Observability Confirmation
// preregistration.  The central-distance rows are always analyzed raw.
struct RawSpectrumPolicy final {
    double rank_roundoff_factor{512.0};
    double ambiguity_factor{8.0};
    double residual_factor{4096.0};
    double similarity_factor{16384.0};
    double row_norm_factor{64.0};
    double minimum_mu_retention{1.0 / 1024.0};
};

enum class SingularClassification : std::uint8_t {
    accepted_nonzero,
    ambiguous,
    resolved_zero,
};

[[nodiscard]] std::string_view classification_name(
    SingularClassification classification) noexcept;

struct SingularEntry final {
    std::size_t index{0};
    double value{0.0};
    SingularClassification classification{
        SingularClassification::resolved_zero};
};

struct NullModeDiagnostic final {
    std::size_t index{0};
    double normalized_operator_residual{0.0};
    double rigid_projection_norm{0.0};
    double rigid_orthogonality_residual{0.0};
    bool accepted{false};
};

struct ModularRankDiagnostic final {
    std::vector<std::uint32_t> primes{};
    std::vector<std::size_t> ranks{};
    bool unanimous{false};
    std::size_t rank{0};
};

struct RawObservabilityDiagnostic final {
    observation::RankStatus status{observation::RankStatus::empty};
    std::size_t row_count{0};
    std::size_t column_count{0};
    std::size_t dimension_scale{0};
    std::size_t cpqr_rank{0};
    std::size_t svd_rank{0};
    std::size_t modular_rank_value{0};
    std::size_t nullity{0};
    std::size_t realized_rigid_rank{0};
    std::size_t nonrigid_nullity{0};
    double cpqr_threshold{0.0};
    double svd_threshold{0.0};
    double residual_tolerance{0.0};
    double row_norm_tolerance{0.0};
    double maximum_row_norm_relative_error{0.0};
    double normalized_rigid_residual{0.0};
    double normalized_null_residual{0.0};
    double normalized_nonrigid_residual{0.0};
    double rigid_orthogonality_residual{0.0};
    double sigma_min_nonzero{0.0};
    double sigma_max{0.0};
    double mu{0.0};
    double nonzero_threshold_separation{0.0};
    double null_threshold_separation{0.0};
    bool row_norms_pass{false};
    bool direct_svd_unambiguous{false};
    bool rank_paths_agree{false};
    bool rigid_subspace_in_kernel{false};
    bool kernel_equals_rigid_subspace{false};
    bool all_null_modes_accepted{false};
    bool nonrigid_basis_complete{false};
    std::vector<double> row_norms{};
    std::vector<SingularEntry> spectrum{};
    std::vector<NullModeDiagnostic> null_modes{};
    observation::RankDiagnostics cpqr{};
    observation::RigidMotionSubspace rigid{};
    observation::DenseMatrix nonrigid_nullspace_basis{};
    ModularRankDiagnostic modular_rank{};
};

// Three finite-field rank diagnostics for the dyadic-coordinate,
// unnormalised central-distance rigidity matrix.  A modular rank is a lower
// bound on rational rank, not by itself a certificate of rational rank.
// Agreement across the three frozen primes is an implementation gate; the
// independent Python reference supplies the exact/reference decision.
[[nodiscard]] ModularRankDiagnostic three_prime_modular_rigidity_rank(
    std::span<const observation::MechanicalPacket> packets,
    std::span<const observation::BondRelation> relations);

// Candidate-C-only analysis.  This calls the inherited bond operator, the
// inherited raw CPQR, and the audited direct rectangular Jacobi SVD.  It never
// calls normalize_operator_rows or diagnose_mechanical_observability.
[[nodiscard]] RawObservabilityDiagnostic analyze_raw_central_rigidity(
    std::span<const observation::MechanicalPacket> packets,
    std::span<const observation::BondRelation> relations,
    const RawSpectrumPolicy& policy = {});

[[nodiscard]] double normalized_spectrum_difference(
    std::span<const SingularEntry> actual,
    std::span<const SingularEntry> reference);

} // namespace mls::experimental::relational_observability_confirmation
