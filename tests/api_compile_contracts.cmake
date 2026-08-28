# Compile real external-client expressions instead of inferring access through
# requires-expressions. MSVC 19.51 can incorrectly report private member access
# as well-formed inside a requires-expression.

set(_mls_had_try_compile_target_type FALSE)
if(DEFINED CMAKE_TRY_COMPILE_TARGET_TYPE)
  set(_mls_had_try_compile_target_type TRUE)
  set(_mls_saved_try_compile_target_type "${CMAKE_TRY_COMPILE_TARGET_TYPE}")
endif()
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(
  _mls_api_probe_cmake_flags
  "-DCMAKE_CXX_STANDARD:STRING=20"
  "-DCMAKE_CXX_STANDARD_REQUIRED:BOOL=ON"
  "-DCMAKE_CXX_EXTENSIONS:BOOL=OFF"
  "-DINCLUDE_DIRECTORIES:STRING=${PROJECT_SOURCE_DIR}/include")

try_compile(
  _mls_public_read_probe_compiles
  SOURCE_FROM_CONTENT
    packet_store_public_read_probe.cpp
    [=[
#include "mls/packet_store.hpp"

std::size_t probe(const mls::PacketStore& store) {
    return store.alive_count();
}
]=]
  CMAKE_FLAGS ${_mls_api_probe_cmake_flags}
  NO_CACHE
  OUTPUT_VARIABLE _mls_public_read_probe_output)

if(NOT _mls_public_read_probe_compiles)
  message(
    FATAL_ERROR
      "PacketStore API probes are invalid: the public read positive control failed:\n"
      "${_mls_public_read_probe_output}")
endif()

function(mls_assert_external_call_rejected probe_name probe_source)
  try_compile(
    _mls_private_call_compiles
    SOURCE_FROM_CONTENT "${probe_name}.cpp" "${probe_source}"
    CMAKE_FLAGS ${_mls_api_probe_cmake_flags}
    NO_CACHE
    OUTPUT_VARIABLE _mls_private_call_output)

  if(_mls_private_call_compiles)
    message(
      FATAL_ERROR
        "Authoritative API violation: external PacketStore call '${probe_name}' compiled")
  endif()
  message(STATUS "Verified external PacketStore call is rejected: ${probe_name}")
endfunction()

mls_assert_external_call_rejected(
  packet_store_create
  [=[
#include "mls/packet_store.hpp"

void probe(mls::PacketStore& store, mls::PacketInitialState initial) {
    static_cast<void>(store.create(initial, mls::Tick{0}));
}
]=])

mls_assert_external_call_rejected(
  packet_store_transfer_heat
  [=[
#include "mls/packet_store.hpp"

void probe(mls::PacketStore& store) {
    store.transfer_heat(
        mls::PacketHandle{},
        mls::PacketHandle{},
        mls::Energy::from_raw(1),
        mls::Tick{1});
}
]=])

mls_assert_external_call_rejected(
  packet_store_adjust_boundary_momentum
  [=[
#include "mls/packet_store.hpp"

void probe(mls::PacketStore& store) {
    static_cast<void>(store.adjust_boundary_momentum(
        mls::PacketHandle{}, mls::Momentum3{}, mls::Tick{1}));
}
]=])

if(_mls_had_try_compile_target_type)
  set(CMAKE_TRY_COMPILE_TARGET_TYPE "${_mls_saved_try_compile_target_type}")
else()
  unset(CMAKE_TRY_COMPILE_TARGET_TYPE)
endif()

unset(_mls_api_probe_cmake_flags)
unset(_mls_had_try_compile_target_type)
unset(_mls_saved_try_compile_target_type)
unset(_mls_public_read_probe_compiles)
unset(_mls_public_read_probe_output)
