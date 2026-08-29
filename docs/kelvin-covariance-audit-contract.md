# Kelvin covariance audit contract

**Status:** preregistered bounded diagnostic. This audit cannot promote a
mechanical representation, select a constitutive law, or alter the accepted
Mechanical Observability Lab result at
`a71decf8a60c9937e568e712cf9bf13cb68c9bb7`.

## 1. Question and stop boundary

The accepted Mechanical Observability Lab used a six-component orthonormal
Kelvin representation for each corrected symmetric-gradient block, then
independently normalized every scalar output row before its numerical rank and
metamorphic spectrum diagnostics. This audit tests the provisional diagnosis
that the 16 Candidate-B metamorphic failures were caused by that diagnostic
coordinate operation rather than by the raw corrected-gradient operator.

Only Candidate B's already implemented, read-only corrected local gradient is
in scope. Candidate C and D do not participate. No candidate can be promoted.
No transfer, force, stiffness, stress, elasticity, pressure, contact, damage,
fracture, gravity, diffusion, chemistry, organism, rendering, or GPU work may
be added. The later relational-observability confirmation requires a separate
head-agent authorization and branch.

## 2. State, units, and raw operator

The input is a finite packet configuration with stable ID and position `x_p`
in metres, plus a positive support radius `H` in metres. Velocities are only
operator inputs and have units metres per second. The frozen corrected local
gradient is rebuilt from positions exactly as specified in the accepted
Mechanical Observability Lab contract. Its symmetric part is exported in the
orthonormal Kelvin order

```
(E_xx, E_yy, E_zz, sqrt(2) E_xy, sqrt(2) E_xz, sqrt(2) E_yz).
```

Thus the raw matrix `R(x,H)` has `6N` rows, `3N` columns, and units `m^-1`;
`R v` has units `s^-1`. The audit changes no authoritative state, clock,
matter, momentum, or energy. All matrices, singular values, normalizations,
and residuals are transient diagnostics.

## 3. Registered similarity law

For

```
x' = s Q x + t,   H' = s H,
```

`s` is finite and strictly positive, `t` is a finite translation, and `Q` is
a proper orthogonal 3-by-3 matrix. Let `T_N(Q)` be the block-diagonal input
map with one `Q` per packet. Let `K(Q)` be the six-dimensional Kelvin map
defined by

```
kelvin(Q E Q^T) = K(Q) kelvin(E)
```

for symmetric `E`, and let `K_N(Q)` contain one `K(Q)` block per output
packet. Both maps are orthogonal in their Euclidean coordinates. The raw
operator claim is

```
R(x',sH) = (1/s) K_N(Q) R(x,H) T_N(Q)^T.                 (1)
```

Translation does not enter the right side. Consequently every raw singular
value scales by `1/s`:

```
s sigma_j(R(x',sH)) = sigma_j(R(x,H)).                   (2)
```

No claim is made for independently rescaled scalar Kelvin rows.

## 4. Frozen numerical matrix

The final C++ sweep uses four deterministic, full-dimensional packet sets:

| ID | Geometry | Packet count | Base support |
|---|---|---:|---:|
| `cube8` | corners of a unit cube | 8 | `2.0 m` |
| `bcc9` | `cube8` plus its body centre | 9 | `2.0 m` |
| `jitter27` | seeded (`260829`) perturbed `3x3x3` bulk | 27 | `2.2 m` |
| `surface18` | two complete `3x3` layers | 18 | `3.1 m` |

Every selected local moment must pass the frozen builder's existing inverse
and condition gates before a covariance comparison is available. A failure is
preserved; it is not regularized or dropped.

Each base is compared with these transformations:

1. translation `(0.37,-0.29,0.41) m`;
2. the rational proper rotation
   `[[1,8,4],[8,1,-4],[-4,4,-7]]/9`;
3. that rotation plus the registered translation;
4. the same rotation and translation with `s=1/2`;
5. the same rotation and translation with `s=2`.

