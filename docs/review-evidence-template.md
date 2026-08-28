# MLS publication and review evidence record

> Copy this template for each claim-bearing build or experiment. Do not overwrite
> an earlier record. Replace every `<required>` field, retain raw logs, and mark an
> unexecuted command `NOT RUN`; never infer a pass from source inspection.

## 1. Record identity

| Field | Required value |
|---|---|
| Evidence record ID | `<date>-<commit-or-tree>-<scope>` |
| Record schema | `mls.review-evidence.v1` |
| Created at, including UTC offset | `<required>` |
| Runner | `<required>` |
| Independent reviewer | `<required before publication>` |
| Claim under review | `<one narrow falsifiable statement>` |
| MLS purity level | `<MLS-0 / MLS-1 / MLS-2 / MLS-3>` |
| Gate(s) | `<G0..G15; do not infer adjacent gates>` |
| Evidence column | `<formal / exact executable / numerical / empirical-evolution>` |
| Disposition | `<draft / pass for narrow claim / fail / blocked / superseded>` |

### Mandatory scope declaration

Copy this sentence unchanged into every completed record:

> Passing unit tests establishes only that the tested implementation satisfied
> the encoded assertions for the recorded build and inputs. It does not establish
> physical validity, numerical convergence, material expressivity, life,
> evolvability, ecology, open-endedness, or any untested MLS gate.

## 2. Source and worktree provenance

| Field | Value |
|---|---|
| Repository URL/origin | `<required>` |
| Branch | `<required>` |
| Commit SHA | `<required; write NO COMMIT for an initial tree>` |
| Commit timestamp | `<required>` |
| Worktree clean? | `<yes/no>` |
| `git status --short` artifact | `<path + SHA-256>` |
| Dirty diff artifact | `<path + SHA-256, or EMPTY>` |
| Submodules/dependency locks | `<identities + hashes, or NONE>` |
| Configuration files | `<paths + SHA-256>` |

Run from the repository root and capture stdout/stderr and exit code:

```powershell
git rev-parse --show-toplevel
git remote -v
git branch --show-current
git rev-parse HEAD
git show -s --format=fuller HEAD
git status --short
git diff --binary
git diff --binary | git hash-object --stdin
```

An uncommitted tree is reviewable only when the complete diff and untracked source
artifacts are archived. Publication evidence should normally come from a clean,
immutable commit.

## 3. Host, compiler, and toolchain

| Component | Executable/path | Exact version output | Configuration/notes |
|---|---|---|---|
| Operating system | `<required>` | `<edition/build/kernel>` | `<updates/container/VM>` |
| CPU | `<required>` | `<model/features>` | `<logical/physical count>` |
| RAM | `<required>` | `<capacity>` | `<limits>` |
| GPU/driver | `<required or NONE>` | `<exact versions>` | `<not used / role>` |
| C++ compiler | `<required>` | `<full output>` | `<target ABI>` |
| CMake | `<required>` | `<full output>` | `<generator>` |
| Ninja/build tool | `<required>` | `<full output>` | `<parallelism>` |
| Python | `<required for exact suite>` | `<full output>` | `<implementation>` |
| Lean | `<path or NOT INSTALLED>` | `<full output or NOT RUN>` | `<toolchain>` |
| Lake | `<path or NOT INSTALLED>` | `<full output or NOT RUN>` | `<manifest hash>` |
| Mathlib | `<revision or NOT RESOLVED>` | `<tag + commit>` | `<dependency hash>` |

Suggested discovery commands:

```powershell
Get-ComputerInfo | Select-Object WindowsProductName,WindowsVersion,OsBuildNumber,OsArchitecture
Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
Get-Command cmake,ninja,c++,python,lean,lake -ErrorAction SilentlyContinue | Select-Object Name,Source
cmake --version
ninja --version
c++ --version
python --version
lean --version
lake --version
```

Record missing tools as missing. Do not substitute an intended version for an
executed version.

## 4. Build configuration

| Setting | Value |
|---|---|
| Configure preset/generator | `<required>` |
| Build type | `<Debug / Release / other>` |
| C++ standard | `C++20` |
| `BUILD_TESTING` | `<ON/OFF>` |
| `MLS_BUILD_TESTS` | `<ON/OFF>` |
| `MLS_AUDIT_DEFAULT` | `<ON/OFF>` |
| `MLS_WARNINGS_AS_ERRORS` | `<ON/OFF>` |
| Compiler flags/definitions | `<verbatim>` |
| Environment differences | `<required; NONE if controlled>` |
| Sanitizers/instrumentation | `<required; NONE if absent>` |

