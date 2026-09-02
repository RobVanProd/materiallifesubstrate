include("${CMAKE_CURRENT_SOURCE_DIR}/api_compile_contracts.cmake")
find_package(Python3 QUIET COMPONENTS Interpreter)

add_executable(
  mls_validation
  test_main.cpp
  core_validation_tests.cpp
  angular_momentum_tests.cpp
  authoritative_drift_state_bridge_tests.cpp
  authoritative_mechanics_state_bridge_tests.cpp
  authoritative_api_tests.cpp
  compound_identity_tests.cpp
  conservative_force_consistency_tests.cpp
  constitutive_expressivity_tests.cpp
  physical_support_tests.cpp
  affine_advection_tests.cpp
  moving_apic_limit_tests.cpp
  kelvin_covariance_audit_tests.cpp
  mechanical_observability_tests.cpp
  projection_exactness_nullspace_tests.cpp
  projection_foundation_tests.cpp
  relation_geometry_resolution_tests.cpp
  relational_observability_confirmation_tests.cpp
  transfer_lab_tests.cpp
  time_checkpoint_tests.cpp
  time_integration_foundation_tests.cpp)

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
  NAME mls.time_integration_foundation.schema.audit
  COMMAND mls_time_integration_foundation_diagnostic --schema-audit)
set_tests_properties(
  mls.time_integration_foundation.schema.audit
  PROPERTIES
    LABELS "deterministic;time-integration;schema"
    PASS_REGULAR_EXPRESSION
      "Time Integration Foundation raw schema audit: PASS"
    TIMEOUT 30)

