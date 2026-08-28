#include "mls/checkpoint.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <limits>
#include <map>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace mls {
namespace {

constexpr std::array<std::uint8_t, 8> checkpoint_magic{
    'M', 'L', 'S', 'T', 'T', 'L', 'A', 'B'};
constexpr std::uint64_t fnv_offset = 14695981039346656037ULL;
constexpr std::uint64_t fnv_prime = 1099511628211ULL;

[[noreturn]] void reject(const char* message) {
    throw std::invalid_argument(message);
}

[[nodiscard]] std::uint64_t checkpoint_checksum(
    std::span<const std::uint8_t> bytes) noexcept {
    auto hash = fnv_offset;
    for (const auto byte : bytes) {
        hash = (hash ^ byte) * fnv_prime;
    }
    return hash;
}

class Writer final {
public:
    void write_u8(std::uint8_t value) { bytes_.push_back(value); }

    void write_u16(std::uint16_t value) {
        write_unsigned(value);
    }

    void write_u32(std::uint32_t value) {
        write_unsigned(value);
    }

    void write_u64(std::uint64_t value) {
        write_unsigned(value);
    }

    void write_i64(std::int64_t value) {
        write_u64(static_cast<std::uint64_t>(value));
    }

    void write_size(std::size_t value) {
        static_assert(sizeof(std::size_t) <= sizeof(std::uint64_t));
        write_u64(static_cast<std::uint64_t>(value));
    }

    void write_magic() {
        bytes_.insert(bytes_.end(), checkpoint_magic.begin(), checkpoint_magic.end());
    }

    [[nodiscard]] const std::vector<std::uint8_t>& bytes() const noexcept { return bytes_; }
    [[nodiscard]] std::vector<std::uint8_t> take() && { return std::move(bytes_); }

private:
    template <typename Unsigned>
    void write_unsigned(Unsigned value) {
        static_assert(std::is_unsigned_v<Unsigned>);
        for (std::size_t index = 0; index < sizeof(Unsigned); ++index) {
            const auto shift = static_cast<unsigned int>(index * 8U);
            bytes_.push_back(static_cast<std::uint8_t>(
                (value >> shift) & static_cast<Unsigned>(0xffU)));
        }
    }

    std::vector<std::uint8_t> bytes_{};
};

class Reader final {
public:
    explicit Reader(std::span<const std::uint8_t> bytes)
        : bytes_(bytes), payload_size_(validated_payload_size(bytes)) {}

    [[nodiscard]] std::uint8_t read_u8() {
        require_available(1);
        return bytes_[position_++];
    }

    [[nodiscard]] std::uint16_t read_u16() {
        return read_unsigned<std::uint16_t>();
    }

    [[nodiscard]] std::uint32_t read_u32() {
        return read_unsigned<std::uint32_t>();
    }

    [[nodiscard]] std::uint64_t read_u64() {
        return read_unsigned<std::uint64_t>();
    }

    [[nodiscard]] std::int64_t read_i64() {
        const auto bits = read_u64();
        constexpr auto signed_max = static_cast<std::uint64_t>(
            std::numeric_limits<std::int64_t>::max());
        if (bits <= signed_max) {
            return static_cast<std::int64_t>(bits);
        }
        const auto distance_from_minus_one = std::numeric_limits<std::uint64_t>::max() - bits;
        return static_cast<std::int64_t>(
            -1 - static_cast<std::int64_t>(distance_from_minus_one));
    }

    [[nodiscard]] std::size_t read_size() {
        const auto value = read_u64();
        if (value > static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max())) {
            reject("checkpoint collection size exceeds this platform");
        }
        return static_cast<std::size_t>(value);
    }

    [[nodiscard]] std::size_t read_collection_size(
        std::size_t minimum_encoded_bytes_per_entry = 1) {
        const auto value = read_size();
        if (minimum_encoded_bytes_per_entry == 0 ||
            value > remaining() / minimum_encoded_bytes_per_entry) {
            reject("checkpoint collection count exceeds the remaining payload");
        }
        return value;
    }

