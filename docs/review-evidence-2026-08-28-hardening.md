# MLS-0 baseline-hardening review evidence — 2026-08-28

## Identity and narrow disposition

| Field | Value |
|---|---|
| Repository | `https://github.com/RobVanProd/materiallifesubstrate` |
| Branch | `baseline-hardening` |
| Initial hardened candidate | `ba15ea97b51af4a3c892fdc618a93b8586585b1f` |
| Accepted implementation and MSVC remediation | `4ac4c868d7f8afba65321d7f1d563ca9b17aa86d` |
| Canonical seed | `260828` |
| Accepted scope | Exact MLS-0 matter/energy/linear- and orbital-angular-momentum accounting, integer ballistic transport, structural compound identity, and point-pair support eligibility |
| Scientific disposition | **GREEN only for the encoded narrow contracts; physical validity remains unclaimed** |

This record deliberately separates local execution from GitHub-hosted CI. The
Python hardening oracle is separately authored and imports no C++ production
code, but GitHub CI still exercises the same repository specifications and is
not an independent simulator implementation.

## Implemented hardening findings

- A committed counterexample shows that an equal/opposite non-central impulse
  can conserve linear momentum while changing orbital angular momentum. The
  accepted point-pair transition now requires a central impulse. Boundary point
  impulses record opposite linear momentum, `r x J`, and kinetic-energy exchange.
- Voxel membership is not an interaction predicate. Pair eligibility is based
  only on packet positions and the explicit `Length` interaction radius using a
  checked, portable two-limb squared-distance comparison.
- Connected compound graphs are canonicalized independently of atom-site
  numbering within the explicit eight-site MLS-0 bound. Disconnected graphs and
  parallel/multiple edge encodings are rejected.
- Packet mutation is private to staged `World` transitions. Authoritative totals
  fold packet snapshots independently of voxel diagnostics.
- The momentum operation is explicitly named and tested as an
  actuated/dissipative scaffold. A closed forward/reverse cycle restores
  momentum but converts stored energy to heat; it is blocked from serving as a
  generic conservative mechanics primitive.

These are acceptance-contract results, not evidence for contact, force,
chemistry kinetics, continuum mechanics, or emergent behavior.

## Local Windows/GCC clean execution

The clean build directory `D:\MaterialLifeSubstrate\build\final-hardening-gcc-4ac4c86`
was confirmed absent before configuration. The commands, run from the repository
root, were:

```powershell
cmake -S . -B build/final-hardening-gcc-4ac4c86 -G Ninja -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DMLS_BUILD_TESTS=ON -DMLS_AUDIT_DEFAULT=ON -DMLS_WARNINGS_AS_ERRORS=ON -DMLS_RUN_EXTENDED_EXACT_TESTS=ON
cmake --build build/final-hardening-gcc-4ac4c86 --parallel
.\build\final-hardening-gcc-4ac4c86\tests\mls_validation.exe
ctest --test-dir build/final-hardening-gcc-4ac4c86 --output-on-failure
```

Recorded tools were Windows 11 Pro `10.0.26200`, MinGW-W64 GCC `16.1.0`,
CMake `4.3.2`, Ninja `1.13.2`, and Python `3.13.14`. Configuration and build
passed with warnings treated as errors. Configuration also verified that direct
external calls to all three private packet mutators fail compilation. The direct
C++ harness reported `MLS validation: 43/43 passed`. CTest reported `5/5`
passed in `55.28 s`:

```text
mls.validation                      Passed   2.15 s
mls.exact.quick                     Passed   0.47 s
mls.exact.provenance                Passed  13.55 s
mls.exact.extended.full             Passed  38.87 s
mls.hardening.independent.oracle    Passed   0.21 s
```

The exact witnesses, all with seed `260828`, were:

```text
historical reference pre-hash  92405699657c404e4dcd324a16ca0d3cd0e7a82ff395ccfb277c47c10766a2da
extended oracle pre-hash       21b6f6563aefa3073618c685d2d04d0c72056377208ff5ff7363fc63e264c4c3
hardening oracle pre-hash      9546019b4f346fe25463f2e065bc04b139987391b39c684df178f319a9e70630
```

The hardening oracle executed 10,000 angular-delta cases, 1,596 translated
support cases, the graph-isomorphism/rejection witnesses, and the dissipative
closed-cycle witness. Two headless runs were byte-identical with physical-state
hash `16587461159375120790`.

## Local Windows/MSVC clean execution

The fresh directory `build/msvc-hardening-recheck` was confirmed absent before
this command. No source edit occurred during validation.

```powershell
cmd.exe /d /c 'call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cmake -S . -B build/msvc-hardening-recheck -G Ninja -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DMLS_BUILD_TESTS=ON -DMLS_AUDIT_DEFAULT=ON -DMLS_WARNINGS_AS_ERRORS=ON -DMLS_RUN_EXTENDED_EXACT_TESTS=ON && cmake --build build/msvc-hardening-recheck --parallel && ctest --test-dir build/msvc-hardening-recheck --output-on-failure'
```

Microsoft C/C++ `19.44.35228` from Visual Studio 2022 Community, Ninja,
`Debug`, and warnings-as-errors were used. Configuration emitted all three
expected private-call rejection probes; the build completed `17/17`. CTest
reported `5/5` passed in `72.03 s`, with individual times `10.94`, `0.48`,
`19.13`, `41.25`, and `0.21 s`. The C++ test output was `43/43 passed`; the
same seed and three exact hashes listed above were reproduced.

## Local Lean build and trust boundary

