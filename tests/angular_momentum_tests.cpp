#include "test_harness.hpp"

#include "mls/world.hpp"

#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace {

[[nodiscard]] mls::Position3 position(mls::Scalar x, mls::Scalar y = 0, mls::Scalar z = 0) {
    return {
        mls::Length::from_raw(x),
        mls::Length::from_raw(y),
        mls::Length::from_raw(z)};
}

[[nodiscard]] mls::Momentum3 momentum(
    mls::Scalar x, mls::Scalar y = 0, mls::Scalar z = 0) {
    return {
        mls::Momentum::from_raw(x),
        mls::Momentum::from_raw(y),
        mls::Momentum::from_raw(z)};
}

struct AngularFixture final {
    mls::ElementId element{0};
    mls::CompoundId atom{};
    mls::World world;
};

[[nodiscard]] AngularFixture make_angular_world() {
    const mls::ElementId element{0};
    mls::ElementCatalog elements;
    elements.define(
        element,
        mls::ElementProperties{
            mls::Mass::from_raw(10),
            mls::HeatCapacity::from_raw(1),
            mls::Energy::from_raw(10)});

    mls::CompoundRegistry compounds;
    const auto atom = compounds.intern(mls::CompoundGraph(
        std::vector<mls::ElementId>{element}, {}));
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(10);
    config.packet_history_limit = 8;
    return {element, atom, mls::World(std::move(elements), std::move(compounds), config)};
}