    void require_magic() {
        for (const auto expected : checkpoint_magic) {
            if (read_u8() != expected) {
                reject("checkpoint magic does not identify an MLS Time + Transfer image");
            }
        }
    }

    [[nodiscard]] bool finished() const noexcept { return position_ == payload_size_; }
    [[nodiscard]] std::size_t remaining() const noexcept {
        return payload_size_ - position_;
    }

private:
    [[nodiscard]] static std::uint64_t read_tail_u64(
        std::span<const std::uint8_t> bytes) noexcept {
        std::uint64_t value = 0;
        const auto start = bytes.size() - sizeof(std::uint64_t);
        for (std::size_t index = 0; index < sizeof(std::uint64_t); ++index) {
            const auto shift = static_cast<unsigned int>(index * 8U);
            value |= static_cast<std::uint64_t>(bytes[start + index]) << shift;
        }
        return value;
    }

    [[nodiscard]] static std::size_t validated_payload_size(
        std::span<const std::uint8_t> bytes) {
        if (bytes.size() < checkpoint_magic.size() + sizeof(std::uint32_t) * 2U +
                               sizeof(std::uint64_t)) {
            reject("checkpoint is truncated");
        }
        const auto payload_size = bytes.size() - sizeof(std::uint64_t);
        const auto recorded = read_tail_u64(bytes);
        const auto computed = checkpoint_checksum(bytes.first(payload_size));
        if (recorded != computed) {
            reject("checkpoint checksum mismatch");
        }
        return payload_size;
    }

    void require_available(std::size_t count) const {
        if (count > payload_size_ - position_) {
            reject("checkpoint is truncated");
        }
    }

    template <typename Unsigned>
    [[nodiscard]] Unsigned read_unsigned() {
        static_assert(std::is_unsigned_v<Unsigned>);
        require_available(sizeof(Unsigned));
        std::uint64_t value = 0;
        for (std::size_t index = 0; index < sizeof(Unsigned); ++index) {
            const auto shift = static_cast<unsigned int>(index * 8U);
            value |= static_cast<std::uint64_t>(bytes_[position_++]) << shift;
        }
        return static_cast<Unsigned>(value);
    }

    std::span<const std::uint8_t> bytes_{};
    std::size_t payload_size_{0};
    std::size_t position_{0};
};

template <typename QuantityType>
void write_quantity(Writer& writer, QuantityType value) {
    writer.write_i64(value.raw());
}

template <typename QuantityType>
[[nodiscard]] QuantityType read_quantity(Reader& reader) {
    return QuantityType::from_raw(reader.read_i64());
}

template <typename QuantityType>
void write_vector(Writer& writer, const Vector3<QuantityType>& value) {
    write_quantity(writer, value.x);
    write_quantity(writer, value.y);
    write_quantity(writer, value.z);
}

template <typename QuantityType>
[[nodiscard]] Vector3<QuantityType> read_vector(Reader& reader) {
    return {
        read_quantity<QuantityType>(reader),
        read_quantity<QuantityType>(reader),
        read_quantity<QuantityType>(reader)};
}

void write_inventory(Writer& writer, const ElementInventory& inventory) {
    writer.write_size(inventory.amounts().size());
    for (const auto& [element, count] : inventory.amounts()) {
        if (count <= 0) {
            throw std::logic_error("authoritative element inventory contains a nonpositive entry");
        }
        writer.write_u16(element.value);
        writer.write_i64(count);
    }
}

[[nodiscard]] ElementInventory read_inventory(Reader& reader) {
    ElementInventory result;
    const auto count = reader.read_collection_size(sizeof(std::uint16_t) + sizeof(std::int64_t));
    ElementId previous{};
    bool has_previous = false;
    for (std::size_t index = 0; index < count; ++index) {
        const ElementId element{reader.read_u16()};
        const auto amount = reader.read_i64();
        if ((has_previous && element <= previous) || amount <= 0) {
            reject("checkpoint element inventory is not in canonical map form");
        }
        result.add(element, amount);
        previous = element;
        has_previous = true;
    }
    return result;
}