The committed toolchain resolved Lean `4.33.0-rc1` at commit
`62eed1db4d67327ec8120be05f1a1b0847d74561`, Lake
`5.0.0-src+62eed1d`, and Mathlib
`79d0395a1825a6264ad5d269e35e60537518955e`. The manifest SHA-256 was
`67CF0A8124F65A19244B61834B8D34EE9F51F888096584DF1C100DD80B7D4C65`.

From `D:\MaterialLifeSubstrate\formal`:

```powershell
$env:ELAN_HOME='D:\MaterialLifeSubstrate\.tools\elan'
& "$env:USERPROFILE\.elan\bin\lake.exe" --wfail build
```

Result: `Build completed successfully (967 jobs)`. The source trust scan found
zero `sorry`, `admit`, `sorryAx`, or project-defined `axiom` declarations.
`AxiomReport.lean` runs `#print axioms` on all 27 exported theorems, including
the executable `PacketLite`/`WorldLite` transition claims. Reported dependencies
were either none or only Lean's standard `propext`, `Classical.choice`, and
`Quot.sound`; no project-defined conservation axiom was used.

The transition-level report includes heat transfer, balanced reaction,
structural/thermal replacement, boundary material and energy transfer,
actuated/dissipative pair momentum and energy, the exact
`Delta L = (r1-r2) x J` equation, central-pair angular conservation, and boundary
point-impulse momentum/angular/energy accounting. These rational algebraic
proofs do not certify the C++ floating-point/fixed-width implementation or any
continuum physics approximation.

## Preserved CI failure and remediation run

The first public workflow run is intentionally retained:

| Run | Tested SHA | Result |
|---|---|---|
| [33192022500](https://github.com/RobVanProd/materiallifesubstrate/actions/runs/33192022500) | `ba15ea97b51af4a3c892fdc618a93b8586585b1f` | **FAILED** overall: Linux GCC, Linux Clang, Python exact oracle, and pinned Lean succeeded; Windows/MSVC failed during compilation. |

The MSVC job used hosted MSVC `19.51.36256` with warnings-as-errors. It exposed
warning C4146 in the test harness's unsigned unary-minus rejection-sampling
threshold and an MSVC private-member `requires`-expression incompatibility in
the API compile check.
The failure was not suppressed or rerun as green. Its job log and artifact
`cpp-Windows MSVC-33192022500-1` were preserved with artifact digest
`sha256:c85f9096793b0037030783953913056058af7fd57ded899431d9396c5cc1c2b2`.
Commit `4ac4c868...` changed the threshold to equivalent unsigned subtraction
and moved the negative API checks to external-client compiler probes that must
fail to compile for configuration to succeed.

The remediation run completed:

| Run | Tested SHA | Per-job status |
|---|---|---|
| [33193019451](https://github.com/RobVanProd/materiallifesubstrate/actions/runs/33193019451) | `4ac4c868d7f8afba65321d7f1d563ca9b17aa86d` | **COMPLETED: SUCCESS**. Linux GCC, Linux Clang, Windows/MSVC, Python exact oracle, and pinned Lean build/source/axiom scan: success. |

Resolved hosted tools were Ubuntu 24 image `20260823.283.1`, GCC `13.3.0`,
Clang `18.1.3`, CMake `3.31.6`, Ninja `1.13.2`, and Python `3.13.15`; and Windows
image `20260824.214.3`, MSVC `19.51.36256`, CMake `4.4.2`, Ninja `1.13.2`, and
Python `3.13.15`. The Lean job used the same pinned Lean/Lake/Mathlib versions
listed above, built successfully, printed all 27 axiom reports, and passed its
source scan.

The retained artifact digests reported by GitHub were:

```text
cpp-Linux Clang-33193019451-1   sha256:9c40d5e1b9cf7c2757995663b92c34044aa37a18330be69482ce378cf1d326a6
cpp-Linux GCC-33193019451-1     sha256:ef8461465c17110d2730d66e722a0f71e73c1bd08b48b69ec9bd2c7e06abe9b8
cpp-Windows MSVC-33193019451-1  sha256:db6b4e57f7ecd7c9f37ab62656c1ec688844925be80a93af59829f760dd17cae
exact-oracle-33193019451-1       sha256:446578d8b452efabf54a70aec07a28675a9ec82e50f5d5d94526ec164e579808
lean-33193019451-1               sha256:7fadd85532e2786d6bd57198cdec05b745ea7a82809b1d01559e452a0734f609
```

The CI annotations also warn that the pinned v4 action revisions target
deprecated Node.js 20 and were forced onto Node.js 24 by the hosted runners.
This did not fail any job, but it remains dependency-maintenance work.

## Known RED limitations and rejected promotions

- There is no dimensioned timestep, so `dt/2` convergence remains **RED**. The
  within-tick impulse-order witness demonstrates sensitivity; exact tick batching
  is not a timestep-refinement study.
- Dynamic chemistry remains **RED** beyond a bounded structural identity
  scaffold. Canonicalization supports at most eight atom sites; no graph-derived
  material properties, reaction kinetics, spatial complexes, or chemical
  richness claim is promoted.
- The hard spherical support cutoff is an exact eligibility contract, not a
  validated kernel, contact law, or isotropy/convergence result.
- The accepted pair impulse is actuated/dissipative. Conservative mechanics
  remains blocked pending an explicit reversible potential/field-energy state
  and update law.
- There is no MPM, gravity, contact, fracture, diffusion, reaction kinetics,
  organism, evolution, rendering, GPU backend, alternate solver, or independent
  C++ implementation.
- Local and CI success establish only conformance to the encoded contracts.
  They do not make an observed behavior physically valid.
