# Verify actual external compilation, not introspection of inaccessible APIs.
if(DEFINED CMAKE_TRY_COMPILE_TARGET_TYPE)
  set(_world_saved_try_type "${CMAKE_TRY_COMPILE_TARGET_TYPE}")
endif()
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
set(_world_probe_flags "-DCMAKE_CXX_STANDARD:STRING=20" "-DINCLUDE_DIRECTORIES:STRING=${PROJECT_SOURCE_DIR}/include")
try_compile(_world_default_read SOURCE_FROM_CONTENT world_default_read.cpp
  "#include <mls/world.hpp>\nauto read(const mls::World& w) { return w.tick(); }\n"
  CMAKE_FLAGS ${_world_probe_flags} NO_CACHE)
if(NOT _world_default_read)
  message(FATAL_ERROR "Default World positive compilation control failed")
endif()
try_compile(_world_default_research SOURCE_FROM_CONTENT world_default_research.cpp
  "#include <mls/world.hpp>\nauto read(const mls::World& w) { return w.research_mechanics(); }\n"
  CMAKE_FLAGS ${_world_probe_flags} NO_CACHE)
if(_world_default_research)
  message(FATAL_ERROR "Research mechanics leaked into the default World API")
endif()
try_compile(_world_enabled_research SOURCE_FROM_CONTENT world_enabled_research.cpp
  "#include <mls/world.hpp>\nauto read(const mls::World& w) { return w.research_mechanics(); }\n"
  CMAKE_FLAGS ${_world_probe_flags} COMPILE_DEFINITIONS -DMLS_RESEARCH_WORLD_MECHANICS=1 NO_CACHE)
if(NOT _world_enabled_research)
  message(FATAL_ERROR "Explicit research World API compilation control failed")
endif()
if(DEFINED _world_saved_try_type)
  set(CMAKE_TRY_COMPILE_TARGET_TYPE "${_world_saved_try_type}")
  unset(_world_saved_try_type)
else()
  unset(CMAKE_TRY_COMPILE_TARGET_TYPE)
endif()
message(STATUS "World integration build quarantine: PASS")
