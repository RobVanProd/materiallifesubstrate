#include "mls/world.hpp"

#include "test_harness.hpp"

#include <type_traits>

static_assert(std::is_same_v<
              decltype(std::declval<const mls::World&>().packets()),
              const mls::PacketStore&>);

MLS_TEST("hardening/abi/world_exposes_only_const_packet_store") {
    MLS_REQUIRE((std::is_same_v<
        decltype(std::declval<const mls::World&>().packets()),
        const mls::PacketStore&>));
}
