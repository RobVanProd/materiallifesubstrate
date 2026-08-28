#pragma once

#include "mls/sparse_grid.hpp"

#include <map>

namespace mls {

struct BoundaryBalance final {
    std::map<ElementId, ElementCount> element_net{};
    Mass mass_net{};
    Energy energy_net{};
    Momentum3 momentum_net{};
    AngularMomentum3 angular_momentum_net{};

    void clear() noexcept;
    [[nodiscard]] bool operator==(const BoundaryBalance&) const noexcept = default;
};

struct ConservationReport final {
    bool elements_conserved{false};
    bool mass_conserved{false};
    bool energy_conserved{false};
    bool momentum_conserved{false};
    bool angular_momentum_conserved{false};
    std::map<ElementId, ElementCount> element_error{};
    Mass mass_error{};
    Energy energy_error{};
    Momentum3 momentum_error{};
    AngularMomentum3 angular_momentum_error{};

    [[nodiscard]] bool ok() const noexcept {
        return elements_conserved && mass_conserved && energy_conserved && momentum_conserved &&
               angular_momentum_conserved;
    }
};

// One conservation contract covers internal state and every world boundary.
// Signed boundary values use the convention ingress > 0, egress < 0.
class ConservationLedger final {
public:
    ConservationLedger() = default;
    explicit ConservationLedger(ExtensiveTotals baseline);

    void establish_baseline(ExtensiveTotals baseline);
    [[nodiscard]] const ExtensiveTotals& baseline() const noexcept { return baseline_; }
    [[nodiscard]] const BoundaryBalance& boundary() const noexcept { return boundary_; }

    void record_boundary_ingress(const ExtensiveTotals& amount);
    void record_boundary_egress(const ExtensiveTotals& amount);
    void record_boundary_energy(Energy signed_amount);
    // A point boundary impulse changes both linear and orbital angular
    // momentum. Both entries are staged transactionally and use exact checked
    // arithmetic. Future boundary couples require a separate explicit API.
    void record_boundary_point_impulse(Position3 position, Momentum3 signed_amount);

    [[nodiscard]] ConservationReport audit(const ExtensiveTotals& current) const;

private:
    void record_elements(const ElementInventory& inventory, Scalar sign);

    ExtensiveTotals baseline_{};
    BoundaryBalance boundary_{};
};

} // namespace mls
