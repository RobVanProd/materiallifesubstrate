# Bounded Phase Tail Certification Lab — result

Decision: `stop_certificate_unsound_or_inconclusive`.
Subclassification: **inconclusive**, not a demonstrated unsound certificate.
Selected precision: `null`. Promotion: `NO_PROMOTION`.

The frozen parent is `17532284c2f0878e908f6a613f4c2e3baa47cbcd`.
Its disposition, candidate arithmetic, and public evidence are unchanged.
This result establishes neither a bounded-state structural defect nor a
full-horizon error certificate. No mechanics is activated in World.

## What the anchor audit establishes

Exact rational extraction reproduces all three and only three mandatory
192-to-256 anchor failures: internal level 1 final position, level 2 final
representation energy, and level 3 representation-energy slope. All other
levels and boosted comparisons are retained as controls. The independent
signed prefix replays check each reconstructed candidate and rational state
against its sealed hash. These are targeted prefixes, not new dynamics sweeps.

| Failure | Signed 192-bit error | Signed 256-bit error | Interpretation |
| --- | ---: | ---: | --- |
| L1 final position, packet 3, y, sample 405 | +5.3425830556e-58 m | +1.6611125540e-76 m | Exact failure reproduced; local-versus-propagated cause unresolved |
| L2 final energy, sample 403 | +1.7220542080e-64 J | -7.8136318153e-83 J | Exact failure and sign change reproduced; cancellation cause not established |
| L3 least-squares energy slope, samples 0–400 | +2.5290007700e-64 J/s | +6.4530790370e-82 J/s | Signed cancellation accounts for part, not all, of the excess |

Displays above are not the mathematical inputs. Evidence preserves exact
rational values, coordinate argmax ties, all signed energy samples, and exact
least-squares numerators, denominators, and sums of absolute contributions.
Internal L4 and boosted L4 are matched signed passing controls (the frozen
boosted anchor gates concern position/momentum, not energy). The extractor
also preserves the complete parent comparison inventory.

For L3 let A_B = sum |(t_n - mean(t)) deltaE_n| and S_B be the corresponding
signed sum. The measured |S_B|/A_B is 0.114022746569 at B192 and
0.961467161775 at B256. Consequently the 11.7673251523 excess factors exactly
as 1.39551592293 times 8.43223997583: the first factor is the excess for the
absolute-contribution sums; the second is the change in cancellation fraction.
Cancellation therefore amplifies this particular ratio, but even the
absolute-contribution ratio misses the factor-four rule. We do not claim that
cancellation fully explains the failure or identify a local rounding mechanism
for the other two metrics.

The exact 1/201 nearest-rounding control violates the proposed necessary
factor-four rule by 12.5 while obeying both half-ULP bounds. The 1+2^-10
control also violates the ratio while obeying the bounds. Preregistered signed
sums separately check accumulated upper allowances and realized signed errors.
This disproves necessity of the ratio in general, not the possibility of an
implementation defect in a particular trajectory.

The parent retrospectively checked 22,404/22,404 length/conjugate scalar pairs
and 3,734/3,734 potential values at each of B192 and B256. These authenticated
parent aggregate records are retained with their independently derived energy
and slope bound maxima. The new replays additionally check potential equality
at every replayed sample. Aggregate bounds are not case-local error
decompositions and are not forward tail enclosures. Missing case-local
rounding-budget utilization and a complete propagated signed decomposition
remain explicitly unresolved.

The reversal-position excess of 1024/9 is preserved separately as **non-gating**
under the ordinary post-budget rule. Approximate time recovery remains
different from bit-exact reversal. Replay does not change that fact.

## The actual tail-certificate boundary

The preregistered first implementation uses exact rational intermediate
arithmetic and outward 512-bit dyadic box endpoints. It propagates the actual
frozen rational KDK map only when every relative-coordinate conversion is
certified to have one binary64 bit pattern. It never substitutes the B256
trace, assumes smoothness across binary64 rounding boundaries, or uses an
inward parent witness as an unconditional upper bound.

All ten full-horizon pilots stop at step 1, second kick. Each has passed
withheld exact containment after the first kick and drift. Independent boxes
lose correlations in a relation component; the enclosure spans distinguishable
binary64 conversion results. The registered single-cell verifier refuses to
choose one. It does not branch across possible force inputs. Increasing
candidate precision or quietly assuming a force-scalar trace is forbidden.

There are 90 registered checkpoint/block combinations. Sixty blocks starting
at exact rational checkpoints 8 and 32 complete, covering block lengths 1, 4,
and 16. Thirty blocks starting at zero stop at the same unresolved cell.
All 1,320 executed withheld exact stage-containment checks pass. Generation
receives only its incoming enclosure; the exact comparator is evaluated
afterward for checking. Exact checkpoints are justified starting enclosures,
not zero-radius restarts from bounded state. These separate blocks do not
repair the missing continuous enclosure from time zero.

The pilot twins are byte-identical. Exact arithmetic tests and negative
controls detect omitted rounding, inward endpoints, an unjustified zero-radius
restart, an uncertified scalar assumption, and an endpoint-only domain check
that misses a crossing chord. These are bounded verifier controls, not a
formal implementation proof or exhaustive floating-point verification.

No full-tail state, representation-energy, or energy-slope budget is certified.
No physical budget violation is demonstrated. More correlation-aware or
multi-cell verifier arithmetic could be investigated separately; this result
does not rule it out. It records precisely where this preregistered verifier
becomes inconclusive rather than expanding its acceptance rule after the fact.

## Formal and executable scope

Lean establishes trajectory enclosure induction under an explicit one-step
preservation hypothesis, an upper-slack implication, weighted sample-error
bounds, and exact rational/remainder statements for the rounding control.
It does not prove the Python implementation, MPFR, or binary64 force graph.
The existing formal mechanics theorems are preserved. The axiom report only
adds the new declarations; no existing theorem statement changes.

The executable verifier independently recomputes signed-sample arithmetic,
checks the parent gates and exact envelopes, and reruns the withheld/pilot
inventory. Its optional full-prefix replay reconstructs the exact states
again. A record-only verification receipt must not be described as a full
phase-state replay. Compiler CI remains a bounded unchanged-C++ regression;
no new integrator experiment is included.

## Disposition

An unpublished packaging/verifier attempt at source `0681df1d5bc07d65a583b1c0c2912c8c51c2a957`
failed because the new record verifier indexed an energy-anchor field in the
boosted parent control, where no such field exists. Its twin archives, SHA-256
`baa7a0f2c94a4e2de3b9edcc527cf16d9989f5b4fd53e3b573e89e491fca0bc4`,
are preserved locally as failed attempts and have no public scientific seal.
The correction checks all mandatory internal energy gates and explicitly
labels boosted energy as diagnostic-only. No parent gate or result changed.

The ratio rule is not mathematically necessary. Its three particular failures
are reproduced; the slope has a measured cancellation amplification, while
the other causal decompositions remain incomplete. The full-tail enclosure
is unavailable because the single-cell box verifier cannot resolve the first
post-drift force conversion. Hence the narrower 'all anchor failures explained'
disposition is not justified; certification is inconclusive.

All parent physical budgets, precision inventory, finite 16-second horizons,
safe domain, and null selection remain frozen. Conservation residuals remain
measured residuals, not exact invariants. No numerical discrepancy enters a
physical reservoir. This checkpoint supports no indefinite-simulation,
arbitrary-material, evolutionary-safety, or authoritative-dynamics claim.
