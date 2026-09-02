#pragma once

#include "mls/packet_store.hpp"
#include "mls/relation_geometry_resolution_lab.hpp"

#include <cstdint>
#include <string>

namespace mls::experimental::authoritative_mechanics_state_bridge {

struct PositiveRational final {
    std::uint64_t numerator{1};
    std::uint64_t denominator{1};

    [[nodiscard]] constexpr auto operator<=>(
        const PositiveRational&) const noexcept = default;
};

struct MechanicsUnitContract final {
    PositiveRational length_quantum_m{1, 1'000'000'000};
    PositiveRational mass_quantum_kg{1, 4'096};
    PositiveRational time_quantum_s{1, 1'000'000'000};
    PositiveRational momentum_quantum_kg_m_per_s{1, 4'096};
    PositiveRational energy_quantum_j{1, 4'096};
    PositiveRational force_quantum_n{1'953'125, 8};
    std::uint32_t refinement{1};
    PhysicalTimeScale physical_time_scale{};
    MomentumMassToVelocityScale momentum_mass_to_velocity_scale{};
    Scalar kinetic_energy_scale_denominator{1};

    [[nodiscard]] constexpr auto operator<=>(
        const MechanicsUnitContract&) const noexcept = default;
};

// Returns the preregistered coherent representation family.  The mechanics
// bridge selected R=16; the authorized drift fallback may additionally audit
// R=32,64,128 without changing the exact SI state or physics.
[[nodiscard]] MechanicsUnitContract mechanics_unit_contract(
    std::uint32_t refinement);

// Verifies every derived-unit identity and its embedding in the existing raw
// ballistic and kinetic-energy conventions.  It throws rather than accepting
// a merely positive but dimensionally inconsistent configuration.
void validate_mechanics_unit_contract(const MechanicsUnitContract& contract);

struct AuthoritativePacket final {
    std::uint64_t id{0};
    Position3 position{};
    Momentum3 momentum{};
    Mass mass{};

    [[nodiscard]] constexpr auto operator<=>(
        const AuthoritativePacket&) const noexcept = default;
};

struct Binary64PacketMapping final {
    std::uint64_t id{0};
    Vec3d position_m{};
    Vec3d momentum_kg_m_per_s{};
    double mass_kg{0.0};
    bool nearest_roundtrip_exact{false};
};

[[nodiscard]] Binary64PacketMapping map_packet_to_binary64_si(
    const AuthoritativePacket& packet,
    const MechanicsUnitContract& contract);

enum class QuantizationPath : std::uint8_t {
    direct_nearest,
    fixed_point_refinement,
    explicit_remainder,
};

[[nodiscard]] const char* path_name(QuantizationPath path) noexcept;

struct CentralImpulseInput final {
    AuthoritativePacket first{};
    AuthoritativePacket second{};
    Vec3d force_to_first_n{};
    // Exact registered interval in authoritative time quanta.
    Time interval{};
    std::uint32_t subdivisions{1};
    QuantizationPath path{QuantizationPath::direct_nearest};
};

struct ExplicitRemainderCheckpoint final {
    std::uint64_t first_id{0};
    std::uint64_t second_id{0};
    // IEEE-754 bits of the causal scalar remainder in refined primitive
    // momentum quanta.  It is present only for the explicit-remainder path.
    std::uint64_t scalar_remainder_bits{0};

    [[nodiscard]] constexpr auto operator<=>(
        const ExplicitRemainderCheckpoint&) const noexcept = default;
};

[[nodiscard]] std::string encode_remainder_checkpoint(
    const ExplicitRemainderCheckpoint& checkpoint);
[[nodiscard]] ExplicitRemainderCheckpoint decode_remainder_checkpoint(
    const std::string& encoded);
[[nodiscard]] std::uint64_t hash_remainder_checkpoint(
    const ExplicitRemainderCheckpoint& checkpoint) noexcept;

struct CentralImpulseEvaluation final {
    QuantizationPath path{QuantizationPath::direct_nearest};
    std::uint32_t refinement{1};
    std::uint32_t subdivisions{1};
    Position3 primitive_direction{};
    Scalar applied_primitive_multiple{0};
    Momentum3 impulse_to_first{};
    Momentum3 impulse_to_second{};
    Momentum3 total_momentum_delta{};
    AngularMomentum3 orbital_angular_momentum_delta{};
    double target_primitive_multiple{0.0};
    double remainder_primitive_quanta{0.0};
    Vec3d target_impulse_kg_m_per_s{};
    Vec3d applied_impulse_kg_m_per_s{};
    Vec3d discarded_impulse_kg_m_per_s{};
    Energy quantized_kinetic_delta{};
    double exact_kinetic_delta_j{0.0};
    double quantized_kinetic_delta_j{0.0};
    double kinetic_floor_residual_j{0.0};
    double exact_impulse_work_j{0.0};
    double remainder_balance_error{0.0};
    ExplicitRemainderCheckpoint remainder_checkpoint{};
    std::uint64_t remainder_checkpoint_hash{0};
    bool exact_linear_momentum{false};
    bool exact_orbital_angular_momentum{false};
    bool remainder_checkpoint_roundtrip{false};
};

// Read-only prescribed impulse evaluation.  Positions, momenta, clock, and
// World state are never mutated.  The integer impulse is constrained to the
// primitive authoritative relation direction before rounding.
[[nodiscard]] CentralImpulseEvaluation evaluate_central_impulse(
    const CentralImpulseInput& input,
    const MechanicsUnitContract& contract);

} // namespace mls::experimental::authoritative_mechanics_state_bridge
