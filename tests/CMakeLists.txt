include("${CMAKE_CURRENT_SOURCE_DIR}/api_compile_contracts.cmake")

add_executable(
  mls_validation
  test_main.cpp
  core_validation_tests.cpp
  angular_momentum_tests.cpp
  authoritative_api_tests.cpp
  compound_identity_tests.cpp
  physical_support_tests.cpp
  transfer_lab_tests.cpp
  time_checkpoint_tests.cpp)

target_link_libraries(mls_validation PRIVATE mls_core)
target_include_directories(mls_validation PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_features(mls_validation PRIVATE cxx_std_20)

if(MSVC)
  target_compile_options(mls_validation PRIVATE /W4 /permissive- /Zc:__cplusplus)
else()
  target_compile_options(mls_validation PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
endif()

add_test(NAME mls.validation COMMAND mls_validation)
set_tests_properties(mls.validation PROPERTIES LABELS "deterministic;core")

find_package(Python3 QUIET COMPONENTS Interpreter)
if(Python3_Interpreter_FOUND)
  add_test(
    NAME mls.exact.quick
    COMMAND "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/exact_validation.py" --mode quick)
  set_tests_properties(mls.exact.quick PROPERTIES LABELS "deterministic;exact;quick")

  add_test(
    NAME mls.exact.provenance
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/tools/exact_validation.py"
      --mode full
      --provenance-only
      --verify
      "${PROJECT_SOURCE_DIR}/reference/validation_results_v0.json")
  set_tests_properties(
    mls.exact.provenance
    PROPERTIES LABELS "deterministic;exact;full;provenance" TIMEOUT 120)

  option(
    MLS_RUN_EXTENDED_EXACT_TESTS
    "Run the slower full witness-digest oracle in the default CTest set"
    OFF)
  if(MLS_RUN_EXTENDED_EXACT_TESTS)
    add_test(
      NAME mls.exact.extended.full
      COMMAND
        "${Python3_EXECUTABLE}"
        "${PROJECT_SOURCE_DIR}/tools/exact_validation.py"
        --mode full
        --verify
        "${CMAKE_CURRENT_SOURCE_DIR}/exact_validation_full.canonical.json")
    set_tests_properties(
      mls.exact.extended.full
      PROPERTIES LABELS "deterministic;exact;extended;full" TIMEOUT 180)

    add_test(
      NAME mls.hardening.independent.oracle
      COMMAND
        "${Python3_EXECUTABLE}"
        "${PROJECT_SOURCE_DIR}/reference/hardening_oracle.py"
        --verify
        "${CMAKE_CURRENT_SOURCE_DIR}/hardening_oracle.canonical.json")
    set_tests_properties(
      mls.hardening.independent.oracle
      PROPERTIES LABELS "deterministic;exact;hardening;independent" TIMEOUT 30)

    add_test(
      NAME mls.transfer.independent.oracle
      COMMAND
        "${Python3_EXECUTABLE}"
        "${PROJECT_SOURCE_DIR}/reference/transfer_oracle.py"
        --cases 1000
        --verify
        "${CMAKE_CURRENT_SOURCE_DIR}/transfer_oracle.canonical.json")
    set_tests_properties(
      mls.transfer.independent.oracle
      PROPERTIES LABELS "deterministic;exact;transfer;independent" TIMEOUT 120)
  endif()
endif()
