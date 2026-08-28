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

include(CTest)
if(BUILD_TESTING AND MLS_BUILD_TESTS)
  add_subdirectory(tests)
endif()
