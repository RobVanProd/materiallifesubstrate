set(_material_saved_try_type "${CMAKE_TRY_COMPILE_TARGET_TYPE}")
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
set(_material_flags "-DCMAKE_CXX_STANDARD:STRING=20" "-DINCLUDE_DIRECTORIES:STRING=${PROJECT_SOURCE_DIR}/include")
try_compile(_material_default SOURCE_FROM_CONTENT material_default.cpp
  "#include <mls/world.hpp>\nauto f(const mls::World& w) { return w.material_phase_mechanics(); }\n"
  CMAKE_FLAGS ${_material_flags} NO_CACHE)
if(_material_default)
  message(FATAL_ERROR "Unified mechanics leaked into default World")
endif()
try_compile(_material_enabled SOURCE_FROM_CONTENT material_enabled.cpp
  "#include <mls/world.hpp>\ntemplate<class T> concept LegacyPosition = requires(T p) { p.position; };\ntemplate<class T> concept LegacyMomentum = requires(T p) { p.momentum; };\nstatic_assert(!LegacyPosition<mls::MaterialPhasePacket> && !LegacyMomentum<mls::MaterialPhasePacket>);\nstatic_assert(sizeof(mls::MaterialPhasePacket{}.phase)==102);\nauto f(const mls::World& w) { return w.material_phase_mechanics(); }\n"
  CMAKE_FLAGS ${_material_flags} COMPILE_DEFINITIONS -DMLS_RESEARCH_WORLD_MECHANICS=1 -DMLS_RESEARCH_MATERIAL_PHASE=1 NO_CACHE)
if(NOT _material_enabled)
  message(FATAL_ERROR "Single B96 material authority compilation contract failed")
endif()
if(_material_saved_try_type)
  set(CMAKE_TRY_COMPILE_TARGET_TYPE "${_material_saved_try_type}")
else()
  unset(CMAKE_TRY_COMPILE_TARGET_TYPE)
endif()
message(STATUS "Material phase build quarantine and no legacy phase fields: PASS")
