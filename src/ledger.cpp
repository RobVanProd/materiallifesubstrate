#include "mls/ledger.hpp"

#include <set>
#include <stdexcept>

namespace mls {
namespace {

void require_nonnegative_boundary_amount(const ExtensiveTotals& amount) {
    if (!is_nonnegative(amount.mass) || !is_nonnegative(amount.structural_energy) ||
        !is_nonnegative(amount.stored_energy) || !is_nonnegative(amount.thermal_energy) ||
        !is_nonnegative(amount.kinetic_energy)) {
        throw std::invalid_argument("boundary ingress/egress amounts must be nonnegative");
    }
    for (const auto& [element, count] : amount.elements.amounts()) {
        static_cast<void>(element);
        if (count < 0) {
            throw std::invalid_argument("boundary element amounts must be nonnegative");
        }
    }
}

} // namespace

void BoundaryBalance::clear() noexcept {
    element_net.clear();
    mass_net = Mass{};
    energy_net = Energy{};
    momentum_net = Momentum3{};
}

ConservationLedger::ConservationLedger(ExtensiveTotals baseline)
    : baseline_(std::move(baseline)) {}

void ConservationLedger::establish_baseline(ExtensiveTotals baseline) {
    baseline_ = std::move(baseline);
    boundary_.clear();
}

void ConservationLedger::record_elements(const ElementInventory& inventory, Scalar sign) {
    if (sign != -1 && sign != 1) {
        throw std::invalid_argument("boundary element sign must be -1 or +1");
    }
    auto updated = boundary_.element_net;
    for (const auto& [element, count] : inventory.amounts()) {
        const auto delta = detail::checked_multiply(count, sign);
        updated[element] = detail::checked_add(updated[element], delta);
        if (updated[element] == 0) {
            updated.erase(element);
        }
    }
    boundary_.element_net.swap(updated);
}

void ConservationLedger::record_boundary_ingress(const ExtensiveTotals& amount) {
    require_nonnegative_boundary_amount(amount);
    auto updated_mass = boundary_.mass_net + amount.mass;
    auto updated_energy = boundary_.energy_net + amount.total_energy();
    auto updated_momentum = boundary_.momentum_net + amount.momentum;
    record_elements(amount.elements, 1);
    boundary_.mass_net = updated_mass;
    boundary_.energy_net = updated_energy;
    boundary_.momentum_net = updated_momentum;
}

void ConservationLedger::record_boundary_egress(const ExtensiveTotals& amount) {
    require_nonnegative_boundary_amount(amount);
    auto updated_mass = boundary_.mass_net - amount.mass;
    auto updated_energy = boundary_.energy_net - amount.total_energy();
    auto updated_momentum = boundary_.momentum_net - amount.momentum;
    record_elements(amount.elements, -1);
    boundary_.mass_net = updated_mass;
    boundary_.energy_net = updated_energy;
    boundary_.momentum_net = updated_momentum;
}

void ConservationLedger::record_boundary_energy(Energy signed_amount) {
    boundary_.energy_net += signed_amount;
}

void ConservationLedger::record_boundary_momentum(Momentum3 signed_amount) {
    boundary_.momentum_net += signed_amount;
}

ConservationReport ConservationLedger::audit(const ExtensiveTotals& current) const {
    ConservationReport report;
    std::set<ElementId> element_ids;
    for (const auto& [element, count] : baseline_.elements.amounts()) {
        static_cast<void>(count);
        element_ids.insert(element);
    }
    for (const auto& [element, count] : boundary_.element_net) {
        static_cast<void>(count);
        element_ids.insert(element);
    }
    for (const auto& [element, count] : current.elements.amounts()) {
        static_cast<void>(count);
        element_ids.insert(element);
    }
    for (const auto element : element_ids) {
        const auto expected = detail::checked_add(
            baseline_.elements.amount(element),
            boundary_.element_net.contains(element) ? boundary_.element_net.at(element) : 0);
        const auto error = detail::checked_subtract(current.elements.amount(element), expected);
        if (error != 0) {
            report.element_error.emplace(element, error);
        }
    }
    report.elements_conserved = report.element_error.empty();

    const auto expected_mass = baseline_.mass + boundary_.mass_net;
    report.mass_error = current.mass - expected_mass;
    report.mass_conserved = report.mass_error == Mass{};

    const auto expected_energy = baseline_.total_energy() + boundary_.energy_net;
    report.energy_error = current.total_energy() - expected_energy;
    report.energy_conserved = report.energy_error == Energy{};

    const auto expected_momentum = baseline_.momentum + boundary_.momentum_net;
    report.momentum_error = current.momentum - expected_momentum;
    report.momentum_conserved = report.momentum_error == Momentum3{};
    return report;
}

} // namespace mls
