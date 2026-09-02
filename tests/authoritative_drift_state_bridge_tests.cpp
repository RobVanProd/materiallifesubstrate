#include "test_harness.hpp"

#include "mls/authoritative_drift_state_bridge_lab.hpp"
#include "mls/world.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace {

namespace drift = mls::experimental::authoritative_drift_state_bridge;
namespace mechanics = mls::experimental::authoritative_mechanics_state_bridge;
using mls::Length;
using mls::Mass;
using mls::Momentum;
using mls::Time;

[[nodiscard]] drift::DriftPacket packet(
    std::uint64_t id,
    mls::Scalar px,
    mls::Scalar py,
    mls::Scalar pz,
    mls::Scalar mass) {
    return {
        id,
        {Length::from_raw(static_cast<mls::Scalar>(id * 3U)),
         Length::from_raw(-static_cast<mls::Scalar>(id * 2U)),
         Length::from_raw(static_cast<mls::Scalar>(id))},
        {Momentum::from_raw(px), Momentum::from_raw(py), Momentum::from_raw(pz)},
        Mass::from_raw(mass),
    };
}

struct FingerprintFixture final {
    mls::CompoundId material{};
    mls::World world;
};

[[nodiscard]] FingerprintFixture fingerprint_world() {
    const mls::ElementId element{1};
    mls::ElementCatalog elements;
    elements.define(
        element,
        {Mass::from_raw(4), mls::HeatCapacity::from_raw(2),
         mls::Energy::from_raw(20)});
    mls::CompoundRegistry compounds;
    const auto material = compounds.intern(mls::CompoundGraph({element}, {}));
    return {material, mls::World(std::move(elements), std::move(compounds))};
}

[[nodiscard]] mls::MaterialSeed seed(
    mls::CompoundId material, mls::Momentum3 momentum) {
    return {{}, momentum, {{material, 1}}, mls::Energy::from_raw(100),
            mls::Energy::from_raw(50)};
}

[[nodiscard]] double maximum_component_error_base_quanta(
    const drift::DriftEvaluation& value) {
    constexpr auto base_lq = 1.0e-9;
    return std::max(
        {std::abs(value.component_error_m.x),
         std::abs(value.component_error_m.y),
         std::abs(value.component_error_m.z)}) /
        base_lq;
}

} // namespace

MLS_TEST("authoritative drift reproduces exact-pass and fractional-reject parent fingerprint") {
    auto exact = fingerprint_world();
    const auto exact_packet = exact.world.introduce_material_from_boundary(seed(
        exact.material, {Momentum::from_raw(4), {}, {}}));
    exact.world.step();
    MLS_REQUIRE_EQ(
        exact.world.packets().snapshot(exact_packet).position.x,
        Length::from_raw(1));

    auto fractional = fingerprint_world();
    static_cast<void>(fractional.world.introduce_material_from_boundary(seed(
        fractional.material, {Momentum::from_raw(1), {}, {}})));
    const auto hash_before = fractional.world.physical_state_hash();
    MLS_REQUIRE_THROWS(std::domain_error, fractional.world.step());
    MLS_REQUIRE_EQ(fractional.world.physical_state_hash(), hash_before);
    MLS_REQUIRE_EQ(fractional.world.tick(), mls::Tick{});
    MLS_REQUIRE_EQ(fractional.world.physical_time(), Time{});
}

MLS_TEST("authoritative drift signed rational rounding is nearest even") {
    MLS_REQUIRE_EQ(drift::nearest_even_rational(1, 2), 0);
    MLS_REQUIRE_EQ(drift::nearest_even_rational(3, 2), 2);
    MLS_REQUIRE_EQ(drift::nearest_even_rational(5, 2), 2);
    MLS_REQUIRE_EQ(drift::nearest_even_rational(-1, 2), 0);
    MLS_REQUIRE_EQ(drift::nearest_even_rational(-3, 2), -2);
    MLS_REQUIRE_EQ(drift::nearest_even_rational(-5, 2), -2);
    MLS_REQUIRE_EQ(drift::nearest_even_rational(2, 3), 1);
    MLS_REQUIRE_EQ(drift::nearest_even_rational(-2, 3), -1);
}

MLS_TEST("Cartesian drift negative control produces resolved orbital torque") {
    const auto value = drift::evaluate_drift(
        {packet(3, -3, 5, -7, 41), Time::from_raw(32), 32,
         drift::DriftPath::cartesian_nearest},
        mechanics::mechanics_unit_contract(16));
    MLS_REQUIRE(!value.exact_orbital_angular_momentum);
    MLS_REQUIRE(value.orbital_angular_momentum_delta != mls::AngularMomentum3{});
    MLS_REQUIRE(value.exact_momentum_unchanged);
    MLS_REQUIRE(value.exact_kinetic_energy_unchanged);
}

