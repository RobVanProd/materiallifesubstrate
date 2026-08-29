# Projection Exactness + Nullspace Lab result

**Status:** stopped with **NO PROMOTION** under the frozen decision rules.

This lab diagnoses the previously sealed full-consistent-projection result. It
does not add or select a transfer family and does not authorize constitutive
mechanics.

## Bounded result

The directly constructed affine nodal witness satisfies the assembled finite
system and reconstructs the particle-center field within the preregistered
roundoff bounds for all 76 systems (228 component rows). The maximum normalized
`Mg-q` residual is `1.1103491734586566e-15`; the single registered vector
particle-mass normalized `Sg-V` residual is at most
`3.4777030346300917e-16`.

All four selected numerical full-rank systems (12 component rows) pass the
separate approximately 106-bit double-double reference gates. The maximum
normalized high-precision backward, grid-forward, and particle-reconstruction
errors are respectively:

- `7.980131821544994e-33`;
- `9.894105556165525e-11`;
- `1.700989438207356e-14`.

The reference solve operates on the exact assembled binary64 `M` and `q`, with
no shift, regularization, node drop, basis alteration, or pseudoinverse. Its 862
accepted complete-pivot steps are retained with row/column order, magnitude,
and threshold. Numerical rank remains a threshold diagnostic, not a
certificate. No high-precision condition estimate was produced: its condition
value is explicitly `NA`/`unavailable`, and no pivot ratio is mislabeled as a
condition number.

The preserved legacy PCG control reports these mutually exclusive raw
statuses:

| Raw component status | Count |
|---|---:|
| solved | 147 |
| structurally rank deficient | 78 |
| ill conditioned | 3 |

The separate accuracy classification is:

| Accuracy classification | Count |
|---|---:|
| backward and forward gates pass | 99 |
| backward status passes but forward/reconstruction gate fails | 48 |
| unavailable because PCG did not return a solution | 81 |

Its original `5e-12` normalized-residual gate, applicability flag, observed
legacy residual, iteration count, and termination reason are reported
separately from the lab's normwise backward-error metric.

Among solved components, maximum normalized backward, grid-forward, and
particle-reconstruction errors are `8.523616908997105e-11`,
`2.988901505062656e-05`, and `1.719417890374835e-08`. A small selected
full-rank micro-system is recovered by the high-precision path after PCG
reports no acceptable solution. However, both preregistered prior-failure main
geometries pass the current PCG gates. The evidence therefore does **not** make
the broader claim that solver conditioning explains the earlier sealed affine
failures.

## Decisive nullspace finding

The ten selected singular systems produce 692 accepted numerical modes. Every
mode satisfies the registered `Mz`, `Sz`, shifted-minus-base equation-residual
change, and reconstructed-center-change gates. Their worst normalized
residuals are:

| Metric | Maximum |
|---|---:|
| `Mz` | `2.658646061445428e-17` |
| `Sz` | `3.19242246469467e-17` |
| shifted-minus-base equation residual | `7.523545202021824e-17` |
| shifted-minus-base particle reconstruction | `6.908550678807895e-17` |

All 692 accepted center-invisible modes are gradient-visible. The maximum
particle velocity-gradient norm ranges from `6.88355838538202e-05 1/s` to
`3.697435560051688 1/s`; the smallest observed ratio to its roundoff visibility
bound is about `3.9792711047e10`.

The finding occurs in every selected phase/orientation family:

| Phase / orientation | Modes | Gradient-max range (`1/s`) |
|---|---:|---:|
| `p000 / p012_sppp` | 122 | `6.752313e-04` – `2.891215e-01` |
| `p000 / p210_sppm` | 122 | `4.167529e-04` – `2.891215e-01` |
| `p049_001_083 / p012_sppp` | 224 | `6.883558e-05` – `3.697436` |
| `p049_001_083 / p210_sppm` | 224 | `6.883558e-05` – `3.697436` |

The `p049_001_083` groups include their corresponding ppc=1 singular control;
the table is a retained family summary, not a cross-system equivalence gate.

The preregistered decision is therefore:

> `stop_center_state_gradient_nullspace_blocker`

For the tested quadratic B-spline center-only representation, particle-center
velocity does not uniquely determine the grid velocity gradient needed by
future mechanics. This is an architecture blocker for that center-only state,
not a general rejection of particles, grids, or consistent projection.

## Formal scope

Pinned Lean proves the finite exact-rational operator statements:

- `consistentMass_is_gram_operator` (`M=S^T W S` extensionally);
- `consistentMass_kernel_eq_interpolation_kernel` under strictly positive
  particle masses; and
- `consistentProjection_solutions_have_equal_reconstruction` for two supplied
  exact solutions of the same system, without an invertibility assumption.

`#print axioms` reports only `propext`, `Classical.choice`, and `Quot.sound` for
these exported claims. There are no project-defined conservation axioms,
`sorry`, `admit`, or `sorryAx`. The formal model does not connect those exact
rational objects to C++ binary64 assembly or QR, and it does not prove gradient
visibility.

## Evidence boundary

The final evidence requires two byte-identical full producer runs, independent
Python reconstruction/validation, the exact oracle, all C++ tests, a clean
warnings-as-errors build, pinned Lean compilation and axiom reporting, and the
Linux GCC, Linux Clang, Windows/MSVC, Python, and Lean CI jobs. Smoke runs are
explicitly provisional and issue no scientific decision.

The independent validator checks the registered selection, exact mass and
checkpoint hashes, assembly identities for exported systems, vector witness,
solver metrics, pivot trace, nullspace status/mode completeness, center and
gradient images, decisions, manifest, and cross-run byte equality. Numerical
rank and floating-point QR remain empirical diagnostics. Raw assembly is
retained for 14 selected systems; the other 62 systems are metric-only, so the
validator can enforce their schema, registered inputs, decisions, and internal
metric relations but cannot reconstruct their absent `M` and `q`. A passing
unit test is not evidence that an observed behavior is physically valid.

No new transfer family, force, stress, constitutive law, gravity, contact,
fracture, chemistry, organism, renderer, or GPU path was introduced.
