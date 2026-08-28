#include "mls/packet_store.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>
#include <utility>

namespace mls {
namespace {

[[nodiscard]] Scalar checked_square(Scalar value) {
    if (value == std::numeric_limits<Scalar>::min()) {
        throw std::overflow_error("momentum magnitude is outside the reference range");
    }
    const auto magnitude = value < 0 ? static_cast<Scalar>(-value) : value;
    return detail::checked_multiply(magnitude, magnitude);
}

[[nodiscard]] Length advance_axis_exact(
    Length position, Scalar old_remainder, Momentum momentum, Mass mass) {
    const auto denominator = mass.raw();
    if (old_remainder != 0 || momentum.raw() % denominator != 0) {
        throw std::domain_error(
            "reference ballistic step requires an exactly representable integer displacement");
    }
    return position + Length::from_raw(momentum.raw() / denominator);
}

void require_nonnegative(Energy value, const char* message) {
    if (!is_nonnegative(value)) {
        throw std::invalid_argument(message);
    }
}

} // namespace

Energy kinetic_energy_of(Mass mass, const Momentum3& momentum, Scalar scale_denominator) {
    if (mass.raw() <= 0) {
        throw std::invalid_argument("kinetic energy requires positive mass");
    }
    if (scale_denominator <= 0) {
        throw std::invalid_argument("kinetic energy scale denominator must be positive");
    }
    auto squared = checked_square(momentum.x.raw());
    squared = detail::checked_add(squared, checked_square(momentum.y.raw()));
    squared = detail::checked_add(squared, checked_square(momentum.z.raw()));

    auto result = static_cast<Scalar>(squared / mass.raw());
    result = static_cast<Scalar>(result / scale_denominator);
    result = static_cast<Scalar>(result / 2);
    return Energy::from_raw(result);
}

PacketStore::PacketStore(std::size_t history_limit, Scalar kinetic_energy_scale_denominator)
    : history_limit_(history_limit),
      kinetic_energy_scale_denominator_(kinetic_energy_scale_denominator) {
    if (kinetic_energy_scale_denominator_ <= 0) {
        throw std::invalid_argument("kinetic energy scale denominator must be positive");
    }
}

PacketHandle PacketStore::create(PacketInitialState initial, Tick tick) {
    if (initial.mass.raw() <= 0) {
        throw std::invalid_argument("material packet mass must be positive");
    }
    if (initial.composition.empty() || initial.elements.empty()) {
        throw std::invalid_argument("material packet requires nonempty structural composition");
    }
    if (!is_nonnegative(initial.heat_capacity) ||
        !is_nonnegative(initial.structural_energy) ||
        !is_nonnegative(initial.stored_energy) ||
        !is_nonnegative(initial.thermal_energy)) {
        throw std::invalid_argument("packet extensive quantities cannot be negative");
    }
    static_cast<void>(kinetic_energy_of(
        initial.mass, initial.momentum, kinetic_energy_scale_denominator_));
    if (next_id_.value == 0 || next_id_.value == std::numeric_limits<std::uint64_t>::max()) {
        throw std::overflow_error("packet ID space exhausted");
    }

    const auto id = next_id_;
    ++next_id_.value;
    const auto index = ids_.size();
    index_by_id_.emplace(id, index);
    ids_.push_back(id);
    generations_.push_back(1);
    alive_.push_back(true);
    position_x_.push_back(initial.position.x);
    position_y_.push_back(initial.position.y);
    position_z_.push_back(initial.position.z);
    position_remainder_x_.push_back(0);
    position_remainder_y_.push_back(0);
    position_remainder_z_.push_back(0);
    momentum_x_.push_back(initial.momentum.x);
    momentum_y_.push_back(initial.momentum.y);
    momentum_z_.push_back(initial.momentum.z);
    compositions_.push_back(std::move(initial.composition));
    elements_.push_back(std::move(initial.elements));
    masses_.push_back(initial.mass);
    heat_capacities_.push_back(initial.heat_capacity);
    structural_energies_.push_back(initial.structural_energy);
    stored_energies_.push_back(initial.stored_energy);
    thermal_energies_.push_back(initial.thermal_energy);
    histories_.emplace_back();
    ++alive_count_;

    const PacketHandle handle{id, 1};
    append_history(index, PacketEvent{
                              tick,
                              PacketEventKind::created,
                              {},
                              initial.position,
                              {},
                              initial.thermal_energy,
                              initial.stored_energy});
    return handle;
}

void PacketStore::erase(PacketHandle packet, Tick tick) {
    const auto index = index_of(packet);
    append_history(index, PacketEvent{
                              tick,
                              PacketEventKind::removed,
                              {},
                              {position_x_[index], position_y_[index], position_z_[index]},
                              {},
                              -thermal_energies_[index],
                              -stored_energies_[index]});
    alive_[index] = false;
    if (generations_[index] == std::numeric_limits<std::uint32_t>::max()) {
        throw std::overflow_error("packet generation exhausted");
    }
    ++generations_[index];
    --alive_count_;
}

bool PacketStore::contains(PacketHandle packet) const noexcept {
    const auto found = index_by_id_.find(packet.id);
    return found != index_by_id_.end() && alive_[found->second] &&
           generations_[found->second] == packet.generation;
}

std::size_t PacketStore::index_of(PacketHandle packet) const {
    const auto found = index_by_id_.find(packet.id);
    if (found == index_by_id_.end() || !alive_[found->second] ||
        generations_[found->second] != packet.generation) {
        throw std::out_of_range("stale or unknown material packet handle");
    }
    return found->second;
}

PacketSnapshot PacketStore::snapshot_at(std::size_t index) const {
    const Momentum3 momentum{momentum_x_[index], momentum_y_[index], momentum_z_[index]};
    return PacketSnapshot{
        PacketHandle{ids_[index], generations_[index]},
        {position_x_[index], position_y_[index], position_z_[index]},
        {position_remainder_x_[index], position_remainder_y_[index], position_remainder_z_[index]},
        momentum,
        compositions_[index],
        elements_[index],
        masses_[index],
        heat_capacities_[index],
        structural_energies_[index],
        stored_energies_[index],
        thermal_energies_[index],
        kinetic_energy_of(masses_[index], momentum, kinetic_energy_scale_denominator_)};
}

PacketSnapshot PacketStore::snapshot(PacketHandle packet) const {
    return snapshot_at(index_of(packet));
}

std::vector<PacketSnapshot> PacketStore::snapshots() const {
    std::vector<PacketSnapshot> result;
    result.reserve(alive_count_);
    for (std::size_t index = 0; index < ids_.size(); ++index) {
        if (alive_[index]) {
            result.push_back(snapshot_at(index));
        }
    }
    return result;
}

const std::vector<PacketEvent>& PacketStore::history(PacketHandle packet) const {
    return histories_.at(index_of(packet));
}

const std::vector<PacketEvent>& PacketStore::debug_history(PacketId packet) const {
    const auto found = index_by_id_.find(packet);
    if (found == index_by_id_.end()) {
        throw std::out_of_range("unknown material packet ID");
    }
    return histories_.at(found->second);
}

void PacketStore::append_history(std::size_t index, PacketEvent event) {
    if (history_limit_ == 0) {
        return;
    }
    auto& events = histories_.at(index);
    if (events.size() == history_limit_) {
        events.erase(events.begin());
    }
    events.push_back(event);
}

void PacketStore::advance_positions_one_tick(Tick resulting_tick) {
    auto next_x = position_x_;
    auto next_y = position_y_;
    auto next_z = position_z_;
    auto next_remainder_x = position_remainder_x_;
    auto next_remainder_y = position_remainder_y_;
    auto next_remainder_z = position_remainder_z_;
    for (std::size_t index = 0; index < ids_.size(); ++index) {
        if (!alive_[index]) {
            continue;
        }
        const auto x = advance_axis_exact(
            position_x_[index], position_remainder_x_[index], momentum_x_[index], masses_[index]);
        const auto y = advance_axis_exact(
            position_y_[index], position_remainder_y_[index], momentum_y_[index], masses_[index]);
        const auto z = advance_axis_exact(
            position_z_[index], position_remainder_z_[index], momentum_z_[index], masses_[index]);
        next_x[index] = x;
        next_y[index] = y;
        next_z[index] = z;
        next_remainder_x[index] = 0;
        next_remainder_y[index] = 0;
        next_remainder_z[index] = 0;
    }
    position_x_.swap(next_x);
    position_y_.swap(next_y);
    position_z_.swap(next_z);
    position_remainder_x_.swap(next_remainder_x);
    position_remainder_y_.swap(next_remainder_y);
    position_remainder_z_.swap(next_remainder_z);
    for (std::size_t index = 0; index < ids_.size(); ++index) {
        if (!alive_[index]) {
            continue;
        }
        append_history(index, PacketEvent{
                                  resulting_tick,
                                  PacketEventKind::advanced,
                                  {},
                                  {position_x_[index], position_y_[index], position_z_[index]}});
    }
}

Energy PacketStore::energy_at(std::size_t index, EnergyChannel channel) const noexcept {
    return channel == EnergyChannel::stored ? stored_energies_[index] : thermal_energies_[index];
}

void PacketStore::set_energy_at(std::size_t index, EnergyChannel channel, Energy value) {
    require_nonnegative(value, "packet energy channel cannot become negative");
    if (channel == EnergyChannel::stored) {
        stored_energies_[index] = value;
    } else {
        thermal_energies_[index] = value;
    }
}

void PacketStore::transfer_heat(
    PacketHandle from, PacketHandle to, Energy amount, Tick tick) {
    require_nonnegative(amount, "heat transfer amount cannot be negative");
    if (from == to) {
        return;
    }
    const auto from_index = index_of(from);
    const auto to_index = index_of(to);
    if (thermal_energies_[from_index] < amount) {
        throw std::domain_error("heat source would become negative");
    }
    const auto next_from = thermal_energies_[from_index] - amount;
    const auto next_to = thermal_energies_[to_index] + amount;
    thermal_energies_[from_index] = next_from;
    thermal_energies_[to_index] = next_to;
    append_history(from_index, PacketEvent{
                                   tick,
                                   PacketEventKind::heat_transferred,
                                   to.id,
                                   {position_x_[from_index], position_y_[from_index], position_z_[from_index]},
                                   {},
                                   -amount});
    append_history(to_index, PacketEvent{
                                 tick,
                                 PacketEventKind::heat_transferred,
                                 from.id,
                                 {position_x_[to_index], position_y_[to_index], position_z_[to_index]},
                                 {},
                                 amount});
}

void PacketStore::convert_energy(
    PacketHandle packet,
    EnergyChannel from,
    EnergyChannel to,
    Energy amount,
    Tick tick) {
    require_nonnegative(amount, "energy conversion amount cannot be negative");
    if (from == to || amount == Energy{}) {
        return;
    }
    const auto index = index_of(packet);
    if (energy_at(index, from) < amount) {
        throw std::domain_error("energy source channel would become negative");
    }
    const auto next_from = energy_at(index, from) - amount;
    const auto next_to = energy_at(index, to) + amount;
    set_energy_at(index, from, next_from);
    set_energy_at(index, to, next_to);
    const auto thermal_delta = to == EnergyChannel::thermal ? amount : -amount;
    const auto stored_delta = to == EnergyChannel::stored ? amount : -amount;
    append_history(index, PacketEvent{
                              tick,
                              PacketEventKind::energy_converted,
                              {},
                              {position_x_[index], position_y_[index], position_z_[index]},
                              {},
                              thermal_delta,
                              stored_delta});
}

void PacketStore::apply_actuated_dissipative_central_pair_impulse(
    PacketHandle first,
    PacketHandle second,
    Momentum3 impulse_to_first,
    PacketHandle energy_source,
    PacketHandle dissipation_sink,
    Tick tick) {
    if (first == second) {
        throw std::invalid_argument("momentum exchange requires two packets");
    }
    if ((energy_source != first && energy_source != second) ||
        (dissipation_sink != first && dissipation_sink != second)) {
        throw std::invalid_argument("energy source and sink must participate in the exchange");
    }
    const auto first_index = index_of(first);
    const auto second_index = index_of(second);
    const Position3 first_position{
        position_x_[first_index], position_y_[first_index], position_z_[first_index]};
    const Position3 second_position{
        position_x_[second_index], position_y_[second_index], position_z_[second_index]};
    if (pair_angular_momentum_delta(first_position, second_position, impulse_to_first) !=
        AngularMomentum3{}) {
        throw std::domain_error(
            "point interaction impulse must be central to conserve angular momentum");
    }
    const auto source_index = index_of(energy_source);
    const auto sink_index = index_of(dissipation_sink);
    const Momentum3 before_first{
        momentum_x_[first_index], momentum_y_[first_index], momentum_z_[first_index]};
    const Momentum3 before_second{
        momentum_x_[second_index], momentum_y_[second_index], momentum_z_[second_index]};
    const auto before_kinetic =
        kinetic_energy_of(masses_[first_index], before_first, kinetic_energy_scale_denominator_) +
        kinetic_energy_of(masses_[second_index], before_second, kinetic_energy_scale_denominator_);
    const auto after_first = before_first + impulse_to_first;
    const auto after_second = before_second - impulse_to_first;
    const auto after_kinetic =
        kinetic_energy_of(masses_[first_index], after_first, kinetic_energy_scale_denominator_) +
        kinetic_energy_of(masses_[second_index], after_second, kinetic_energy_scale_denominator_);

    auto next_source_stored = stored_energies_[source_index];
    auto next_sink_thermal = thermal_energies_[sink_index];
    if (after_kinetic > before_kinetic) {
        const auto required = after_kinetic - before_kinetic;
        if (next_source_stored < required) {
            throw std::domain_error("momentum exchange lacks stored energy");
        }
        next_source_stored -= required;
    } else {
        next_sink_thermal += before_kinetic - after_kinetic;
    }

    stored_energies_[source_index] = next_source_stored;
    thermal_energies_[sink_index] = next_sink_thermal;
    momentum_x_[first_index] = after_first.x;
    momentum_y_[first_index] = after_first.y;
    momentum_z_[first_index] = after_first.z;
    momentum_x_[second_index] = after_second.x;
    momentum_y_[second_index] = after_second.y;
    momentum_z_[second_index] = after_second.z;

    const auto kinetic_delta = after_kinetic - before_kinetic;
    append_history(first_index, PacketEvent{
                                    tick,
                                    PacketEventKind::actuated_dissipative_impulse,
                                    second.id,
                                    {position_x_[first_index], position_y_[first_index], position_z_[first_index]},
                                    impulse_to_first,
                                    before_kinetic > after_kinetic && sink_index == first_index
                                        ? before_kinetic - after_kinetic
                                        : Energy{},
                                    after_kinetic > before_kinetic && source_index == first_index
                                        ? -kinetic_delta
                                        : Energy{}});
    append_history(second_index, PacketEvent{
                                     tick,
                                     PacketEventKind::actuated_dissipative_impulse,
                                     first.id,
                                     {position_x_[second_index], position_y_[second_index], position_z_[second_index]},
                                     -impulse_to_first,
                                     before_kinetic > after_kinetic && sink_index == second_index
                                         ? before_kinetic - after_kinetic
                                         : Energy{},
                                     after_kinetic > before_kinetic && source_index == second_index
                                         ? -kinetic_delta
                                         : Energy{}});
}

void PacketStore::replace_composition(
    PacketHandle packet,
    CompoundMixture composition,
    ElementInventory elements,
    Mass mass,
    HeatCapacity heat_capacity,
    Energy structural_energy,
    Energy activation_threshold,
    Tick tick) {
    const auto index = index_of(packet);
    if (composition.empty() || elements != elements_[index] || mass != masses_[index]) {
        throw std::invalid_argument("composition replacement must preserve matter and mass exactly");
    }
    if (!is_nonnegative(heat_capacity) || !is_nonnegative(structural_energy) ||
        !is_nonnegative(activation_threshold)) {
        throw std::invalid_argument("replacement extensive values cannot be negative");
    }
    if (thermal_energies_[index] < activation_threshold) {
        throw std::domain_error("reaction activation threshold is not met");
    }

    const auto old_structural = structural_energies_[index];
    auto next_thermal = thermal_energies_[index];
    if (structural_energy > old_structural) {
        const auto required = structural_energy - old_structural;
        if (next_thermal < required) {
            throw std::domain_error("structural change lacks thermal energy");
        }
        next_thermal -= required;
    } else {
        next_thermal += old_structural - structural_energy;
    }
    compositions_[index] = std::move(composition);
    elements_[index] = std::move(elements);
    heat_capacities_[index] = heat_capacity;
    structural_energies_[index] = structural_energy;
    thermal_energies_[index] = next_thermal;
    append_history(index, PacketEvent{
                              tick,
                              PacketEventKind::composition_changed,
                              {},
                              {position_x_[index], position_y_[index], position_z_[index]},
                              {},
                              old_structural - structural_energy});
}

void PacketStore::adjust_boundary_energy(
    PacketHandle packet, EnergyChannel channel, Energy signed_delta, Tick tick) {
    const auto index = index_of(packet);
    const auto updated = energy_at(index, channel) + signed_delta;
    set_energy_at(index, channel, updated);
    append_history(index, PacketEvent{
                              tick,
                              PacketEventKind::boundary_exchange,
                              {},
                              {position_x_[index], position_y_[index], position_z_[index]},
                              {},
                              channel == EnergyChannel::thermal ? signed_delta : Energy{},
                              channel == EnergyChannel::stored ? signed_delta : Energy{}});
}

Energy PacketStore::adjust_boundary_momentum(
    PacketHandle packet, Momentum3 impulse, Tick tick) {
    const auto index = index_of(packet);
    const Momentum3 before{momentum_x_[index], momentum_y_[index], momentum_z_[index]};
    const auto before_energy =
        kinetic_energy_of(masses_[index], before, kinetic_energy_scale_denominator_);
    const auto after = before + impulse;
    const auto after_energy =
        kinetic_energy_of(masses_[index], after, kinetic_energy_scale_denominator_);
    momentum_x_[index] = after.x;
    momentum_y_[index] = after.y;
    momentum_z_[index] = after.z;
    append_history(index, PacketEvent{
                              tick,
                              PacketEventKind::boundary_exchange,
                              {},
                              {position_x_[index], position_y_[index], position_z_[index]},
                              impulse});
    return after_energy - before_energy;
}

} // namespace mls
