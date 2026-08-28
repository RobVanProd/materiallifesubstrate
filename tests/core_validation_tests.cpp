#include "test_harness.hpp"

#include "mls/chemistry.hpp"
#include "mls/ledger.hpp"
#include "mls/packet_store.hpp"
#include "mls/quantity.hpp"
#include "mls/sparse_grid.hpp"
#include "mls/world.hpp"

#include <array>
#include <cstdint>
#include <limits>
#include <map>
#include <stdexcept>
#include <vector>

namespace {

constexpr std::uint64_t validation_seed = 260828;

[[nodiscard]] mls::CompoundGraph atom(mls::ElementId element) {
    return mls::CompoundGraph(std::vector<mls::ElementId>{element}, {});
}

struct ChemistryFixture final {
    mls::ElementId a{0};
    mls::ElementId b{1};
    mls::CompoundRegistry compounds;
    mls::CompoundId a_id;
    mls::CompoundId b_id;
    mls::CompoundId ab_id;

    ChemistryFixture()
        : a_id(compounds.intern(atom(a))),
          b_id(compounds.intern(atom(b))),
          ab_id(compounds.intern(mls::CompoundGraph(
              std::vector<mls::ElementId>{a, b},
              std::vector<mls::Bond>{{0, 1, 1}}))) {}
};

using Rotation = std::array<std::array<mls::Scalar, 3>, 3>;

[[nodiscard]] int permutation_parity(const std::array<int, 3>& permutation) {
    int inversions = 0;
    for (std::size_t first = 0; first < permutation.size(); ++first) {
        for (std::size_t second = first + 1; second < permutation.size(); ++second) {
            if (permutation[first] > permutation[second]) {
                ++inversions;
            }
        }
    }
    return inversions % 2 == 0 ? 1 : -1;
}

[[nodiscard]] std::vector<Rotation> proper_cube_rotations() {
    constexpr std::array<std::array<int, 3>, 6> permutations{{
        {{0, 1, 2}}, {{0, 2, 1}}, {{1, 0, 2}}, {{1, 2, 0}}, {{2, 0, 1}}, {{2, 1, 0}},
    }};
    std::vector<Rotation> rotations;
    for (const auto& permutation : permutations) {
        for (const int first_sign : {-1, 1}) {
            for (const int second_sign : {-1, 1}) {
                for (const int third_sign : {-1, 1}) {
                    if (permutation_parity(permutation) * first_sign * second_sign * third_sign != 1) {
                        continue;
                    }
                    const std::array<int, 3> signs{first_sign, second_sign, third_sign};
                    Rotation rotation{};
                    for (std::size_t row = 0; row < 3; ++row) {
                        rotation[row][static_cast<std::size_t>(permutation[row])] = signs[row];
                    }
                    rotations.push_back(rotation);
                }
            }
        }
    }
    return rotations;
}

[[nodiscard]] mls::Momentum3 rotate(const Rotation& rotation, const mls::Momentum3& vector) {
    const std::array<mls::Momentum, 3> components{vector.x, vector.y, vector.z};
    std::array<mls::Momentum, 3> result{};
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            result[row] += components[column] * rotation[row][column];
        }
    }
    return {result[0], result[1], result[2]};
}

[[nodiscard]] mls::Scalar squared_norm(const mls::Momentum3& vector) {
    return vector.x.raw() * vector.x.raw() + vector.y.raw() * vector.y.raw() +
           vector.z.raw() * vector.z.raw();
}