void write_mixture(Writer& writer, const CompoundMixture& mixture) {
    writer.write_size(mixture.amounts().size());
    for (const auto& [compound, count] : mixture.amounts()) {
        if (count <= 0) {
            throw std::logic_error("authoritative compound mixture contains a nonpositive entry");
        }
        writer.write_u64(compound.value);
        writer.write_i64(count);
    }
}

[[nodiscard]] CompoundMixture read_mixture(Reader& reader) {
    CompoundMixture result;
    const auto count = reader.read_collection_size(sizeof(std::uint64_t) + sizeof(std::int64_t));
    CompoundId previous{};
    bool has_previous = false;
    for (std::size_t index = 0; index < count; ++index) {
        const CompoundId compound{reader.read_u64()};
        const auto amount = reader.read_i64();
        if ((has_previous && compound <= previous) || amount <= 0) {
            reject("checkpoint compound mixture is not in canonical map form");
        }
        result.add(compound, amount);
        previous = compound;
        has_previous = true;
    }
    return result;
}

void write_extensive_totals(Writer& writer, const ExtensiveTotals& totals) {
    write_inventory(writer, totals.elements);
    write_quantity(writer, totals.mass);
    write_quantity(writer, totals.structural_energy);
    write_quantity(writer, totals.stored_energy);
    write_quantity(writer, totals.thermal_energy);
    write_quantity(writer, totals.kinetic_energy);
    write_vector(writer, totals.momentum);
    write_vector(writer, totals.angular_momentum);
    writer.write_size(totals.packet_count);
}

[[nodiscard]] ExtensiveTotals read_extensive_totals(Reader& reader) {
    ExtensiveTotals result;
    result.elements = read_inventory(reader);
    result.mass = read_quantity<Mass>(reader);
    result.structural_energy = read_quantity<Energy>(reader);
    result.stored_energy = read_quantity<Energy>(reader);
    result.thermal_energy = read_quantity<Energy>(reader);
    result.kinetic_energy = read_quantity<Energy>(reader);
    result.momentum = read_vector<Momentum>(reader);
    result.angular_momentum = read_vector<AngularMomentum>(reader);
    result.packet_count = reader.read_size();
    return result;
}

void require_nonnegative_totals(const ExtensiveTotals& totals) {
    if (!is_nonnegative(totals.mass) || !is_nonnegative(totals.structural_energy) ||
        !is_nonnegative(totals.stored_energy) || !is_nonnegative(totals.thermal_energy) ||
        !is_nonnegative(totals.kinetic_energy)) {
        reject("checkpoint ledger baseline contains a negative extensive quantity");
    }
}

void write_boundary(Writer& writer, const BoundaryBalance& boundary) {
    writer.write_size(boundary.element_net.size());
    for (const auto& [element, count] : boundary.element_net) {
        if (count == 0) {
            throw std::logic_error("boundary element ledger contains a zero map entry");
        }
        writer.write_u16(element.value);
        writer.write_i64(count);
    }
    write_quantity(writer, boundary.mass_net);
    write_quantity(writer, boundary.energy_net);
    write_vector(writer, boundary.momentum_net);
    write_vector(writer, boundary.angular_momentum_net);
}

[[nodiscard]] BoundaryBalance read_boundary(Reader& reader) {
    BoundaryBalance result;
    const auto count = reader.read_collection_size(sizeof(std::uint16_t) + sizeof(std::int64_t));
    ElementId previous{};
    bool has_previous = false;
    for (std::size_t index = 0; index < count; ++index) {
        const ElementId element{reader.read_u16()};
        const auto amount = reader.read_i64();
        if ((has_previous && element <= previous) || amount == 0) {
            reject("checkpoint boundary element ledger is not in canonical map form");
        }
        result.element_net.emplace(element, amount);
        previous = element;
        has_previous = true;
    }
    result.mass_net = read_quantity<Mass>(reader);
    result.energy_net = read_quantity<Energy>(reader);
    result.momentum_net = read_vector<Momentum>(reader);
    result.angular_momentum_net = read_vector<AngularMomentum>(reader);
    return result;
}