add_test(
  NAME mls.time_integration_foundation.smoke.a
  COMMAND
    mls_time_integration_foundation_diagnostic
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/time-integration-foundation-smoke-a")
add_test(
  NAME mls.time_integration_foundation.smoke.b
  COMMAND
    mls_time_integration_foundation_diagnostic
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/time-integration-foundation-smoke-b")
set_tests_properties(
  mls.time_integration_foundation.smoke.a
  mls.time_integration_foundation.smoke.b
  PROPERTIES
    LABELS "deterministic;time-integration;raw;smoke"
    PASS_REGULAR_EXPRESSION
      "TIME INTEGRATION FOUNDATION RAW COMPLETE: R=128 NO_PROMOTION"
    TIMEOUT 300)

if(Python3_Interpreter_FOUND)
add_test(
  NAME mls.time_integration_foundation.raw_twin
  COMMAND
    "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/compare_evidence_directories.py"
    --first
    "${CMAKE_CURRENT_BINARY_DIR}/time-integration-foundation-smoke-a"
    --second
    "${CMAKE_CURRENT_BINARY_DIR}/time-integration-foundation-smoke-b")
set_tests_properties(
  mls.time_integration_foundation.raw_twin
  PROPERTIES
    DEPENDS
      "mls.time_integration_foundation.smoke.a;mls.time_integration_foundation.smoke.b"
    LABELS "deterministic;time-integration;twin"
    PASS_REGULAR_EXPRESSION "byte comparison: PASS"
    TIMEOUT 60)

add_test(
  NAME mls.time_integration_foundation.oracle
  COMMAND
    "${Python3_EXECUTABLE}"
    "${CMAKE_SOURCE_DIR}/reference/time_integration_foundation_oracle.py"
    --raw
    "${CMAKE_CURRENT_BINARY_DIR}/time-integration-foundation-smoke-a"
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/time-integration-foundation-oracle.json")
set_tests_properties(
  mls.time_integration_foundation.oracle
  PROPERTIES
    DEPENDS "mls.time_integration_foundation.raw_twin"
    ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1"
    LABELS "deterministic;time-integration;oracle"
    PASS_REGULAR_EXPRESSION
      "TIME INTEGRATION FOUNDATION ORACLE: PASS temporal_convergence_blocked_by_authoritative_quantization NO_PROMOTION"
    TIMEOUT 1800)

add_test(
  NAME mls.time_integration_foundation.oracle_mutations
  COMMAND
    "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/time_integration_foundation_oracle_test.py"
    --raw
    "${CMAKE_CURRENT_BINARY_DIR}/time-integration-foundation-smoke-a")
set_tests_properties(
  mls.time_integration_foundation.oracle_mutations
  PROPERTIES
    DEPENDS "mls.time_integration_foundation.oracle"
    ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1"
    LABELS "deterministic;time-integration;mutation"
    PASS_REGULAR_EXPRESSION
      "PASS \\(1 deterministic positive, 20 mutations\\)"
    TIMEOUT 1800)

add_test(
  NAME mls.time_integration_foundation.seal_mutations
  COMMAND
    "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/time_integration_foundation_seal_test.py")
set_tests_properties(
  mls.time_integration_foundation.seal_mutations
  PROPERTIES
    ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1"
    LABELS "deterministic;time-integration;seal;mutation"
    PASS_REGULAR_EXPRESSION "PASS \\(2 positives, 3 mutations\\)"
    TIMEOUT 60)
endif()

add_test(
  NAME mls.authoritative_drift_state_bridge.schema.audit
  COMMAND mls_authoritative_drift_state_bridge_diagnostic --schema-audit)
set_tests_properties(
  mls.authoritative_drift_state_bridge.schema.audit
  PROPERTIES
    LABELS "deterministic;drift-bridge;schema"
    PASS_REGULAR_EXPRESSION
      "Authoritative Drift State Bridge raw schema audit: PASS"
    TIMEOUT 30)

add_test(
  NAME mls.authoritative_drift_state_bridge.smoke.a
  COMMAND
    mls_authoritative_drift_state_bridge_diagnostic
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/authoritative-drift-state-bridge-smoke-a")
add_test(
  NAME mls.authoritative_drift_state_bridge.smoke.b
  COMMAND
    mls_authoritative_drift_state_bridge_diagnostic
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/authoritative-drift-state-bridge-smoke-b")
set_tests_properties(
  mls.authoritative_drift_state_bridge.smoke.a
  mls.authoritative_drift_state_bridge.smoke.b
  PROPERTIES
    LABELS "deterministic;drift-bridge;raw;smoke"
    PASS_REGULAR_EXPRESSION
      "retain_refined_stateless_mechanics_representation_for_research R=128 NO_PROMOTION"
    TIMEOUT 180)

if(Python3_Interpreter_FOUND)
add_test(
  NAME mls.authoritative_drift_state_bridge.raw_twin
  COMMAND
    "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/compare_evidence_directories.py"
    --first
    "${CMAKE_CURRENT_BINARY_DIR}/authoritative-drift-state-bridge-smoke-a"
    --second
    "${CMAKE_CURRENT_BINARY_DIR}/authoritative-drift-state-bridge-smoke-b")
set_tests_properties(
  mls.authoritative_drift_state_bridge.raw_twin
  PROPERTIES
    DEPENDS
      "mls.authoritative_drift_state_bridge.smoke.a;mls.authoritative_drift_state_bridge.smoke.b"
    LABELS "deterministic;drift-bridge;twin"
    PASS_REGULAR_EXPRESSION "byte comparison: PASS"
    TIMEOUT 60)

add_test(
  NAME mls.authoritative_drift_state_bridge.oracle
  COMMAND
    "${Python3_EXECUTABLE}"
    "${CMAKE_SOURCE_DIR}/reference/authoritative_drift_state_bridge_oracle.py"
    --raw
    "${CMAKE_CURRENT_BINARY_DIR}/authoritative-drift-state-bridge-smoke-a"
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/authoritative-drift-state-bridge-oracle.json")
set_tests_properties(
  mls.authoritative_drift_state_bridge.oracle
  PROPERTIES
    DEPENDS "mls.authoritative_drift_state_bridge.raw_twin"
    ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1"
    LABELS "deterministic;drift-bridge;oracle"
    PASS_REGULAR_EXPRESSION
      "AUTHORITATIVE DRIFT STATE BRIDGE ORACLE: PASS R=128"
    TIMEOUT 1200)

add_test(
  NAME mls.authoritative_drift_state_bridge.oracle_mutations
  COMMAND
    "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/authoritative_drift_state_bridge_oracle_test.py"
    --raw
    "${CMAKE_CURRENT_BINARY_DIR}/authoritative-drift-state-bridge-smoke-a")
set_tests_properties(
  mls.authoritative_drift_state_bridge.oracle_mutations
  PROPERTIES
    DEPENDS "mls.authoritative_drift_state_bridge.oracle"
    ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1"
    LABELS "deterministic;drift-bridge;mutation"
    PASS_REGULAR_EXPRESSION
      "PASS \\(2 deterministic positives, 14 mutations\\)"
    TIMEOUT 1200)

add_test(
  NAME mls.authoritative_drift_state_bridge.seal_mutations
  COMMAND
    "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/authoritative_drift_state_bridge_seal_test.py")
set_tests_properties(
  mls.authoritative_drift_state_bridge.seal_mutations
  PROPERTIES
    ENVIRONMENT "PYTHONDWRITEBYTECODE=1"
    LABELS "deterministic;drift-bridge;seal;mutation"
    PASS_REGULAR_EXPRESSION
      "PASS \\(2 positives, 3 mutations\\)"
    TIMEOUT 60)
endif()

add_test(
  NAME mls.authoritative_mechanics_state_bridge.schema.audit
  COMMAND mls_authoritative_mechanics_state_bridge_diagnostic --schema-audit)
set_tests_properties(
  mls.authoritative_mechanics_state_bridge.schema.audit
  PROPERTIES
    LABELS "deterministic;mechanics-bridge;schema"
    PASS_REGULAR_EXPRESSION
      "Authoritative Mechanics State Bridge raw schema audit: PASS"
    TIMEOUT 30)

add_test(
  NAME mls.authoritative_mechanics_state_bridge.smoke.a
  COMMAND
    mls_authoritative_mechanics_state_bridge_diagnostic
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/authoritative-mechanics-state-bridge-smoke-a")
add_test(
  NAME mls.authoritative_mechanics_state_bridge.smoke.b
  COMMAND
    mls_authoritative_mechanics_state_bridge_diagnostic
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/authoritative-mechanics-state-bridge-smoke-b")
set_tests_properties(
  mls.authoritative_mechanics_state_bridge.smoke.a
  mls.authoritative_mechanics_state_bridge.smoke.b
  PROPERTIES
    LABELS "deterministic;mechanics-bridge;raw;smoke"
    PASS_REGULAR_EXPRESSION
      "retain_direct_quantized_mechanics_bridge_for_research R=16 NO_PROMOTION"
    TIMEOUT 120)

add_test(
  NAME mls.conservative_force_consistency.schema.audit
  COMMAND mls_conservative_force_consistency_diagnostic --schema-audit)
set_tests_properties(
  mls.conservative_force_consistency.schema.audit
  PROPERTIES
    LABELS "deterministic;conservative-force;schema"
    PASS_REGULAR_EXPRESSION
      "Conservative Force Consistency raw schema audit: PASS"
    TIMEOUT 30)

add_test(
  NAME mls.conservative_force_consistency.smoke.a
  COMMAND
    mls_conservative_force_consistency_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/conservative-force-smoke-a")
add_test(
  NAME mls.conservative_force_consistency.smoke.b
  COMMAND
    mls_conservative_force_consistency_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/conservative-force-smoke-b")
set_tests_properties(
  mls.conservative_force_consistency.smoke.a
  mls.conservative_force_consistency.smoke.b
  PROPERTIES
    LABELS "deterministic;conservative-force;raw;smoke"
    PASS_REGULAR_EXPRESSION
      "CONSERVATIVE FORCE RAW BUNDLE COMPLETE"
    TIMEOUT 300)

add_test(
  NAME mls.constitutive_expressivity.schema.audit
  COMMAND mls_constitutive_expressivity_diagnostic --schema-audit)
set_tests_properties(
  mls.constitutive_expressivity.schema.audit
  PROPERTIES
    LABELS "deterministic;constitutive-expressivity;schema"
    PASS_REGULAR_EXPRESSION "Constitutive Expressivity schema audit: PASS"
    TIMEOUT 30)

add_test(
  NAME mls.constitutive_expressivity.smoke.a
  COMMAND
    mls_constitutive_expressivity_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/constitutive-expressivity-smoke-a")
add_test(
  NAME mls.constitutive_expressivity.smoke.b
  COMMAND
    mls_constitutive_expressivity_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/constitutive-expressivity-smoke-b")
set_tests_properties(
  mls.constitutive_expressivity.smoke.a
  mls.constitutive_expressivity.smoke.b
  PROPERTIES
    LABELS "deterministic;constitutive-expressivity;smoke"
    PASS_REGULAR_EXPRESSION "retain_local_collective_relational_energy_for_research NO_PROMOTION"
    TIMEOUT 180)

add_test(
  NAME mls.relational_observability.schema.audit
  COMMAND mls_relational_observability_diagnostic --schema-audit)
add_test(
  NAME mls.relational_observability.logic.audit
  COMMAND mls_relational_observability_diagnostic --logic-audit)
set_tests_properties(
  mls.relational_observability.schema.audit
  PROPERTIES
    LABELS "deterministic;relational-observability;schema"
    PASS_REGULAR_EXPRESSION
      "Relational Observability Confirmation schema audit: PASS"
    TIMEOUT 30)
set_tests_properties(
  mls.relational_observability.logic.audit
  PROPERTIES
    LABELS "deterministic;relational-observability;logic"
    PASS_REGULAR_EXPRESSION
      "Relational Observability Confirmation logic audit: PASS"
    TIMEOUT 30)

add_test(
  NAME mls.relational_observability.smoke.a
  COMMAND
    mls_relational_observability_diagnostic
    --smoke
    --fixture-bundle
    "${CMAKE_CURRENT_SOURCE_DIR}/fixtures/relational_observability_smoke"
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/relational-observability-smoke-a")
add_test(
  NAME mls.relational_observability.smoke.b
  COMMAND
    mls_relational_observability_diagnostic
    --smoke
    --fixture-bundle
    "${CMAKE_CURRENT_SOURCE_DIR}/fixtures/relational_observability_smoke"
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/relational-observability-smoke-b")
set_tests_properties(
  mls.relational_observability.smoke.a
  mls.relational_observability.smoke.b
  PROPERTIES
    LABELS "deterministic;relational-observability;smoke"
    PASS_REGULAR_EXPRESSION "Relational Observability evidence written"
    TIMEOUT 300)

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

add_test(
  NAME mls.mechanical_observability.smoke.a
  COMMAND
    mls_mechanical_observability_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/mechanical-observability-smoke-a")
add_test(
  NAME mls.mechanical_observability.smoke.b
  COMMAND
    mls_mechanical_observability_diagnostic
    --smoke
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/mechanical-observability-smoke-b")
set_tests_properties(
  mls.mechanical_observability.smoke.a
  mls.mechanical_observability.smoke.b
  PROPERTIES
    LABELS "deterministic;mechanical-observability;smoke"
    PASS_REGULAR_EXPRESSION
      "Mechanical Observability provisional smoke evidence written"
    TIMEOUT 300)

add_test(
  NAME mls.mechanical_observability.schema.audit
  COMMAND mls_mechanical_observability_diagnostic --schema-audit)
set_tests_properties(
  mls.mechanical_observability.schema.audit
  PROPERTIES
    LABELS "deterministic;mechanical-observability;schema"
    PASS_REGULAR_EXPRESSION "Mechanical Observability schema audit: PASS"
    TIMEOUT 30)

add_test(
  NAME mls.mechanical_observability.logic.audit
  COMMAND mls_mechanical_observability_diagnostic --logic-audit)
set_tests_properties(
  mls.mechanical_observability.logic.audit
  PROPERTIES
    LABELS "deterministic;mechanical-observability;logic"
    PASS_REGULAR_EXPRESSION "Mechanical Observability logic audit: PASS"
    TIMEOUT 30)

add_test(
  NAME mls.kelvin_covariance.smoke.a
  COMMAND
    mls_kelvin_covariance_diagnostic
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/kelvin-covariance-smoke-a")
add_test(
  NAME mls.kelvin_covariance.smoke.b
  COMMAND
    mls_kelvin_covariance_diagnostic
    --output
    "${CMAKE_CURRENT_BINARY_DIR}/kelvin-covariance-smoke-b")
set_tests_properties(
  mls.kelvin_covariance.smoke.a
  mls.kelvin_covariance.smoke.b
  PROPERTIES
    LABELS "deterministic;kelvin-covariance;smoke"
    PASS_REGULAR_EXPRESSION "Decision: SUPPORTED_DIAGNOSTIC_COORDINATE_DEFECT"
    TIMEOUT 120)

add_test(
  NAME mls.kelvin_covariance.schema.audit
  COMMAND mls_kelvin_covariance_diagnostic --schema-audit)
add_test(
  NAME mls.kelvin_covariance.logic.audit
  COMMAND mls_kelvin_covariance_diagnostic --logic-audit)
set_tests_properties(
  mls.kelvin_covariance.schema.audit
  PROPERTIES
    LABELS "deterministic;kelvin-covariance;schema"
    PASS_REGULAR_EXPRESSION "Kelvin Covariance Audit schema audit: PASS"
    TIMEOUT 30)
set_tests_properties(
  mls.kelvin_covariance.logic.audit
  PROPERTIES
    LABELS "deterministic;kelvin-covariance;logic"
    PASS_REGULAR_EXPRESSION "Kelvin Covariance Audit logic audit: PASS"
    TIMEOUT 30)

if(Python3_Interpreter_FOUND)
  add_test(
    NAME mls.authoritative_mechanics_state_bridge.smoke.compare
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/compare_evidence_directories.py"
      --first
      "${CMAKE_CURRENT_BINARY_DIR}/authoritative-mechanics-state-bridge-smoke-a"
      --second
      "${CMAKE_CURRENT_BINARY_DIR}/authoritative-mechanics-state-bridge-smoke-b")
  set_tests_properties(
    mls.authoritative_mechanics_state_bridge.smoke.compare
    PROPERTIES
      DEPENDS
        "mls.authoritative_mechanics_state_bridge.smoke.a;mls.authoritative_mechanics_state_bridge.smoke.b"
      LABELS "deterministic;mechanics-bridge;raw;twin"
      PASS_REGULAR_EXPRESSION "byte comparison: PASS"
      TIMEOUT 60)

  if(MLS_CONFIGURED_SOURCE_BRANCH STREQUAL "authoritative-mechanics-state-bridge-lab")
  add_test(
    NAME mls.authoritative_mechanics_state_bridge.oracle
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/authoritative_mechanics_state_bridge_oracle.py"
      --raw
      "${CMAKE_CURRENT_BINARY_DIR}/authoritative-mechanics-state-bridge-smoke-a"
      --output
      "${CMAKE_CURRENT_BINARY_DIR}/authoritative-mechanics-state-bridge-oracle.json")
  set_tests_properties(
    mls.authoritative_mechanics_state_bridge.oracle
    PROPERTIES
      DEPENDS "mls.authoritative_mechanics_state_bridge.smoke.a"
      LABELS "deterministic;mechanics-bridge;oracle;independent"
      PASS_REGULAR_EXPRESSION
        "AUTHORITATIVE MECHANICS STATE BRIDGE ORACLE: PASS.*NO_PROMOTION"
      TIMEOUT 120)

  add_test(
    NAME mls.authoritative_mechanics_state_bridge.oracle.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/authoritative_mechanics_state_bridge_oracle_test.py"
      --raw
      "${CMAKE_CURRENT_BINARY_DIR}/authoritative-mechanics-state-bridge-smoke-a")
  set_tests_properties(
    mls.authoritative_mechanics_state_bridge.oracle.regression
    PROPERTIES
      DEPENDS "mls.authoritative_mechanics_state_bridge.smoke.a"
      LABELS "deterministic;mechanics-bridge;oracle;mutations"
      PASS_REGULAR_EXPRESSION
        "authoritative mechanics state bridge oracle regression: PASS"
      TIMEOUT 180)
  endif()

  add_test(
    NAME mls.authoritative_mechanics_state_bridge.seal.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/authoritative_mechanics_state_bridge_seal_test.py"
      --tool
      "${PROJECT_SOURCE_DIR}/tools/seal_authoritative_mechanics_state_bridge_evidence.py")
  set_tests_properties(
    mls.authoritative_mechanics_state_bridge.seal.regression
    PROPERTIES
      LABELS "deterministic;mechanics-bridge;seal;mutations"
      PASS_REGULAR_EXPRESSION
        "authoritative mechanics bridge outer-seal regression: PASS"
      TIMEOUT 60)

  add_test(
    NAME mls.conservative_force_consistency.smoke.compare
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/compare_evidence_directories.py"
      --first
      "${CMAKE_CURRENT_BINARY_DIR}/conservative-force-smoke-a"
      --second
      "${CMAKE_CURRENT_BINARY_DIR}/conservative-force-smoke-b")
  set_tests_properties(
    mls.conservative_force_consistency.smoke.compare
    PROPERTIES
      DEPENDS
        "mls.conservative_force_consistency.smoke.a;mls.conservative_force_consistency.smoke.b"
      LABELS "deterministic;conservative-force;raw;smoke;twin"
      PASS_REGULAR_EXPRESSION "byte comparison: PASS"
      TIMEOUT 60)

  # This sealed validator intentionally requires the literal source branch
  # conservative-force-consistency-lab.  Its reusable force/oracle/seal tests
  # remain active on descendants, but rematerializing that historical bundle
  # under a different branch identity is correctly invalid.
  if(MLS_CONFIGURED_SOURCE_BRANCH STREQUAL "conservative-force-consistency-lab")
    add_test(
      NAME mls.conservative_force_consistency.validator.regression
      COMMAND
        "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/conservative_force_bundle_validator_test.py"
        --producer
        "${CMAKE_CURRENT_BINARY_DIR}/conservative-force-smoke-a"
        --producer-compare
        "${CMAKE_CURRENT_BINARY_DIR}/conservative-force-smoke-b"
        --validator
        "${PROJECT_SOURCE_DIR}/reference/validate_conservative_force_bundle.py")
    set_tests_properties(
      mls.conservative_force_consistency.validator.regression
      PROPERTIES
        DEPENDS
          "mls.conservative_force_consistency.smoke.a;mls.conservative_force_consistency.smoke.b"
        LABELS "deterministic;conservative-force;validator;independent"
        PASS_REGULAR_EXPRESSION
          "conservative force two-stage validator regression: PASS.*NO_PROMOTION"
        TIMEOUT 900)
  endif()

  add_test(
    NAME mls.conservative_force_consistency.oracle.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/conservative_force_oracle_test.py")
  set_tests_properties(
    mls.conservative_force_consistency.oracle.regression
    PROPERTIES
      LABELS "deterministic;conservative-force;oracle;independent"
      PASS_REGULAR_EXPRESSION
        "conservative force high-precision oracle regression: PASS"
      TIMEOUT 300)

  add_test(
    NAME mls.conservative_force_consistency.seal.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/conservative_force_seal_test.py"
      --tool
      "${PROJECT_SOURCE_DIR}/tools/seal_conservative_force_consistency_evidence.py")
  set_tests_properties(
    mls.conservative_force_consistency.seal.regression
    PROPERTIES
      LABELS "deterministic;conservative-force;seal;independent"
      PASS_REGULAR_EXPRESSION
        "conservative force consistency outer-seal mutation regression: PASS"
      TIMEOUT 120)

  add_test(
    NAME mls.relation_geometry_resolution.seal.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/relation_geometry_resolution_seal_test.py"
      --tool
      "${PROJECT_SOURCE_DIR}/tools/seal_relation_geometry_resolution_evidence.py")
  set_tests_properties(
    mls.relation_geometry_resolution.seal.regression
    PROPERTIES
      LABELS "deterministic;relation-geometry;seal;independent"
      PASS_REGULAR_EXPRESSION
        "relation geometry outer-seal regression: PASS"
      TIMEOUT 60)

  add_test(
    NAME mls.constitutive_expressivity.smoke.compare
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/compare_evidence_directories.py"
      --first
      "${CMAKE_CURRENT_BINARY_DIR}/constitutive-expressivity-smoke-a"
      --second
      "${CMAKE_CURRENT_BINARY_DIR}/constitutive-expressivity-smoke-b")
  set_tests_properties(
    mls.constitutive_expressivity.smoke.compare
    PROPERTIES
      DEPENDS
        "mls.constitutive_expressivity.smoke.a;mls.constitutive_expressivity.smoke.b"
      LABELS "deterministic;constitutive-expressivity;smoke;twin"
      PASS_REGULAR_EXPRESSION "byte comparison: PASS"
      TIMEOUT 30)

  add_test(
    NAME mls.constitutive_expressivity.smoke.verify
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/validate_constitutive_expressivity_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/constitutive-expressivity-smoke-a"
      --compare
      "${CMAKE_CURRENT_BINARY_DIR}/constitutive-expressivity-smoke-b"
      --allow-dirty
      --expected-source-branch
      "${MLS_CONFIGURED_SOURCE_BRANCH}")
  set_tests_properties(
    mls.constitutive_expressivity.smoke.verify
    PROPERTIES
      DEPENDS
        "mls.constitutive_expressivity.smoke.a;mls.constitutive_expressivity.smoke.b"
      LABELS "deterministic;constitutive-expressivity;smoke;independent"
      PASS_REGULAR_EXPRESSION
        "CONSTITUTIVE EXPRESSIVITY BUNDLE VALID.*NO_PROMOTION"
      TIMEOUT 300)

  add_test(
    NAME mls.constitutive_expressivity.validator.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/constitutive_expressivity_bundle_validator_test.py"
      --validator
      "${PROJECT_SOURCE_DIR}/reference/validate_constitutive_expressivity_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/constitutive-expressivity-smoke-a"
      --compare
      "${CMAKE_CURRENT_BINARY_DIR}/constitutive-expressivity-smoke-b"
      --expected-source-branch
      "${MLS_CONFIGURED_SOURCE_BRANCH}")
  set_tests_properties(
    mls.constitutive_expressivity.validator.regression
    PROPERTIES
      DEPENDS
        "mls.constitutive_expressivity.smoke.a;mls.constitutive_expressivity.smoke.b"
      LABELS "deterministic;constitutive-expressivity;validator;independent"
      PASS_REGULAR_EXPRESSION
        "constitutive expressivity bundle validator regression: PASS"
      TIMEOUT 300)

  add_test(
    NAME mls.constitutive_expressivity.seal.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/constitutive_expressivity_seal_test.py")
  set_tests_properties(
    mls.constitutive_expressivity.seal.regression
    PROPERTIES
      LABELS "deterministic;constitutive-expressivity;seal;independent"
      PASS_REGULAR_EXPRESSION
        "constitutive expressivity outer-seal mutation regression: PASS"
      TIMEOUT 60)

  add_test(
    NAME mls.relational_observability.smoke.verify
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/validate_relational_observability_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/relational-observability-smoke-a"
      --compare
      "${CMAKE_CURRENT_BINARY_DIR}/relational-observability-smoke-b"
      --allow-dirty)
  set_tests_properties(
    mls.relational_observability.smoke.verify
    PROPERTIES
      DEPENDS
        "mls.relational_observability.smoke.a;mls.relational_observability.smoke.b"
      LABELS "deterministic;relational-observability;smoke;independent"
      PASS_REGULAR_EXPRESSION
        "RELATIONAL OBSERVABILITY BUNDLE VALID.*byte comparison: PASS"
      TIMEOUT 300)

  add_test(
    NAME mls.relational_observability.validator.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/relational_observability_bundle_validator_test.py"
      --validator
      "${PROJECT_SOURCE_DIR}/reference/validate_relational_observability_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/relational-observability-smoke-a")
  set_tests_properties(
    mls.relational_observability.validator.regression
    PROPERTIES
      DEPENDS "mls.relational_observability.smoke.a"
      LABELS "deterministic;relational-observability;validator;independent"
      PASS_REGULAR_EXPRESSION
        "relational observability bundle validator regression: PASS"
      TIMEOUT 300)

  add_test(
    NAME mls.relational_observability.seal.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/relational_observability_seal_test.py")
  set_tests_properties(
    mls.relational_observability.seal.regression
    PROPERTIES
      LABELS "deterministic;relational-observability;seal;independent"
      PASS_REGULAR_EXPRESSION
        "relational observability outer-seal mutation regression: PASS"
      TIMEOUT 60)

  add_test(
    NAME mls.kelvin_covariance.smoke.byte_compare
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/compare_evidence_directories.py"
      --first
      "${CMAKE_CURRENT_BINARY_DIR}/kelvin-covariance-smoke-a"
      --second
      "${CMAKE_CURRENT_BINARY_DIR}/kelvin-covariance-smoke-b")
  set_tests_properties(
    mls.kelvin_covariance.smoke.byte_compare
    PROPERTIES
      DEPENDS "mls.kelvin_covariance.smoke.a;mls.kelvin_covariance.smoke.b"
      LABELS "deterministic;kelvin-covariance;smoke;independent"
      PASS_REGULAR_EXPRESSION "smoke byte comparison: PASS"
      TIMEOUT 30)

  add_test(
    NAME mls.kelvin_covariance.smoke.verify
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/validate_kelvin_covariance_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/kelvin-covariance-smoke-a"
      --compare
      "${CMAKE_CURRENT_BINARY_DIR}/kelvin-covariance-smoke-b"
      --allow-dirty
      --expected-source-branch
      "${MLS_CONFIGURED_SOURCE_BRANCH}")
  set_tests_properties(
    mls.kelvin_covariance.smoke.verify
    PROPERTIES
      DEPENDS "mls.kelvin_covariance.smoke.a;mls.kelvin_covariance.smoke.b"
      LABELS "deterministic;kelvin-covariance;smoke;independent"
      PASS_REGULAR_EXPRESSION "KELVIN COVARIANCE BUNDLE VALID"
      TIMEOUT 120)

  add_test(
    NAME mls.kelvin_covariance.validator.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/kelvin_covariance_bundle_validator_test.py"
      --validator
      "${PROJECT_SOURCE_DIR}/reference/validate_kelvin_covariance_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/kelvin-covariance-smoke-a"
      --expected-source-branch
      "${MLS_CONFIGURED_SOURCE_BRANCH}")
  set_tests_properties(
    mls.kelvin_covariance.validator.regression
    PROPERTIES
      DEPENDS "mls.kelvin_covariance.smoke.a"
      LABELS "deterministic;kelvin-covariance;validator;independent"
      PASS_REGULAR_EXPRESSION
        "kelvin covariance bundle validator regression: PASS"
      TIMEOUT 120)

  add_test(
    NAME mls.kelvin_covariance.seal.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/kelvin_covariance_seal_test.py")
  set_tests_properties(
    mls.kelvin_covariance.seal.regression
    PROPERTIES
      LABELS "deterministic;kelvin-covariance;seal;independent"
      PASS_REGULAR_EXPRESSION
        "kelvin covariance outer-seal mutation regression: PASS"
      TIMEOUT 60)

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
    NAME mls.mechanical_observability.smoke.byte_compare
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/compare_evidence_directories.py"
      --first
      "${CMAKE_CURRENT_BINARY_DIR}/mechanical-observability-smoke-a"
      --second
      "${CMAKE_CURRENT_BINARY_DIR}/mechanical-observability-smoke-b")
  set_tests_properties(
    mls.mechanical_observability.smoke.byte_compare
    PROPERTIES
      DEPENDS
        "mls.mechanical_observability.smoke.a;mls.mechanical_observability.smoke.b"
      LABELS "deterministic;mechanical-observability;smoke;independent"
      PASS_REGULAR_EXPRESSION
        "Projection exactness/nullspace smoke byte comparison: PASS"
      TIMEOUT 30)

  add_test(
    NAME mls.mechanical_observability.smoke.verify
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/validate_mechanical_observability_bundle.py"
      --bundle
      "${CMAKE_CURRENT_BINARY_DIR}/mechanical-observability-smoke-a"
      --compare
      "${CMAKE_CURRENT_BINARY_DIR}/mechanical-observability-smoke-b"
      --allow-smoke)
  set_tests_properties(
    mls.mechanical_observability.smoke.verify
    PROPERTIES
      DEPENDS
        "mls.mechanical_observability.smoke.a;mls.mechanical_observability.smoke.b"
      LABELS "deterministic;mechanical-observability;smoke;independent"
      PASS_REGULAR_EXPRESSION "MECHANICAL OBSERVABILITY BUNDLE VALID"
      TIMEOUT 900)

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
    NAME mls.kelvin_covariance.exact.oracle
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/kelvin_covariance_oracle.py"
      --verify
      "${CMAKE_CURRENT_SOURCE_DIR}/kelvin_covariance_oracle.canonical.json")
  set_tests_properties(
    mls.kelvin_covariance.exact.oracle
    PROPERTIES
      LABELS "deterministic;exact;kelvin-covariance;independent"
      PASS_REGULAR_EXPRESSION "result_sha256_before_hash_field"
      TIMEOUT 60)

  add_test(
    NAME mls.kelvin_covariance.exact.oracle.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/kelvin_covariance_oracle_test.py")
  set_tests_properties(
    mls.kelvin_covariance.exact.oracle.regression
    PROPERTIES
      LABELS "deterministic;exact;kelvin-covariance;independent"
      PASS_REGULAR_EXPRESSION "kelvin covariance exact-oracle regression: PASS"
      TIMEOUT 90)

  add_test(
    NAME mls.mechanical_observability.exact.oracle
    COMMAND
      "${Python3_EXECUTABLE}"
      "${PROJECT_SOURCE_DIR}/reference/mechanical_observability_oracle.py"
      --verify
      "${CMAKE_CURRENT_SOURCE_DIR}/mechanical_observability_oracle.canonical.json")
  set_tests_properties(
    mls.mechanical_observability.exact.oracle
    PROPERTIES
      LABELS "deterministic;exact;mechanical-observability;independent"
      PASS_REGULAR_EXPRESSION "result_sha256_before_hash_field"
      TIMEOUT 60)

  add_test(
    NAME mls.mechanical_observability.exact.oracle.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/mechanical_observability_oracle_test.py")
  set_tests_properties(
    mls.mechanical_observability.exact.oracle.regression
    PROPERTIES
      LABELS "deterministic;exact;mechanical-observability;independent"
      PASS_REGULAR_EXPRESSION "mechanical observability exact-oracle regression: PASS"
      TIMEOUT 90)

  add_test(
    NAME mls.mechanical_observability.validator.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/mechanical_observability_bundle_validator_test.py")
  set_tests_properties(
    mls.mechanical_observability.validator.regression
    PROPERTIES
      LABELS "deterministic;mechanical-observability;validator;independent"
      PASS_REGULAR_EXPRESSION
        "mechanical observability bundle validator regression: PASS"
      TIMEOUT 1800)

  add_test(
    NAME mls.mechanical_observability.seal.regression
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/mechanical_observability_seal_test.py")
  set_tests_properties(
    mls.mechanical_observability.seal.regression
    PROPERTIES
      LABELS "deterministic;mechanical-observability;seal;independent"
      PASS_REGULAR_EXPRESSION
        "mechanical observability outer seal mutation regression PASS"
      TIMEOUT 900)

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
