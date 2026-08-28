#pragma once

#include "mls/chemistry.hpp"
#include "mls/ledger.hpp"
#include "mls/packet_store.hpp"
#include "mls/sparse_grid.hpp"

#include <cstddef>
#include <cstdint>

#ifndef MLS_AUDIT_DEFAULT
#define MLS_AUDIT_DEFAULT 1
#endif

namespace mls {

struct WorldConfig final {
    Length voxel_edge{Length::from_raw(1)};
    Scalar kinetic_energy_scale_denominator{1};
    std::size_t packet_history_limit{0};
    bool audit_after_each_operation{MLS_AUDIT_DEFAULT != 0};
};

struct MaterialSeed final {
    Position3 position{};
    Momentum3 momentum{};
    CompoundMixture composition{};
    Energy stored_energy{};
    Energy thermal_energy{};
};

// Deterministic, headless authoritative reference world. It accepts physical
// state and low-level local operations only. There is intentionally no camera,
// renderer, organism, reward, fitness, sensor, tool, or gameplay interface.
class World final {
public:
    World(ElementCatalog elements, CompoundRegistry compounds, WorldConfig config = {});

    [[nodiscard]] const WorldConfig& config() const noexcept { return config_; }
    [[nodiscard]] Tick tick() const noexcept { return tick_; }
    [[nodiscard]] const ElementCatalog& element_catalog() const noexcept { return elements_; }
    [[nodiscard]] const CompoundRegistry& compound_registry() const noexcept { return compounds_; }
    [[nodiscard]] const PacketStore& packets() const noexcept { return packets_; }
    [[nodiscard]] const SparseVoxelGrid& grid() const noexcept { return grid_; }
    [[nodiscard]] const ConservationLedger& ledger() const noexcept { return ledger_; }

    // Scenario/open-boundary ports only: each call is entered in the unified
    // ledger. These controls are not part of the material-agent interaction ABI.
    [[nodiscard]] PacketHandle introduce_material_from_boundary(const MaterialSeed& seed);
    void remove_material_to_boundary(PacketHandle packet);

    void transfer_heat(PacketHandle from, PacketHandle to, Energy amount);
    void convert_energy(
        PacketHandle packet, EnergyChannel from, EnergyChannel to, Energy amount);
    void exchange_momentum(
        PacketHandle first,
        PacketHandle second,
        Momentum3 impulse_to_first,
        PacketHandle energy_source,
        PacketHandle dissipation_sink);
    void apply_reaction(
        PacketHandle packet, const ReactionDefinition& reaction, MoleculeCount extent);

    // Explicit open-boundary operations. Their signed changes are added to the
    // same ledger used to audit all internal conservation.
    void exchange_energy_with_boundary(
        PacketHandle packet, EnergyChannel channel, Energy signed_amount);
    void exchange_momentum_with_boundary(PacketHandle packet, Momentum3 impulse);

    void step(Tick count = 1);
    void establish_current_state_as_baseline();
    [[nodiscard]] ExtensiveTotals totals() const;
    [[nodiscard]] ConservationReport audit() const;

    // Stable hash of laws + physical state, excluding debug IDs, generations,
    // packet history, and the disposable voxel index.
    [[nodiscard]] std::uint64_t physical_state_hash() const;

private:
    void rebuild_and_verify();
    void require_local(PacketHandle first, PacketHandle second) const;

    WorldConfig config_{};
    Tick tick_{0};
    ElementCatalog elements_{};
    CompoundRegistry compounds_{};
    PacketStore packets_;
    SparseVoxelGrid grid_;
    ConservationLedger ledger_{};
};

} // namespace mls