void validate_clock(Tick tick, Time physical_time, Time physical_timestep) {
    if (physical_time.raw() < 0) {
        reject("checkpoint physical time cannot be negative");
    }
    if (tick > static_cast<Tick>(std::numeric_limits<Scalar>::max())) {
        reject("checkpoint Tick cannot be represented by the exact physical clock");
    }
    const auto expected = detail::checked_multiply(
        static_cast<Scalar>(tick), physical_timestep.raw());
    if (physical_time.raw() != expected) {
        reject("checkpoint physical time is inconsistent with Tick and configured timestep");
    }
}

struct DecodedPacket final {
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
};

void write_packet(Writer& writer, const PacketSnapshot& packet) {
    writer.write_u64(packet.handle.id.value);
    writer.write_u32(packet.handle.generation);
    write_vector(writer, packet.position);
    writer.write_i64(packet.integration_remainder.x);
    writer.write_i64(packet.integration_remainder.y);
    writer.write_i64(packet.integration_remainder.z);
    write_vector(writer, packet.momentum);
    write_mixture(writer, packet.composition);
    write_inventory(writer, packet.elements);
    write_quantity(writer, packet.mass);
    write_quantity(writer, packet.heat_capacity);
    write_quantity(writer, packet.structural_energy);
    write_quantity(writer, packet.stored_energy);
    write_quantity(writer, packet.thermal_energy);
}

[[nodiscard]] DecodedPacket read_packet(Reader& reader) {
    DecodedPacket result;
    result.handle.id.value = reader.read_u64();
    result.handle.generation = reader.read_u32();
    result.position = read_vector<Length>(reader);
    result.integration_remainder.x = reader.read_i64();
    result.integration_remainder.y = reader.read_i64();
    result.integration_remainder.z = reader.read_i64();
    result.momentum = read_vector<Momentum>(reader);
    result.composition = read_mixture(reader);
    result.elements = read_inventory(reader);
    result.mass = read_quantity<Mass>(reader);
    result.heat_capacity = read_quantity<HeatCapacity>(reader);
    result.structural_energy = read_quantity<Energy>(reader);
    result.stored_energy = read_quantity<Energy>(reader);
    result.thermal_energy = read_quantity<Energy>(reader);
    return result;
}

void require_packet_invariants(
    const DecodedPacket& packet,
    const CompoundRegistry& compounds,
    const ElementCatalog& elements,
    Scalar kinetic_energy_scale_denominator) {
    // Checkpoint format v2 encodes only currently reachable live handles.
    // Packet IDs are not reused, so every live packet has generation one.
    if (packet.handle.id.value == 0 || packet.handle.generation != 1U ||
        packet.composition.empty()) {
        reject("checkpoint contains an invalid live packet identity or composition");
    }
    if (packet.integration_remainder != PositionRemainder3{}) {
        reject("checkpoint contains a remainder unsupported by exact reference stepping");
    }
    if (inventory_of(packet.composition, compounds) != packet.elements ||
        mass_of(packet.composition, compounds, elements) != packet.mass ||
        heat_capacity_of(packet.composition, compounds, elements) != packet.heat_capacity ||
        structural_energy_of(packet.composition, compounds, elements) !=
            packet.structural_energy) {
        reject("checkpoint packet derived material fields are inconsistent");
    }
    if (packet.mass.raw() <= 0 || !is_nonnegative(packet.heat_capacity) ||
        !is_nonnegative(packet.structural_energy) || !is_nonnegative(packet.stored_energy) ||
        !is_nonnegative(packet.thermal_energy)) {
        reject("checkpoint packet contains an invalid extensive quantity");
    }
    static_cast<void>(kinetic_energy_of(
        packet.mass, packet.momentum, kinetic_energy_scale_denominator));
}

[[nodiscard]] std::uint64_t append_checksum(Writer& writer) {
    const auto checksum = checkpoint_checksum(writer.bytes());
    writer.write_u64(checksum);
    return checksum;
}

} // namespace