Archive `CMakeCache.txt`, generated build rules, and the complete build log. A
warnings-as-errors build is a useful separate record, not a substitute for
runtime or physical validation.

## 5. Randomness and experimental controls

| Field | Value |
|---|---|
| Canonical deterministic seed | `260828` |
| PRNG | `SplitMix64` for current C++/extended exact suites; record implementation identity |
| Additional derived seeds | `<constants and derivation>` |
| Random stream checkpoint | `<state/hash or NOT IMPLEMENTED>` |
| Replicate seeds | `<required for empirical work; one seed is insufficient>` |
| Preregistered thresholds | `<document/version/hash>` |
| Null/sham/control conditions | `<required for causal claims>` |

Seed `260828` makes a run reproducible; it does not make one run representative.
Empirical/evolutionary claims require replicated seeds and a declared sampling
analysis.

## 6. Exact commands and captured results

Record commands exactly as executed—working directory, arguments, environment,
start/end times, duration, exit code, and raw-log hashes.

| Run ID | Working directory | Exact command | Start/end | Exit | Stdout/stderr artifacts + SHA-256 | Result |
|---|---|---|---|---:|---|---|
| BUILD-DEV | `<required>` | `cmake --preset dev` then `cmake --build --preset dev --parallel` | `<required>` | `<required>` | `<required>` | `<PASS/FAIL/NOT RUN>` |
| UNIT-DEV | `<required>` | `ctest --preset dev` | `<required>` | `<required>` | `<required>` | `<x/y; PASS/FAIL/NOT RUN>` |
| UNIT-LIST | `<required>` | `.\build\dev\tests\mls_validation.exe --list` | `<required>` | `<required>` | `<required>` | `<case count>` |
| HEADLESS | `<required>` | `.\build\dev\mls_headless.exe` | `<required>` | `<required>` | `<required>` | `<captured JSON + status>` |
| EXACT-V0 | `<required>` | `python reference/exact_arithmetic_v0.py` | `<required>` | `<required>` | `<required>` | `<counts/hash>` |
| EXACT-VERIFY | `<required>` | `python tools/exact_validation.py --mode full --provenance-only --verify reference/validation_results_v0.json` | `<required>` | `<required>` | `<required>` | `<PASS/FAIL>` |
| EXACT-EXT | `<required>` | `python tools/exact_validation.py --mode full --output <artifact-path>` | `<required>` | `<required>` | `<required>` | `<PASS/FAIL>` |
| LEAN | `formal/` | `lake update` then `lake build` | `<required>` | `<required>` | `<required>` | `<KERNEL PASS/FAIL/NOT RUN>` |

The expected historical provenance baseline for `EXACT-V0` and `EXACT-VERIFY` is:

```text
seed=260828
pair_transfer_cases=100000
momentum_exchange_cases=100000
stoichiometric_reactions_balanced=6
stoichiometric_random_extent_cases=100000
energy_ledger_cases=100000
hierarchical_aggregation_cases=25000
dynamic_similarity_cases=10000
coarse_grain_counterexample=fine false, coarse true, A/B conserved
result_sha256_before_hash_field=92405699657c404e4dcd324a16ca0d3cd0e7a82ff395ccfb277c47c10766a2da
```

A mismatch is a failed provenance check and must be investigated; do not update
the expected hash merely to make a changed implementation pass.

### Per-test result inventory

Paste the complete `--list` output and map each executed case to its raw result:

| Test name | Executed? | Result | Duration | Assertion scope | Failure/log link |
|---|---:|---|---:|---|---|
| `<exact registered test name>` | `<yes/no>` | `<pass/fail/not run>` | `<required>` | `<what it actually asserts>` | `<required>` |

## 7. Formal-proof evidence boundary

| Check | Result/evidence |
|---|---|
| Pinned `lean-toolchain` | `leanprover/lean4:v4.33.0-rc1` |
| Pinned Mathlib declaration | `v4.33.0-rc1` |
| Resolved Lean version and binary hash | `<required or NOT RUN>` |
| Resolved Mathlib commit | `<required or NOT RUN>` |
| `lake-manifest.json` SHA-256 | `<required or NOT RUN>` |
| `lake build` exit/log | `<required or NOT RUN>` |
| `sorry`/`admit` source scan | `<command, result, artifact>` |
| Unexpected axioms review | `<required before kernel-verified claim>` |

Use **proof candidate** unless the recorded pinned `lake build` succeeds and the
assumption review is complete. A successful build proves only the encoded Lean
statements; it does not validate C++ conformance or physical laws.

