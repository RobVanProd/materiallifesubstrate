# Bounded Integrator Bakeoff Lab — result for independent review

**NO_PROMOTION TO AUTHORITATIVE WORLD DYNAMICS.**

```text
decision: retain_existing_b96_kdk_baseline_for_research
pareto_set: [A]
selected_precision: 96 (inherited, not newly selected)
production_integrator_selected: false
```

The unchanged KDK baseline is the sole qualifying registered candidate.
Neither implicit alternative reaches the full-trajectory comparison. This
retains the baseline; it does not demonstrate that KDK generally dominates
implicit midpoint or discrete-gradient methods.

The accepted parent is `a5f83d13c276bd1f41f6121e4d3bc50dc7287983`.
The governing preregistration and amendment are at
`f3b43a0ea75738724a0283c3fd93425bda6546ea`. Their physics, precision inventory,
budgets, iteration ceiling, stopping rules and horizons are unchanged.
The final source identity, CI receipt and payload inventory are supplied by
the outer seal; the bundle builder refuses sealing before all five required
CI jobs pass on that exact source. This source document is not itself a seal.

## Candidate dispositions

| Candidate | Exact disposition | Evidence and limit |
|---|---|---|
| A: frozen B96 KDK | `retain_existing_b96_kdk_baseline_for_research` | Registered short gates and ten certified 16-second tails pass |
| B: registered midpoint solver | `reject_integrator_solver` | Five octahedron 256/384 RN96 output mismatches; also five breathing `stop_integrator_certification_inconclusive` force-cell controls |
| C: registered relation-coordinate DG | `candidate_c_incompatible_with_frozen_path_b` | First breathing L0 endpoint pair fails the zero-tolerance extension chain |

B's five internal first-step controls have certified unique exact fixed-cell
roots with matching B96 output and safe complete root chords. These are not
accepted full trajectories or a workaround for the failed inventory. B runs
no long tails. The breathing root box fails to resolve structural zero
relative coordinates; this is a certificate limitation, not a target escape.
The octahedron mismatch counts at L0..4 are 8, 5, 24, 16 and 5 phase components.
Exact signed differences, residuals, operation records and force bits are
included. No tolerance is substituted for the registered bit-equality gate.
No physical-budget exceedance or general midpoint defect is inferred.

C's first extension residual, at relation 0, is exactly

```text
-483775444003205331452991478362985918891706764919 /
7314798567868856072024734951918272331010078146560000000000000000
```

The conjugate and potential-chain residuals are retained separately, together
with the identical-endpoint positive control. C stops immediately: no C solver,
trajectory, correction, fitted secant, replacement potential or altered Path B.
The real-arithmetic chain theorem was compiled in commit `2a34166` before the
first executable compatibility interpretation. A mathematically valid exact
formula is not asserted to satisfy the frozen binary64 endpoint graph.

## Baseline qualification and references

The frozen A implementation hash remains
`c4ac14cdcd46f948c1640535164c5bee400b4811868a572fe3873646cbed06de`.
Every reused A sample wire hash matches the sealed parent.

- Thirty one-second trajectories: three scenarios, five levels, KDK plus the
  permanently ineligible first-order control. Each KDK case has the required
  three-successive-halving second-order window; the control is distinguishable.
- Fifteen exact-rational KDK short comparisons finish. A separate Python-integer
  implementation reproduces the GMP-rational target's exact errors and hashes.
  The independently refined 110-digit smooth ODE calculation remains separate
  from this same-integrator discrete reference.
- All 120 proper cubic rotation controls and 70 additional reversal, checkpoint,
  frame, ordering/orientation and domain controls pass their frozen budgets.
  None of the 15 short bounded reversals recovers bit-identically; this is
  reported literally. Checkpoint/replay identity is a different property.
- A separate integer-rounder reconstruction checks all short physical stages
  and committed snapshots, forces, energy, P/L and centrality residuals against
  independently accumulated local half-ULP bounds as well as physical budgets.
- All ten 16-second internal/boosted cases complete: 15,872 steps and 47,616
  physical KDK stages. The accepted relation-coordinate certificate was
  independently replayed, including 90/90 withheld blocks and all ten tails,
  with exact record equality. B256 is never used as truth.
- Long position, momentum, representation-energy/slope, P/L/centrality, frame
  and safe-domain requirements use that authenticated KDK-only certificate.
  Exact wire-derived P/L slopes also satisfy their frozen slope budgets.
