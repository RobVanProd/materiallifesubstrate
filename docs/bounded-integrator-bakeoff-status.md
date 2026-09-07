# Bounded integrator bakeoff — local implementation checkpoint

This is an **unsealed, provisional checkpoint**, not a completed release or a
new accepted scientific disposition. NO_PROMOTION TO AUTHORITATIVE WORLD
DYNAMICS. The accepted parent and all its evidence remain unchanged.

## Authorization and identity

- Accepted parent: `a5f83d13c276bd1f41f6121e4d3bc50dc7287983`.
- Reviewed amended preregistration: `f3b43a0ea75738724a0283c3fd93425bda6546ea`.
- The subsequent user mandate authorized implementation and the registered
  experiment end-to-end. The preregistration's historical stop notice is not
  edited retroactively.
- Proof-first commit: `2a34166` (Lean built before C interpretation).
- Initial implementation commit: `66e8edd`.
- Frozen Candidate A file SHA-256 remains
  `c4ac14cdcd46f948c1640535164c5bee400b4811868a572fe3873646cbed06de`.
- Experimental arithmetic: Python 3.13.13, gmpy2 2.3.1, MPFR 4.2.2; persistent
  B96 only, solver scratch 256, output verifier 384. No new integrator state.

## Current findings

| Candidate | Registered local finding | Consequence |
|---|---|---|
| A, unchanged B96 KDK | All existing short/long wire hashes reproduce; new short and long gates checked so far pass | Provisional sole eligible baseline, subject to remaining validation/sealing |
| B, midpoint | Five breathing root-box force-cell ambiguities; five internal first-step exact roots certified; five octahedron 256/384 output disagreements | Not eligible for tails; retain every rejection and inconclusive subcode |
| C, registered DG construction | Exact frozen-Path-B extension chain fails on the first authenticated breathing L0 endpoint pair | Stop C; no C solver or C trajectory |

B's breathing failure is a root-box dependency limitation, not a target escape
or a proved physical-budget exceedance. Its octahedron disagreement is a
literal output-stability rejection, not a rejection of implicit midpoint in
ordinary real arithmetic. The number of differing B96 components across levels
0..4 is 8, 5, 24, 16, 5; exact signed SI differences are exported, not inferred
from decimal displays. Internal first-step certification does not qualify a
complete internal trajectory or the candidate inventory.

C fails this registered zero-tolerance construction, not every discrete
gradient method. The first relation's exact extension-chain residual is:

```text
-483775444003205331452991478362985918891706764919/
7314798567868856072024734951918272331010078146560000000000000000
```

Conjugate and potential residuals and an identical-endpoint positive control
are retained separately. No correction was introduced to force compatibility.

If the remaining validation succeeds, the proposed result is
`retain_existing_b96_kdk_baseline_for_research`, with A as the sole eligible
Pareto member. This would retain the baseline, not demonstrate improvement or
general superiority over either integrator family. No exact conservation,
bit-exact bounded reversal, arbitrary-material or indefinite-horizon claim.

## Completed local evidence

- 30 authenticated one-second trajectories: three scenarios, five levels,
  KDK and permanently ineligible first-order control. All sample state hashes
  match the sealed parent.
- All fifteen exact-rational KDK short comparisons complete, including the
  internal-velocity case. The independent 110-digit smooth ODE calculation
  retains its separate role; it is not the same-integrator representation target.
- All three KDK second-order windows pass; the first-order control remains
  distinguishable. Observer uncertainty includes both endpoints of an energy
  difference; no adjacent-error ratio was used as a replacement gate.
- All 120 proper cubic rotation controls pass, plus 70 reversal, checkpoint,
  frame, permutation/orientation and inherited domain controls. Tolerance passes
  are not relabeled exact covariance or exact time reversal.
- A separate integer-rounder implementation reconstructs all fifteen short
  KDK trajectories, every physical stage and committed snapshot, relation
  impulses, energy and independently accumulated local half-ULP bounds.
