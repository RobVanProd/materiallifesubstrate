#pragma once

#include "mls/packet_store.hpp"

#include <utility>

namespace mls::test {

// Test-only friend seam for adversarial unit tests of the non-authoritative SoA
// implementation. Production callers cannot mutate PacketStore directly.
class PacketStoreTestAccess final {
public:
    [[nodiscard]] static PacketHandle create(
        PacketStore& store, PacketInitialState initial, Tick tick = 0) {
        return store.create(std::move(initial), tick);
    }

    static void erase(PacketStore& store, PacketHandle packet, Tick tick) {
        store.erase(packet, tick);
    }

    static void advance_positions_one_tick(
        PacketStore& store, Tick resulting_tick) {
        store.advance_positions_one_tick(resulting_tick);
    }

    static void transfer_heat(
        PacketStore& store,
        PacketHandle from,
        PacketHandle to,
        Energy amount,
        Tick tick) {
        store.transfer_heat(from, to, amount, tick);
    }

    static void convert_energy(
        PacketStore& store,
        PacketHandle packet,
        EnergyChannel from,
        EnergyChannel to,
        Energy amount,
        Tick tick) {
        store.convert_energy(packet, from, to, amount, tick);
    }

    static void apply_actuated_dissipative_central_pair_impulse(
        PacketStore& store,
        PacketHandle first,
        PacketHandle second,
        Momentum3 impulse,
        PacketHandle energy_source,
        PacketHandle dissipation_sink,
        Tick tick) {
        store.apply_actuated_dissipative_central_pair_impulse(
            first, second, impulse, energy_source, dissipation_sink, tick);
    }

    static void replace_composition(
        PacketStore& store,
        PacketHandle packet,
        CompoundMixture composition,
        ElementInventory elements,
        Mass mass,
        HeatCapacity heat_capacity,
        Energy structural_energy,
        Energy activation_threshold,
        Tick tick) {
        store.replace_composition(
            packet,
            std::move(composition),
            std::move(elements),
            mass,
            heat_capacity,
            structural_energy,
            activation_threshold,
            tick);
    }

    static void adjust_boundary_energy(
        PacketStore& store,
        PacketHandle packet,
        EnergyChannel channel,
        Energy delta,
        Tick tick) {
        store.adjust_boundary_energy(packet, channel, delta, tick);
    }

    [[nodiscard]] static Energy adjust_boundary_momentum(
        PacketStore& store, PacketHandle packet, Momentum3 impulse, Tick tick) {
        return store.adjust_boundary_momentum(packet, impulse, tick);
    }
};

} // namespace mls::test
