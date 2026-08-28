#include "mls/world.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>
#include <type_traits>
#include <utility>
#include <vector>

namespace mls {
namespace {

static_assert(
    std::is_nothrow_move_assignable_v<World>,
    "staged world commits require no-throw move assignment");

[[nodiscard]] ExtensiveTotals totals_for(const PacketSnapshot& packet) {
    ExtensiveTotals result;
    result.add(packet);
    return result;
}

[[nodiscard]] std::uint64_t fnv_byte(std::uint64_t hash, std::uint8_t value) noexcept {
    return (hash ^ value) * 1099511628211ULL;
}

template <typename Integer>
[[nodiscard]] std::uint64_t hash_integer(std::uint64_t hash, Integer value) noexcept {
    using Unsigned = std::make_unsigned_t<Integer>;
    const auto bits = static_cast<Unsigned>(value);
    for (std::size_t index = 0; index < sizeof(Integer); ++index) {
        const auto shift = static_cast<unsigned int>(index * 8U);
        const auto byte = static_cast<std::uint8_t>((bits >> shift) & static_cast<Unsigned>(0xffU));
        hash = fnv_byte(hash, byte);
    }
    return hash;
}

template <typename QuantityType>
void append_quantity(std::vector<std::uint64_t>& words, QuantityType quantity) {
    words.push_back(static_cast<std::uint64_t>(quantity.raw()));
}

void append_vector(std::vector<std::uint64_t>& words, const Momentum3& vector) {
    append_quantity(words, vector.x);
    append_quantity(words, vector.y);
    append_quantity(words, vector.z);
}

[[nodiscard]] std::vector<std::uint64_t> physical_packet_words(const PacketSnapshot& packet) {
    std::vector<std::uint64_t> words;
    words.reserve(24U + packet.composition.amounts().size() * 2U);
    append_quantity(words, packet.position.x);
    append_quantity(words, packet.position.y);
    append_quantity(words, packet.position.z);
    words.push_back(static_cast<std::uint64_t>(packet.integration_remainder.x));
    words.push_back(static_cast<std::uint64_t>(packet.integration_remainder.y));
    words.push_back(static_cast<std::uint64_t>(packet.integration_remainder.z));
    append_vector(words, packet.momentum);
    append_quantity(words, packet.mass);
    append_quantity(words, packet.heat_capacity);
    append_quantity(words, packet.structural_energy);
    append_quantity(words, packet.stored_energy);
    append_quantity(words, packet.thermal_energy);
    words.push_back(static_cast<std::uint64_t>(packet.composition.amounts().size()));
    for (const auto& [compound, count] : packet.composition.amounts()) {
        words.push_back(compound.value);
        words.push_back(static_cast<std::uint64_t>(count));
    }
    return words;
}

} // namespace

World::World(ElementCatalog elements, CompoundRegistry compounds, WorldConfig config)
    : config_(config),
      elements_(std::move(elements)),
      compounds_(std::move(compounds)),
      packets_(config_.packet_history_limit, config_.kinetic_energy_scale_denominator),
      grid_(config_.voxel_edge) {
    if (config_.kinetic_energy_scale_denominator <= 0) {
        throw std::invalid_argument("kinetic energy scale denominator must be positive");
    }
    if (config_.interaction_radius.raw() <= 0) {
        throw std::invalid_argument("interaction radius must be positive");
    }
    // Validate all configured structures eagerly so laws cannot change merely
    // because a compound first participates in an operation.
    for (const auto& [id, compound] : compounds_.compounds()) {
        static_cast<void>(id);
        static_cast<void>(elements_.molecule_mass(compound));
        static_cast<void>(elements_.molecule_heat_capacity(compound));
        static_cast<void>(elements_.molecule_structural_energy(compound));
    }
    grid_.rebuild(packets_);
    ledger_.establish_baseline(authoritative_totals(packets_));
}

PacketHandle World::introduce_material_from_boundary(const MaterialSeed& seed) {
    if (seed.composition.empty()) {
        throw std::invalid_argument("introduced material must contain compounds");
    }
    for (const auto& [compound, count] : seed.composition.amounts()) {
        if (!compounds_.contains(compound) || count <= 0) {
            throw std::invalid_argument("material seed contains unknown or empty compound amount");
        }
    }
    if (!is_nonnegative(seed.stored_energy) || !is_nonnegative(seed.thermal_energy)) {
        throw std::invalid_argument("introduced energy cannot be negative");
    }
    PacketInitialState initial{
        seed.position,
        seed.momentum,
        seed.composition,
        inventory_of(seed.composition, compounds_),
        mass_of(seed.composition, compounds_, elements_),
        heat_capacity_of(seed.composition, compounds_, elements_),
        structural_energy_of(seed.composition, compounds_, elements_),
        seed.stored_energy,
        seed.thermal_energy};
    const PacketSnapshot prospective{
        {},
        initial.position,
        {},
        initial.momentum,
        initial.composition,
        initial.elements,
        initial.mass,
        initial.heat_capacity,
        initial.structural_energy,
        initial.stored_energy,
        initial.thermal_energy,
        kinetic_energy_of(
            initial.mass, initial.momentum, config_.kinetic_energy_scale_denominator)};
    auto candidate = *this;
    candidate.ledger_.record_boundary_ingress(totals_for(prospective));
    const auto packet = candidate.packets_.create(std::move(initial), candidate.tick_);
    candidate.rebuild_and_verify();
    *this = std::move(candidate);
    return packet;
}

void World::remove_material_to_boundary(PacketHandle packet) {
    auto candidate = *this;
    const auto departing = totals_for(candidate.packets_.snapshot(packet));
    candidate.ledger_.record_boundary_egress(departing);
    candidate.packets_.erase(packet, candidate.tick_);
    candidate.rebuild_and_verify();
    *this = std::move(candidate);
}

void World::require_physical_support(PacketHandle first, PacketHandle second) const {
    const auto first_position = packets_.snapshot(first).position;
    const auto second_position = packets_.snapshot(second).position;
    if (!within_spherical_support(first_position, second_position, config_.interaction_radius)) {
        throw std::domain_error("operation requires packets inside physical interaction support");
    }
}

void World::transfer_heat(PacketHandle from, PacketHandle to, Energy amount) {
    auto candidate = *this;
    candidate.require_physical_support(from, to);
    candidate.packets_.transfer_heat(from, to, amount, candidate.tick_);
    candidate.rebuild_and_verify();
    *this = std::move(candidate);
}

void World::convert_energy(
    PacketHandle packet, EnergyChannel from, EnergyChannel to, Energy amount) {
    auto candidate = *this;
    candidate.packets_.convert_energy(packet, from, to, amount, candidate.tick_);
    candidate.rebuild_and_verify();
    *this = std::move(candidate);
}

void World::apply_actuated_dissipative_central_impulse(
    PacketHandle first,
    PacketHandle second,
    Momentum3 impulse_to_first,
    PacketHandle energy_source,
    PacketHandle dissipation_sink) {
    auto candidate = *this;
    candidate.require_physical_support(first, second);
    const auto first_position = candidate.packets_.snapshot(first).position;
    const auto second_position = candidate.packets_.snapshot(second).position;
    if (pair_angular_momentum_delta(first_position, second_position, impulse_to_first) !=
        AngularMomentum3{}) {
        throw std::domain_error(
            "point interaction impulse must be central to conserve angular momentum");
    }
    candidate.packets_.apply_actuated_dissipative_central_pair_impulse(
        first,
        second,
        impulse_to_first,
        energy_source,
        dissipation_sink,
        candidate.tick_);
    candidate.rebuild_and_verify();
    *this = std::move(candidate);
}

void World::apply_reaction(
    PacketHandle packet, const ReactionDefinition& reaction, MoleculeCount extent) {
    if (extent < 0) {
        throw std::invalid_argument("reaction extent cannot be negative");
    }
    if (!reaction.is_balanced(compounds_)) {
        throw std::invalid_argument("unbalanced reactions are forbidden");
    }
    auto candidate = *this;
    auto composition = candidate.packets_.snapshot(packet).composition;
    if (!reaction.can_apply(composition, extent)) {
        throw std::domain_error("reaction extent exceeds local reactants");
    }
    reaction.apply(composition, extent);
    const auto activation = reaction.activation_energy_per_extent() * extent;
    candidate.packets_.replace_composition(
        packet,
        composition,
        inventory_of(composition, candidate.compounds_),
        mass_of(composition, candidate.compounds_, candidate.elements_),
        heat_capacity_of(composition, candidate.compounds_, candidate.elements_),
        structural_energy_of(composition, candidate.compounds_, candidate.elements_),
        activation,
        candidate.tick_);
    candidate.rebuild_and_verify();
    *this = std::move(candidate);
}

void World::exchange_energy_with_boundary(
    PacketHandle packet, EnergyChannel channel, Energy signed_amount) {
    auto candidate = *this;
    candidate.ledger_.record_boundary_energy(signed_amount);
    candidate.packets_.adjust_boundary_energy(
        packet, channel, signed_amount, candidate.tick_);
    candidate.rebuild_and_verify();
    *this = std::move(candidate);
}

void World::apply_point_impulse_from_boundary(PacketHandle packet, Momentum3 impulse) {
    auto candidate = *this;
    const auto before = candidate.packets_.snapshot(packet);
    const auto after_momentum = before.momentum + impulse;
    const auto after_kinetic = kinetic_energy_of(
        before.mass, after_momentum, candidate.config_.kinetic_energy_scale_denominator);
    const auto energy_delta = after_kinetic - before.kinetic_energy;
    candidate.ledger_.record_boundary_point_impulse(before.position, impulse);
    candidate.ledger_.record_boundary_energy(energy_delta);
    const auto applied_delta =
        candidate.packets_.adjust_boundary_momentum(packet, impulse, candidate.tick_);
    if (applied_delta != energy_delta) {
        throw std::logic_error("boundary momentum energy calculation diverged");
    }
    candidate.rebuild_and_verify();
    *this = std::move(candidate);
}

void World::step(Tick count) {
    if (count > std::numeric_limits<Tick>::max() - tick_) {
        throw std::overflow_error("world tick overflow");
    }
    auto candidate = *this;
    for (Tick index = 0; index < count; ++index) {
        const auto next_tick = candidate.tick_ + 1;
        candidate.packets_.advance_positions_one_tick(next_tick);
        candidate.tick_ = next_tick;
        candidate.grid_.rebuild(candidate.packets_);
        if (candidate.config_.audit_after_each_operation && !candidate.audit().ok()) {
            throw std::logic_error("conservation audit failed during world step");
        }
    }
    *this = std::move(candidate);
}

void World::establish_current_state_as_baseline() {
    grid_.rebuild(packets_);
    ledger_.establish_baseline(authoritative_totals(packets_));
}

ExtensiveTotals World::totals() const {
    return authoritative_totals(packets_);
}

ConservationReport World::audit() const {
    return ledger_.audit(totals());
}

void World::rebuild_and_verify() {
    grid_.rebuild(packets_);
    if (config_.audit_after_each_operation && !audit().ok()) {
        throw std::logic_error("world conservation audit failed");
    }
}

std::uint64_t World::physical_state_hash() const {
    std::uint64_t hash = 14695981039346656037ULL;
    hash = hash_integer(hash, tick_);
    hash = hash_integer(hash, config_.voxel_edge.raw());
    hash = hash_integer(hash, config_.interaction_radius.raw());
    hash = hash_integer(hash, config_.kinetic_energy_scale_denominator);

    for (const auto& [element, properties] : elements_.elements()) {
        hash = hash_integer(hash, element.value);
        hash = hash_integer(hash, properties.unit_mass.raw());
        hash = hash_integer(hash, properties.unit_heat_capacity.raw());
        hash = hash_integer(hash, properties.isolated_energy.raw());
    }
    for (const auto& [key, energy] : elements_.bond_rules()) {
        hash = hash_integer(hash, key.first.value);
        hash = hash_integer(hash, key.second.value);
        hash = hash_integer(hash, key.order);
        hash = hash_integer(hash, energy.raw());
    }
    for (const auto& [compound_id, compound] : compounds_.compounds()) {
        hash = hash_integer(hash, compound_id.value);
        hash = hash_integer(hash, static_cast<std::uint64_t>(compound.atoms().size()));
        for (const auto atom : compound.atoms()) {
            hash = hash_integer(hash, atom.value);
        }
        hash = hash_integer(hash, static_cast<std::uint64_t>(compound.bonds().size()));
        for (const auto& bond : compound.bonds()) {
            hash = hash_integer(hash, bond.first);
            hash = hash_integer(hash, bond.second);
            hash = hash_integer(hash, bond.order);
        }
    }

    std::vector<std::vector<std::uint64_t>> packet_words;
    packet_words.reserve(packets_.alive_count());
    for (const auto& packet : packets_.snapshots()) {
        packet_words.push_back(physical_packet_words(packet));
    }
    std::sort(packet_words.begin(), packet_words.end());
    hash = hash_integer(hash, static_cast<std::uint64_t>(packet_words.size()));
    for (const auto& words : packet_words) {
        for (const auto word : words) {
            hash = hash_integer(hash, word);
        }
    }
    return hash;
}

} // namespace mls