[[nodiscard]] mls::MaterialSeed seed(
    const AngularFixture& fixture,
    mls::Position3 packet_position,
    mls::Momentum3 packet_momentum = {}) {
    return {
        .position = packet_position,
        .momentum = packet_momentum,
        .composition = mls::CompoundMixture{{fixture.atom, 1}},
        .stored_energy = mls::Energy::from_raw(1'000),
        .thermal_energy = mls::Energy::from_raw(1'000),
    };
}

} // namespace

template <typename WorldType>
concept StepAcceptsDimensionedTime = requires(WorldType& world, mls::Time timestep) {
    world.step(timestep);
};

MLS_TEST("hardening/angular/noncentral_equal_opposite_impulse_counterexample") {
    // This is the regression witness for the old primitive: linear momentum
    // closes, but Delta L = (r1-r2) x J is nonzero.
    const auto r1 = position(1, 0, 0);
    const auto r2 = position(0, 0, 0);
    const auto impulse = momentum(0, 1, 0);
    const auto p1_after = impulse;
    const auto p2_after = -impulse;

    MLS_REQUIRE_EQ(p1_after + p2_after, mls::Momentum3{});
    const auto delta = mls::pair_angular_momentum_delta(r1, r2, impulse);
    MLS_REQUIRE(delta != mls::AngularMomentum3{});
    MLS_REQUIRE_EQ(delta.z, mls::AngularMomentum::from_raw(1));
    MLS_REQUIRE_EQ(
        mls::cross(r1, p1_after) + mls::cross(r2, p2_after), delta);
}

MLS_TEST("hardening/angular/accepted_pair_transition_requires_central_impulse") {
    auto fixture = make_angular_world();
    const auto first = fixture.world.introduce_material_from_boundary(seed(fixture, position(0)));
    const auto second = fixture.world.introduce_material_from_boundary(seed(fixture, position(1)));
    const auto before_hash = fixture.world.physical_state_hash();

    MLS_REQUIRE_THROWS(
        std::domain_error,
        fixture.world.apply_actuated_dissipative_central_impulse(
            first, second, momentum(0, 20), first, second));
    MLS_REQUIRE_EQ(fixture.world.physical_state_hash(), before_hash);

    fixture.world.apply_actuated_dissipative_central_impulse(
        first, second, momentum(20), first, second);
    MLS_REQUIRE_EQ(fixture.world.totals().momentum, mls::Momentum3{});
    MLS_REQUIRE_EQ(fixture.world.totals().angular_momentum, mls::AngularMomentum3{});
    MLS_REQUIRE(fixture.world.audit().ok());
}

MLS_TEST("hardening/angular/boundary_point_impulse_accounts_for_orbital_angular_momentum") {
    auto fixture = make_angular_world();
    const auto packet =
        fixture.world.introduce_material_from_boundary(seed(fixture, position(2, 3)));
    fixture.world.apply_point_impulse_from_boundary(packet, momentum(0, 20));

    const auto expected = mls::AngularMomentum3{
        {}, {}, mls::AngularMomentum::from_raw(40)};
    MLS_REQUIRE_EQ(fixture.world.totals().angular_momentum, expected);
    MLS_REQUIRE_EQ(fixture.world.ledger().boundary().angular_momentum_net, expected);
    MLS_REQUIRE(fixture.world.audit().ok());

    fixture.world.remove_material_to_boundary(packet);
    MLS_REQUIRE_EQ(fixture.world.ledger().boundary().angular_momentum_net, mls::AngularMomentum3{});
    MLS_REQUIRE(fixture.world.audit().ok());
}

MLS_TEST("hardening/angular/actuated_dissipative_impulse_cycle_is_not_conservative_mechanics") {
    auto fixture = make_angular_world();
    const auto first = fixture.world.introduce_material_from_boundary(seed(fixture, position(0)));
    const auto second = fixture.world.introduce_material_from_boundary(seed(fixture, position(1)));
    const auto before_first = fixture.world.packets().snapshot(first);
    const auto before_second = fixture.world.packets().snapshot(second);

    fixture.world.apply_actuated_dissipative_central_impulse(
        first, second, momentum(20), first, second);
    fixture.world.apply_actuated_dissipative_central_impulse(
        first, second, momentum(-20), first, second);

    const auto after_first = fixture.world.packets().snapshot(first);
    const auto after_second = fixture.world.packets().snapshot(second);
    MLS_REQUIRE_EQ(after_first.momentum, before_first.momentum);
    MLS_REQUIRE_EQ(after_second.momentum, before_second.momentum);
    MLS_REQUIRE(after_first.stored_energy < before_first.stored_energy);
    MLS_REQUIRE(after_second.thermal_energy > before_second.thermal_energy);
    MLS_REQUIRE_EQ(
        before_first.stored_energy - after_first.stored_energy,
        after_second.thermal_energy - before_second.thermal_energy);
    MLS_REQUIRE(fixture.world.audit().ok());
}

MLS_TEST("hardening/angular/ballistic_step_accepts_only_exact_displacement_and_preserves_L") {
    auto exact = make_angular_world();
    static_cast<void>(exact.world.introduce_material_from_boundary(
        seed(exact, position(0, 1), momentum(10))));
    const auto before = exact.world.totals().angular_momentum;
    exact.world.step();
    MLS_REQUIRE_EQ(exact.world.totals().angular_momentum, before);
    MLS_REQUIRE(exact.world.audit().ok());

    auto fractional = make_angular_world();
    static_cast<void>(fractional.world.introduce_material_from_boundary(
        seed(fractional, position(0, 1), momentum(1))));
    const auto before_hash = fractional.world.physical_state_hash();
    MLS_REQUIRE_THROWS(std::domain_error, fractional.world.step());
    MLS_REQUIRE_EQ(fractional.world.physical_state_hash(), before_hash);
}

MLS_TEST("hardening/angular/cross_product_overflow_is_rejected") {
    const auto large_position = position(std::numeric_limits<mls::Scalar>::max(), 1, 0);
    MLS_REQUIRE_THROWS(
        std::overflow_error,
        mls::cross(large_position, momentum(0, 2, 0)));
}

MLS_TEST("hardening/angular/boundary_cross_overflow_rejects_whole_transition") {
    auto fixture = make_angular_world();
    const auto packet = fixture.world.introduce_material_from_boundary(
        seed(fixture, position(std::numeric_limits<mls::Scalar>::max(), 1, 0)));
    const auto hash_before = fixture.world.physical_state_hash();
    const auto boundary_before = fixture.world.ledger().boundary();
    MLS_REQUIRE_THROWS(
        std::overflow_error,
        fixture.world.apply_point_impulse_from_boundary(packet, momentum(0, 2, 0)));
    MLS_REQUIRE_EQ(fixture.world.physical_state_hash(), hash_before);
    MLS_REQUIRE_EQ(fixture.world.ledger().boundary(), boundary_before);
    MLS_REQUIRE(fixture.world.audit().ok());
}

MLS_TEST("hardening/timestep/physical_dt_is_configured_not_passed_as_Tick") {
    // Physical dt now lives in WorldConfig as a dimensioned Time. The step
    // argument remains only an operation count, preventing an unconfigured
    // caller-supplied Time from bypassing the authoritative clock contract.
    MLS_REQUIRE(!StepAcceptsDimensionedTime<mls::World>);
}

MLS_TEST("hardening/timestep/impulse_phase_within_a_tick_changes_position") {
    auto impulse_before = make_angular_world();
    auto impulse_after = make_angular_world();
    const auto before_packet = impulse_before.world.introduce_material_from_boundary(
        seed(impulse_before, position(0)));
    const auto after_packet = impulse_after.world.introduce_material_from_boundary(
        seed(impulse_after, position(0)));

    impulse_before.world.apply_point_impulse_from_boundary(
        before_packet, momentum(10));
    impulse_before.world.step();

    impulse_after.world.step();
    impulse_after.world.apply_point_impulse_from_boundary(
        after_packet, momentum(10));

    MLS_REQUIRE_EQ(
        impulse_before.world.packets().snapshot(before_packet).momentum,
        impulse_after.world.packets().snapshot(after_packet).momentum);
    MLS_REQUIRE(
        impulse_before.world.packets().snapshot(before_packet).position !=
        impulse_after.world.packets().snapshot(after_packet).position);
    MLS_REQUIRE(
        impulse_before.world.physical_state_hash() !=
        impulse_after.world.physical_state_hash());
    MLS_REQUIRE(impulse_before.world.audit().ok());
    MLS_REQUIRE(impulse_after.world.audit().ok());
}
