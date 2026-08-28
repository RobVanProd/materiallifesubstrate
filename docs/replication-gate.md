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
| Local hardening GCC, MSVC, Python, and Lean recorded in `review-evidence-2026-08-28-hardening.md` | `ba15ea97b51af4a3c892fdc618a93b8586585b1f` plus MSVC portability check at `4ac4c868d7f8afba65321d7f1d563ca9b17aa86d`, `baseline-hardening` | Executed and passed | Local conformance evidence for the narrow hardening contracts, not physical validation. |
| [GitHub Actions run 33192022500](https://github.com/RobVanProd/materiallifesubstrate/actions/runs/33192022500) | `ba15ea97b51af4a3c892fdc618a93b8586585b1f`, `baseline-hardening` | **FAILED and preserved** | GCC, Clang, Python, and Lean succeeded; hosted MSVC found portability failures. |
| [GitHub Actions remediation run 33193019451](https://github.com/RobVanProd/materiallifesubstrate/actions/runs/33193019451) | `4ac4c868d7f8afba65321d7f1d563ca9b17aa86d`, `baseline-hardening` | **COMPLETED: SUCCESS** | GCC, Clang, MSVC, Python, and the pinned Lean build/source/axiom scan all succeeded. This replicates only the encoded narrow contracts. |

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

## Recorded public CI attempts

Run `33192022500` was a push event and completed with an overall failure. Its
non-fail-fast matrix preserved useful positive evidence while the Windows job
failed: Linux GCC, Linux Clang, the exact Python oracle, and the pinned Lean
build/axiom scan all concluded `success`; Windows/MSVC concluded `failure`.
MSVC `19.51.36256` reported warning-as-error C4146 in the test harness's unsigned
unary-minus rejection-sampling threshold and a failed private-API static
assertion. The job log and artifact `cpp-Windows MSVC-33192022500-1` remain
attached to the failed run.

Commit `4ac4c868d7f8afba65321d7f1d563ca9b17aa86d` remediated those portability
findings without weakening warnings-as-errors or making a forbidden API public.
Run `33193019451` completed successfully: GCC, Clang, MSVC, Python, and the
pinned Lean build/source/axiom scan all concluded `success`.

## Recording a completed independent-CI result

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
- Hosted Windows/MSVC and the complete workflow succeeded for commit
  `4ac4c868...` in run `33193019451`.
- The pinned v4 action revisions emitted Node.js 20 deprecation annotations on
  the 2026 hosted images, which forced those actions onto Node.js 24. This did
  not fail a job, but it is an operational warning to resolve in a future
  dependency-only update.