## 8. Numerical and physical validity

Unit and exact-arithmetic results leave this section red until separate benchmark
evidence is supplied.

| Required study | Scenario/version | Resolution/timestep sweep | Reference/analytic target | Acceptance threshold | Result |
|---|---|---|---|---|---|
| Conservation residual convergence | `<required>` | `<required>` | `<required>` | `<preregistered>` | `<pass/fail/not run>` |
| Mechanics | `<required>` | `<required>` | `<required>` | `<preregistered>` | `<pass/fail/not run>` |
| Transport/thermal | `<required>` | `<required>` | `<required>` | `<preregistered>` | `<pass/fail/not run>` |
| Chemistry kinetics/energy | `<required>` | `<required>` | `<required>` | `<preregistered>` | `<pass/fail/not run>` |
| Rotation/translation | `<required>` | `<angles/offsets>` | `<invariant/equivariant target>` | `<preregistered>` | `<pass/fail/not run>` |
| Cross-fidelity replay | `<required>` | `<implementations>` | `<causal observation>` | `<preregistered>` | `<pass/fail/not run>` |

Passing current integer rotation, translation, batching, replay, or accounting
tests is a scaffold result. It is not a convergence study and cannot fill this
table automatically.

## 9. Empirical/evolutionary evidence

Complete only for H1–H6 or Gates 7–15:

| Field | Required value |
|---|---|
| Hypothesis/falsifier | `<H1..H6 exact statement>` |
| Population/run protocol | `<version/hash>` |
| Replicates and seeds | `<required>` |
| Baseline/null/sham | `<required>` |
| Blinding | `<who knew targets and when>` |
| Search/compute budget | `<matched values>` |
| Primary outcome | `<preregistered>` |
| Exclusions/stopping | `<preregistered>` |
| Statistical analysis | `<method and assumptions>` |
| Exploit-quarantine disposition | `<physical/unresolved/exploit/observer artifact>` |
| Negative results | `<required>` |

No unit, exact, numerical, or formal result may be copied into this column as an
empirical pass.

## 10. Known failures, limitations, and deviations

This section may not be blank. If none were observed, write “none observed within
the executed scope” and still list known coverage limitations.

| ID | First observed | Subsystem | Trigger/command | Expected | Actual | Scope/impact | Disposition/issue | Retest evidence |
|---|---|---|---|---|---|---|---|---|
| `<required>` | `<required>` | `<required>` | `<required>` | `<required>` | `<required>` | `<required>` | `<open/fixed/accepted>` | `<required>` |

Mandatory known-limitations checklist:

- [ ] Current `step` is ballistic only; no force/contact/fracture solver.
- [ ] Sparse grid is a disposable index; no MPM scatter/gather.
- [ ] Chemistry uses configured integer reaction extents; no kinetics/equilibrium.
- [ ] Ledger omits angular momentum, charge, local transaction pairs, and named reservoirs.
- [ ] FNV-1a physical hash is non-cryptographic and omits ledger history.
- [ ] No unit-test pass is being presented as physical validity.
- [ ] Lean status is stated from an executed build, or explicitly `NOT RUN`.
- [ ] Failed, interrupted, excluded, and flaky cases are enumerated.

## 11. Artifact manifest

| Artifact | Purpose | Bytes | SHA-256 | Retention/location |
|---|---|---:|---|---|
| `<source archive/commit>` | `<required>` | `<required>` | `<required>` | `<required>` |
| `<build log>` | `<required>` | `<required>` | `<required>` | `<required>` |
| `<test log>` | `<required>` | `<required>` | `<required>` | `<required>` |
| `<raw JSON/results>` | `<required>` | `<required>` | `<required>` | `<required>` |
| `<config/checkpoint>` | `<as applicable>` | `<required>` | `<required>` | `<required>` |

Generate file hashes on Windows with:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath <artifact-path>
```

## 12. Review conclusion

| Reviewer question | Answer and evidence |
|---|---|
| Is the narrow claim stated without scope inflation? | `<required>` |
| Is the source/build identity reproducible? | `<required>` |
| Are failures and omissions visible? | `<required>` |
| Is each evidence column independent? | `<required>` |
| Did any observer, camera, semantic API, or unledgered boundary affect state? | `<required>` |
| Did the result pass exploit quarantine where required? | `<required>` |
| What result would falsify the claim next? | `<required>` |

Final reviewer disposition: `<accept narrow claim / reject / request more evidence>`.
