#include "mls/world.hpp"

#include "test_harness.hpp"

#include <type_traits>

template <typename Store>
concept PublicPacketCreation = requires(Store& store, mls::PacketInitialState initial) {
    store.create(initial);
};

template <typename Store>
concept PublicPacketHeatMutation = requires(
    Store& store, mls::PacketHandle first, mls::PacketHandle second) {
    store.transfer_heat(first, second, mls::Energy::from_raw(1), mls::Tick{1});
};

template <typename Store>
concept PublicPacketBoundaryMutation = requires(
    Store& store, mls::PacketHandle packet) {
    store.adjust_boundary_momentum(packet, mls::Momentum3{}, mls::Tick{1});
};

static_assert(!PublicPacketCreation<mls::PacketStore>);
static_assert(!PublicPacketHeatMutation<mls::PacketStore>);
static_assert(!PublicPacketBoundaryMutation<mls::PacketStore>);
static_assert(std::is_same_v<
              decltype(std::declval<const mls::World&>().packets()),
              const mls::PacketStore&>);

MLS_TEST("hardening/abi/packet_mutation_is_world_private") {
    MLS_REQUIRE(!PublicPacketCreation<mls::PacketStore>);
    MLS_REQUIRE(!PublicPacketHeatMutation<mls::PacketStore>);
    MLS_REQUIRE(!PublicPacketBoundaryMutation<mls::PacketStore>);
}
