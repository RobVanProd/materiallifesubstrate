#pragma once

#include "mls/quantity.hpp"

#include <compare>
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <map>
#include <span>
#include <vector>

namespace mls {

// Canonicalization deliberately uses an exhaustive permutation search in the
// small reference model. The bound makes its factorial cost explicit and keeps
// adversarial inputs from turning compound construction into unbounded work.
inline constexpr std::size_t max_compound_atom_sites = 8;

using ElementCount = std::int64_t;
using MoleculeCount = std::int64_t;

struct ElementId final {
    std::uint16_t value{0};

    [[nodiscard]] constexpr auto operator<=>(const ElementId&) const noexcept = default;
};

// A CompoundId is a cache key derived from CompoundGraph::structural_hash().
// It carries no material semantics and may never be used to assign behavior.
struct CompoundId final {
    std::uint64_t value{0};

    [[nodiscard]] constexpr auto operator<=>(const CompoundId&) const noexcept = default;
};

struct Bond final {
    std::uint32_t first{0};
    std::uint32_t second{0};
    std::uint8_t order{1};

    [[nodiscard]] constexpr auto operator<=>(const Bond&) const noexcept = default;
};

class ElementInventory final {
public:
    ElementInventory() = default;
    ElementInventory(std::initializer_list<std::pair<const ElementId, ElementCount>> values);

    [[nodiscard]] ElementCount amount(ElementId element) const noexcept;
    [[nodiscard]] bool empty() const noexcept { return amounts_.empty(); }
    [[nodiscard]] const std::map<ElementId, ElementCount>& amounts() const noexcept {
        return amounts_;
    }

    void add(ElementId element, ElementCount amount);
    void remove(ElementId element, ElementCount amount);
    void add_inventory(const ElementInventory& other);
    void remove_inventory(const ElementInventory& other);
    [[nodiscard]] ElementInventory scaled(ElementCount factor) const;

    [[nodiscard]] bool can_apply(
        const std::map<ElementId, ElementCount>& signed_delta) const noexcept;
    void apply(const std::map<ElementId, ElementCount>& signed_delta);

    [[nodiscard]] bool operator==(const ElementInventory&) const noexcept = default;

private:
    std::map<ElementId, ElementCount> amounts_;
};

class CompoundGraph final {
public:
    CompoundGraph(std::vector<ElementId> atoms, std::vector<Bond> bonds);

    [[nodiscard]] const std::vector<ElementId>& atoms() const noexcept { return atoms_; }
    [[nodiscard]] const std::vector<Bond>& bonds() const noexcept { return bonds_; }
    [[nodiscard]] ElementInventory formula() const;

    // Stable FNV-1a cache hash of the canonical labeled-graph encoding. Site
    // numbering and input bond order are not species identity. Registry
    // equality remains authoritative when detecting a hash collision.
    [[nodiscard]] CompoundId structural_hash() const noexcept;

    [[nodiscard]] bool operator==(const CompoundGraph&) const noexcept = default;

private:
    std::vector<ElementId> atoms_;
    std::vector<Bond> bonds_;
};

struct ElementProperties final {
    Mass unit_mass{};
    HeatCapacity unit_heat_capacity{};
    // Energy of an isolated element unit in the configured mesoscale model.
    Energy isolated_energy{};
};

struct BondRuleKey final {
    ElementId first{};
    ElementId second{};
    std::uint8_t order{1};

    [[nodiscard]] constexpr auto operator<=>(const BondRuleKey&) const noexcept = default;
};

class ElementCatalog final {
public:
    void define(ElementId id, ElementProperties properties);
    [[nodiscard]] bool contains(ElementId id) const noexcept;
    [[nodiscard]] const ElementProperties& at(ElementId id) const;

    void define_bond_energy(
        ElementId first, ElementId second, std::uint8_t order, Energy dissociation_energy);
    [[nodiscard]] Energy bond_energy(
        ElementId first, ElementId second, std::uint8_t order) const;

    [[nodiscard]] Mass molecule_mass(const CompoundGraph& compound) const;
    [[nodiscard]] HeatCapacity molecule_heat_capacity(const CompoundGraph& compound) const;
    [[nodiscard]] Energy molecule_structural_energy(const CompoundGraph& compound) const;