class CanonicalCheckpointCodec final {
public:
    [[nodiscard]] static std::vector<std::uint8_t> serialize(const World& world) {
        validate_time_configuration(
            world.config_.physical_timestep,
            world.config_.physical_time_scale,
            world.config_.momentum_mass_to_velocity_scale);
        validate_clock(world.tick_, world.physical_time_, world.config_.physical_timestep);
        if (!world.audit().ok()) {
            throw std::logic_error("cannot checkpoint a world with an open conservation error");
        }

        Writer writer;
        writer.write_magic();
        writer.write_u32(canonical_checkpoint_format_version);
        writer.write_u32(authoritative_physics_abi_version);

        write_quantity(writer, world.config_.voxel_edge);
        write_quantity(writer, world.config_.interaction_radius);
        writer.write_i64(world.config_.kinetic_energy_scale_denominator);
        write_quantity(writer, world.config_.physical_timestep);
        writer.write_u64(
            world.config_.physical_time_scale.seconds_per_time_quantum_numerator);
        writer.write_u64(
            world.config_.physical_time_scale.seconds_per_time_quantum_denominator);
        writer.write_i64(
            world.config_.momentum_mass_to_velocity_scale.length_quanta_numerator);
        writer.write_i64(
            world.config_.momentum_mass_to_velocity_scale.length_quanta_denominator);
        writer.write_size(world.config_.packet_history_limit);
        writer.write_u8(world.config_.audit_after_each_operation ? 1U : 0U);

        writer.write_u64(world.tick_);
        write_quantity(writer, world.physical_time_);

        writer.write_size(world.elements_.elements().size());
        for (const auto& [element, properties] : world.elements_.elements()) {
            writer.write_u16(element.value);
            write_quantity(writer, properties.unit_mass);
            write_quantity(writer, properties.unit_heat_capacity);
            write_quantity(writer, properties.isolated_energy);
        }
        writer.write_size(world.elements_.bond_rules().size());
        for (const auto& [key, energy] : world.elements_.bond_rules()) {
            writer.write_u16(key.first.value);
            writer.write_u16(key.second.value);
            writer.write_u8(key.order);
            write_quantity(writer, energy);
        }

        writer.write_size(world.compounds_.compounds().size());
        for (const auto& [compound_id, compound] : world.compounds_.compounds()) {
            writer.write_u64(compound_id.value);
            writer.write_size(compound.atoms().size());
            for (const auto atom : compound.atoms()) {
                writer.write_u16(atom.value);
            }
            writer.write_size(compound.bonds().size());
            for (const auto& bond : compound.bonds()) {
                writer.write_u32(bond.first);
                writer.write_u32(bond.second);
                writer.write_u8(bond.order);
            }
        }

        auto packets = world.packets_.snapshots();
        std::sort(
            packets.begin(),
            packets.end(),
            [](const PacketSnapshot& lhs, const PacketSnapshot& rhs) {
                return lhs.handle < rhs.handle;
            });
        writer.write_u64(world.packets_.next_id_.value);
        writer.write_size(packets.size());
        for (const auto& packet : packets) {
            write_packet(writer, packet);
        }

        write_extensive_totals(writer, world.ledger_.baseline_);
        write_boundary(writer, world.ledger_.boundary_);

        static_cast<void>(append_checksum(writer));
        return std::move(writer).take();
    }