MLS_TEST("primitive directional drift preserves point momentum orbit and kinetic energy") {
    const std::array packets{
        packet(1, 0, 0, 0, 37), packet(2, 5, 0, 0, 37),
        packet(3, -3, 5, -7, 41), packet(4, 14, -21, 28, 43),
        packet(5, 33, 22, -11, 47)};
    for (const auto refinement : std::array{1U, 2U, 4U, 8U, 16U, 32U, 64U, 128U}) {
        const auto units = mechanics::mechanics_unit_contract(refinement);
        for (const auto& value : packets) {
            for (const auto horizon : std::array{32, 96, 160}) {
                for (const auto subdivisions : std::array{1U, 2U, 4U, 8U, 16U, 32U}) {
                    const auto evaluated = drift::evaluate_drift(
                        {value, Time::from_raw(horizon), subdivisions,
                         drift::DriftPath::primitive_directional},
                        units);
                    MLS_REQUIRE(evaluated.exact_momentum_unchanged);
                    MLS_REQUIRE(evaluated.exact_kinetic_energy_unchanged);
                    MLS_REQUIRE(evaluated.exact_orbital_angular_momentum);
                    MLS_REQUIRE_EQ(
                        evaluated.orbital_angular_momentum_delta,
                        mls::AngularMomentum3{});
                }
            }
        }
    }
}

MLS_TEST("R16 fails and R128 passes the preregistered drift error gate") {
    const auto witness = packet(3, -3, 5, -7, 41);
    const auto r16 = drift::evaluate_drift(
        {witness, Time::from_raw(32), 32,
         drift::DriftPath::primitive_directional},
        mechanics::mechanics_unit_contract(16));
    MLS_REQUIRE(maximum_component_error_base_quanta(r16) > 1.0);

    double maximum_component = 0.0;
    double maximum_vector = 0.0;
    for (const auto value :
         std::array{packet(1, 0, 0, 0, 37), packet(2, 5, 0, 0, 37),
                    packet(3, -3, 5, -7, 41), packet(4, 14, -21, 28, 43),
                    packet(5, 33, 22, -11, 47)}) {
        for (const auto horizon : std::array{32, 96, 160}) {
            for (const auto subdivisions : std::array{1U, 2U, 4U, 8U, 16U, 32U}) {
                const auto evaluated = drift::evaluate_drift(
                    {value, Time::from_raw(horizon), subdivisions,
                     drift::DriftPath::primitive_directional},
                    mechanics::mechanics_unit_contract(128));
                maximum_component = std::max(
                    maximum_component,
                    maximum_component_error_base_quanta(evaluated));
                maximum_vector = std::max(
                    maximum_vector, evaluated.vector_error_m / 1.0e-9);
            }
        }
    }
    MLS_REQUIRE(maximum_component <= 1.0);
    MLS_REQUIRE(maximum_vector <= 1.5);
}

MLS_TEST("equal exact velocities receive equal directional displacement") {
    const auto first = packet(6, 2, -3, 1, 5);
    const auto second = packet(7, 6, -9, 3, 15);
    for (const auto refinement : std::array{16U, 32U, 64U, 128U}) {
        const auto units = mechanics::mechanics_unit_contract(refinement);
        for (const auto horizon : std::array{32, 96, 160}) {
            for (const auto subdivisions : std::array{1U, 2U, 4U, 8U, 16U, 32U}) {
                const auto a = drift::evaluate_drift(
                    {first, Time::from_raw(horizon), subdivisions,
                     drift::DriftPath::primitive_directional}, units);
                const auto b = drift::evaluate_drift(
                    {second, Time::from_raw(horizon), subdivisions,
                     drift::DriftPath::primitive_directional}, units);
                MLS_REQUIRE_EQ(a.applied_displacement, b.applied_displacement);
            }
        }
    }
}