- Physical-energy maximum excursion and absolute final error contract from
  L0 to L4 for both internal and boosted inventories under the amended gate.
  No case has the inherited secular quarter-endpoint classification. Signed
  slopes, means, quarter-window means and individual refinement rows remain
  evidence, not numerical energy assigned to heat or another reservoir.

Raw parent recurrence reports intentionally retain `observers_pending` status;
the separately recomputed final audit closes their observer and frame budgets.
The new audit checks both layers. It does not mistake an intermediate Boolean
for the final certificate or an inward retrospective witness for a tail bound.

## Pareto interpretation and cost

Only A passes the registered eligibility inventory, so the Pareto set contains
A without a cross-family dominance claim. The matching-row evidence retains
smooth-ODE endpoint accuracy and its reference uncertainty, same-integrator
representation error, structural/recovery/frame residuals, energy behavior,
literal operation/evaluation counts and external timings. The same-integrator
time-discretization error is constrained separately by the ODE endpoint error
and the certified representation uncertainty (triangle bounds); no 16-second
smooth ODE reference is invented.

Every eligible short and long case has one warmup and five serial timed repeats.
The long K4 candidate-step medians range from about 0.46 seconds at L0 to 7.39
seconds at L4 on this host; these exclude observers, authentication and the
independent verifier, and are not production-performance claims. Full timings
and ranges are retained outside deterministic scientific hashes. Midpoint
operation/sweep costs and C's failed compatibility work are retained rather
than reported as zero-cost eligible methods.

## Independent checking, failures and sealing

The new verifier reconstructs midpoint's entire rounded Picard graph using
Python integer/rational arithmetic, not just a list of individually correct
operations. It checks the ballistic guess, old/new dependency, fresh residual,
exact-unit norms, first passing iterate, force bits, impulses, root equations,
output rounding and rejection state. B/C control execution twins are
byte-identical apart from the explicitly external resource record.

Eighteen arithmetic/control test methods and five evidence-integrity methods
include targeted mutations for precision changes, warm starts, altered H or
reference, omitted/fused primitives and impulses, false residual/norm/force
cells, output disagreement, noncanonical state, signed-slope misuse, changed
budgets, incomplete inventory, false eligibility, missing/failed/wrong-source
CI and promotion claims. Inherited tail mutation suites remain in CI and in
the parent verification chain. Exact mathematics and executable arithmetic
checks remain separate; Lean does not prove MPFR correctness or bounded-map
symplecticity.

All failed attempts are preserved. Development failures include the initial
driver abort before classifying an actual output mismatch, the wrong duration
in a domain-test adapter, and schema-adapter errors distinguishing committed
snapshots and raw/final parent certificate fields. Pre-seal verification added
the exact-root chord check and finished the chord-minimum proofs; an unused
Lean hypothesis warning was corrected without weakening the theorem. These
are disclosed implementation/test corrections, not changed experiment gates.
The provisional implementation commits remain in branch history.

A later pre-seal review found that the short-record wrapper had left the
noncausal stage `level` label at its default zero. Correctly labeled records
were regenerated and compared to the preserved originals: all thirty numerical
traces, energies and residuals are identical; only labels and their event hashes
change. A regression now checks the level explicitly. The earlier checkpoint
checks covered state and energy; a supplementary replay now checks complete
canonical observer-event suffixes on all fifteen short and ten long cases,
with independent event reconstruction for the short and long corpora. This closes a
verification-coverage omission without altering the candidate trajectory or
loosening a gate. The earlier source/CI attempt and raw records are retained.

The archive contains source, authenticated parent, all primary control twins,
short and long records, independent audit receipts, preserved failed attempts,
and exact-source CI. Two independently generated archive streams must match
byte-for-byte. No tag, public release, archive upload or main merge is performed.

From an extracted archive, using Python with the registered dependencies:

```sh
PYTHONDONTWRITEBYTECODE=1 python source/tools/verify_bounded_integrator_bakeoff.py .
```

The default verifies the closed manifest and replays new midpoint graphs,
short integer arithmetic and all long candidate steps and observer events. It authenticates
the full parent replay receipt but does not silently rerun that expensive
certificate. Request `--replay-parent` for all 90 parent blocks and ten tails;
`--replay-exact-short` separately reruns all fifteen Python-integer rational
comparators. `--records-only` is explicitly weaker. No mode claims to rerun
every older optional historical exact-prefix experiment.

The final claim remains bounded to the registered small systems and finite
one/16-second horizons. No authoritative World integration, contact, fracture,
arbitrary-material certification, indefinite simulation or evolutionary-safety
claim follows from this research result.
