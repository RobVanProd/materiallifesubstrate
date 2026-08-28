#include "test_harness.hpp"

#include "mls/checkpoint.hpp"
#include "mls/time.hpp"
#include "mls/world.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <span>
#include <stdexcept>
#include <utility>
#include <vector>

namespace {

struct TimeFixture final {
    mls::ElementId a{1};
    mls::ElementId b{2};
    mls::CompoundId a_id{};
    mls::CompoundId b_id{};
    mls::World world;
};

[[nodiscard]] TimeFixture make_time_world(mls::WorldConfig config = {}) {
    const mls::ElementId a{1};
    const mls::ElementId b{2};
    mls::ElementCatalog elements;
    elements.define(
        a,
        mls::ElementProperties{
            mls::Mass::from_raw(4),
            mls::HeatCapacity::from_raw(2),
            mls::Energy::from_raw(20)});
    elements.define(
        b,
        mls::ElementProperties{
            mls::Mass::from_raw(6),
            mls::HeatCapacity::from_raw(3),
            mls::Energy::from_raw(30)});
    elements.define_bond_energy(a, b, 1, mls::Energy::from_raw(5));
    mls::CompoundRegistry compounds;
    const auto a_id = compounds.intern(mls::CompoundGraph({a}, {}));
    const auto b_id = compounds.intern(mls::CompoundGraph({b}, {}));
    static_cast<void>(compounds.intern(mls::CompoundGraph(
        {a, b}, std::vector<mls::Bond>{{0, 1, 1}})));
    return {a, b, a_id, b_id, mls::World(std::move(elements), std::move(compounds), config)};
}

[[nodiscard]] mls::MaterialSeed seed(
    mls::CompoundId compound,
    mls::Position3 position = {},
    mls::Momentum3 momentum = {}) {
    return {
        position,
        momentum,
        mls::CompoundMixture{{compound, 1}},
        mls::Energy::from_raw(100),
        mls::Energy::from_raw(50)};
}

[[nodiscard]] std::uint64_t fnv1a(std::span<const std::uint8_t> bytes) noexcept {
    auto hash = UINT64_C(14695981039346656037);
    for (const auto byte : bytes) {
        hash = (hash ^ byte) * UINT64_C(1099511628211);
    }
    return hash;
}

void append_u64_little_endian(std::vector<std::uint8_t>& bytes, std::uint64_t value) {
    for (std::size_t index = 0; index < sizeof(value); ++index) {
        const auto shift = static_cast<unsigned int>(index * 8U);
        bytes.push_back(static_cast<std::uint8_t>((value >> shift) & UINT64_C(0xff)));
    }
}

void refresh_checksum(std::vector<std::uint8_t>& checkpoint) {
    MLS_REQUIRE(checkpoint.size() >= sizeof(std::uint64_t));
    checkpoint.resize(checkpoint.size() - sizeof(std::uint64_t));
    append_u64_little_endian(checkpoint, fnv1a(checkpoint));
}

[[nodiscard]] bool rejects_checkpoint(const std::vector<std::uint8_t>& bytes) {
    try {
        static_cast<void>(mls::deserialize_canonical_checkpoint(bytes));
    } catch (const std::invalid_argument&) {
        return true;
    }
    return false;
}

[[nodiscard]] std::size_t read_size_little_endian(
    const std::vector<std::uint8_t>& bytes, std::size_t& offset) {
    if (offset > bytes.size() || sizeof(std::uint64_t) > bytes.size() - offset) {
        throw std::logic_error("canonical test fixture is unexpectedly truncated");
    }
    std::uint64_t value = 0;
    for (std::size_t index = 0; index < sizeof(value); ++index) {
        const auto shift = static_cast<unsigned int>(index * 8U);
        value |= static_cast<std::uint64_t>(bytes[offset + index]) << shift;
    }
    offset += sizeof(value);
    if (value > static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max())) {
        throw std::logic_error("canonical test fixture count exceeds this platform");
    }
    return static_cast<std::size_t>(value);
}

void skip_bytes(
    const std::vector<std::uint8_t>& bytes, std::size_t& offset, std::size_t count) {
    if (offset > bytes.size() || count > bytes.size() - offset) {
        throw std::logic_error("canonical test fixture is unexpectedly truncated");
    }
    offset += count;
}

