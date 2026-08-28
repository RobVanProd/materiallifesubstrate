#pragma once

#include "mls/affine_advection_lab.hpp"

#include <cstdint>
#include <span>
#include <vector>

namespace mls::experimental::moving_apic_limit {

// Diagnostic-only intervention applied after the unchanged JST force-free
// G2P transition. It is permanently ineligible for transfer promotion.
//
// `particles` differs from the supplied paper state only in B_m2_per_s. The
// pre/post totals deliberately keep representation quantities separate from
// physical center-particle quantities; neither total is an energy ledger.
struct OracleBIntervention final {
    std::vector<affine_advection::MovingApicParticle> particles{};
    TransferTotals pre_override_totals{};
    TransferTotals post_override_totals{};
    std::int64_t exact_mass_quanta_before{0};
    std::int64_t exact_mass_quanta_after{0};
    double max_relative_B_override{0.0};
    double max_relative_B_constraint_error{0.0};
};

// Copy a completed paper G2P particle state, recompute D_p at each supplied
// new particle position, and replace only
//
//     B_p <- A_exact(t_next) D_p(x_p(t_next)).
//
// This function does not perform P2G, grid evolution, G2P, advection, or an
// analytic-field update. Callers must invoke the sealed Path E transition
// exactly once and supply the already advanced analytic field explicitly.
[[nodiscard]] OracleBIntervention apply_oracle_B_after_G2P(
    std::span<const affine_advection::MovingApicParticle> paper_particles,
    const TransferConfig& config,
    const affine_advection::AffineField& exact_next_field);

} // namespace mls::experimental::moving_apic_limit
