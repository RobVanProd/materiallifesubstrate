#include "mls/sparse_grid.hpp"

#include <array>
#include <limits>
#include <set>
#include <stdexcept>
#include <utility>

namespace mls {
namespace {

[[nodiscard]] std::int64_t floor_divide(std::int64_t numerator, std::int64_t denominator) noexcept {
    auto quotient = static_cast<std::int64_t>(numerator / denominator);
    if (numerator % denominator < 0) {
        --quotient;
    }
    return quotient;
}

[[nodiscard]] std::uint64_t unsigned_distance(std::int64_t lhs, std::int64_t rhs) noexcept {
    if (lhs >= rhs) {
        return static_cast<std::uint64_t>(lhs) - static_cast<std::uint64_t>(rhs);
    }
    return static_cast<std::uint64_t>(rhs) - static_cast<std::uint64_t>(lhs);
}

} // namespace

void ExtensiveTotals::add(const PacketSnapshot& packet) {
    auto updated = *this;
    updated.elements.add_inventory(packet.elements);
    updated.mass += packet.mass;
    updated.structural_energy += packet.structural_energy;
    updated.stored_energy += packet.stored_energy;
    updated.thermal_energy += packet.thermal_energy;
    updated.kinetic_energy += packet.kinetic_energy;
    updated.momentum += packet.momentum;
    if (updated.packet_count == std::numeric_limits<std::size_t>::max()) {
        throw std::overflow_error("packet count overflow");
    }
    ++updated.packet_count;
    *this = std::move(updated);
}

void ExtensiveTotals::add(const ExtensiveTotals& other) {
    auto updated = *this;
    updated.elements.add_inventory(other.elements);
    updated.mass += other.mass;
    updated.structural_energy += other.structural_energy;
    updated.stored_energy += other.stored_energy;
    updated.thermal_energy += other.thermal_energy;
    updated.kinetic_energy += other.kinetic_energy;
    updated.momentum += other.momentum;
    if (other.packet_count > std::numeric_limits<std::size_t>::max() - updated.packet_count) {
        throw std::overflow_error("packet count overflow");
    }
    updated.packet_count += other.packet_count;
    *this = std::move(updated);
}

SparseVoxelGrid::SparseVoxelGrid(Length voxel_edge) : voxel_edge_(voxel_edge) {
    if (voxel_edge_.raw() <= 0) {
        throw std::invalid_argument("voxel edge must be positive");
    }
}

VoxelCoord SparseVoxelGrid::coordinate_for(const Position3& position) const noexcept {
    return {
        floor_divide(position.x.raw(), voxel_edge_.raw()),
        floor_divide(position.y.raw(), voxel_edge_.raw()),
        floor_divide(position.z.raw(), voxel_edge_.raw())};
}

void SparseVoxelGrid::rebuild(const PacketStore& packets) {
    std::map<VoxelCoord, VoxelCell> rebuilt;
    for (const auto& packet : packets.snapshots()) {
        auto& cell = rebuilt[coordinate_for(packet.position)];
        cell.packets.push_back(packet.handle);
        cell.totals.add(packet);
    }
    cells_.swap(rebuilt);
}

const VoxelCell* SparseVoxelGrid::find(VoxelCoord coordinate) const noexcept {
    const auto found = cells_.find(coordinate);
    return found == cells_.end() ? nullptr : &found->second;
}

std::span<const PacketHandle> SparseVoxelGrid::packets_at(VoxelCoord coordinate) const noexcept {
    const auto* cell = find(coordinate);
    return cell == nullptr ? std::span<const PacketHandle>{}
                           : std::span<const PacketHandle>{cell->packets};
}

ExtensiveTotals SparseVoxelGrid::totals() const {
    ExtensiveTotals result;
    for (const auto& [coordinate, cell] : cells_) {
        static_cast<void>(coordinate);
        result.add(cell.totals);
    }
    return result;
}

ExtensiveTotals SparseVoxelGrid::aggregate(std::span<const VoxelCoord> coordinates) const {
    ExtensiveTotals result;
    std::set<VoxelCoord> visited;
    for (const auto coordinate : coordinates) {
        if (!visited.insert(coordinate).second) {
            throw std::invalid_argument("aggregate coordinates must be unique");
        }
        const auto* cell = find(coordinate);
        if (cell != nullptr) {
            result.add(cell->totals);
        }
    }
    return result;
}

bool face_local(VoxelCoord first, VoxelCoord second) noexcept {
    const auto dx = unsigned_distance(first.x, second.x);
    const auto dy = unsigned_distance(first.y, second.y);
    const auto dz = unsigned_distance(first.z, second.z);
    return dx <= 1U && dy <= 1U && dz <= 1U && dx + dy + dz <= 1U;
}

} // namespace mls
