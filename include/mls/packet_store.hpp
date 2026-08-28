#pragma once

#include "mls/chemistry.hpp"
#include "mls/quantity.hpp"

#include <compare>
#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <vector>

namespace mls {

using Tick = std::uint64_t;

struct PacketId final {
    std::uint64_t value{0};

    [[nodiscard]] constexpr auto operator<=>(const PacketId&) const noexcept = default;
};

struct PacketHandle final {
    PacketId id{};
    std::uint32_t generation{0};

    [[nodiscard]] constexpr auto operator<=>(const PacketHandle&) const noexcept = default;
};

enum class PacketEventKind : std::uint8_t {
    created,
    advanced,
    heat_transferred,
    energy_converted,
    actuated_dissipative_impulse,
    composition_changed,
    boundary_exchange,
    removed,
};

// Packet history is audit/debug metadata. No stepping operation reads it.
struct PacketEvent final {
    Tick tick{0};
    PacketEventKind kind{PacketEventKind::created};
    PacketId related_packet{};
    Position3 position_after{};
    Momentum3 momentum_delta{};
    Energy thermal_delta{};
    Energy stored_delta{};
};

struct PacketInitialState final {
    Position3 position{};
    Momentum3 momentum{};
    CompoundMixture composition{};
    ElementInventory elements{};
    Mass mass{};
    HeatCapacity heat_capacity{};
    Energy structural_energy{};
    Energy stored_energy{};
    Energy thermal_energy{};
};

struct PositionRemainder3 final {
    Scalar x{0};
    Scalar y{0};
    Scalar z{0};

    [[nodiscard]] constexpr auto operator<=>(const PositionRemainder3&) const noexcept = default;
};

struct PacketSnapshot final {
    PacketHandle handle{};
    Position3 position{};
    PositionRemainder3 integration_remainder{};
    Momentum3 momentum{};
    CompoundMixture composition{};
    ElementInventory elements{};
    Mass mass{};
    HeatCapacity heat_capacity{};
    Energy structural_energy{};
    Energy stored_energy{};
    Energy thermal_energy{};
    Energy kinetic_energy{};

    [[nodiscard]] Energy total_energy() const {
        return structural_energy + stored_energy + thermal_energy + kinetic_energy;
    }
};

enum class EnergyChannel : std::uint8_t {
    stored,
    thermal,
};

// Exact integer kinetic-energy convention for the reference backend:
// floor((px^2 + py^2 + pz^2) / mass / scale_denominator / 2).
// Unit scales must be chosen so that this expression maps to one energy quantum.
[[nodiscard]] Energy kinetic_energy_of(
    Mass mass, const Momentum3& momentum, Scalar scale_denominator = 1);

class World;
namespace test {
class PacketStoreTestAccess;
}

// Structure-of-arrays packet storage. Variable-length mixture/inventory/history
// lanes remain separate vectors; scalar hot fields never live in an AoS object.
class PacketStore final {
public:
    explicit PacketStore(
        std::size_t history_limit = 0, Scalar kinetic_energy_scale_denominator = 1);

    [[nodiscard]] bool contains(PacketHandle packet) const noexcept;
    [[nodiscard]] std::size_t alive_count() const noexcept { return alive_count_; }
    [[nodiscard]] std::size_t slot_count() const noexcept { return ids_.size(); }
    [[nodiscard]] Scalar kinetic_energy_scale_denominator() const noexcept {
        return kinetic_energy_scale_denominator_;
    }

    [[nodiscard]] PacketSnapshot snapshot(PacketHandle packet) const;
    [[nodiscard]] std::vector<PacketSnapshot> snapshots() const;
    [[nodiscard]] const std::vector<PacketEvent>& history(PacketHandle packet) const;
    // Tombstone-safe audit access. PacketId is not accepted by physics methods.
    [[nodiscard]] const std::vector<PacketEvent>& debug_history(PacketId packet) const;

private:
    friend class World;
    // Test-only seam is declared here but defined outside the installed/public
    // library API. Authoritative callers mutate packets only through World.
    friend class test::PacketStoreTestAccess;

    [[nodiscard]] PacketHandle create(PacketInitialState initial, Tick tick = 0);
    void erase(PacketHandle packet, Tick tick);
    void advance_positions_one_tick(Tick resulting_tick);
    void transfer_heat(PacketHandle from, PacketHandle to, Energy amount, Tick tick);
    void convert_energy(
        PacketHandle packet,
        EnergyChannel from,
        EnergyChannel to,
        Energy amount,
        Tick tick);
    void apply_actuated_dissipative_central_pair_impulse(
        PacketHandle first,
        PacketHandle second,
        Momentum3 impulse_to_first,
        PacketHandle energy_source,
        PacketHandle dissipation_sink,
        Tick tick);
    void replace_composition(
        PacketHandle packet,
        CompoundMixture composition,
        ElementInventory elements,
        Mass mass,
        HeatCapacity heat_capacity,
        Energy structural_energy,
        Energy activation_threshold,
        Tick tick);
    void adjust_boundary_energy(
        PacketHandle packet, EnergyChannel channel, Energy signed_delta, Tick tick);
    [[nodiscard]] Energy adjust_boundary_momentum(
        PacketHandle packet, Momentum3 impulse, Tick tick);

    [[nodiscard]] std::size_t index_of(PacketHandle packet) const;
    [[nodiscard]] PacketSnapshot snapshot_at(std::size_t index) const;
    void append_history(std::size_t index, PacketEvent event);
    [[nodiscard]] Energy energy_at(std::size_t index, EnergyChannel channel) const noexcept;
    void set_energy_at(std::size_t index, EnergyChannel channel, Energy value);

    std::size_t history_limit_{0};
    Scalar kinetic_energy_scale_denominator_{1};
    PacketId next_id_{1};
    std::size_t alive_count_{0};
    std::map<PacketId, std::size_t> index_by_id_;

    std::vector<PacketId> ids_;
    std::vector<std::uint32_t> generations_;
    std::vector<bool> alive_;
    std::vector<Length> position_x_;
    std::vector<Length> position_y_;
    std::vector<Length> position_z_;
    std::vector<Scalar> position_remainder_x_;
    std::vector<Scalar> position_remainder_y_;
    std::vector<Scalar> position_remainder_z_;
    std::vector<Momentum> momentum_x_;
    std::vector<Momentum> momentum_y_;
    std::vector<Momentum> momentum_z_;
    std::vector<CompoundMixture> compositions_;
    std::vector<ElementInventory> elements_;
    std::vector<Mass> masses_;
    std::vector<HeatCapacity> heat_capacities_;
    std::vector<Energy> structural_energies_;
    std::vector<Energy> stored_energies_;
    std::vector<Energy> thermal_energies_;
    std::vector<std::vector<PacketEvent>> histories_;
};

} // namespace mls
