# MLS-0 baseline review evidence — 2026-08-28

## Identity and narrow disposition

| Field | Value |
|---|---|
| Evidence schema | `mls.review-evidence.v1` |
| Repository | `https://github.com/RobVanProd/materiallifesubstrate` |
| Branch | `main` |
| Tested source commit | `31c5733c618aead558dd7e4232a0976e2fc88bda` |
| Recorded at | `2026-08-28T11:53:11-04:00` |
| Scope | Small deterministic MLS-0 fixed-point accounting and ballistic packet/grid reference |
| Canonical seed | `260828` |
| Disposition | Code baseline passed its encoded build, unit, exact, repeatability, and formal checks |
| Scientific publication ready | **No** — physical/numerical gates remain unpassed |

> Passing unit tests establishes only that the tested implementation satisfied
> the encoded assertions for the recorded build and inputs. It does not establish
> physical validity, numerical convergence, material expressivity, life,
> evolvability, ecology, open-endedness, or any untested MLS gate.

The committed reference implementation and the exact oracle are intentionally
separate. `reference/exact_arithmetic_v0.py` is the unchanged standard-library
`fractions.Fraction` program supplied for provenance. `tools/exact_validation.py`
is a separate Python exact oracle and does not import or execute the C++ core.

## Host and toolchain

| Component | Executed version |
|---|---|
| OS | Microsoft Windows 11 Pro, `10.0.26200`, build `26200`, 64-bit |
| CPU | AMD Ryzen 7 5700, 8 cores / 16 logical processors |
| RAM | `34224615424` bytes |
| C++ compiler | MinGW-W64 x86_64 UCRT POSIX SEH GCC `16.1.0` |
| CMake | `4.3.2` |
| Ninja | `1.13.2` |
| Python | `3.13.14` |
| Git | `2.54.0.windows.1` |
| GitHub CLI | `2.95.0` |
| Elan | `4.2.4 (227caca13 2026-08-25)` |
| Lean | `4.33.0-rc1`, commit `62eed1db4d67327ec8120be05f1a1b0847d74561` |
| Lake | `5.0.0-src+62eed1d` |
| Mathlib | tag input `v4.33.0-rc1`, resolved commit `79d0395a1825a6264ad5d269e35e60537518955e` |

The Lean toolchain and temporary compiler files were placed on D: with
`ELAN_HOME=D:\MaterialLifeSubstrate\.tools\elan` and
`TEMP=TMP=D:\MaterialLifeSubstrate\.tools\tmp`. E: was not accessed.

The clean CMake cache recorded:

```text
CMAKE_BUILD_TYPE=Debug
BUILD_TESTING=ON
MLS_BUILD_TESTS=ON
MLS_AUDIT_DEFAULT=ON
MLS_WARNINGS_AS_ERRORS=ON
MLS_RUN_EXTENDED_EXACT_TESTS=ON
```

## Exact commands and final outputs

All C++ commands ran from `D:\MaterialLifeSubstrate` after the previous generated
build directory was moved intact to the ignored D: tool area.

```powershell
$env:TEMP='D:\MaterialLifeSubstrate\.tools\tmp'
$env:TMP=$env:TEMP
cmake --preset dev
cmake --build --preset dev --parallel
ctest --preset dev
```

Final configure/build result:

```text
CXX compiler identification: GNU 16.1.0
Configure/generate: PASS
Build: 12/12 targets, PASS
Compiler warnings: 0 (warnings-as-errors enabled)
```

Final CTest result:

```text
1/4 mls.validation              Passed  2.00 sec
2/4 mls.exact.quick             Passed  0.47 sec
3/4 mls.exact.provenance        Passed 13.68 sec
4/4 mls.exact.extended.full     Passed 38.52 sec
100% tests passed, 0 tests failed out of 4
Total Test time (real) = 54.69 sec
```

The direct harness was also executed:

```powershell
.\build\dev\tests\mls_validation.exe --list
.\build\dev\tests\mls_validation.exe
```

Result: `MLS validation: 23/23 passed`. The registered cases include exact
transfers, momentum/energy exchange, chemistry balance, sparse aggregation,
duplication/loss detection, every boundary channel, negative boundary rejection,
arithmetic failure atomicity, zero state, independent and interacting update
orders, fractional grid-phase translation, an exact 3–4–5 off-axis ballistic
rotation, tick batching, renderer/camera isolation, and deterministic replay.

The unchanged historical reference was executed directly:

```powershell
python reference\exact_arithmetic_v0.py
python tools\exact_validation.py --mode full --provenance-only --verify reference\validation_results_v0.json
python tools\exact_validation.py --mode full --verify tests\exact_validation_full.canonical.json
```

Results:

```text
Historical reference: PASS
seed=260828
pair transfers=100000
momentum exchanges=100000
balanced reaction definitions=6
random reaction extents=100000
energy ledger cases=100000
hierarchical aggregation cases=25000
dynamic-similarity cases=10000
historical pre-hash=92405699657c404e4dcd324a16ca0d3cd0e7a82ff395ccfb277c47c10766a2da

Extended exact oracle: PASS
extended pre-hash=21b6f6563aefa3073618c685d2d04d0c72056377208ff5ff7363fc63e264c4c3
```

The headless executable was run twice and compared byte-for-byte:

```text
schema=mls.headless-audit.v0
tick=1
packet_count=2
occupied_voxels=1
reaction_definition_balanced=true
fine_reactable_before_transport=false
lossy_aggregate_looks_reactable=true
fine_reactable_after_physical_transport=true
conservation_ok=true
physical_state_hash_fnv1a64=11231715700036493075
repeat_output_identical=True
```

Formal commands ran from `D:\MaterialLifeSubstrate\formal`:

```powershell
$env:ELAN_HOME='D:\MaterialLifeSubstrate\.tools\elan'
$env:Path='C:\Users\usa50\.elan\bin;'+$env:Path
lake --wfail build
rg -n --glob '*.lean' '\b(sorry|admit)\b' .
```

Result:

```text
Build completed successfully (963 jobs).
No sorry/admit tokens found in Lean sources.
```

`#print axioms` was run for all 15 exported theorems. Five use no axioms; the
others use only the standard Lean axioms `propext`, `Classical.choice`, and/or
`Quot.sound`. No theorem reported `sorryAx`.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `formal/lake-manifest.json` | `67CF0A8124F65A19244B61834B8D34EE9F51F888096584DF1C100DD80B7D4C65` |
| `reference/exact_arithmetic_v0.py` | `9E8172793F373A08625D21A926EEA6E37E7654E554697ADB774AAAC85D1FA8BE` |
| `reference/validation_results_v0.json` | `3448C6F6795C7B0EA8540362198937DA85EB819C5D99451310F2ECBDCDDA1FB7` |
| `tools/exact_validation.py` | `4CAE4159FCF4D141D648D4465AB54B8B9144E9F8C901B40B8BEA25E09C51C8F7` |
| `tests/exact_validation_full.canonical.json` | `E1A420B7F37328FF9F1C828607BCD9EFFADCFA198F54B28529ECA0186A7D863B` |

## Failed and interrupted preliminary runs

- The first Lean attempt used Elan's default C: storage and failed with Windows
  error 112 (insufficient disk space). The toolchain was redirected to D:.
- Broad `import Mathlib` statements caused excessive cold-build memory/I/O and
  two manually interrupted builds. Imports were narrowed without changing any
  theorem statement; the final warning-failing build passed.
- One preliminary CTest run reported 22/23 C++ cases because a tombstone-history
  assertion used the intentional default history limit of zero. The test fixture
  was corrected to request a bounded history; the final clean run passed 23/23.
- A recursive deletion request for the old generated build directory was rejected
  by the safety layer. It was recoverably moved inside `.tools/`; the final build
  directory was therefore created from scratch.
- Invoking Lean from the repository root reports no default toolchain by design.
  Invoking it from `formal/` resolves the committed `lean-toolchain` and produced
  the successful versions/results above.

## Known failures, limitations, and red gates

- The implemented `step` is exact integer ballistic transport only. There is no
  force, MPM scatter/gather, contact, stress, deformation, plasticity, fracture,
  diffusion, thermal conduction, fluid solve, physical field, or reaction
  kinetics.
- There is no physical timestep parameter, so tick batching is **not** a timestep
  refinement or convergence study. Timestep sensitivity remains unvalidated.
- Translation and 3–4–5 off-axis rotation tests cover this integer ballistic
  scaffold only. They do not establish continuum/grid isotropy.
- Chemistry supplies structural graphs, exact stoichiometry, and caller-selected
  extents. It does not establish a causally rich material-property model.
- `physical_state_hash()` is a non-cryptographic regression fingerprint. It
  intentionally omits packet IDs/generations and ledger baseline/boundary state;
  deterministic replay separately compares the ledger.
- Authoritative `World` mutations use full-copy staging before commit. Direct
  `PacketStore` use does not provide the same allocation-failure transaction
  guarantee, and no allocator fault-injection suite exists.
- There is no checkpoint serialization, alternate C++ implementation, second
  solver/backend, GPU backend, or cross-compiler replication.
- No organism, fitness, reward, plant, animal, tool, ecological, or evolutionary
  subsystem exists in the authoritative code.
- Gates requiring mechanics, transport, fracture/cutting, the affordance
  gauntlet, rediscovery, cells, ecology, or long-run evolution remain red/not run.

External adversarial review should therefore review only the narrow MLS-0
accounting/ballistic baseline. No observed behavior is called physically valid on
the strength of these tests.
