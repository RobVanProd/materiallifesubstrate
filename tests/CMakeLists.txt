include("${CMAKE_CURRENT_SOURCE_DIR}/api_compile_contracts.cmake")

add_executable(
  mls_validation
  test_main.cpp
  core_validation_tests.cpp
  angular_momentum_tests.cpp
  authoritative_api_tests.cpp
  compound_identity_tests.cpp
  physical_support_tests.cpp
  affine_advection_tests.cpp
  moving_apic_limit_tests.cpp
  projection_exactness_nullspace_tests.cpp
  projection_foundation_tests.cpp
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

add_test(
  NAME mls.transfer.bakeoff.smoke.a
  COMMAND
    mls_transfer_bakeoff
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/transfer-bakeoff-smoke-a")
add_test(
  NAME mls.transfer.bakeoff.smoke.b
  COMMAND
    mls_transfer_bakeoff
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/transfer-bakeoff-smoke-b")
set_tests_properties(
  mls.transfer.bakeoff.smoke.a
  mls.transfer.bakeoff.smoke.b
  PROPERTIES
    LABELS "deterministic;transfer;smoke"
    PASS_REGULAR_EXPRESSION "Time \\+ Transfer smoke evidence written"
    TIMEOUT 120)

add_test(
  NAME mls.affine_advection.smoke.a
  COMMAND
    mls_affine_advection_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/affine-advection-smoke-a")
add_test(
  NAME mls.affine_advection.smoke.b
  COMMAND
    mls_affine_advection_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/affine-advection-smoke-b")
set_tests_properties(
  mls.affine_advection.smoke.a
  mls.affine_advection.smoke.b
  PROPERTIES
    LABELS "deterministic;affine;smoke"
    PASS_REGULAR_EXPRESSION "Affine Advection smoke diagnostic evidence written"
    TIMEOUT 120)

add_test(
  NAME mls.moving_apic_limit.smoke.a
  COMMAND
    mls_moving_apic_limit_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/moving-apic-limit-smoke-a")
add_test(
  NAME mls.moving_apic_limit.smoke.b
  COMMAND
    mls_moving_apic_limit_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/moving-apic-limit-smoke-b")
set_tests_properties(
  mls.moving_apic_limit.smoke.a
  mls.moving_apic_limit.smoke.b
  PROPERTIES
    LABELS "deterministic;moving-apic-limit;smoke"
    PASS_REGULAR_EXPRESSION "Moving APIC Limit smoke evidence written"
    TIMEOUT 180)

add_test(
  NAME mls.projection_foundation.smoke.a
  COMMAND
    mls_projection_foundation_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/projection-foundation-smoke-a")
add_test(
  NAME mls.projection_foundation.smoke.b
  COMMAND
    mls_projection_foundation_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/projection-foundation-smoke-b")
set_tests_properties(
  mls.projection_foundation.smoke.a
  mls.projection_foundation.smoke.b
  PROPERTIES
    LABELS "deterministic;projection-foundation;smoke"
    PASS_REGULAR_EXPRESSION "Projection Foundation smoke evidence written"
    TIMEOUT 180)

add_test(
  NAME mls.projection_foundation.schema.audit
  COMMAND mls_projection_foundation_diagnostic --schema-audit)
set_tests_properties(
  mls.projection_foundation.schema.audit
  PROPERTIES
    LABELS "deterministic;projection-foundation;schema"
    PASS_REGULAR_EXPRESSION "Projection Foundation full schema audit: PASS"
    TIMEOUT 30)

add_test(
  NAME mls.projection_exactness_nullspace.smoke.a
  COMMAND
    mls_projection_exactness_nullspace_diagnostic
    --smoke
    --jobs 2
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/projection-exactness-nullspace-smoke-a")
add_test(
  NAME mls.projection_exactness_nullspace.smoke.b
  COMMAND
    mls_projection_exactness_nullspace_diagnostic
    --smoke
    --jobs 2
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/projection-exactness-nullspace-smoke-b")
set_tests_properties(
  mls.projection_exactness_nullspace.smoke.a
  mls.projection_exactness_nullspace.smoke.b
  PROPERTIES
    LABELS "deterministic;projection-nullspace;smoke"
    PASS_REGULAR_EXPRESSION
      "Projection Exactness \\+ Nullspace provisional smoke evidence written"
    TIMEOUT 180)

add_test(
  NAME mls.projection_exactness_nullspace.schema.audit
  COMMAND mls_projection_exactness_nullspace_diagnostic --schema-audit)
set_tests_properties(
  mls.projection_exactness_nullspace.schema.audit
  PROPERTIES
    LABELS "deterministic;projection-nullspace;schema"
    PASS_REGULAR_EXPRESSION
      "Projection Exactness \\+ Nullspace schema audit: PASS"
    TIMEOUT 30)

add_test(
  NAME mls.projection_exactness_nullspace.logic.audit
  COMMAND mls_projection_exactness_nullspace_diagnostic --logic-audit)
set_tests_properties(
  mls.projection_exactness_nullspace.logic.audit
  PROPERTIES
    LABELS "deterministic;projection-nullspace;logic"
    PASS_REGULAR_EXPRESSION
      "Projection Exactness \\+ Nullspace logic audit: PASS"
    TIMEOUT 30)

find_package(Python3 QUIET COMPONENTS Interpreter)
if(Python3_Interpreter_FOUND)
  add_test(
    NAME mls.projection_exactness_nullspace.smoke.byte_compare
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/compare_evidence_directories.py"
      --first
      "${CMAKE_CURRENT_BINARY_DIR}/projection-exactness-nullspace-smoke-a"
      --second
      "${CMAKE_CURRENT_BINARY_DIR}/projection-exactness-nullspace-smoke-b")
  set_tests_properties(
    mls.projection_exactness_nullspace.smoke.byte_compare
    PROPERTIES
      DEPENDS
        "mls.projection_exactness_nullspace.smoke.a;mls.projection_exactness_nullspace.smoke.b"
      LABELS "deterministic;projection-nullspace;smoke;independent"
      PASS_REGULAR_EXPRESSION
        "Projection exactness/nullspace smoke byte comparison: PASS"
      TIMEOUT 30)

  add_test(
    NAME mls.projection_exactness_nullspace.smoke.verify
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/validate_projection_exactness_nullspace_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/projection-exactness-nullspace-smoke-a"
      --compare
      "${CMAKE_CURRENT_BINARY_DIR}/projection-exactness-nullspace-smoke-b"
      --smoke-provisional)
  set_tests_properties(
    mls.projection_exactness_nullspace.smoke.verify
    PROPERTIES
      DEPENDS
        "mls.projection_exactness_nullspace.smoke.a;mls.projection_exactness_nullspace.smoke.b"
      LABELS "deterministic;projection-nullspace;smoke;independent"
      PASS_REGULAR_EXPRESSION
        "PROJECTION EXACTNESS NULLSPACE BUNDLE VALID"
      TIMEOUT 300)

  add_test(
    NAME mls.formal.source.scan
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/tools/formal_trust_scan.py"
      --formal-root
      "${PROJECT_SOURCE_DIR}/formal")
  set_tests_properties(
    mls.formal.source.scan
    PROPERTIES
      LABELS "deterministic;formal;trust"
      PASS_REGULAR_EXPRESSION
        "PASS: no sorry, admit, sorryAx, project-defined axiom declaration, or unreported theorem"
      TIMEOUT 30)

  add_test(
    NAME mls.transfer.bakeoff.smoke.verify
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/validate_transfer_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/transfer-bakeoff-smoke-a"
      --compare
      "${CMAKE_CURRENT_BINARY_DIR}/transfer-bakeoff-smoke-b"
      --smoke-provisional)
  set_tests_properties(
    mls.transfer.bakeoff.smoke.verify
    PROPERTIES
      DEPENDS "mls.transfer.bakeoff.smoke.a;mls.transfer.bakeoff.smoke.b"
      LABELS "deterministic;transfer;smoke;independent"
      PASS_REGULAR_EXPRESSION "TRANSFER BUNDLE VALID"
      TIMEOUT 120)

  add_test(
    NAME mls.transfer.verifier.convergence
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/transfer_verifier_convergence_test.py")
  set_tests_properties(
    mls.transfer.verifier.convergence
    PROPERTIES
      LABELS "deterministic;transfer;verifier"
      PASS_REGULAR_EXPRESSION "verifier convergence regression: PASS")

  add_test(
    NAME mls.affine_advection.exact.oracle
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/affine_advection_oracle.py"
      --verify
      "${CMAKE_CURRENT_SOURCE_DIR}/affine_advection_oracle.canonical.json")
  set_tests_properties(
    mls.affine_advection.exact.oracle
    PROPERTIES
      LABELS "deterministic;exact;affine;independent"
      PASS_REGULAR_EXPRESSION "result_sha256_before_hash_field"
      TIMEOUT 60)

  add_test(
    NAME mls.moving_apic_limit.exact.oracle
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/moving_apic_limit_oracle.py"
      --verify
      "${CMAKE_CURRENT_SOURCE_DIR}/moving_apic_limit_oracle.canonical.json")
  set_tests_properties(
    mls.moving_apic_limit.exact.oracle
    PROPERTIES
      LABELS "deterministic;exact;moving-apic-limit;independent"
      PASS_REGULAR_EXPRESSION "result_sha256_before_hash_field"
      TIMEOUT 60)

  add_test(
    NAME mls.projection_foundation.exact.oracle
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/projection_foundation_oracle.py"
      --verify
      "${CMAKE_CURRENT_SOURCE_DIR}/projection_foundation_oracle.canonical.json")
  set_tests_properties(
    mls.projection_foundation.exact.oracle
    PROPERTIES
      LABELS "deterministic;exact;projection-foundation;independent"
      PASS_REGULAR_EXPRESSION "result_sha256_before_hash_field"
      TIMEOUT 60)

  add_test(
    NAME mls.projection_exactness_nullspace.exact.oracle
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/projection_exactness_nullspace_oracle.py"
      --verify
      "${CMAKE_CURRENT_SOURCE_DIR}/projection_exactness_nullspace_oracle.canonical.json")
  set_tests_properties(
    mls.projection_exactness_nullspace.exact.oracle
    PROPERTIES
      LABELS "deterministic;exact;projection-nullspace;independent"
      PASS_REGULAR_EXPRESSION "result_sha256_before_hash_field"
      TIMEOUT 60)

  add_test(
    NAME mls.projection_exactness_nullspace.validator.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/projection_exactness_nullspace_validator_test.py")
  set_tests_properties(
    mls.projection_exactness_nullspace.validator.regression
    PROPERTIES
      LABELS "deterministic;projection-nullspace;validator;independent"
      PASS_REGULAR_EXPRESSION
        "Projection exactness/nullspace validator regression: PASS"
      TIMEOUT 180)

  add_test(
    NAME mls.projection_exactness_nullspace.seal.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/projection_exactness_nullspace_seal_test.py"
      --tool
      "${PROJECT_SOURCE_DIR}/tools/seal_projection_exactness_nullspace_evidence.py")
  set_tests_properties(
    mls.projection_exactness_nullspace.seal.regression
    PROPERTIES
      LABELS "deterministic;projection-nullspace;seal;independent"
      PASS_REGULAR_EXPRESSION
        "projection exactness/nullspace outer seal mutation regression PASS"
      TIMEOUT 180)

  add_test(
    NAME mls.affine_advection.smoke.verify
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/validate_affine_advection_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/affine-advection-smoke-a"
      --compare
      "${CMAKE_CURRENT_BINARY_DIR}/affine-advection-smoke-b"
      --smoke-provisional)
  set_tests_properties(
    mls.affine_advection.smoke.verify
    PROPERTIES
      DEPENDS "mls.affine_advection.smoke.a;mls.affine_advection.smoke.b"
      LABELS "deterministic;affine;smoke;independent"
      PASS_REGULAR_EXPRESSION "AFFINE ADVECTION BUNDLE SMOKE PROVISIONAL"
      TIMEOUT 120)

  add_test(
    NAME mls.affine_advection.validator.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/affine_advection_bundle_validator_test.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/affine-advection-smoke-a"
      --validator
      "${PROJECT_SOURCE_DIR}/reference/validate_affine_advection_bundle.py")
  set_tests_properties(
    mls.affine_advection.validator.regression
    PROPERTIES
      DEPENDS "mls.affine_advection.smoke.a"
      LABELS "deterministic;affine;validator;independent"
      PASS_REGULAR_EXPRESSION "Affine-advection bundle validator regression: PASS"
      TIMEOUT 120)

  add_test(
    NAME mls.moving_apic_limit.smoke.verify
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/validate_moving_apic_limit_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/moving-apic-limit-smoke-a"
      --compare
      "${CMAKE_CURRENT_BINARY_DIR}/moving-apic-limit-smoke-b"
      --smoke-provisional)
  set_tests_properties(
    mls.moving_apic_limit.smoke.verify
    PROPERTIES
      DEPENDS "mls.moving_apic_limit.smoke.a;mls.moving_apic_limit.smoke.b"
      LABELS "deterministic;moving-apic-limit;smoke;independent"
      PASS_REGULAR_EXPRESSION "MOVING APIC LIMIT BUNDLE SMOKE PROVISIONAL"
      TIMEOUT 180)

  add_test(
    NAME mls.moving_apic_limit.validator.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/moving_apic_limit_bundle_validator_test.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/moving-apic-limit-smoke-a"
      --validator
      "${PROJECT_SOURCE_DIR}/reference/validate_moving_apic_limit_bundle.py")
  set_tests_properties(
    mls.moving_apic_limit.validator.regression
    PROPERTIES
      DEPENDS "mls.moving_apic_limit.smoke.a"
      LABELS "deterministic;moving-apic-limit;validator;independent"
      PASS_REGULAR_EXPRESSION "Moving APIC limit bundle validator regression: PASS"
      TIMEOUT 180)

  add_test(
    NAME mls.projection_foundation.smoke.verify
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/validate_projection_foundation_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/projection-foundation-smoke-a"
      --compare
      "${CMAKE_CURRENT_BINARY_DIR}/projection-foundation-smoke-b"
      --smoke-provisional)
  set_tests_properties(
    mls.projection_foundation.smoke.verify
    PROPERTIES
      DEPENDS "mls.projection_foundation.smoke.a;mls.projection_foundation.smoke.b"
      LABELS "deterministic;projection-foundation;smoke;independent"
      PASS_REGULAR_EXPRESSION "PROJECTION FOUNDATION BUNDLE SMOKE PROVISIONAL"
      TIMEOUT 180)

  add_test(
    NAME mls.projection_foundation.validator.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/projection_foundation_bundle_validator_test.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/projection-foundation-smoke-a"
      --validator
      "${PROJECT_SOURCE_DIR}/reference/validate_projection_foundation_bundle.py")
  set_tests_properties(
    mls.projection_foundation.validator.regression
    PROPERTIES
      DEPENDS "mls.projection_foundation.smoke.a"
      LABELS "deterministic;projection-foundation;validator;independent"
      PASS_REGULAR_EXPRESSION "Projection foundation bundle validator regression: PASS"
      TIMEOUT 180)

  add_test(
    NAME mls.projection_foundation.seal.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/projection_foundation_seal_test.py"
      --tool
      "${PROJECT_SOURCE_DIR}/tools/seal_projection_foundation_evidence.py")
  set_tests_properties(
    mls.projection_foundation.seal.regression
    PROPERTIES
      LABELS "deterministic;projection-foundation;seal;independent"
      PASS_REGULAR_EXPRESSION "projection foundation outer seal mutation regression PASS"
      TIMEOUT 180)

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