    [[nodiscard]] static World deserialize(std::span<const std::uint8_t> checkpoint) {
        Reader reader(checkpoint);
        reader.require_magic();
        if (reader.read_u32() != canonical_checkpoint_format_version) {
            reject("checkpoint format version is unsupported");
        }
        if (reader.read_u32() != authoritative_physics_abi_version) {
            reject("checkpoint physics ABI version is unsupported");
        }

        WorldConfig config;
        config.voxel_edge = read_quantity<Length>(reader);
        config.interaction_radius = read_quantity<Length>(reader);
        config.kinetic_energy_scale_denominator = reader.read_i64();
        config.physical_timestep = read_quantity<Time>(reader);
        config.physical_time_scale.seconds_per_time_quantum_numerator = reader.read_u64();
        config.physical_time_scale.seconds_per_time_quantum_denominator = reader.read_u64();
        config.momentum_mass_to_velocity_scale.length_quanta_numerator = reader.read_i64();
        config.momentum_mass_to_velocity_scale.length_quanta_denominator = reader.read_i64();
        config.packet_history_limit = reader.read_size();
        const auto audit_flag = reader.read_u8();
        if (audit_flag > 1U) {
            reject("checkpoint boolean field is noncanonical");
        }
        config.audit_after_each_operation = audit_flag == 1U;
        validate_time_configuration(
            config.physical_timestep,
            config.physical_time_scale,
            config.momentum_mass_to_velocity_scale);

        const auto tick = reader.read_u64();
        const auto physical_time = read_quantity<Time>(reader);
        validate_clock(tick, physical_time, config.physical_timestep);

        ElementCatalog elements;
        const auto element_count = reader.read_collection_size(
            sizeof(std::uint16_t) + sizeof(std::int64_t) * 3U);
        ElementId previous_element{};
        bool has_previous_element = false;
        for (std::size_t index = 0; index < element_count; ++index) {
            const ElementId element{reader.read_u16()};
            if (has_previous_element && element <= previous_element) {
                reject("checkpoint element catalog is not in canonical map order");
            }
            elements.define(
                element,
                ElementProperties{
                    read_quantity<Mass>(reader),
                    read_quantity<HeatCapacity>(reader),
                    read_quantity<Energy>(reader)});
            previous_element = element;
            has_previous_element = true;
        }

        const auto bond_rule_count = reader.read_collection_size(
            sizeof(std::uint16_t) * 2U + sizeof(std::uint8_t) + sizeof(std::int64_t));
        BondRuleKey previous_bond_rule{};
        bool has_previous_bond_rule = false;
        for (std::size_t index = 0; index < bond_rule_count; ++index) {
            const BondRuleKey key{
                ElementId{reader.read_u16()}, ElementId{reader.read_u16()}, reader.read_u8()};
            const auto energy = read_quantity<Energy>(reader);
            if (key.second < key.first ||
                (has_previous_bond_rule && key <= previous_bond_rule)) {
                reject("checkpoint bond rules are not in canonical map order");
            }
            elements.define_bond_energy(key.first, key.second, key.order, energy);
            previous_bond_rule = key;
            has_previous_bond_rule = true;
        }

        CompoundRegistry compounds;
        const auto compound_count = reader.read_collection_size();
        CompoundId previous_compound{};
        bool has_previous_compound = false;
        for (std::size_t index = 0; index < compound_count; ++index) {
            const CompoundId encoded_id{reader.read_u64()};
            if (has_previous_compound && encoded_id <= previous_compound) {
                reject("checkpoint compounds are not in canonical map order");
            }
            const auto atom_count = reader.read_collection_size(sizeof(std::uint16_t));
            if (atom_count == 0 || atom_count > max_compound_atom_sites) {
                reject("checkpoint compound atom count is invalid");
            }
            std::vector<ElementId> atoms;
            atoms.reserve(atom_count);
            for (std::size_t atom_index = 0; atom_index < atom_count; ++atom_index) {
                atoms.push_back(ElementId{reader.read_u16()});
            }
            const auto bond_count = reader.read_collection_size(
                sizeof(std::uint32_t) * 2U + sizeof(std::uint8_t));
            std::vector<Bond> bonds;
            bonds.reserve(bond_count);
            for (std::size_t bond_index = 0; bond_index < bond_count; ++bond_index) {
                bonds.push_back(Bond{
                    reader.read_u32(), reader.read_u32(), reader.read_u8()});
            }
            const auto encoded_atoms = atoms;
            const auto encoded_bonds = bonds;
            CompoundGraph compound(std::move(atoms), std::move(bonds));
            if (compound.atoms() != encoded_atoms || compound.bonds() != encoded_bonds) {
                reject("checkpoint compound graph encoding is not canonical");
            }
            const auto computed_id = compounds.intern(std::move(compound));
            if (computed_id != encoded_id) {
                reject("checkpoint compound ID does not match its canonical graph");
            }
            previous_compound = encoded_id;
            has_previous_compound = true;
        }

        const PacketId next_id{reader.read_u64()};
        const auto packet_count = reader.read_collection_size();
        std::vector<DecodedPacket> packets;
        packets.reserve(packet_count);
        PacketId previous_packet{};
        bool has_previous_packet = false;
        for (std::size_t index = 0; index < packet_count; ++index) {
            auto packet = read_packet(reader);
            if (has_previous_packet && packet.handle.id <= previous_packet) {
                reject("checkpoint live packets are not in canonical ID order");
            }
            require_packet_invariants(
                packet, compounds, elements, config.kinetic_energy_scale_denominator);
            previous_packet = packet.handle.id;
            has_previous_packet = true;
            packets.push_back(std::move(packet));
        }
        if (next_id.value == 0 || (has_previous_packet && next_id <= previous_packet)) {
            reject("checkpoint next packet ID is inconsistent with live packet IDs");
        }

        auto baseline = read_extensive_totals(reader);
        require_nonnegative_totals(baseline);
        for (const auto& [element, amount] : baseline.elements.amounts()) {
            static_cast<void>(amount);
            if (!elements.contains(element)) {
                reject("checkpoint baseline ledger references an undefined element");
            }
        }
        auto boundary = read_boundary(reader);
        for (const auto& [element, amount] : boundary.element_net) {
            static_cast<void>(amount);
            if (!elements.contains(element)) {
                reject("checkpoint boundary ledger references an undefined element");
            }
        }
        if (!reader.finished()) {
            reject("checkpoint contains trailing or unrecognized payload bytes");
        }

        World result(std::move(elements), std::move(compounds), config);
        result.tick_ = tick;
        result.physical_time_ = physical_time;
        result.packets_ = PacketStore(
            config.packet_history_limit, config.kinetic_energy_scale_denominator);
        result.packets_.next_id_ = next_id;
        result.packets_.alive_count_ = packets.size();
        for (auto& packet : packets) {
            const auto slot = result.packets_.ids_.size();
            const auto [unused, inserted] =
                result.packets_.index_by_id_.emplace(packet.handle.id, slot);
            static_cast<void>(unused);
            if (!inserted) {
                reject("checkpoint contains duplicate packet IDs");
            }
            result.packets_.ids_.push_back(packet.handle.id);
            result.packets_.generations_.push_back(packet.handle.generation);
            result.packets_.alive_.push_back(true);
            result.packets_.position_x_.push_back(packet.position.x);
            result.packets_.position_y_.push_back(packet.position.y);
            result.packets_.position_z_.push_back(packet.position.z);
            result.packets_.position_remainder_x_.push_back(packet.integration_remainder.x);
            result.packets_.position_remainder_y_.push_back(packet.integration_remainder.y);
            result.packets_.position_remainder_z_.push_back(packet.integration_remainder.z);
            result.packets_.momentum_x_.push_back(packet.momentum.x);
            result.packets_.momentum_y_.push_back(packet.momentum.y);
            result.packets_.momentum_z_.push_back(packet.momentum.z);
            result.packets_.compositions_.push_back(std::move(packet.composition));
            result.packets_.elements_.push_back(std::move(packet.elements));
            result.packets_.masses_.push_back(packet.mass);
            result.packets_.heat_capacities_.push_back(packet.heat_capacity);
            result.packets_.structural_energies_.push_back(packet.structural_energy);
            result.packets_.stored_energies_.push_back(packet.stored_energy);
            result.packets_.thermal_energies_.push_back(packet.thermal_energy);
            result.packets_.histories_.emplace_back();
        }
        result.ledger_.baseline_ = std::move(baseline);
        result.ledger_.boundary_ = std::move(boundary);
        result.grid_.rebuild(result.packets_);
        if (!result.audit().ok()) {
            reject("checkpoint reconstructed state violates its conservation ledger");
        }
        if (serialize(result) != std::vector<std::uint8_t>(checkpoint.begin(), checkpoint.end())) {
            reject("checkpoint payload is valid but not canonically encoded");
        }
        return result;
    }
};

std::vector<std::uint8_t> serialize_canonical_checkpoint(const World& world) {
    return CanonicalCheckpointCodec::serialize(world);
}

World deserialize_canonical_checkpoint(std::span<const std::uint8_t> checkpoint) {
    return CanonicalCheckpointCodec::deserialize(checkpoint);
}

} // namespace mls
