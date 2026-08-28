#pragma once

#include "mls/packet_store.hpp"

#include <compare>
#include <cstddef>
#include <cstdint>
#include <map>
#include <span>
#include <vector>

namespace mls {

struct VoxelCoord final {
    std::int64_t x{0};
    std::int64_t y{0};
    std::int64_t z{0};

    [[nodiscard]] constexpr auto operator<=>(const VoxelCoord&) const noexcept = default;
};

struct ExtensiveTotals final {
    ElementInventory elements{};
    Mass mass{};
    Energy structural_energy{};
    Energy stored_energy{};
    Energy thermal_energy{};
    Energy kinetic_energy{};
    Momentum3 momentum{};
    std::size_t packet_count{0};

    [[nodiscard]] Energy total_energy() const {
        return structural_energy + stored_energy + thermal_energy + kinetic_energy;
    }

    void add(const PacketSnapshot& packet);
    void add(const ExtensiveTotals& other);

    [[nodiscard]] bool operator==(const ExtensiveTotals&) const noexcept = default;
};

struct VoxelCell final {
    std::vector<PacketHandle> packets{};
    ExtensiveTotals totals{};
};

// SparseVoxelGrid is a disposable control-volume index. PacketStore remains the
// authoritative material state, and aggregates are never fed into reactions.
class SparseVoxelGrid final {
public:
    explicit SparseVoxelGrid(Length voxel_edge);

    [[nodiscard]] Length voxel_edge() const noexcept { return voxel_edge_; }
    [[nodiscard]] VoxelCoord coordinate_for(const Position3& position) const noexcept;
    void rebuild(const PacketStore& packets);

    [[nodiscard]] const std::map<VoxelCoord, VoxelCell>& cells() const noexcept {
        return cells_;
    }
    [[nodiscard]] const VoxelCell* find(VoxelCoord coordinate) const noexcept;
    [[nodiscard]] std::span<const PacketHandle> packets_at(VoxelCoord coordinate) const noexcept;
    [[nodiscard]] ExtensiveTotals totals() const;
    [[nodiscard]] ExtensiveTotals aggregate(std::span<const VoxelCoord> coordinates) const;

private:
    Length voxel_edge_{};
    std::map<VoxelCoord, VoxelCell> cells_;
};

[[nodiscard]] bool face_local(VoxelCoord first, VoxelCoord second) noexcept;

} // namespace mls
