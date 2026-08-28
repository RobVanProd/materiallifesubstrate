#include "mls/sparse_grid.hpp"

#include <array>
#include <algorithm>
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

[[nodiscard]] Scalar cancellation_safe_sum(std::vector<Scalar> values) {
    std::vector<Scalar> positive;
    std::vector<Scalar> negative;
    positive.reserve(values.size());
    negative.reserve(values.size());
    for (const auto value : values) {
        if (value > 0) {
            positive.push_back(value);
        } else if (value < 0) {
            negative.push_back(value);
        }
    }

    std::size_t positive_index = 0;
    std::size_t negative_index = 0;
    Scalar total = 0;
    while (positive_index < positive.size() || negative_index < negative.size()) {
        if (total > 0 && negative_index < negative.size()) {
            total = detail::checked_add(total, negative[negative_index++]);
        } else if (total < 0 && positive_index < positive.size()) {
            total = detail::checked_add(total, positive[positive_index++]);
        } else if (positive_index < positive.size()) {
            total = detail::checked_add(total, positive[positive_index++]);
        } else {
            total = detail::checked_add(total, negative[negative_index++]);
        }
    }
    return total;
}

[[nodiscard]] ExtensiveTotals totals_of(std::span<const PacketSnapshot> packets) {
    ExtensiveTotals result;
    std::vector<Scalar> momentum_x;
    std::vector<Scalar> momentum_y;
    std::vector<Scalar> momentum_z;
    std::vector<Scalar> angular_x;
    std::vector<Scalar> angular_y;
    std::vector<Scalar> angular_z;
    momentum_x.reserve(packets.size());
    momentum_y.reserve(packets.size());
    momentum_z.reserve(packets.size());
    angular_x.reserve(packets.size());
    angular_y.reserve(packets.size());
    angular_z.reserve(packets.size());

    for (const auto& packet : packets) {
        result.elements.add_inventory(packet.elements);
        result.mass += packet.mass;
        result.structural_energy += packet.structural_energy;
        result.stored_energy += packet.stored_energy;
        result.thermal_energy += packet.thermal_energy;
        result.kinetic_energy += packet.kinetic_energy;
        if (result.packet_count == std::numeric_limits<std::size_t>::max()) {
            throw std::overflow_error("packet count overflow");
        }
        ++result.packet_count;

        momentum_x.push_back(packet.momentum.x.raw());
        momentum_y.push_back(packet.momentum.y.raw());
        momentum_z.push_back(packet.momentum.z.raw());
        const auto angular = cross(packet.position, packet.momentum);
        angular_x.push_back(angular.x.raw());
        angular_y.push_back(angular.y.raw());
        angular_z.push_back(angular.z.raw());
    }
    result.momentum = {
        Momentum::from_raw(cancellation_safe_sum(std::move(momentum_x))),
        Momentum::from_raw(cancellation_safe_sum(std::move(momentum_y))),
        Momentum::from_raw(cancellation_safe_sum(std::move(momentum_z)))};
    result.angular_momentum = {
        AngularMomentum::from_raw(cancellation_safe_sum(std::move(angular_x))),
        AngularMomentum::from_raw(cancellation_safe_sum(std::move(angular_y))),
        AngularMomentum::from_raw(cancellation_safe_sum(std::move(angular_z)))};
    return result;
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
    updated.angular_momentum += cross(packet.position, packet.momentum);
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
    updated.angular_momentum += other.angular_momentum;
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
    std::map<VoxelCoord, std::vector<PacketSnapshot>> rebuilt_snapshots;
    for (const auto& packet : packets.snapshots()) {
        const auto coordinate = coordinate_for(packet.position);
        auto& cell = rebuilt[coordinate];
        cell.packets.push_back(packet.handle);
        rebuilt_snapshots[coordinate].push_back(packet);
    }
    for (auto& [coordinate, cell] : rebuilt) {
        try {
            cell.totals = totals_of(rebuilt_snapshots.at(coordinate));
        } catch (const std::overflow_error&) {
            cell.totals.reset();
        }
    }
    cells_.swap(rebuilt);
    snapshots_by_cell_.swap(rebuilt_snapshots);
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
    std::vector<PacketSnapshot> packets;
    for (const auto& [coordinate, cell_packets] : snapshots_by_cell_) {
        static_cast<void>(coordinate);
        packets.insert(packets.end(), cell_packets.begin(), cell_packets.end());
    }
    return totals_of(packets);
}

ExtensiveTotals SparseVoxelGrid::aggregate(std::span<const VoxelCoord> coordinates) const {
    std::vector<PacketSnapshot> packets;
    std::set<VoxelCoord> visited;
    for (const auto coordinate : coordinates) {
        if (!visited.insert(coordinate).second) {
            throw std::invalid_argument("aggregate coordinates must be unique");
        }
        const auto found = snapshots_by_cell_.find(coordinate);
        if (found != snapshots_by_cell_.end()) {
            packets.insert(packets.end(), found->second.begin(), found->second.end());
        }
    }
    return totals_of(packets);
}

ExtensiveTotals authoritative_totals(const PacketStore& packets) {
    return totals_of(packets.snapshots());
}

} // namespace mls