[[nodiscard]] std::size_t first_packet_offset(
    const std::vector<std::uint8_t>& checkpoint) {
    // Skip magic/format/physics ABI, configuration, Tick, and physical Time.
    std::size_t offset = 105;
    const auto element_count = read_size_little_endian(checkpoint, offset);
    skip_bytes(checkpoint, offset, element_count * 26U);
    const auto bond_rule_count = read_size_little_endian(checkpoint, offset);
    skip_bytes(checkpoint, offset, bond_rule_count * 13U);
    const auto compound_count = read_size_little_endian(checkpoint, offset);
    for (std::size_t compound_index = 0; compound_index < compound_count; ++compound_index) {
        skip_bytes(checkpoint, offset, sizeof(std::uint64_t)); // structural ID
        const auto atom_count = read_size_little_endian(checkpoint, offset);
        skip_bytes(checkpoint, offset, atom_count * sizeof(std::uint16_t));
        const auto bond_count = read_size_little_endian(checkpoint, offset);
        skip_bytes(checkpoint, offset, bond_count * 9U);
    }
    skip_bytes(checkpoint, offset, sizeof(std::uint64_t)); // next packet ID
    const auto packet_count = read_size_little_endian(checkpoint, offset);
    if (packet_count == 0) {
        throw std::logic_error("canonical test fixture contains no packet");
    }
    return offset;
}

[[nodiscard]] std::size_t first_packet_mass_offset(
    const std::vector<std::uint8_t>& checkpoint) {
    auto offset = first_packet_offset(checkpoint);
    skip_bytes(
        checkpoint,
        offset,
        sizeof(std::uint64_t) + sizeof(std::uint32_t) + 24U + 24U + 24U);
    const auto mixture_count = read_size_little_endian(checkpoint, offset);
    skip_bytes(checkpoint, offset, mixture_count * 16U);
    const auto inventory_count = read_size_little_endian(checkpoint, offset);
    skip_bytes(checkpoint, offset, inventory_count * 10U);
    return offset;
}

} // namespace

