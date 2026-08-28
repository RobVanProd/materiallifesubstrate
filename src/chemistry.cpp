#include "mls/chemistry.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>
#include <utility>

namespace mls {
namespace {

[[nodiscard]] ElementCount checked_count_multiply(ElementCount lhs, ElementCount rhs) {
    return detail::checked_multiply(lhs, rhs);
}

void validate_nonnegative_count(ElementCount amount, const char* description) {
    if (amount < 0) {
        throw std::invalid_argument(description);
    }
}

template <typename QuantityType>
[[nodiscard]] QuantityType scale_nonnegative(QuantityType value, MoleculeCount factor) {
    validate_nonnegative_count(factor, "negative molecule count");
    return value * factor;
}

[[nodiscard]] std::uint64_t fnv_byte(std::uint64_t hash, std::uint8_t byte) noexcept {
    constexpr std::uint64_t prime = 1099511628211ULL;
    return (hash ^ byte) * prime;
}

template <typename Integer>
[[nodiscard]] std::uint64_t fnv_integer(std::uint64_t hash, Integer value) noexcept {
    using Unsigned = std::make_unsigned_t<Integer>;
    const auto bits = static_cast<Unsigned>(value);
    for (std::size_t index = 0; index < sizeof(Integer); ++index) {
        const auto shift = static_cast<unsigned int>(index * 8U);
        const auto byte = static_cast<std::uint8_t>((bits >> shift) & static_cast<Unsigned>(0xffU));
        hash = fnv_byte(hash, byte);
    }
    return hash;
}

} // namespace

ElementInventory::ElementInventory(
    std::initializer_list<std::pair<const ElementId, ElementCount>> values) {
    for (const auto& [element, count] : values) {
        add(element, count);
    }
}

ElementCount ElementInventory::amount(ElementId element) const noexcept {
    const auto found = amounts_.find(element);
    return found == amounts_.end() ? 0 : found->second;
}

void ElementInventory::add(ElementId element, ElementCount amount_to_add) {
    validate_nonnegative_count(amount_to_add, "cannot add a negative element count");
    if (amount_to_add == 0) {
        return;
    }
    amounts_[element] = detail::checked_add(amount(element), amount_to_add);
}

void ElementInventory::remove(ElementId element, ElementCount amount_to_remove) {
    validate_nonnegative_count(amount_to_remove, "cannot remove a negative element count");
    const auto current = amount(element);
    if (amount_to_remove > current) {
        throw std::domain_error("element inventory would become negative");
    }
    if (amount_to_remove == current) {
        amounts_.erase(element);
    } else {
        amounts_[element] = detail::checked_subtract(current, amount_to_remove);
    }
}

void ElementInventory::add_inventory(const ElementInventory& other) {
    auto updated = *this;
    for (const auto& [element, count] : other.amounts_) {
        updated.add(element, count);
    }
    *this = std::move(updated);
}

void ElementInventory::remove_inventory(const ElementInventory& other) {
    for (const auto& [element, count] : other.amounts_) {
        if (count > amount(element)) {
            throw std::domain_error("element inventory would become negative");
        }
    }
    for (const auto& [element, count] : other.amounts_) {
        remove(element, count);
    }
}

ElementInventory ElementInventory::scaled(ElementCount factor) const {
    validate_nonnegative_count(factor, "cannot scale inventory by a negative count");
    ElementInventory result;
    for (const auto& [element, count] : amounts_) {
        result.add(element, checked_count_multiply(count, factor));
    }
    return result;
}

bool ElementInventory::can_apply(
    const std::map<ElementId, ElementCount>& signed_delta) const noexcept {
    for (const auto& [element, delta] : signed_delta) {
        if (delta < 0) {
            if (delta == std::numeric_limits<ElementCount>::min() || amount(element) < -delta) {
                return false;
            }
        } else if (amount(element) > std::numeric_limits<ElementCount>::max() - delta) {
            return false;
        }
    }
    return true;
}

void ElementInventory::apply(const std::map<ElementId, ElementCount>& signed_delta) {
    if (!can_apply(signed_delta)) {
        throw std::domain_error("element delta is not applicable without underflow or overflow");
    }
    for (const auto& [element, delta] : signed_delta) {
        if (delta < 0) {
            remove(element, -delta);
        } else {
            add(element, delta);
        }
    }
}

CompoundGraph::CompoundGraph(std::vector<ElementId> atoms, std::vector<Bond> bonds)
    : atoms_(std::move(atoms)), bonds_(std::move(bonds)) {
    if (atoms_.empty()) {
        throw std::invalid_argument("a compound graph must contain at least one atom site");
    }
    for (auto& bond : bonds_) {
        if (bond.first >= atoms_.size() || bond.second >= atoms_.size()) {
            throw std::out_of_range("compound bond references a missing atom site");
        }
        if (bond.first == bond.second) {
            throw std::invalid_argument("compound self-bonds are not supported");
        }
        if (bond.order == 0) {
            throw std::invalid_argument("compound bond order must be positive");
        }
        if (bond.second < bond.first) {
            std::swap(bond.first, bond.second);
        }
    }
    std::sort(bonds_.begin(), bonds_.end());
    if (std::adjacent_find(bonds_.begin(), bonds_.end()) != bonds_.end()) {
        throw std::invalid_argument("duplicate compound bond");
    }
}

ElementInventory CompoundGraph::formula() const {
    ElementInventory result;
    for (const auto element : atoms_) {
        result.add(element, 1);
    }
    return result;
}

CompoundId CompoundGraph::structural_hash() const noexcept {
    std::uint64_t hash = 14695981039346656037ULL;
    hash = fnv_integer(hash, static_cast<std::uint64_t>(atoms_.size()));
    for (const auto atom : atoms_) {
        hash = fnv_integer(hash, atom.value);
    }
    hash = fnv_integer(hash, static_cast<std::uint64_t>(bonds_.size()));
    for (const auto& bond : bonds_) {
        hash = fnv_integer(hash, bond.first);
        hash = fnv_integer(hash, bond.second);
        hash = fnv_integer(hash, bond.order);
    }
    return CompoundId{hash};
}

void ElementCatalog::define(ElementId id, ElementProperties properties) {
    if (!is_nonnegative(properties.unit_mass) || properties.unit_mass.raw() == 0) {
        throw std::invalid_argument("element unit mass must be positive");
    }
    if (!is_nonnegative(properties.unit_heat_capacity)) {
        throw std::invalid_argument("element heat capacity cannot be negative");
    }
    if (!is_nonnegative(properties.isolated_energy)) {
        throw std::invalid_argument("element isolated energy cannot be negative");
    }
    const auto [unused, inserted] = elements_.emplace(id, properties);
    static_cast<void>(unused);
    if (!inserted) {
        throw std::invalid_argument("element already defined");
    }
}

bool ElementCatalog::contains(ElementId id) const noexcept {
    return elements_.contains(id);
}

const ElementProperties& ElementCatalog::at(ElementId id) const {
    return elements_.at(id);
}

BondRuleKey ElementCatalog::normalized_bond_key(
    ElementId first, ElementId second, std::uint8_t order) noexcept {
    if (second < first) {
        std::swap(first, second);
    }
    return BondRuleKey{first, second, order};
}

void ElementCatalog::define_bond_energy(
    ElementId first, ElementId second, std::uint8_t order, Energy dissociation_energy) {
    if (!contains(first) || !contains(second)) {
        throw std::invalid_argument("bond rule references an undefined element");
    }
    if (order == 0 || !is_nonnegative(dissociation_energy)) {
        throw std::invalid_argument("bond rule requires positive order and nonnegative energy");
    }
    const auto key = normalized_bond_key(first, second, order);
    const auto [unused, inserted] = bond_energies_.emplace(key, dissociation_energy);
    static_cast<void>(unused);
    if (!inserted) {
        throw std::invalid_argument("bond energy rule already defined");
    }
}

Energy ElementCatalog::bond_energy(
    ElementId first, ElementId second, std::uint8_t order) const {
    const auto found = bond_energies_.find(normalized_bond_key(first, second, order));
    if (found == bond_energies_.end()) {
        throw std::out_of_range("compound uses an undefined bond energy rule");
    }
    return found->second;
}

Mass ElementCatalog::molecule_mass(const CompoundGraph& compound) const {
    Mass result{};
    for (const auto atom : compound.atoms()) {
        result += at(atom).unit_mass;
    }
    return result;
}

HeatCapacity ElementCatalog::molecule_heat_capacity(const CompoundGraph& compound) const {
    HeatCapacity result{};
    for (const auto atom : compound.atoms()) {
        result += at(atom).unit_heat_capacity;
    }
    return result;
}

Energy ElementCatalog::molecule_structural_energy(const CompoundGraph& compound) const {
    Energy isolated{};
    for (const auto atom : compound.atoms()) {
        isolated += at(atom).isolated_energy;
    }
    Energy binding{};
    for (const auto& bond : compound.bonds()) {
        binding += bond_energy(
            compound.atoms().at(bond.first), compound.atoms().at(bond.second), bond.order);
    }
    if (binding > isolated) {
        throw std::domain_error("configured bond energy exceeds isolated structural energy");
    }
    return isolated - binding;
}

CompoundId CompoundRegistry::intern(CompoundGraph compound) {
    const auto id = compound.structural_hash();
    const auto found = compounds_.find(id);
    if (found != compounds_.end()) {
        if (found->second != compound) {
            throw std::runtime_error("compound structural-hash collision");
        }
        return id;
    }
    compounds_.emplace(id, std::move(compound));
    return id;
}

bool CompoundRegistry::contains(CompoundId id) const noexcept {
    return compounds_.contains(id);
}

const CompoundGraph& CompoundRegistry::at(CompoundId id) const {
    return compounds_.at(id);
}

CompoundMixture::CompoundMixture(
    std::initializer_list<std::pair<const CompoundId, MoleculeCount>> values) {
    for (const auto& [compound, count] : values) {
        add(compound, count);
    }
}

MoleculeCount CompoundMixture::amount(CompoundId compound) const noexcept {
    const auto found = amounts_.find(compound);
    return found == amounts_.end() ? 0 : found->second;
}

void CompoundMixture::add(CompoundId compound, MoleculeCount amount_to_add) {
    validate_nonnegative_count(amount_to_add, "cannot add a negative molecule count");
    if (amount_to_add == 0) {
        return;
    }
    amounts_[compound] = detail::checked_add(amount(compound), amount_to_add);
}

void CompoundMixture::remove(CompoundId compound, MoleculeCount amount_to_remove) {
    validate_nonnegative_count(amount_to_remove, "cannot remove a negative molecule count");
    const auto current = amount(compound);
    if (amount_to_remove > current) {
        throw std::domain_error("compound mixture would become negative");
    }
    if (amount_to_remove == current) {
        amounts_.erase(compound);
    } else {
        amounts_[compound] = detail::checked_subtract(current, amount_to_remove);
    }
}

ReactionDefinition::ReactionDefinition(
    std::vector<StoichiometricTerm> reactants,
    std::vector<StoichiometricTerm> products,
    Energy activation_energy_per_extent)
    : reactants_(normalize_terms(reactants)),
      products_(normalize_terms(products)),
      activation_energy_per_extent_(activation_energy_per_extent) {
    if (reactants_.empty() || products_.empty()) {
        throw std::invalid_argument("a reaction requires reactants and products");
    }
    if (!is_nonnegative(activation_energy_per_extent_)) {
        throw std::invalid_argument("reaction activation energy cannot be negative");
    }
}

std::vector<StoichiometricTerm> ReactionDefinition::normalize_terms(
    std::span<const StoichiometricTerm> terms) {
    std::map<CompoundId, MoleculeCount> totals;
    for (const auto& term : terms) {
        if (term.coefficient <= 0) {
            throw std::invalid_argument("stoichiometric coefficients must be positive");
        }
        totals[term.compound] = detail::checked_add(totals[term.compound], term.coefficient);
    }
    std::vector<StoichiometricTerm> normalized;
    normalized.reserve(totals.size());
    for (const auto& [compound, coefficient] : totals) {
        normalized.push_back({compound, coefficient});
    }
    return normalized;
}

std::map<ElementId, ElementCount> ReactionDefinition::element_delta(
    const CompoundRegistry& compounds) const {
    std::map<ElementId, ElementCount> delta;
    const auto accumulate = [&delta, &compounds](
                                const std::vector<StoichiometricTerm>& terms, Scalar sign) {
        for (const auto& term : terms) {
            const auto formula = compounds.at(term.compound).formula();
            for (const auto& [element, count] : formula.amounts()) {
                const auto scaled = detail::checked_multiply(
                    detail::checked_multiply(count, term.coefficient), sign);
                delta[element] = detail::checked_add(delta[element], scaled);
            }
        }
    };
    accumulate(reactants_, -1);
    accumulate(products_, 1);
    for (auto iterator = delta.begin(); iterator != delta.end();) {
        if (iterator->second == 0) {
            iterator = delta.erase(iterator);
        } else {
            ++iterator;
        }
    }
    return delta;
}

bool ReactionDefinition::is_balanced(const CompoundRegistry& compounds) const {
    return element_delta(compounds).empty();
}

MoleculeCount ReactionDefinition::maximum_extent(const CompoundMixture& mixture) const noexcept {
    MoleculeCount result = std::numeric_limits<MoleculeCount>::max();
    for (const auto& term : reactants_) {
        result = std::min(result, mixture.amount(term.compound) / term.coefficient);
    }
    return result;
}

bool ReactionDefinition::can_apply(
    const CompoundMixture& mixture, MoleculeCount extent) const noexcept {
    return extent >= 0 && extent <= maximum_extent(mixture);
}

void ReactionDefinition::apply(CompoundMixture& mixture, MoleculeCount extent) const {
    if (!can_apply(mixture, extent)) {
        throw std::domain_error("reaction extent exceeds available reactants");
    }
    if (extent == 0) {
        return;
    }
    auto updated = mixture;
    for (const auto& term : reactants_) {
        updated.remove(term.compound, checked_count_multiply(term.coefficient, extent));
    }
    for (const auto& term : products_) {
        updated.add(term.compound, checked_count_multiply(term.coefficient, extent));
    }
    mixture = std::move(updated);
}

ElementInventory inventory_of(
    const CompoundMixture& mixture, const CompoundRegistry& compounds) {
    ElementInventory result;
    for (const auto& [compound, count] : mixture.amounts()) {
        result.add_inventory(compounds.at(compound).formula().scaled(count));
    }
    return result;
}

Mass mass_of(
    const CompoundMixture& mixture,
    const CompoundRegistry& compounds,
    const ElementCatalog& elements) {
    Mass result{};
    for (const auto& [compound, count] : mixture.amounts()) {
        result += scale_nonnegative(elements.molecule_mass(compounds.at(compound)), count);
    }
    return result;
}

HeatCapacity heat_capacity_of(
    const CompoundMixture& mixture,
    const CompoundRegistry& compounds,
    const ElementCatalog& elements) {
    HeatCapacity result{};
    for (const auto& [compound, count] : mixture.amounts()) {
        result += scale_nonnegative(
            elements.molecule_heat_capacity(compounds.at(compound)), count);
    }
    return result;
}

Energy structural_energy_of(
    const CompoundMixture& mixture,
    const CompoundRegistry& compounds,
    const ElementCatalog& elements) {
    Energy result{};
    for (const auto& [compound, count] : mixture.amounts()) {
        result += scale_nonnegative(
            elements.molecule_structural_energy(compounds.at(compound)), count);
    }
    return result;
}

} // namespace mls
