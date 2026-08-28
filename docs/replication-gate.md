# MLS-0 replication gate

This document separates evidence produced on a developer workstation from
evidence produced by GitHub-hosted runners. The same source passing in another
compiler or operating-system environment is a cross-environment replication of
the build and encoded tests. It is **not** an independent implementation and is
not evidence that the encoded behavior is physically valid.

## Current evidence state

| Evidence source | Commit/branch | Status | Meaning |
|---|---|---|---|
| Local Windows/GCC baseline recorded in `review-evidence-2026-08-28-baseline.md` | `31c5733c618aead558dd7e4232a0976e2fc88bda`, `main` at time of execution | Executed and passed | Local evidence for that historical commit only. |
| GitHub Actions workflow in `.github/workflows/baseline-replication.yml` | `baseline-hardening` | **CONFIGURED, NOT YET RUN** | No independent-CI result may be claimed until a run URL, run ID, tested SHA, and job conclusions are recorded. |

The workflow file existing or validating as YAML does not promote any row to
`replicated`. A green badge without the tested commit and individual job results
is also insufficient evidence.

## Required jobs

The workflow deliberately has a non-fail-fast C++ matrix so one toolchain failure
does not cancel evidence from the others.

| Job | Hosted environment | Commands under test |
|---|---|---|
| C++ / Linux GCC | `ubuntu-latest`, explicit `CC=gcc`, `CXX=g++` | `cmake --preset dev`; `cmake --build --preset dev --parallel`; `ctest --preset dev --output-on-failure` |
| C++ / Linux Clang | `ubuntu-latest`, explicit `CC=clang`, `CXX=clang++` | Same clean preset build and full CTest set. |
| C++ / Windows MSVC | `windows-latest`, x64 MSVC developer environment | Same Ninja preset build and full CTest set. |
| Python exact oracle | `ubuntu-latest`, Python 3.13 | Historical reference, provenance verification, extended full witness-digest verification, and the separately authored hardening oracle for angular delta, support, compound identity, and dissipative-cycle witnesses. |
| Lean | `ubuntu-latest`, Elan `v4.2.4`, repository-pinned Lean/Mathlib | `lake --wfail build`, source trust-boundary scan, and emitted `#print axioms` output from imported formal modules. |

The `dev` preset enables `MLS_WARNINGS_AS_ERRORS=ON` and
`MLS_RUN_EXTENDED_EXACT_TESTS=ON`. Therefore each compiler job treats warnings as
failures and also executes every CTest entry registered by that preset. The
separate exact-oracle job is intentional: it produces easily isolated evidence
from the implementation-independent Python path rather than relying only on the
CTest wrapper.

## Failure preservation

GitHub retains the normal log of each failed job. In addition, every job has an
`if: always()` artifact-upload step. Available tool-version, configure, build,
test, exact-oracle, Lean-build, source-scan, and axiom-output logs are retained for
30 days. A configure failure can prevent later log files from existing; the
artifact upload permits missing files so that earlier evidence is still kept.

The C++ matrix uses `fail-fast: false`. Failures are not marked
`continue-on-error`: a failed compiler, test, oracle, source scan, or Lean build
keeps its job red.

## Recording an independent-CI result

After the branch is pushed and the workflow completes, append a dated evidence
record containing:

```text
workflow run URL and run ID
run attempt and event type
tested branch and exact source SHA
runner image/OS information from each job
compiler, CMake, Ninja, Python, Elan, Lean, Lake, and Mathlib versions
conclusion of every matrix entry and standalone job
artifact names and SHA-256 values after download
all failures, cancellations, exclusions, and reruns
```

Only record `replicated` for the particular build/test property reproduced by a
different environment. Do not use these jobs to promote numerical mechanics,
chemistry richness, physical validity, or any empirical/evolutionary gate.

## Workflow limitations and operational risks

- `ubuntu-latest` and `windows-latest` are moving GitHub-hosted images. Each run
  must record the resolved runner image and tool versions; the label alone is not
  reproducible provenance.
- GitHub Action dependencies are pinned to commit SHAs. The Windows compiler
  setup action is third-party code and remains part of the CI trust boundary.
- The Elan installer archive is pinned by version and SHA-256. The Lean and
  Mathlib versions remain pinned by `formal/lean-toolchain` and
  `formal/lake-manifest.json`; dependency downloads still depend on network
  availability.
- Hosted-runner success tests the same C++ and Lean source, not an independently
  authored implementation. Shared specification or implementation bugs can pass
  every job.
- Windows/MSVC is included because the current CMake project advertises MSVC
  warning settings, but it remains **pending** until an actual hosted run proves
  the Ninja/MSVC environment and source are compatible.