MLS_TEST("time/physical_clock_is_dimensioned_and_not_Tick") {
    auto fixture = make_time_world();
    const auto packet = fixture.world.introduce_material_from_boundary(seed(
        fixture.a_id,
        {mls::Length::from_raw(10), {}, {}},
        {mls::Momentum::from_raw(8), {}, {}}));
    MLS_REQUIRE_EQ(fixture.world.tick(), mls::Tick{0});
    MLS_REQUIRE_EQ(fixture.world.physical_time(), mls::Time{});
    MLS_REQUIRE_EQ(
        fixture.world.config().physical_time_scale,
        (mls::PhysicalTimeScale{1, 1'000'000'000}));

    fixture.world.step(3);
    MLS_REQUIRE_EQ(fixture.world.tick(), mls::Tick{3});
    MLS_REQUIRE_EQ(fixture.world.physical_time(), mls::Time::from_raw(3));
    MLS_REQUIRE_EQ(
        fixture.world.packets().snapshot(packet).position.x,
        mls::Length::from_raw(16));
    MLS_REQUIRE(fixture.world.audit().ok());
}

MLS_TEST("time/dt_dt2_dt4_agree_at_a_common_exact_physical_horizon") {
    auto dt4_config = mls::WorldConfig{};
    dt4_config.physical_timestep = mls::Time::from_raw(4);
    auto dt2_config = dt4_config;
    dt2_config.physical_timestep = mls::Time::from_raw(2);
    auto dt1_config = dt4_config;
    dt1_config.physical_timestep = mls::Time::from_raw(1);
    auto dt4 = make_time_world(dt4_config);
    auto dt2 = make_time_world(dt2_config);
    auto dt1 = make_time_world(dt1_config);
    const auto material = seed(
        dt4.a_id,
        {mls::Length::from_raw(-3), mls::Length::from_raw(5), {}},
        {mls::Momentum::from_raw(8), mls::Momentum::from_raw(4), {}});
    const auto packet4 = dt4.world.introduce_material_from_boundary(material);
    const auto packet2 = dt2.world.introduce_material_from_boundary(material);
    const auto packet1 = dt1.world.introduce_material_from_boundary(material);

    dt4.world.step(1);
    dt2.world.step(2);
    dt1.world.step(4);
    const auto state4 = dt4.world.packets().snapshot(packet4);
    const auto state2 = dt2.world.packets().snapshot(packet2);
    const auto state1 = dt1.world.packets().snapshot(packet1);
    MLS_REQUIRE_EQ(dt4.world.physical_time(), mls::Time::from_raw(4));
    MLS_REQUIRE_EQ(dt2.world.physical_time(), mls::Time::from_raw(4));
    MLS_REQUIRE_EQ(dt1.world.physical_time(), mls::Time::from_raw(4));
    MLS_REQUIRE_EQ(state4.position, state2.position);
    MLS_REQUIRE_EQ(state2.position, state1.position);
    MLS_REQUIRE_EQ(state4.momentum, state2.momentum);
    MLS_REQUIRE_EQ(state2.momentum, state1.momentum);
    MLS_REQUIRE_EQ(dt4.world.totals(), dt2.world.totals());
    MLS_REQUIRE_EQ(dt2.world.totals(), dt1.world.totals());
}

MLS_TEST("time/invalid_scales_and_fractional_steps_reject_transactionally") {
    auto zero_dt = mls::WorldConfig{};
    zero_dt.physical_timestep = mls::Time{};
    MLS_REQUIRE_THROWS(std::invalid_argument, make_time_world(zero_dt));
    auto zero_seconds = mls::WorldConfig{};
    zero_seconds.physical_time_scale.seconds_per_time_quantum_numerator = 0;
    MLS_REQUIRE_THROWS(std::invalid_argument, make_time_world(zero_seconds));
    auto zero_velocity_denominator = mls::WorldConfig{};
    zero_velocity_denominator.momentum_mass_to_velocity_scale.length_quanta_denominator = 0;
    MLS_REQUIRE_THROWS(std::invalid_argument, make_time_world(zero_velocity_denominator));

    auto fixture = make_time_world();
    static_cast<void>(fixture.world.introduce_material_from_boundary(seed(
        fixture.a_id, {}, {mls::Momentum::from_raw(1), {}, {}})));
    const auto before_hash = fixture.world.physical_state_hash();
    MLS_REQUIRE_THROWS(std::domain_error, fixture.world.step());
    MLS_REQUIRE_EQ(fixture.world.physical_state_hash(), before_hash);
    MLS_REQUIRE_EQ(fixture.world.tick(), mls::Tick{});
    MLS_REQUIRE_EQ(fixture.world.physical_time(), mls::Time{});
}

MLS_TEST("time/clock_and_displacement_overflow_reject_whole_batch") {
    auto clock = make_time_world();
    const auto clock_hash = clock.world.physical_state_hash();
    MLS_REQUIRE_THROWS(
        std::overflow_error,
        clock.world.step(std::numeric_limits<mls::Tick>::max()));
    MLS_REQUIRE_EQ(clock.world.physical_state_hash(), clock_hash);

    auto position = make_time_world();
    const auto packet = position.world.introduce_material_from_boundary(seed(
        position.a_id,
        {mls::Length::from_raw(std::numeric_limits<mls::Scalar>::max() - 1), {}, {}},
        {mls::Momentum::from_raw(4), {}, {}}));
    const auto position_hash = position.world.physical_state_hash();
    MLS_REQUIRE_THROWS(std::overflow_error, position.world.step(2));
    MLS_REQUIRE_EQ(position.world.physical_state_hash(), position_hash);
    MLS_REQUIRE_EQ(
        position.world.packets().snapshot(packet).position.x,
        mls::Length::from_raw(std::numeric_limits<mls::Scalar>::max() - 1));

    auto denominator_config = mls::WorldConfig{};
    denominator_config.momentum_mass_to_velocity_scale.length_quanta_denominator =
        std::numeric_limits<mls::Scalar>::max();
    auto denominator = make_time_world(denominator_config);
    static_cast<void>(
        denominator.world.introduce_material_from_boundary(seed(denominator.a_id)));
    const auto denominator_hash = denominator.world.physical_state_hash();
    MLS_REQUIRE_THROWS(std::overflow_error, denominator.world.step());
    MLS_REQUIRE_EQ(denominator.world.physical_state_hash(), denominator_hash);
}

MLS_TEST("checkpoint/canonical_roundtrip_preserves_authoritative_state") {
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(17);
    config.interaction_radius = mls::Length::from_raw(41);
    config.kinetic_energy_scale_denominator = 2;
    config.physical_timestep = mls::Time::from_raw(2);
    config.physical_time_scale = mls::PhysicalTimeScale{1, 1'000'000};
    config.momentum_mass_to_velocity_scale = mls::MomentumMassToVelocityScale{3, 2};
    config.packet_history_limit = 16;
    config.audit_after_each_operation = false;
    auto original = make_time_world(config);
    const auto removed = original.world.introduce_material_from_boundary(
        seed(original.b_id, {mls::Length::from_raw(-20), {}, {}}));
    original.world.remove_material_to_boundary(removed);
    const auto live = original.world.introduce_material_from_boundary(seed(
        original.a_id,
        {mls::Length::from_raw(3), mls::Length::from_raw(4), {}},
        {mls::Momentum::from_raw(4), {}, {}}));
    const auto second_live = original.world.introduce_material_from_boundary(seed(
        original.b_id, {mls::Length::from_raw(-9), mls::Length::from_raw(2), {}}));
    original.world.establish_current_state_as_baseline();
    original.world.exchange_energy_with_boundary(
        live, mls::EnergyChannel::stored, mls::Energy::from_raw(-7));
    original.world.apply_point_impulse_from_boundary(
        live, {mls::Momentum::from_raw(4), {}, {}});
    original.world.step(2);

    const auto checkpoint = mls::serialize_canonical_checkpoint(original.world);
    auto restored = mls::deserialize_canonical_checkpoint(checkpoint);
    MLS_REQUIRE_EQ(mls::serialize_canonical_checkpoint(restored), checkpoint);
    MLS_REQUIRE_EQ(restored.config().voxel_edge, config.voxel_edge);
    MLS_REQUIRE_EQ(restored.config().interaction_radius, config.interaction_radius);
    MLS_REQUIRE_EQ(
        restored.config().kinetic_energy_scale_denominator,
        config.kinetic_energy_scale_denominator);
    MLS_REQUIRE_EQ(restored.config().physical_timestep, config.physical_timestep);
    MLS_REQUIRE_EQ(restored.config().physical_time_scale, config.physical_time_scale);
    MLS_REQUIRE_EQ(
        restored.config().momentum_mass_to_velocity_scale,
        config.momentum_mass_to_velocity_scale);
    MLS_REQUIRE_EQ(restored.config().packet_history_limit, config.packet_history_limit);
    MLS_REQUIRE_EQ(
        restored.config().audit_after_each_operation,
        config.audit_after_each_operation);
    MLS_REQUIRE_EQ(restored.tick(), original.world.tick());
    MLS_REQUIRE_EQ(restored.physical_time(), original.world.physical_time());
    MLS_REQUIRE_EQ(restored.packets().snapshot(live), original.world.packets().snapshot(live));
    MLS_REQUIRE_EQ(
        restored.packets().snapshot(second_live),
        original.world.packets().snapshot(second_live));
    MLS_REQUIRE_EQ(restored.ledger().baseline(), original.world.ledger().baseline());
    MLS_REQUIRE_EQ(restored.ledger().boundary(), original.world.ledger().boundary());
    MLS_REQUIRE(original.world.ledger().baseline().packet_count > 0U);
    MLS_REQUIRE(original.world.ledger().boundary().energy_net.raw() < 0);
    MLS_REQUIRE(restored.audit().ok());

    // The removed packet's payload is non-authoritative, but its consumed ID
    // must still affect the next live identity after restart.
    const auto next_original =
        original.world.introduce_material_from_boundary(seed(original.a_id));
    const auto next_restored = restored.introduce_material_from_boundary(seed(original.a_id));
    MLS_REQUIRE_EQ(next_restored, next_original);
    MLS_REQUIRE_EQ(
        mls::serialize_canonical_checkpoint(restored),
        mls::serialize_canonical_checkpoint(original.world));
}

MLS_TEST("checkpoint/v2_empty_world_bytes_match_cross_compiler_golden") {
    const auto fixture = make_time_world();
    const auto checkpoint = mls::serialize_canonical_checkpoint(fixture.world);
    MLS_REQUIRE_EQ(checkpoint.size(), std::size_t{483});
    auto checksum_offset = checkpoint.size() - sizeof(std::uint64_t);
    const auto checksum = read_size_little_endian(checkpoint, checksum_offset);
    std::cout << "[EVIDENCE] checkpoint_v2_empty_fnv1a64=" << checksum << '\n';
    MLS_REQUIRE_EQ(
        checksum,
        UINT64_C(6948438975031162627));
    MLS_REQUIRE_EQ(checksum_offset, checkpoint.size());
}

MLS_TEST("checkpoint/continued_evolution_matches_after_restart") {
    auto config = mls::WorldConfig{};
    config.physical_timestep = mls::Time::from_raw(2);
    auto fixture = make_time_world(config);
    const auto packet = fixture.world.introduce_material_from_boundary(seed(
        fixture.a_id,
        {mls::Length::from_raw(7), {}, {}},
        {mls::Momentum::from_raw(4), {}, {}}));
    fixture.world.step(2);
    auto restored = mls::deserialize_canonical_checkpoint(
        mls::serialize_canonical_checkpoint(fixture.world));

    fixture.world.convert_energy(
        packet,
        mls::EnergyChannel::stored,
        mls::EnergyChannel::thermal,
        mls::Energy::from_raw(9));
    restored.convert_energy(
        packet,
        mls::EnergyChannel::stored,
        mls::EnergyChannel::thermal,
        mls::Energy::from_raw(9));
    fixture.world.step(5);
    restored.step(5);
    MLS_REQUIRE_EQ(restored.physical_state_hash(), fixture.world.physical_state_hash());
    MLS_REQUIRE_EQ(
        mls::serialize_canonical_checkpoint(restored),
        mls::serialize_canonical_checkpoint(fixture.world));
}

MLS_TEST("checkpoint/rejects_magic_version_checksum_truncation_and_trailing_payload") {
    const auto fixture = make_time_world();
    const auto canonical = mls::serialize_canonical_checkpoint(fixture.world);

    auto bad_magic = canonical;
    bad_magic[0] ^= UINT8_C(1);
    refresh_checksum(bad_magic);
    MLS_REQUIRE(rejects_checkpoint(bad_magic));

    auto bad_version = canonical;
    bad_version[8] = static_cast<std::uint8_t>(
        mls::canonical_checkpoint_format_version + 1U);
    bad_version[9] = 0;
    bad_version[10] = 0;
    bad_version[11] = 0;
    refresh_checksum(bad_version);
    MLS_REQUIRE(rejects_checkpoint(bad_version));

    auto bad_checksum = canonical;
    if (bad_checksum.empty()) {
        throw std::logic_error("canonical checkpoint unexpectedly has no checksum");
    }
    bad_checksum.back() ^= UINT8_C(1);
    MLS_REQUIRE(rejects_checkpoint(bad_checksum));

    for (std::size_t length = 0; length < canonical.size(); ++length) {
        const auto end = canonical.begin() + static_cast<std::ptrdiff_t>(length);
        const std::vector<std::uint8_t> truncated(canonical.begin(), end);
        MLS_REQUIRE(rejects_checkpoint(truncated));
    }

    std::vector<std::uint8_t> trailing(
        canonical.begin(), canonical.end() - static_cast<std::ptrdiff_t>(sizeof(std::uint64_t)));
    trailing.push_back(UINT8_C(0xa5));
    append_u64_little_endian(trailing, fnv1a(trailing));
    MLS_REQUIRE(rejects_checkpoint(trailing));
}

MLS_TEST("checkpoint/rejects_duplicate_noncanonical_catalog_keys") {
    const auto fixture = make_time_world();
    auto duplicate = mls::serialize_canonical_checkpoint(fixture.world);

    // Canonical v1 prefix: 16-byte header, 73-byte configuration, 16-byte
    // clock, 8-byte element count. Each element entry is 2 + 8 + 8 + 8 bytes.
    constexpr std::size_t first_element_offset = 113;
    constexpr std::size_t second_element_offset = first_element_offset + 26;
    MLS_REQUIRE(duplicate.size() > second_element_offset + 1);
    duplicate[second_element_offset] = duplicate[first_element_offset];
    duplicate[second_element_offset + 1] = duplicate[first_element_offset + 1];
    refresh_checksum(duplicate);
    MLS_REQUIRE(rejects_checkpoint(duplicate));

    auto reordered = mls::serialize_canonical_checkpoint(fixture.world);
    std::swap(reordered[first_element_offset], reordered[second_element_offset]);
    std::swap(reordered[first_element_offset + 1], reordered[second_element_offset + 1]);
    refresh_checksum(reordered);
    MLS_REQUIRE(rejects_checkpoint(reordered));
}

MLS_TEST("checkpoint/rejects_a_clock_inconsistent_with_Tick") {
    const auto fixture = make_time_world();
    auto inconsistent = mls::serialize_canonical_checkpoint(fixture.world);

    // Canonical v2 prefix: 16-byte header and 73-byte configuration. Tick is
    // the next eight bytes; physical Time follows at byte 97.
    constexpr std::size_t physical_time_offset = 97;
    inconsistent[physical_time_offset] = UINT8_C(1);
    refresh_checksum(inconsistent);
    MLS_REQUIRE(rejects_checkpoint(inconsistent));
}

MLS_TEST("checkpoint/rejects_wrong_physics_abi_and_invalid_time_scale") {
    const auto fixture = make_time_world();
    const auto canonical = mls::serialize_canonical_checkpoint(fixture.world);

    auto physics_abi = canonical;
    constexpr std::size_t physics_abi_offset = 12;
    physics_abi[physics_abi_offset] = static_cast<std::uint8_t>(
        mls::authoritative_physics_abi_version + 1U);
    refresh_checksum(physics_abi);
    MLS_REQUIRE(rejects_checkpoint(physics_abi));

    auto time_scale = canonical;
    constexpr std::size_t seconds_numerator_offset = 48;
    std::fill_n(
        time_scale.begin() + static_cast<std::ptrdiff_t>(seconds_numerator_offset),
        sizeof(std::uint64_t),
        std::uint8_t{0});
    refresh_checksum(time_scale);
    MLS_REQUIRE(rejects_checkpoint(time_scale));
}

MLS_TEST("checkpoint/rejects_inconsistent_packet_derived_material_state") {
    auto fixture = make_time_world();
    static_cast<void>(
        fixture.world.introduce_material_from_boundary(seed(fixture.a_id)));
    auto inconsistent = mls::serialize_canonical_checkpoint(fixture.world);
    const auto mass_offset = first_packet_mass_offset(inconsistent);
    std::fill_n(
        inconsistent.begin() + static_cast<std::ptrdiff_t>(mass_offset),
        sizeof(std::int64_t),
        std::uint8_t{0});
    inconsistent[mass_offset] = UINT8_C(5); // configured/derived mass is four
    refresh_checksum(inconsistent);
    MLS_REQUIRE(rejects_checkpoint(inconsistent));
}

MLS_TEST("checkpoint/rejects_unreachable_live_packet_generation") {
    auto fixture = make_time_world();
    static_cast<void>(
        fixture.world.introduce_material_from_boundary(seed(fixture.a_id)));
    auto unreachable = mls::serialize_canonical_checkpoint(fixture.world);
    const auto generation_offset =
        first_packet_offset(unreachable) + sizeof(std::uint64_t);
    std::fill_n(
        unreachable.begin() + static_cast<std::ptrdiff_t>(generation_offset),
        sizeof(std::uint32_t),
        std::uint8_t{0});
    unreachable[generation_offset] = UINT8_C(2);
    refresh_checksum(unreachable);
    MLS_REQUIRE(rejects_checkpoint(unreachable));
}