[[nodiscard]] mls::PacketInitialState packet_state(
    const ChemistryFixture& fixture,
    mls::Momentum3 momentum = {},
    mls::Energy thermal = mls::Energy::from_raw(10'000),
    mls::Energy stored = mls::Energy::from_raw(10'000)) {
    return mls::PacketInitialState{
        .position = {},
        .momentum = momentum,
        .composition = mls::CompoundMixture{{fixture.a_id, 5}},
        .elements = mls::ElementInventory{{fixture.a, 5}},
        .mass = mls::Mass::from_raw(50),
        .heat_capacity = mls::HeatCapacity::from_raw(5),
        .structural_energy = mls::Energy::from_raw(100),
        .stored_energy = stored,
        .thermal_energy = thermal,
    };
}

struct CameraProbe final {
    mls::Scalar x{0};
    mls::Scalar y{0};
    mls::Scalar z{0};
    mls::Scalar field_of_view{90};
};

template <typename WorldType>
concept StepAcceptsCamera = requires(WorldType& world, CameraProbe camera) {
    world.step(camera);
};

static_assert(!StepAcceptsCamera<mls::World>, "authoritative physics must not accept camera state");

struct WorldFixture final {
    mls::ElementId a;
    mls::ElementId b;
    mls::CompoundId a_id;
    mls::CompoundId b_id;
    mls::CompoundId ab_id;
    mls::ReactionDefinition association;
    mls::World world;
};

[[nodiscard]] WorldFixture make_world(mls::WorldConfig config = {}) {
    const mls::ElementId a{0};
    const mls::ElementId b{1};
    mls::ElementCatalog elements;
    elements.define(
        a,
        mls::ElementProperties{
            mls::Mass::from_raw(10),
            mls::HeatCapacity::from_raw(2),
            mls::Energy::from_raw(100)});
    elements.define(
        b,
        mls::ElementProperties{
            mls::Mass::from_raw(20),
            mls::HeatCapacity::from_raw(3),
            mls::Energy::from_raw(150)});
    elements.define_bond_energy(a, b, 1, mls::Energy::from_raw(30));

    mls::CompoundRegistry compounds;
    const auto a_id = compounds.intern(atom(a));
    const auto b_id = compounds.intern(atom(b));
    const auto ab_id = compounds.intern(mls::CompoundGraph(
        std::vector<mls::ElementId>{a, b},
        std::vector<mls::Bond>{{0, 1, 1}}));
    mls::ReactionDefinition association(
        std::vector<mls::StoichiometricTerm>{{a_id, 1}, {b_id, 1}},
        std::vector<mls::StoichiometricTerm>{{ab_id, 1}},
        mls::Energy::from_raw(5));
    return WorldFixture{
        a,
        b,
        a_id,
        b_id,
        ab_id,
        std::move(association),
        mls::World(std::move(elements), std::move(compounds), config),
    };
}

[[nodiscard]] mls::MaterialSeed mixed_seed(
    const WorldFixture& fixture,
    mls::Length x,
    mls::MoleculeCount count = 1'000) {
    return mls::MaterialSeed{
        .position = {
            x + mls::Length::from_raw(500'000),
            mls::Length::from_raw(500'000),
            mls::Length::from_raw(500'000)},
        .momentum = {},
        .composition = mls::CompoundMixture{{fixture.a_id, count}, {fixture.b_id, count}},
        .stored_energy = mls::Energy::from_raw(10'000'000),
        .thermal_energy = mls::Energy::from_raw(10'000'000),
    };
}

[[nodiscard]] std::uint64_t observe_from_camera(const mls::World& world, CameraProbe camera) {
    // This deliberately arbitrary read model proves that view state stays on the
    // observer side of the API. It has no non-const path back into World.
    auto observation = world.physical_state_hash();
    for (const auto& [coordinate, cell] : world.grid().cells()) {
        const auto distance =
            (coordinate.x - camera.x) * (coordinate.x - camera.x) +
            (coordinate.y - camera.y) * (coordinate.y - camera.y) +
            (coordinate.z - camera.z) * (coordinate.z - camera.z);
        if (distance <= camera.field_of_view * camera.field_of_view) {
            observation ^= static_cast<std::uint64_t>(cell.totals.packet_count) +
                           UINT64_C(0x9e3779b97f4a7c15) + (observation << 6U) +
                           (observation >> 2U);
        }
    }
    return observation;
}

} // namespace

MLS_TEST("G0.G1/conservative_pair_transfer_and_nonnegativity") {
    mls::test::SplitMix64 rng(validation_seed);
    for (int iteration = 0; iteration < 100'000; ++iteration) {
        const auto first_raw = rng.integer(0, 1'000'000);
        const auto second_raw = rng.integer(0, 1'000'000);
        const auto transfer_raw = rng.integer(0, first_raw);
        const auto first = mls::Mass::from_raw(first_raw);
        const auto second = mls::Mass::from_raw(second_raw);
        const auto transfer = mls::Mass::from_raw(transfer_raw);
        const auto next_first = first - transfer;
        const auto next_second = second + transfer;
        MLS_REQUIRE(mls::is_nonnegative(next_first));
        MLS_REQUIRE(mls::is_nonnegative(next_second));
        MLS_REQUIRE_EQ(next_first + next_second, first + second);
    }

    mls::ElementInventory inventory{{mls::ElementId{0}, 5}};
    MLS_REQUIRE_THROWS(std::domain_error, inventory.remove(mls::ElementId{0}, 6));
    MLS_REQUIRE_THROWS(std::invalid_argument, inventory.add(mls::ElementId{0}, -1));
    MLS_REQUIRE_EQ(inventory.amount(mls::ElementId{0}), 5);
}

MLS_TEST("G0.G1.G2/equal_and_opposite_momentum_exchange") {
    mls::test::SplitMix64 rng(validation_seed ^ UINT64_C(0x9e3779b97f4a7c15));
    for (int iteration = 0; iteration < 100'000; ++iteration) {
        const auto random_vector = [&rng](std::int64_t magnitude) {
            return mls::Momentum3{
                mls::Momentum::from_raw(rng.integer(-magnitude, magnitude)),
                mls::Momentum::from_raw(rng.integer(-magnitude, magnitude)),
                mls::Momentum::from_raw(rng.integer(-magnitude, magnitude)),
            };
        };
        const auto first = random_vector(1'000'000);
        const auto second = random_vector(1'000'000);
        const auto impulse = random_vector(10'000);
        const auto next_first = first + impulse;
        const auto next_second = second - impulse;
        MLS_REQUIRE_EQ(next_first + next_second, first + second);
    }
}

MLS_TEST("G0.G1/packet_heat_transfer_closes_energy_and_rejects_overdraw") {
    ChemistryFixture fixture;
    mls::PacketStore packets;
    const auto first = packets.create(packet_state(fixture, {}, mls::Energy::from_raw(20'000)));
    const auto second = packets.create(packet_state(fixture, {}, mls::Energy::from_raw(30'000)));
    const auto before = packets.snapshot(first).total_energy() + packets.snapshot(second).total_energy();
    packets.transfer_heat(first, second, mls::Energy::from_raw(12'345), 1);
    const auto after = packets.snapshot(first).total_energy() + packets.snapshot(second).total_energy();
    MLS_REQUIRE_EQ(after, before);
    MLS_REQUIRE_EQ(packets.snapshot(first).thermal_energy, mls::Energy::from_raw(7'655));
    MLS_REQUIRE_EQ(packets.snapshot(second).thermal_energy, mls::Energy::from_raw(42'345));
    MLS_REQUIRE_THROWS(
        std::domain_error,
        packets.transfer_heat(first, second, mls::Energy::from_raw(7'656), 2));
    MLS_REQUIRE_EQ(packets.snapshot(first).total_energy() + packets.snapshot(second).total_energy(), after);
}

MLS_TEST("G0.G1.G3/unified_ledger_closes_internal_and_boundary_energy") {
    ChemistryFixture fixture;
    mls::PacketStore packets;
    const auto first = packets.create(packet_state(fixture, {}, mls::Energy::from_raw(20'000)));
    const auto second = packets.create(packet_state(fixture, {}, mls::Energy::from_raw(30'000)));
    mls::SparseVoxelGrid grid(mls::Length::from_raw(10));
    grid.rebuild(packets);
    mls::ConservationLedger ledger(grid.totals());
    MLS_REQUIRE(ledger.audit(grid.totals()).ok());

    packets.transfer_heat(first, second, mls::Energy::from_raw(12'345), 1);
    grid.rebuild(packets);
    MLS_REQUIRE(ledger.audit(grid.totals()).ok());

    const auto boundary_energy = mls::Energy::from_raw(777);
    packets.adjust_boundary_energy(first, mls::EnergyChannel::thermal, boundary_energy, 2);
    ledger.record_boundary_energy(boundary_energy);
    grid.rebuild(packets);
    MLS_REQUIRE(ledger.audit(grid.totals()).ok());

    packets.adjust_boundary_energy(second, mls::EnergyChannel::stored, -mls::Energy::from_raw(333), 3);
    ledger.record_boundary_energy(-mls::Energy::from_raw(333));
    grid.rebuild(packets);
    MLS_REQUIRE(ledger.audit(grid.totals()).ok());

    auto corrupted = grid.totals();
    corrupted.thermal_energy += mls::Energy::from_raw(1);
    const auto report = ledger.audit(corrupted);
    MLS_REQUIRE(!report.ok());
    MLS_REQUIRE(!report.energy_conserved);
    MLS_REQUIRE_EQ(report.energy_error, mls::Energy::from_raw(1));

    auto invalid_boundary = mls::ExtensiveTotals{};
    invalid_boundary.mass = mls::Mass::from_raw(-1);
    const auto boundary_before = ledger.boundary();
    MLS_REQUIRE_THROWS(
        std::invalid_argument, ledger.record_boundary_ingress(invalid_boundary));
    MLS_REQUIRE_THROWS(
        std::invalid_argument, ledger.record_boundary_egress(invalid_boundary));
    MLS_REQUIRE_EQ(ledger.boundary(), boundary_before);
}

MLS_TEST("G0.G1.G2/packet_momentum_exchange_closes_momentum_and_energy") {
    ChemistryFixture fixture;
    mls::test::SplitMix64 rng(validation_seed ^ UINT64_C(0x94d049bb133111eb));
    for (int iteration = 0; iteration < 10'000; ++iteration) {
        const auto vector = [&rng](std::int64_t magnitude) {
            return mls::Momentum3{
                mls::Momentum::from_raw(rng.integer(-magnitude, magnitude)),
                mls::Momentum::from_raw(rng.integer(-magnitude, magnitude)),
                mls::Momentum::from_raw(rng.integer(-magnitude, magnitude)),
            };
        };
        mls::PacketStore packets;
        const auto first = packets.create(packet_state(
            fixture, vector(100), mls::Energy::from_raw(10'000), mls::Energy::from_raw(1'000'000)));
        const auto second = packets.create(packet_state(
            fixture, vector(100), mls::Energy::from_raw(10'000), mls::Energy::from_raw(1'000'000)));
        const auto before_first = packets.snapshot(first);
        const auto before_second = packets.snapshot(second);
        const auto before_momentum = before_first.momentum + before_second.momentum;
        const auto before_energy = before_first.total_energy() + before_second.total_energy();
        packets.exchange_momentum(first, second, vector(20), first, second, 1);
        const auto after_first = packets.snapshot(first);
        const auto after_second = packets.snapshot(second);
        MLS_REQUIRE_EQ(after_first.momentum + after_second.momentum, before_momentum);
        MLS_REQUIRE_EQ(after_first.total_energy() + after_second.total_energy(), before_energy);
        MLS_REQUIRE(mls::is_nonnegative(after_first.stored_energy));
        MLS_REQUIRE(mls::is_nonnegative(after_second.thermal_energy));
    }
}

MLS_TEST("G0/fixed_point_arithmetic_rejects_overflow") {
    const auto maximum = mls::Energy::from_raw(std::numeric_limits<mls::Scalar>::max());
    const auto minimum = mls::Energy::from_raw(std::numeric_limits<mls::Scalar>::min());
    MLS_REQUIRE_THROWS(std::overflow_error, maximum + mls::Energy::from_raw(1));
    MLS_REQUIRE_THROWS(std::overflow_error, minimum - mls::Energy::from_raw(1));
    MLS_REQUIRE_THROWS(std::overflow_error, -minimum);
    MLS_REQUIRE_THROWS(std::domain_error, maximum / 0);

    mls::Momentum3 vector{
        {}, mls::Momentum::from_raw(std::numeric_limits<mls::Scalar>::max()), {}};
    const auto vector_before = vector;
    const mls::Momentum3 vector_delta{
        mls::Momentum::from_raw(1), mls::Momentum::from_raw(1), {}};
    MLS_REQUIRE_THROWS(std::overflow_error, vector += vector_delta);
    MLS_REQUIRE_EQ(vector, vector_before);

    mls::ExtensiveTotals totals;
    totals.elements.add(mls::ElementId{0}, 1);
    totals.momentum = vector_before;
    const auto totals_before = totals;
    mls::ExtensiveTotals delta;
    delta.elements.add(mls::ElementId{1}, 1);
    delta.momentum = vector_delta;
    MLS_REQUIRE_THROWS(std::overflow_error, totals.add(delta));
    MLS_REQUIRE_EQ(totals, totals_before);
}

MLS_TEST("G0.G4/stoichiometric_balance_and_random_extents") {
    ChemistryFixture fixture;
    const mls::ReactionDefinition balanced(
        std::vector<mls::StoichiometricTerm>{{fixture.a_id, 1}, {fixture.b_id, 1}},
        std::vector<mls::StoichiometricTerm>{{fixture.ab_id, 1}});
    const mls::ReactionDefinition unbalanced(
        std::vector<mls::StoichiometricTerm>{{fixture.a_id, 1}},
        std::vector<mls::StoichiometricTerm>{{fixture.ab_id, 1}});
    MLS_REQUIRE(balanced.is_balanced(fixture.compounds));
    MLS_REQUIRE(!unbalanced.is_balanced(fixture.compounds));
    MLS_REQUIRE(balanced.element_delta(fixture.compounds).empty());

    mls::test::SplitMix64 rng(validation_seed ^ UINT64_C(0xd1b54a32d192ed03));
    for (int iteration = 0; iteration < 100'000; ++iteration) {
        const auto a_count = rng.integer(0, 10'000);
        const auto b_count = rng.integer(0, 10'000);
        const auto ab_count = rng.integer(0, 10'000);
        mls::CompoundMixture mixture{
            {fixture.a_id, a_count},
            {fixture.b_id, b_count},
            {fixture.ab_id, ab_count},
        };
        const auto before = mls::inventory_of(mixture, fixture.compounds);
        const auto maximum_extent = balanced.maximum_extent(mixture);
        const auto extent = rng.integer(0, maximum_extent);
        MLS_REQUIRE(balanced.can_apply(mixture, extent));
        balanced.apply(mixture, extent);
        MLS_REQUIRE_EQ(mls::inventory_of(mixture, fixture.compounds), before);
        MLS_REQUIRE(mixture.amount(fixture.a_id) >= 0);
        MLS_REQUIRE(mixture.amount(fixture.b_id) >= 0);
        MLS_REQUIRE(mixture.amount(fixture.ab_id) >= 0);
    }
}

MLS_TEST("G4/compound_identity_is_structural_not_named_material") {
    const mls::ElementId a{2};
    const mls::ElementId b{9};
    const mls::CompoundGraph first(
        std::vector<mls::ElementId>{a, b, a},
        std::vector<mls::Bond>{{1, 0, 1}, {2, 1, 2}});
    const mls::CompoundGraph same_structure(
        std::vector<mls::ElementId>{a, b, a},
        std::vector<mls::Bond>{{1, 2, 2}, {0, 1, 1}});
    const mls::CompoundGraph different_topology(
        std::vector<mls::ElementId>{a, b, a},
        std::vector<mls::Bond>{{0, 2, 1}, {1, 2, 2}});
    MLS_REQUIRE_EQ(first, same_structure);
    MLS_REQUIRE_EQ(first.structural_hash(), same_structure.structural_hash());
    MLS_REQUIRE(first.structural_hash() != different_topology.structural_hash());
}

MLS_TEST("G5/proper_cubic_rotation_equivariance_scaffold") {
    const auto rotations = proper_cube_rotations();
    MLS_REQUIRE_EQ(rotations.size(), std::size_t{24});
    mls::test::SplitMix64 rng(validation_seed ^ UINT64_C(0xe7037ed1a0b428db));
    for (int iteration = 0; iteration < 10'000; ++iteration) {
        const mls::Momentum3 displacement{
            mls::Momentum::from_raw(rng.integer(-10'000, 10'000)),
            mls::Momentum::from_raw(rng.integer(-10'000, 10'000)),
            mls::Momentum::from_raw(rng.integer(-10'000, 10'000)),
        };
        const auto coefficient = rng.integer(-1'000, 1'000);
        const auto& rotation = rotations[static_cast<std::size_t>(rng.below(rotations.size()))];
        const auto impulse = mls::Momentum3{
            displacement.x * coefficient,
            displacement.y * coefficient,
            displacement.z * coefficient,
        };
        const auto rotated_displacement = rotate(rotation, displacement);
        const auto rotated_impulse = rotate(rotation, impulse);
        const auto recomputed_impulse = mls::Momentum3{
            rotated_displacement.x * coefficient,
            rotated_displacement.y * coefficient,
            rotated_displacement.z * coefficient,
        };
        MLS_REQUIRE_EQ(rotated_impulse, recomputed_impulse);
        MLS_REQUIRE_EQ(squared_norm(rotated_displacement), squared_norm(displacement));
    }
}

MLS_TEST("G1/sparse_grid_hierarchical_extensive_aggregation") {
    ChemistryFixture fixture;
    mls::PacketStore packets;
    mls::test::SplitMix64 rng(validation_seed ^ UINT64_C(0xa0761d6478bd642f));
    constexpr int packet_count = 25'000;
    for (int index = 0; index < packet_count; ++index) {
        auto initial = packet_state(
            fixture,
            mls::Momentum3{
                mls::Momentum::from_raw(rng.integer(-20, 20)),
                mls::Momentum::from_raw(rng.integer(-20, 20)),
                mls::Momentum::from_raw(rng.integer(-20, 20)),
            },
            mls::Energy::from_raw(rng.integer(0, 10'000)),
            mls::Energy::from_raw(rng.integer(0, 10'000)));
        initial.position = {
            mls::Length::from_raw(rng.integer(-1'000'000, 1'000'000)),
            mls::Length::from_raw(rng.integer(-1'000'000, 1'000'000)),
            mls::Length::from_raw(rng.integer(-1'000'000, 1'000'000)),
        };
        static_cast<void>(packets.create(std::move(initial)));
    }

    mls::ExtensiveTotals direct;
    for (const auto& packet : packets.snapshots()) {
        direct.add(packet);
    }
    mls::SparseVoxelGrid grid(mls::Length::from_raw(64));
    grid.rebuild(packets);
    MLS_REQUIRE_EQ(grid.totals(), direct);
    MLS_REQUIRE_EQ(grid.totals().packet_count, static_cast<std::size_t>(packet_count));

    std::vector<mls::VoxelCoord> coordinates;
    coordinates.reserve(grid.cells().size());
    mls::ExtensiveTotals by_cell;
    for (const auto& [coordinate, cell] : grid.cells()) {
        coordinates.push_back(coordinate);
        by_cell.add(cell.totals);
        MLS_REQUIRE_EQ(cell.packets.size(), cell.totals.packet_count);
    }
    MLS_REQUIRE_EQ(by_cell, direct);
    MLS_REQUIRE_EQ(grid.aggregate(coordinates), direct);
    const std::array<mls::VoxelCoord, 2> duplicate_coordinates{
        coordinates.front(), coordinates.front()};
    MLS_REQUIRE_THROWS(std::invalid_argument, grid.aggregate(duplicate_coordinates));

    MLS_REQUIRE_EQ(
        grid.coordinate_for({mls::Length::from_raw(-1), {}, {}}),
        (mls::VoxelCoord{-1, 0, 0}));
    MLS_REQUIRE_EQ(
        grid.coordinate_for({mls::Length::from_raw(-64), {}, {}}),
        (mls::VoxelCoord{-1, 0, 0}));
    MLS_REQUIRE_EQ(
        grid.coordinate_for({mls::Length::from_raw(-65), {}, {}}),
        (mls::VoxelCoord{-2, 0, 0}));
}

MLS_TEST("G7/coarse_graining_false_affordance_counterexample") {
    struct Cell final {
        std::int64_t a;
        std::int64_t b;
    };
    const std::array<Cell, 2> fine{{{1, 0}, {0, 1}}};
    const auto can_react = [](const Cell& cell) { return cell.a > 0 && cell.b > 0; };
    MLS_REQUIRE(!can_react(fine[0]));
    MLS_REQUIRE(!can_react(fine[1]));
    const Cell coarse{
        fine[0].a + fine[1].a,
        fine[0].b + fine[1].b,
    };
    MLS_REQUIRE_EQ(coarse.a, 1);
    MLS_REQUIRE_EQ(coarse.b, 1);
    MLS_REQUIRE(can_react(coarse));
}

MLS_TEST("hard-contract/camera_and_renderer_invariance") {
    auto audit_config = mls::WorldConfig{};
    audit_config.voxel_edge = mls::Length::from_raw(1'000'000);
    audit_config.packet_history_limit = 128;
    audit_config.audit_after_each_operation = true;
    auto lean_config = audit_config;
    lean_config.packet_history_limit = 0;
    lean_config.audit_after_each_operation = false;

    auto observed = make_world(audit_config);
    auto renderer_disabled = make_world(lean_config);
    const auto observed_first = observed.world.introduce_material_from_boundary(
        mixed_seed(observed, mls::Length::from_raw(0)));
    const auto observed_second = observed.world.introduce_material_from_boundary(
        mixed_seed(observed, mls::Length::from_raw(100)));
    const auto disabled_first = renderer_disabled.world.introduce_material_from_boundary(
        mixed_seed(renderer_disabled, mls::Length::from_raw(0)));
    const auto disabled_second = renderer_disabled.world.introduce_material_from_boundary(
        mixed_seed(renderer_disabled, mls::Length::from_raw(100)));
    MLS_REQUIRE_EQ(observed.world.physical_state_hash(), renderer_disabled.world.physical_state_hash());

    mls::test::SplitMix64 camera_rng(validation_seed ^ UINT64_C(0x8ebc6af09c88c6e3));
    std::uint64_t observation_sink = 0;
    for (int iteration = 0; iteration < 256; ++iteration) {
        const CameraProbe camera{
            camera_rng.integer(-10'000, 10'000),
            camera_rng.integer(-10'000, 10'000),
            camera_rng.integer(-10'000, 10'000),
            camera_rng.integer(1, 179),
        };
        observation_sink ^= observe_from_camera(observed.world, camera);

        const auto heat = mls::Energy::from_raw((iteration % 7) + 1);
        if (iteration % 2 == 0) {
            observed.world.transfer_heat(observed_first, observed_second, heat);
            renderer_disabled.world.transfer_heat(disabled_first, disabled_second, heat);
        } else {
            observed.world.transfer_heat(observed_second, observed_first, heat);
            renderer_disabled.world.transfer_heat(disabled_second, disabled_first, heat);
        }
        observed.world.convert_energy(
            observed_first, mls::EnergyChannel::stored, mls::EnergyChannel::thermal, mls::Energy::from_raw(1));
        renderer_disabled.world.convert_energy(
            disabled_first, mls::EnergyChannel::stored, mls::EnergyChannel::thermal, mls::Energy::from_raw(1));
        if (iteration % 32 == 0) {
            observed.world.apply_reaction(observed_first, observed.association, 1);
            renderer_disabled.world.apply_reaction(disabled_first, renderer_disabled.association, 1);
        }
        observed.world.step();
        renderer_disabled.world.step();
        MLS_REQUIRE_EQ(observed.world.physical_state_hash(), renderer_disabled.world.physical_state_hash());
        MLS_REQUIRE(observed.world.audit().ok());
        MLS_REQUIRE(renderer_disabled.world.audit().ok());
    }
    // Prevent an optimizing build from proving that observer work is unused.
    MLS_REQUIRE(observation_sink != 0 || observed.world.grid().cells().empty());
}

MLS_TEST("hard-contract/deterministic_replay_and_state_hash") {
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(1'000'000);
    config.packet_history_limit = 16;
    auto first = make_world(config);
    auto replay = make_world(config);
    const auto first_a = first.world.introduce_material_from_boundary(
        mixed_seed(first, mls::Length::from_raw(0)));
    const auto first_b = first.world.introduce_material_from_boundary(
        mixed_seed(first, mls::Length::from_raw(100)));
    const auto replay_a = replay.world.introduce_material_from_boundary(
        mixed_seed(replay, mls::Length::from_raw(0)));
    const auto replay_b = replay.world.introduce_material_from_boundary(
        mixed_seed(replay, mls::Length::from_raw(100)));

    mls::test::SplitMix64 events(validation_seed ^ UINT64_C(0x589965cc75374cc3));
    for (int iteration = 0; iteration < 512; ++iteration) {
        const auto heat = mls::Energy::from_raw(events.integer(0, 20));
        const auto impulse = mls::Momentum3{
            mls::Momentum::from_raw(events.integer(-3, 3)),
            mls::Momentum::from_raw(events.integer(-3, 3)),
            mls::Momentum::from_raw(events.integer(-3, 3)),
        };
        if (iteration % 2 == 0) {
            first.world.transfer_heat(first_a, first_b, heat);
            replay.world.transfer_heat(replay_a, replay_b, heat);
        } else {
            first.world.transfer_heat(first_b, first_a, heat);
            replay.world.transfer_heat(replay_b, replay_a, heat);
        }
        first.world.exchange_momentum(first_a, first_b, impulse, first_a, first_b);
        replay.world.exchange_momentum(replay_a, replay_b, impulse, replay_a, replay_b);
        if (iteration % 64 == 0) {
            first.world.apply_reaction(first_a, first.association, 1);
            replay.world.apply_reaction(replay_a, replay.association, 1);
        }
        if (iteration % 17 == 0) {
            const auto ingress = mls::Energy::from_raw(11);
            first.world.exchange_energy_with_boundary(first_b, mls::EnergyChannel::stored, ingress);
            replay.world.exchange_energy_with_boundary(replay_b, mls::EnergyChannel::stored, ingress);
        }
        first.world.step();
        replay.world.step();
        MLS_REQUIRE_EQ(first.world.physical_state_hash(), replay.world.physical_state_hash());
        MLS_REQUIRE_EQ(first.world.totals(), replay.world.totals());
        MLS_REQUIRE_EQ(first.world.ledger().baseline(), replay.world.ledger().baseline());
        MLS_REQUIRE_EQ(first.world.ledger().boundary(), replay.world.ledger().boundary());
        MLS_REQUIRE(first.world.audit().ok());
        MLS_REQUIRE(replay.world.audit().ok());
    }
}

MLS_TEST("adversarial/unauthorized_material_duplication_and_loss_are_detected") {
    ChemistryFixture fixture;

    mls::PacketStore duplicated_packets;
    static_cast<void>(duplicated_packets.create(packet_state(fixture)));
    mls::SparseVoxelGrid duplicated_grid(mls::Length::from_raw(10));
    duplicated_grid.rebuild(duplicated_packets);
    mls::ConservationLedger duplication_ledger(duplicated_grid.totals());
    static_cast<void>(duplicated_packets.create(packet_state(fixture)));
    duplicated_grid.rebuild(duplicated_packets);
    const auto duplication_report = duplication_ledger.audit(duplicated_grid.totals());
    MLS_REQUIRE(!duplication_report.ok());
    MLS_REQUIRE(!duplication_report.elements_conserved);
    MLS_REQUIRE(!duplication_report.mass_conserved);
    MLS_REQUIRE(!duplication_report.energy_conserved);

    mls::PacketStore lost_packets;
    const auto doomed = lost_packets.create(packet_state(fixture));
    static_cast<void>(lost_packets.create(packet_state(fixture)));
    mls::SparseVoxelGrid lost_grid(mls::Length::from_raw(10));
    lost_grid.rebuild(lost_packets);
    mls::ConservationLedger loss_ledger(lost_grid.totals());
    lost_packets.erase(doomed, 1);
    lost_grid.rebuild(lost_packets);
    const auto loss_report = loss_ledger.audit(lost_grid.totals());
    MLS_REQUIRE(!loss_report.ok());
    MLS_REQUIRE(!loss_report.elements_conserved);
    MLS_REQUIRE(!loss_report.mass_conserved);
    MLS_REQUIRE(!loss_report.energy_conserved);
}

MLS_TEST("adversarial/all_boundary_channels_round_trip_through_one_ledger") {
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(1'000'000);
    config.packet_history_limit = 16;
    auto fixture = make_world(config);
    const auto packet = fixture.world.introduce_material_from_boundary(
        mixed_seed(fixture, mls::Length::from_raw(0)));
    MLS_REQUIRE(fixture.world.audit().ok());

    fixture.world.exchange_energy_with_boundary(
        packet, mls::EnergyChannel::thermal, -mls::Energy::from_raw(100));
    fixture.world.exchange_energy_with_boundary(
        packet, mls::EnergyChannel::stored, mls::Energy::from_raw(200));
    fixture.world.exchange_momentum_with_boundary(
        packet,
        mls::Momentum3{
            mls::Momentum::from_raw(10'000),
            mls::Momentum::from_raw(-20'000),
            mls::Momentum::from_raw(30'000)});
    MLS_REQUIRE(fixture.world.audit().ok());
    MLS_REQUIRE(!fixture.world.ledger().boundary().element_net.empty());
    MLS_REQUIRE(fixture.world.ledger().boundary().mass_net != mls::Mass{});
    MLS_REQUIRE(fixture.world.ledger().boundary().momentum_net != mls::Momentum3{});

    fixture.world.remove_material_to_boundary(packet);
    MLS_REQUIRE_EQ(fixture.world.totals(), mls::ExtensiveTotals{});
    MLS_REQUIRE(fixture.world.audit().ok());
    MLS_REQUIRE_THROWS(std::out_of_range, fixture.world.packets().history(packet));
    const auto& removed_history = fixture.world.packets().debug_history(packet.id);
    MLS_REQUIRE(!removed_history.empty());
    MLS_REQUIRE_EQ(removed_history.back().kind, mls::PacketEventKind::removed);
    MLS_REQUIRE(fixture.world.ledger().boundary().element_net.empty());
    MLS_REQUIRE_EQ(fixture.world.ledger().boundary().mass_net, mls::Mass{});
    MLS_REQUIRE_EQ(fixture.world.ledger().boundary().energy_net, mls::Energy{});
    MLS_REQUIRE_EQ(fixture.world.ledger().boundary().momentum_net, mls::Momentum3{});
}

MLS_TEST("adversarial/zero_state_and_zero_tick_are_stable") {
    auto first = make_world();
    auto second = make_world();
    MLS_REQUIRE(first.world.audit().ok());
    MLS_REQUIRE_EQ(first.world.totals(), mls::ExtensiveTotals{});
    MLS_REQUIRE(first.world.grid().cells().empty());
    MLS_REQUIRE_EQ(first.world.physical_state_hash(), second.world.physical_state_hash());
    const auto before = first.world.physical_state_hash();
    first.world.step(0);
    first.world.establish_current_state_as_baseline();
    MLS_REQUIRE_EQ(first.world.physical_state_hash(), before);
    MLS_REQUIRE(first.world.audit().ok());
}

MLS_TEST("adversarial/failed_step_overflow_preserves_tick_and_state") {
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(1'000'000);
    auto fixture = make_world(config);
    auto seed = mixed_seed(fixture, mls::Length::from_raw(0), 1);
    seed.position = {
        mls::Length::from_raw(std::numeric_limits<mls::Scalar>::max()), {}, {}};
    seed.momentum = {mls::Momentum::from_raw(30), {}, {}};
    static_cast<void>(fixture.world.introduce_material_from_boundary(seed));

    const auto tick_before = fixture.world.tick();
    const auto hash_before = fixture.world.physical_state_hash();
    const auto totals_before = fixture.world.totals();
    MLS_REQUIRE_THROWS(std::overflow_error, fixture.world.step());
    MLS_REQUIRE_EQ(fixture.world.tick(), tick_before);
    MLS_REQUIRE_EQ(fixture.world.physical_state_hash(), hash_before);
    MLS_REQUIRE_EQ(fixture.world.totals(), totals_before);
    MLS_REQUIRE(fixture.world.audit().ok());
}

MLS_TEST("adversarial/failed_boundary_ingress_preserves_world_state") {
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(1'000'000);
    auto fixture = make_world(config);
    auto near_limit = mixed_seed(fixture, mls::Length::from_raw(0), 1);
    near_limit.stored_energy = mls::Energy::from_raw(
        std::numeric_limits<mls::Scalar>::max() - 250);
    near_limit.thermal_energy = {};
    static_cast<void>(fixture.world.introduce_material_from_boundary(near_limit));
    fixture.world.establish_current_state_as_baseline();

    const auto hash_before = fixture.world.physical_state_hash();
    const auto totals_before = fixture.world.totals();
    const auto packet_count_before = fixture.world.packets().alive_count();
    const auto boundary_before = fixture.world.ledger().boundary();
    auto additional = mixed_seed(fixture, mls::Length::from_raw(10), 1);
    MLS_REQUIRE_THROWS(
        std::overflow_error, fixture.world.introduce_material_from_boundary(additional));
    MLS_REQUIRE_EQ(fixture.world.physical_state_hash(), hash_before);
    MLS_REQUIRE_EQ(fixture.world.totals(), totals_before);
    MLS_REQUIRE_EQ(fixture.world.packets().alive_count(), packet_count_before);
    MLS_REQUIRE_EQ(fixture.world.ledger().boundary(), boundary_before);
    MLS_REQUIRE(fixture.world.audit().ok());
}

MLS_TEST("adversarial/independent_update_order_commutes") {
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(1'000'000);
    auto forward = make_world(config);
    auto reverse = make_world(config);
    std::array<mls::PacketHandle, 4> forward_packets{};
    std::array<mls::PacketHandle, 4> reverse_packets{};
    for (std::size_t index = 0; index < forward_packets.size(); ++index) {
        const auto offset = mls::Length::from_raw(static_cast<mls::Scalar>(index) * 100);
        forward_packets[index] = forward.world.introduce_material_from_boundary(mixed_seed(forward, offset));
        reverse_packets[index] = reverse.world.introduce_material_from_boundary(mixed_seed(reverse, offset));
    }

    forward.world.transfer_heat(forward_packets[0], forward_packets[1], mls::Energy::from_raw(123));
    forward.world.convert_energy(
        forward_packets[2], mls::EnergyChannel::stored, mls::EnergyChannel::thermal, mls::Energy::from_raw(456));
    reverse.world.convert_energy(
        reverse_packets[2], mls::EnergyChannel::stored, mls::EnergyChannel::thermal, mls::Energy::from_raw(456));
    reverse.world.transfer_heat(reverse_packets[0], reverse_packets[1], mls::Energy::from_raw(123));
    MLS_REQUIRE_EQ(forward.world.physical_state_hash(), reverse.world.physical_state_hash());
    MLS_REQUIRE_EQ(forward.world.totals(), reverse.world.totals());
    MLS_REQUIRE(forward.world.audit().ok());
    MLS_REQUIRE(reverse.world.audit().ok());
}

MLS_TEST("adversarial/interacting_update_order_dependence_is_explicit") {
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(1'000'000);
    auto heat_first = make_world(config);
    auto reaction_first = make_world(config);

    const auto make_target = [](const WorldFixture& fixture) {
        return mls::MaterialSeed{
            .position = {
                mls::Length::from_raw(500'000),
                mls::Length::from_raw(500'000),
                mls::Length::from_raw(500'000)},
            .momentum = {},
            .composition = mls::CompoundMixture{{fixture.a_id, 1}, {fixture.b_id, 1}},
            .stored_energy = {},
            .thermal_energy = {},
        };
    };
    const auto make_donor = [](const WorldFixture& fixture) {
        return mls::MaterialSeed{
            .position = {
                mls::Length::from_raw(500'010),
                mls::Length::from_raw(500'000),
                mls::Length::from_raw(500'000)},
            .momentum = {},
            .composition = mls::CompoundMixture{{fixture.a_id, 1}},
            .stored_energy = {},
            .thermal_energy = mls::Energy::from_raw(10),
        };
    };

    const auto heat_target =
        heat_first.world.introduce_material_from_boundary(make_target(heat_first));
    const auto heat_donor =
        heat_first.world.introduce_material_from_boundary(make_donor(heat_first));
    const auto reaction_target =
        reaction_first.world.introduce_material_from_boundary(make_target(reaction_first));
    const auto reaction_donor =
        reaction_first.world.introduce_material_from_boundary(make_donor(reaction_first));

    heat_first.world.transfer_heat(
        heat_donor, heat_target, mls::Energy::from_raw(5));
    heat_first.world.apply_reaction(heat_target, heat_first.association, 1);
    MLS_REQUIRE_THROWS(
        std::domain_error,
        reaction_first.world.apply_reaction(
            reaction_target, reaction_first.association, 1));
    reaction_first.world.transfer_heat(
        reaction_donor, reaction_target, mls::Energy::from_raw(5));

    MLS_REQUIRE(
        heat_first.world.physical_state_hash() != reaction_first.world.physical_state_hash());
    MLS_REQUIRE_EQ(
        heat_first.world.packets().snapshot(heat_target).composition.amount(heat_first.ab_id),
        1);
    MLS_REQUIRE_EQ(
        reaction_first.world.packets().snapshot(reaction_target).composition.amount(
            reaction_first.ab_id),
        0);
    MLS_REQUIRE(heat_first.world.audit().ok());
    MLS_REQUIRE(reaction_first.world.audit().ok());
}

MLS_TEST("adversarial/uniform_grid_translation_preserves_extensive_outcomes") {
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(1'000);
    auto origin = make_world(config);
    auto translated = make_world(config);
    auto origin_first_seed = mixed_seed(origin, mls::Length::from_raw(0));
    auto origin_second_seed = mixed_seed(origin, mls::Length::from_raw(10));
    // Shift by a non-integer number of voxel widths so one setup places both
    // packets in one cell while the translated setup straddles a cell face.
    auto translated_first_seed = mixed_seed(translated, mls::Length::from_raw(20'995));
    auto translated_second_seed = mixed_seed(translated, mls::Length::from_raw(21'005));
    const auto origin_first = origin.world.introduce_material_from_boundary(origin_first_seed);
    const auto origin_second = origin.world.introduce_material_from_boundary(origin_second_seed);
    const auto translated_first = translated.world.introduce_material_from_boundary(translated_first_seed);
    const auto translated_second = translated.world.introduce_material_from_boundary(translated_second_seed);

    const mls::Momentum3 impulse{
        mls::Momentum::from_raw(3'000),
        mls::Momentum::from_raw(-2'000),
        mls::Momentum::from_raw(1'000)};
    origin.world.exchange_momentum(origin_first, origin_second, impulse, origin_first, origin_second);
    translated.world.exchange_momentum(
        translated_first, translated_second, impulse, translated_first, translated_second);
    origin.world.transfer_heat(origin_first, origin_second, mls::Energy::from_raw(321));
    translated.world.transfer_heat(translated_first, translated_second, mls::Energy::from_raw(321));
    origin.world.step(100);
    translated.world.step(100);
    MLS_REQUIRE_EQ(origin.world.totals(), translated.world.totals());
    MLS_REQUIRE(origin.world.audit().ok());
    MLS_REQUIRE(translated.world.audit().ok());
    // Absolute positions are physical state, so translated worlds need not hash equally.
    MLS_REQUIRE(origin.world.physical_state_hash() != translated.world.physical_state_hash());
}

MLS_TEST("G5/adversarial_rational_off_axis_rotation_preserves_ballistic_invariants") {
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(1'000'000);
    auto axis_aligned = make_world(config);
    auto off_axis = make_world(config);
    auto axis_first_seed = mixed_seed(axis_aligned, mls::Length::from_raw(0));
    auto axis_second_seed = mixed_seed(axis_aligned, mls::Length::from_raw(50));
    auto rotated_first_seed = mixed_seed(off_axis, mls::Length::from_raw(0));
    auto rotated_second_seed = mixed_seed(off_axis, mls::Length::from_raw(0));
    rotated_second_seed.position.x += mls::Length::from_raw(30);
    rotated_second_seed.position.y += mls::Length::from_raw(40);
    const auto axis_first =
        axis_aligned.world.introduce_material_from_boundary(axis_first_seed);
    const auto axis_second =
        axis_aligned.world.introduce_material_from_boundary(axis_second_seed);
    const auto rotated_first =
        off_axis.world.introduce_material_from_boundary(rotated_first_seed);
    const auto rotated_second =
        off_axis.world.introduce_material_from_boundary(rotated_second_seed);

    axis_aligned.world.exchange_momentum(
        axis_first,
        axis_second,
        {mls::Momentum::from_raw(30'000), {}, {}},
        axis_first,
        axis_second);
    off_axis.world.exchange_momentum(
        rotated_first,
        rotated_second,
        {mls::Momentum::from_raw(18'000), mls::Momentum::from_raw(24'000), {}},
        rotated_first,
        rotated_second);
    axis_aligned.world.step(20);
    off_axis.world.step(20);
    const auto axis_first_state = axis_aligned.world.packets().snapshot(axis_first);
    const auto axis_second_state = axis_aligned.world.packets().snapshot(axis_second);
    const auto rotated_first_state = off_axis.world.packets().snapshot(rotated_first);
    const auto rotated_second_state = off_axis.world.packets().snapshot(rotated_second);
    MLS_REQUIRE_EQ(
        rotated_first_state.momentum.x,
        mls::Momentum::from_raw(axis_first_state.momentum.x.raw() * 3 / 5));
    MLS_REQUIRE_EQ(
        rotated_first_state.momentum.y,
        mls::Momentum::from_raw(axis_first_state.momentum.x.raw() * 4 / 5));
    MLS_REQUIRE_EQ(
        rotated_second_state.momentum.x,
        mls::Momentum::from_raw(axis_second_state.momentum.x.raw() * 3 / 5));
    MLS_REQUIRE_EQ(
        rotated_second_state.momentum.y,
        mls::Momentum::from_raw(axis_second_state.momentum.x.raw() * 4 / 5));
    MLS_REQUIRE_EQ(axis_first_state.position.x, mls::Length::from_raw(500'020));
    MLS_REQUIRE_EQ(rotated_first_state.position.x, mls::Length::from_raw(500'012));
    MLS_REQUIRE_EQ(rotated_first_state.position.y, mls::Length::from_raw(500'016));
    MLS_REQUIRE_EQ(axis_second_state.position.x, mls::Length::from_raw(500'030));
    MLS_REQUIRE_EQ(rotated_second_state.position.x, mls::Length::from_raw(500'018));
    MLS_REQUIRE_EQ(rotated_second_state.position.y, mls::Length::from_raw(500'024));
    MLS_REQUIRE_EQ(
        axis_aligned.world.totals().total_energy(), off_axis.world.totals().total_energy());
    MLS_REQUIRE_EQ(axis_aligned.world.totals().mass, off_axis.world.totals().mass);
    MLS_REQUIRE_EQ(axis_aligned.world.totals().elements, off_axis.world.totals().elements);
    MLS_REQUIRE(axis_aligned.world.audit().ok());
    MLS_REQUIRE(off_axis.world.audit().ok());
}

MLS_TEST("adversarial/tick_batching_is_exact_but_not_a_convergence_claim") {
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(1'000'000);
    auto batched = make_world(config);
    auto incremental = make_world(config);
    auto batched_seed = mixed_seed(batched, mls::Length::from_raw(0));
    auto incremental_seed = mixed_seed(incremental, mls::Length::from_raw(0));
    const mls::Momentum3 momentum{
        mls::Momentum::from_raw(37'001),
        mls::Momentum::from_raw(-29'003),
        mls::Momentum::from_raw(13'007)};
    batched_seed.momentum = momentum;
    incremental_seed.momentum = momentum;
    static_cast<void>(batched.world.introduce_material_from_boundary(batched_seed));
    static_cast<void>(incremental.world.introduce_material_from_boundary(incremental_seed));
    constexpr mls::Tick ticks = 1'024;
    batched.world.step(ticks);
    for (mls::Tick tick = 0; tick < ticks; ++tick) {
        incremental.world.step();
    }
    MLS_REQUIRE_EQ(batched.world.physical_state_hash(), incremental.world.physical_state_hash());
    MLS_REQUIRE_EQ(batched.world.totals(), incremental.world.totals());
    MLS_REQUIRE(batched.world.audit().ok());
    MLS_REQUIRE(incremental.world.audit().ok());
}