Packet input order is deterministically permuted in a separate control while
stable IDs retain the semantic ordering. The construction records `Q^T Q-I`,
`det(Q)-1`, `K^T K-I`, raw matrix covariance, scaled raw singular-spectrum
covariance, and deterministic repeatability. All final rows are retained.

## 5. Preregistered floating gates

Binary64 reductions are deterministic and use long-double accumulation where
the implementation already does so. For a matrix with `m` rows and `n`
columns, define `d=max(6,m,n)` and `eps=2^-52`. Residuals use a Frobenius norm
and the denominator `max(minnormal, ||reference||_F)`.

| Quantity | Acceptance tolerance |
|---|---:|
| `Q` orthogonality and determinant | `8192 d eps` |
| Kelvin-map orthogonality | `16384 d eps` |
| normalized raw identity (1) | `32768 d eps` |
| maximum normalized scaled singular delta (2) | `65536 d eps` |
| diagnostic block-scalar identity | `65536 d eps` |
| twin-run scalar/CSV output | byte-for-byte identical |

The spectrum comparison includes all singular values in descending order and
uses `max(minnormal, sigma_max(reference))` as its common denominator. A
numerically unresolved tail is reported rather than deleted. The tolerances
are frozen before the final sweep and may not be changed after inspection.

## 6. Row-normalization counterexample

The independent exact/high-precision oracle must exhibit matrices `R` and
`R'=U R V^T`, with orthogonal `U,V`, whose raw singular spectra agree but
whose independently unit-row-normalized spectra differ. It also evaluates an
actual three-dimensional Kelvin rotation. The counterexample passes only if:

- raw Gram/singular invariants agree at the oracle's registered precision;
- the row-normalized spectral difference is nonzero by exact algebra or is at
  least `10^20` times the high-precision arithmetic error bound; and
- the binary64 implementation reproduces a row-normalized delta exceeding
  `1000` times its preregistered spectrum tolerance.

This is evidence about a diagnostic-coordinate defect. It does not establish
Candidate B's observability or fitness for mechanics.

## 7. Optional diagnostic block scalar

The only alternative normalization permitted here assigns one common scalar
to all six rows of a packet's Kelvin block: the Frobenius norm of that complete
`6 x 3N` block. A zero or nonfinite block fails explicitly. Left Kelvin and
right input rotations preserve this norm, while geometric scale changes it by
`1/s`; therefore this block normalization is rotationally invariant and its
normalized transform law omits the physical `1/s` factor. It is diagnostic
only and cannot enter a candidate decision or retroactively repair the sealed
run.

## 8. Formal and independent boundaries

Lean will define the raw finite transform rather than take covariance as a
conservation premise. It will prove the strongest tractable statements for
the `1/s` law, orthogonal input/output maps, induced Gram/spectrum invariance,
and block-scalar equivariance. Any invertibility or positivity assumption is
explicit. An exact finite counterexample will show that nonlinear scalar
row normalization need not commute with orthogonal output mixing. Exported
claims remain subject to the existing source and `#print axioms` gates: zero
`sorry`, `admit`, `sorryAx`, or project-defined axioms.

The Python oracle is separately implemented and does not call the production
C++ operator code. Its canonical result and mutation tests are part of the
evidence. Formal exact statements do not certify binary64 assembly.

## 9. Decision and seal

The bounded audit has only these outcomes:

- `SUPPORTED_DIAGNOSTIC_COORDINATE_DEFECT`: every available raw identity and
  raw-spectrum row passes, the exact/high-precision counterexample passes,
  and the permitted block-scalar diagnostic is covariant;
- `RAW_OPERATOR_COVARIANCE_FAILURE`: an available raw identity or raw spectrum
  fails; stop with the failing data;
- `INCONCLUSIVE`: build/moment, independent-oracle, determinism, formal trust,
  or replication evidence prevents the first two classifications.

No outcome promotes Candidate B or any mechanics representation. The final
source SHA, compilers, Python/Lean versions, exact seed, complete rows, failed
runs, twin-run comparison, independent validation, and outer seal are
preserved. The branch stops immediately after sealing for head-agent review.