- All ten 16-second A runs (15,872 steps) match the sealed state corpus.
  Every case has one warmup and five timed serial repetitions, with identical
  state streams and matching checkpoint/energy suffixes. Short timing cases
  also have one warmup and five repetitions. Timing is outside scientific hashes.
- Complete independent replay of the accepted parent certificate passed:
  90/90 short blocks and all ten full tails, byte-identical to the authenticated
  records. This replay does not claim to rerun all earlier historical labs or
  their optional full exact-prefix validations.
- The separately derived parent final audit closes the raw recurrence records'
  intentionally pending observer fields. Both internal and boosted long energy
  profiles pass the frozen amended overall-contraction gates. Exact signed
  slopes and quarter-window means are retained; none has the inherited secular
  quarter-endpoint classification.
- B/C control scientific files are byte-identical in two independently executed
  runs, excluding the declared external resource record. A separately written
  integer-rounder audit reconstructs every midpoint Picard and residual sweep,
  initial guess, norm, force cell, impulse and output. It independently confirms
  all stored root/cell and output-rejection results.
- Seventeen local test methods pass, including targeted graph mutations,
  changed H/reference, omitted primitives/impulses, false residual/norm/cell,
  warm start, precision changes, signed-slope and complete-chord rejection.
- Local GCC C++ validation passed. Full pinned Lean build passed (2,145 jobs);
  the trust scan found no placeholders, new axioms or unreported theorems.

## Evidence locations (local, not yet sealed)

All paths below are relative to the repository. Do not overwrite the preserved
development attempts when assembling a later immutable bundle.

| Path | Contents |
|---|---|
| `build/bakeoff-controls-development-v2` and `-v3` | A first-step authentication; B/C deterministic control twins |
| `build/bakeoff-midpoint-independent-development-v1.json` | Independent complete midpoint graph audit and exact output differences |
| `build/bakeoff-baseline-development-v1` | Short wires, stage records, 120 rotations |
| `build/bakeoff-baseline-controls-development-v3` | Additional control wires and outcomes |
| `build/bakeoff-baseline-exact-development-v1` | Exact-rational short comparisons |
| `build/bakeoff-smooth-development-v1.json` | Separate smooth ODE endpoints and refinement |
| `build/bakeoff-short-analysis-development-v2.json` | Short order and amended energy gates |
| `build/bakeoff-short-audit-development-v2.json` | Independent stage/force/rounding-bound audit |
| `build/bakeoff-baseline-tails-development-v1` | Full A wires, energy, timing and checkpoint checks |
| `build/bakeoff-long-audit-development-v2.json` | Exact energy, P/L slope and inherited certificate audit |
| `build/bakeoff-short-external-timing-v1.json` | Fifteen serial short timing inventories |
| `build/bakeoff-parent-full-replay.log` | Complete accepted certificate replay receipt |

Preserved implementation failures include the first B control driver abort on
an output mismatch before it was recorded as a rejection, the initial domain
adapter's wrong diagnostic duration (correct inherited duration is one second
at every label), and audit adapters that initially misread committed snapshots
and raw-versus-final certificate status. These did not change candidate physics
or registered gates. Early test-fixture and environment setup failures are
development failures, not additional scientific dispositions.

## Remaining before completion

1. Finish the final closed-inventory evidence verifier/mutation coverage and
   archival manifest; preserve failed attempts and distinguish generated twins
   from archival byte identity.
2. Run all five required GitHub CI jobs on the exact final source, including
   Clang and Windows/MSVC. Local GCC/Lean are not substitutes for those jobs.
3. Only after required validation, assemble deterministic sealed evidence and
   present the proposed disposition for independent review. Public tag/release
   creation and main merging are not performed by this checkpoint.

The attempted public source/workflow push was blocked by the safety review.
Explicit approval was requested to push these commits to
`RobVanProd/materiallifesubstrate` on `bounded-integrator-bakeoff-lab` so GitHub
CI can run. No retry, alternate upload, release, or main change has occurred.