    [[nodiscard]] const std::map<ElementId, ElementProperties>& elements() const noexcept {
        return elements_;
    }
    [[nodiscard]] const std::map<BondRuleKey, Energy>& bond_rules() const noexcept {
        return bond_energies_;
    }

private:
    [[nodiscard]] static BondRuleKey normalized_bond_key(
        ElementId first, ElementId second, std::uint8_t order) noexcept;

    std::map<ElementId, ElementProperties> elements_;
    std::map<BondRuleKey, Energy> bond_energies_;
};

class CompoundRegistry final {
public:
    [[nodiscard]] CompoundId intern(CompoundGraph compound);
    [[nodiscard]] bool contains(CompoundId id) const noexcept;
    [[nodiscard]] const CompoundGraph& at(CompoundId id) const;
    [[nodiscard]] const std::map<CompoundId, CompoundGraph>& compounds() const noexcept {
        return compounds_;
    }

private:
    std::map<CompoundId, CompoundGraph> compounds_;
};

class CompoundMixture final {
public:
    CompoundMixture() = default;
    CompoundMixture(std::initializer_list<std::pair<const CompoundId, MoleculeCount>> values);

    [[nodiscard]] MoleculeCount amount(CompoundId compound) const noexcept;
    [[nodiscard]] bool empty() const noexcept { return amounts_.empty(); }
    [[nodiscard]] const std::map<CompoundId, MoleculeCount>& amounts() const noexcept {
        return amounts_;
    }

    void add(CompoundId compound, MoleculeCount amount);
    void remove(CompoundId compound, MoleculeCount amount);

    [[nodiscard]] bool operator==(const CompoundMixture&) const noexcept = default;

private:
    std::map<CompoundId, MoleculeCount> amounts_;
};

struct StoichiometricTerm final {
    CompoundId compound{};
    MoleculeCount coefficient{1};

    [[nodiscard]] constexpr auto operator<=>(const StoichiometricTerm&) const noexcept = default;
};

class ReactionDefinition final {
public:
    ReactionDefinition(
        std::vector<StoichiometricTerm> reactants,
        std::vector<StoichiometricTerm> products,
        Energy activation_energy_per_extent = Energy{});

    [[nodiscard]] const std::vector<StoichiometricTerm>& reactants() const noexcept {
        return reactants_;
    }
    [[nodiscard]] const std::vector<StoichiometricTerm>& products() const noexcept {
        return products_;
    }
    [[nodiscard]] Energy activation_energy_per_extent() const noexcept {
        return activation_energy_per_extent_;
    }

    [[nodiscard]] std::map<ElementId, ElementCount> element_delta(
        const CompoundRegistry& compounds) const;
    [[nodiscard]] bool is_balanced(const CompoundRegistry& compounds) const;
    [[nodiscard]] MoleculeCount maximum_extent(const CompoundMixture& mixture) const noexcept;
    [[nodiscard]] bool can_apply(const CompoundMixture& mixture, MoleculeCount extent) const noexcept;
    void apply(CompoundMixture& mixture, MoleculeCount extent) const;

private:
    [[nodiscard]] static std::vector<StoichiometricTerm> normalize_terms(
        std::span<const StoichiometricTerm> terms);

    std::vector<StoichiometricTerm> reactants_;
    std::vector<StoichiometricTerm> products_;
    Energy activation_energy_per_extent_{};
};

[[nodiscard]] ElementInventory inventory_of(
    const CompoundMixture& mixture, const CompoundRegistry& compounds);
[[nodiscard]] Mass mass_of(
    const CompoundMixture& mixture,
    const CompoundRegistry& compounds,
    const ElementCatalog& elements);
[[nodiscard]] HeatCapacity heat_capacity_of(
    const CompoundMixture& mixture,
    const CompoundRegistry& compounds,
    const ElementCatalog& elements);
[[nodiscard]] Energy structural_energy_of(
    const CompoundMixture& mixture,
    const CompoundRegistry& compounds,
    const ElementCatalog& elements);

} // namespace mls