MLS_TEST("directional drift is stateless replayable and packet-order invariant") {
    const auto units = mechanics::mechanics_unit_contract(128);
    const std::array packets{
        packet(2, 5, 0, 0, 37), packet(3, -3, 5, -7, 41),
        packet(4, 14, -21, 28, 43), packet(5, 33, 22, -11, 47)};
    mls::Position3 weighted_forward{};
    mls::Position3 weighted_reverse{};
    for (const auto& value : packets) {
        const auto first = drift::evaluate_drift(
            {value, Time::from_raw(96), 32,
             drift::DriftPath::primitive_directional}, units);
        const auto replay = drift::evaluate_drift(
            {value, Time::from_raw(96), 32,
             drift::DriftPath::primitive_directional}, units);
        MLS_REQUIRE_EQ(first.applied_displacement, replay.applied_displacement);
        weighted_forward += mls::Position3{
            first.applied_displacement.x * value.base_mass.raw(),
            first.applied_displacement.y * value.base_mass.raw(),
            first.applied_displacement.z * value.base_mass.raw()};
    }
    for (auto iterator = packets.rbegin(); iterator != packets.rend(); ++iterator) {
        const auto value = drift::evaluate_drift(
            {*iterator, Time::from_raw(96), 32,
             drift::DriftPath::primitive_directional}, units);
        weighted_reverse += mls::Position3{
            value.applied_displacement.x * iterator->base_mass.raw(),
            value.applied_displacement.y * iterator->base_mass.raw(),
            value.applied_displacement.z * iterator->base_mass.raw()};
    }
    MLS_REQUIRE_EQ(weighted_forward, weighted_reverse);

    auto relabeled = packets[1];
    relabeled.id = 700;
    relabeled.base_position = {
        Length::from_raw(-100), Length::from_raw(200), Length::from_raw(3)};
    const auto original = drift::evaluate_drift(
        {packets[1], Time::from_raw(96), 32,
         drift::DriftPath::primitive_directional}, units);
    const auto renamed = drift::evaluate_drift(
        {relabeled, Time::from_raw(96), 32,
         drift::DriftPath::primitive_directional}, units);
    MLS_REQUIRE_EQ(original.applied_displacement, renamed.applied_displacement);
    MLS_REQUIRE_EQ(
        original.orbital_angular_momentum_delta,
        renamed.orbital_angular_momentum_delta);
}

MLS_TEST("drift product overflow rejects instead of wrapping") {
    constexpr auto maximum = std::numeric_limits<mls::Scalar>::max();
    constexpr mls::Scalar multiplier = 32;
    const auto safe = static_cast<mls::Scalar>(maximum / multiplier);
    static_cast<void>(drift::nearest_even_product_ratio(safe, multiplier, maximum));
    MLS_REQUIRE_THROWS(
        std::overflow_error,
        drift::nearest_even_product_ratio(
            static_cast<mls::Scalar>(safe + 1), multiplier, maximum));
}

MLS_TEST("drift chord regression distinguishes safe and force-domain crossing paths") {
    const auto safe = drift::evaluate_relation_chord(
        {1, {Length::from_raw(1'000'000), {}, {}},
         {Length::from_raw(1'000'000), Length::from_raw(10), {}},
         Length::from_raw(1'000'000)});
    MLS_REQUIRE(safe.admissible_force_domain);

    const auto crossing = drift::evaluate_relation_chord(
        {2, {Length::from_raw(1'000'000), {}, {}},
         {Length::from_raw(-1'000'000), {}, {}},
         Length::from_raw(1'000'000)});
    MLS_REQUIRE(crossing.interior_minimum);
    MLS_REQUIRE(!crossing.admissible_force_domain);

    const auto below = drift::evaluate_relation_chord(
        {3, {Length::from_raw(1), {}, {}}, {Length::from_raw(1), {}, {}},
         Length::from_raw(static_cast<mls::Scalar>(1U << 25U))});
    MLS_REQUIRE(!below.interior_minimum);
    MLS_REQUIRE(!below.admissible_force_domain);
}

MLS_TEST("finer selected drift profile reruns inherited impulse and kinetic gates") {
    for (const auto refinement : std::array{32U, 64U, 128U}) {
        const auto units = mechanics::mechanics_unit_contract(refinement);
        const mechanics::AuthoritativePacket first{1, {}, {}, Mass::from_raw(1)};
        const mechanics::AuthoritativePacket second{
            2, {Length::from_raw(1'001'000'000), {}, {}}, {}, Mass::from_raw(1)};
        const auto value = mechanics::evaluate_central_impulse(
            {first, second, {0.0006, 0.0, 0.0}, Time::from_raw(1'000'000'000),
             16, mechanics::QuantizationPath::fixed_point_refinement},
            units);
        MLS_REQUIRE(value.exact_linear_momentum);
        MLS_REQUIRE(value.exact_orbital_angular_momentum);
        const auto energy_quantum =
            static_cast<double>(units.energy_quantum_j.numerator) /
            static_cast<double>(units.energy_quantum_j.denominator);
        MLS_REQUIRE(value.kinetic_floor_residual_j >= -1.0e-18);
        MLS_REQUIRE(value.kinetic_floor_residual_j < 2.0 * energy_quantum);
    }
}
