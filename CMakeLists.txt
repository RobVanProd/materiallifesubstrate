cmake_minimum_required(VERSION 3.25)

project(
  MaterialLifeSubstrate
  VERSION 0.1.0
  DESCRIPTION "Falsification-first material substrate for 3D artificial-life research"
  LANGUAGES CXX)

option(MLS_BUILD_TESTS "Build the deterministic MLS validation suite" ON)
option(MLS_WARNINGS_AS_ERRORS "Treat compiler warnings as errors" OFF)
option(MLS_AUDIT_DEFAULT "Use deterministic audit-mode defaults" ON)

if(MLS_WARNINGS_AS_ERRORS)
  set(CMAKE_COMPILE_WARNING_AS_ERROR ON)
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

file(GLOB_RECURSE MLS_CORE_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp")
file(GLOB_RECURSE MLS_CORE_HEADERS CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/include/mls/*.hpp")

add_library(mls_core STATIC ${MLS_CORE_SOURCES} ${MLS_CORE_HEADERS})
target_include_directories(mls_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/include")
target_compile_features(mls_core PUBLIC cxx_std_20)
target_compile_definitions(mls_core PUBLIC MLS_AUDIT_DEFAULT=$<BOOL:${MLS_AUDIT_DEFAULT}>)

if(MSVC)
  target_compile_options(mls_core PRIVATE /W4 /permissive- /Zc:__cplusplus)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(mls_core PRIVATE /WX)
  endif()
else()
  target_compile_options(mls_core PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(mls_core PRIVATE -Werror)
  endif()
endif()

add_executable(mls_headless apps/mls_headless.cpp)
target_link_libraries(mls_headless PRIVATE mls_core)

find_package(Git QUIET)
set(MLS_CONFIGURED_SOURCE_SHA "unknown")
set(MLS_CONFIGURED_SOURCE_BRANCH "unknown")
set(MLS_CONFIGURED_SOURCE_DIRTY "true")
if(Git_FOUND)
  execute_process(
    COMMAND "${GIT_EXECUTABLE}" rev-parse HEAD
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    OUTPUT_VARIABLE MLS_CONFIGURED_SOURCE_SHA
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
    RESULT_VARIABLE MLS_CONFIGURED_SHA_RESULT)
  execute_process(
    COMMAND "${GIT_EXECUTABLE}" rev-parse --abbrev-ref HEAD
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    OUTPUT_VARIABLE MLS_CONFIGURED_SOURCE_BRANCH
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
    RESULT_VARIABLE MLS_CONFIGURED_BRANCH_RESULT)
  execute_process(
    COMMAND "${GIT_EXECUTABLE}" status --porcelain
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    OUTPUT_VARIABLE MLS_CONFIGURED_STATUS
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
    RESULT_VARIABLE MLS_CONFIGURED_STATUS_RESULT)
  if(MLS_CONFIGURED_SHA_RESULT EQUAL 0
     AND MLS_CONFIGURED_BRANCH_RESULT EQUAL 0
     AND MLS_CONFIGURED_STATUS_RESULT EQUAL 0
     AND MLS_CONFIGURED_STATUS STREQUAL "")
    set(MLS_CONFIGURED_SOURCE_DIRTY "false")
  endif()
endif()

add_executable(mls_transfer_bakeoff apps/transfer_bakeoff.cpp)
target_link_libraries(mls_transfer_bakeoff PRIVATE mls_core)
target_compile_features(mls_transfer_bakeoff PRIVATE cxx_std_20)
target_compile_definitions(
  mls_transfer_bakeoff
  PRIVATE
    MLS_CONFIGURED_SOURCE_SHA="${MLS_CONFIGURED_SOURCE_SHA}"
    MLS_CONFIGURED_SOURCE_BRANCH="${MLS_CONFIGURED_SOURCE_BRANCH}"
    MLS_CONFIGURED_SOURCE_DIRTY="${MLS_CONFIGURED_SOURCE_DIRTY}"
    MLS_CONFIGURED_COMPILER_ID="${CMAKE_CXX_COMPILER_ID}"
    MLS_CONFIGURED_COMPILER_VERSION="${CMAKE_CXX_COMPILER_VERSION}")
if(MSVC)
  target_compile_options(mls_transfer_bakeoff PRIVATE /W4 /permissive- /Zc:__cplusplus)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(mls_transfer_bakeoff PRIVATE /WX)
  endif()
else()
  target_compile_options(
    mls_transfer_bakeoff PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(mls_transfer_bakeoff PRIVATE -Werror)
  endif()
endif()

add_executable(mls_affine_advection_diagnostic apps/affine_advection_diagnostic.cpp)
target_link_libraries(mls_affine_advection_diagnostic PRIVATE mls_core)
target_compile_features(mls_affine_advection_diagnostic PRIVATE cxx_std_20)
target_compile_definitions(
  mls_affine_advection_diagnostic
  PRIVATE
    MLS_CONFIGURED_SOURCE_SHA="${MLS_CONFIGURED_SOURCE_SHA}"
    MLS_CONFIGURED_SOURCE_BRANCH="${MLS_CONFIGURED_SOURCE_BRANCH}"
    MLS_CONFIGURED_SOURCE_DIRTY="${MLS_CONFIGURED_SOURCE_DIRTY}"
    MLS_CONFIGURED_COMPILER_ID="${CMAKE_CXX_COMPILER_ID}"
    MLS_CONFIGURED_COMPILER_VERSION="${CMAKE_CXX_COMPILER_VERSION}")
if(MSVC)
  target_compile_options(
    mls_affine_advection_diagnostic PRIVATE /W4 /permissive- /Zc:__cplusplus)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(mls_affine_advection_diagnostic PRIVATE /WX)
  endif()
else()
  target_compile_options(
    mls_affine_advection_diagnostic
    PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(mls_affine_advection_diagnostic PRIVATE -Werror)
  endif()
endif()

add_executable(mls_moving_apic_limit_diagnostic apps/moving_apic_limit_diagnostic.cpp)
target_link_libraries(mls_moving_apic_limit_diagnostic PRIVATE mls_core)
target_compile_features(mls_moving_apic_limit_diagnostic PRIVATE cxx_std_20)
target_compile_definitions(
  mls_moving_apic_limit_diagnostic
  PRIVATE
    MLS_CONFIGURED_SOURCE_SHA="${MLS_CONFIGURED_SOURCE_SHA}"
    MLS_CONFIGURED_SOURCE_BRANCH="${MLS_CONFIGURED_SOURCE_BRANCH}"
    MLS_CONFIGURED_SOURCE_DIRTY="${MLS_CONFIGURED_SOURCE_DIRTY}"
    MLS_CONFIGURED_COMPILER_ID="${CMAKE_CXX_COMPILER_ID}"
    MLS_CONFIGURED_COMPILER_VERSION="${CMAKE_CXX_COMPILER_VERSION}")
if(MSVC)
  target_compile_options(
    mls_moving_apic_limit_diagnostic PRIVATE /W4 /permissive- /Zc:__cplusplus)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(mls_moving_apic_limit_diagnostic PRIVATE /WX)
  endif()
else()
  target_compile_options(
    mls_moving_apic_limit_diagnostic
    PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(mls_moving_apic_limit_diagnostic PRIVATE -Werror)
  endif()
endif()

find_package(Threads REQUIRED)
add_executable(
  mls_projection_foundation_diagnostic
  apps/projection_foundation_diagnostic.cpp)
target_link_libraries(
  mls_projection_foundation_diagnostic PRIVATE mls_core Threads::Threads)
target_compile_features(mls_projection_foundation_diagnostic PRIVATE cxx_std_20)
target_compile_definitions(
  mls_projection_foundation_diagnostic
  PRIVATE
    MLS_CONFIGURED_SOURCE_SHA="${MLS_CONFIGURED_SOURCE_SHA}"
    MLS_CONFIGURED_SOURCE_BRANCH="${MLS_CONFIGURED_SOURCE_BRANCH}"
    MLS_CONFIGURED_SOURCE_DIRTY="${MLS_CONFIGURED_SOURCE_DIRTY}"
    MLS_CONFIGURED_COMPILER_ID="${CMAKE_CXX_COMPILER_ID}"
    MLS_CONFIGURED_COMPILER_VERSION="${CMAKE_CXX_COMPILER_VERSION}")
if(MSVC)
  target_compile_options(
    mls_projection_foundation_diagnostic PRIVATE /W4 /permissive- /Zc:__cplusplus)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(mls_projection_foundation_diagnostic PRIVATE /WX)
  endif()
else()
  target_compile_options(
    mls_projection_foundation_diagnostic
    PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(mls_projection_foundation_diagnostic PRIVATE -Werror)
  endif()
endif()

add_executable(
  mls_projection_exactness_nullspace_diagnostic
  apps/projection_exactness_nullspace_diagnostic.cpp)
target_link_libraries(
  mls_projection_exactness_nullspace_diagnostic PRIVATE mls_core Threads::Threads)
target_compile_features(
  mls_projection_exactness_nullspace_diagnostic PRIVATE cxx_std_20)
target_compile_definitions(
  mls_projection_exactness_nullspace_diagnostic
  PRIVATE
    MLS_CONFIGURED_SOURCE_SHA="${MLS_CONFIGURED_SOURCE_SHA}"
    MLS_CONFIGURED_SOURCE_BRANCH="${MLS_CONFIGURED_SOURCE_BRANCH}"
    MLS_CONFIGURED_SOURCE_DIRTY="${MLS_CONFIGURED_SOURCE_DIRTY}"
    MLS_CONFIGURED_COMPILER_ID="${CMAKE_CXX_COMPILER_ID}"
    MLS_CONFIGURED_COMPILER_VERSION="${CMAKE_CXX_COMPILER_VERSION}")
if(MSVC)
  target_compile_options(
    mls_projection_exactness_nullspace_diagnostic
    PRIVATE /W4 /permissive- /Zc:__cplusplus)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(
      mls_projection_exactness_nullspace_diagnostic PRIVATE /WX)
  endif()
else()
  target_compile_options(
    mls_projection_exactness_nullspace_diagnostic
    PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
  if(MLS_WARNINGS_AS_ERRORS)
    target_compile_options(
      mls_projection_exactness_nullspace_diagnostic PRIVATE -Werror)
  endif()
endif()

include(CTest)
if(BUILD_TESTING AND MLS_BUILD_TESTS)
  add_subdirectory(tests)
endif()
