# Kelvin Covariance Audit result

**Decision:** `SUPPORTED_DIAGNOSTIC_COORDINATE_DEFECT`.

**Claim boundary:** this bounded result explains the accepted Mechanical
Observability Lab's Candidate-B metamorphic spectrum failures. It does not
promote Candidate B, establish mechanical observability, or authorize the
later Candidate-C confirmation or any constitutive mechanics.

## Preregistered matrix

The C++ audit evaluated four full-dimensional packet configurations under six
registered transformations, for 24 total comparisons. Every base/transformed
corrected-gradient moment build was available. Results were:

| Gate | Passed | Failed |
|---|---:|---:|
| raw operator similarity | 24 | 0 |
| scaled raw singular spectrum | 24 | 0 |
| orthogonal input/Kelvin maps | 24 | 0 |
| rotationally invariant block-scalar diagnostic | 24 | 0 |
| checkpoint exact round trip | 4 | 0 |

The legacy independent scalar-row normalization exceeded its spectrum
tolerance in all 16 rotation-containing comparisons and in none of the pure
translation/packet-permutation controls. That is the same 16-row failure
fingerprint that caused the accepted parent lab's global STOP.

## Numerical extrema

| Metric | Maximum observed | Maximum fraction of its own tolerance |
|---|---:|---:|
| `Q` orthogonality residual | `9.50184e-17` | recorded per row |
| `abs(det(Q)-1)` | `0` | `0` |
| Kelvin-map orthogonality residual | `3.14018e-16` | recorded per row |
| raw operator covariance residual | `5.96975e-16` | `1.02923e-6` |
| scaled raw spectrum delta (GCC direct SVD) | `4.18692e-16` | `5.32820e-7` |
| scaled raw spectrum delta (local MSVC direct SVD) | `4.64076e-15` | `2.66410e-6` |
| block-scalar covariance residual | `5.71238e-16` | `4.68175e-7` |

Across the 16 rotation-containing physical configurations, the legacy
row-normalized spectrum delta ranged from `2.15634e-2` to `1.87007e-1`, many
orders of magnitude above the registered binary64 tolerance.

The standalone actual-Kelvin counterexample used an anisotropic diagonal raw
operator. Its raw transform residual was exactly zero and its direct-SVD raw
spectrum delta was approximately `7.40e-17` in the C++ diagnostic, while the
independently row-normalized spectrum delta was approximately `0.700`.

## Preserved failed compiler replication

The first public replication, CI run `33281716611` at source
`ce374ac3b38e5b9c3b26c4e6aac1b059ab120b05`, is intentionally preserved as a
failure. GCC, Clang, Python, and Lean passed; MSVC failed four cascading tests
because 17 of the 24 raw spectrum rows failed while every raw operator and
block-scalar row passed. A local MSVC reproduction measured the unit-test row
at `8.81355` times tolerance.

The failure was in the C++ diagnostic's former Gram/square-root singular-value
path, not in the raw corrected-gradient covariance law. The direct one-sided
Jacobi path now acts on the rectangular matrix and retains every tail value.
It passes the same frozen tolerance without a rank cutoff, zeroing, deletion,
regularization, or decision-rule change. This correction does not erase or
reinterpret the failed run.

## Independent exact/high-precision result

The independently implemented Python oracle passed exact
`Q(sqrt(2))` input/Kelvin orthogonality, translation independence, full
`sQx+t` pullback with `1/s`, raw Gram similarity, and block-scalar covariance.
Its 100-decimal-digit scaled-eigenvalue maximum delta was `8e-100`.

An exact rational orthogonal row-mixing counterexample preserved the raw input
Gram matrix but changed an invariant of the independently row-normalized
output Gram matrix. The actual three-dimensional Kelvin control produced a
maximum normalized-spectrum split of approximately `2.99154e-1`. The oracle's
canonical pre-hash is
`58fa03bef4451bc5411ce8ee2c59f17e8f1fa6e056f2909147a0e15ef81d9ff6`.

## Interpretation

The raw corrected symmetric-gradient operator transforms as a dimensioned
tensor operator should. The old diagnostic then applied a nonlinear,
coordinate-wise row rescaling that does not commute with a physical rotation's
Kelvin mixing. Its spectrum therefore changed even when the underlying raw
operators were related by the registered orthogonal similarity law.

One common Frobenius scalar per complete six-row Kelvin block is covariant and
was used as a diagnostic control only. It is not a mechanical state variable,
stabilization, constitutive choice, or replacement decision gate.

## Stop

This branch stops after independent validation, compiler/Lean replication,
and outer sealing. The accepted Mechanical Observability evidence remains
unchanged. The separately authorized name
`relational-observability-confirmation` is deliberately not created until a
new head-agent review accepts this small result.
