# Kelvin covariance mathematical/source audit

**Scope:** diagnostic coordinates for the already accepted Candidate-B
corrected local symmetric-gradient operator. This document introduces no
mechanical state, law, or candidate promotion.

## Frozen implementation provenance

The operator builder is `build_corrected_local_gradient` in
`src/mechanical_observability_lab.cpp`. The accepted parent commit
`a71decf8a60c9937e568e712cf9bf13cb68c9bb7` stores that file as Git blob
`9ed0ab945a4178286c59aad9e8f9fd9eb1ac8c87`. The Kelvin audit does not modify
that header or source. It constructs and compares the raw matrix returned by
the frozen builder.

The frozen per-packet moment and full-gradient equations are

```
r_pq = x_q - x_p
w_pq = (1 - ||r_pq||^2/H^2)^2
M_p  = sum_q w_pq r_pq r_pq^T
B_p  = sum_q w_pq (v_q-v_p) r_pq^T
G_p  = B_p M_p^-1.
```

The symmetric output uses the orthonormal Kelvin coordinate order

```
(E_xx, E_yy, E_zz, sqrt(2)E_xy, sqrt(2)E_xz, sqrt(2)E_yz).
```

The existing builder rejects singular/ill-conditioned moments and failed
inverse residuals. The audit retains those gates unchanged.

## Similarity derivation

Let `x'_p=s Q x_p+t`, `H'=sH`, with `s>0` and `Q^TQ=I`. Let velocity
coordinates rotate as `v'_p=Qv_p`. Relative offsets, influence weights, and
moments transform as

```
r'_pq = s Q r_pq
w'_pq = w_pq
M'_p  = s^2 Q M_p Q^T.
```

For arbitrary transformed input velocities, substitute
`v_p=Q^T v'_p`. Direct cancellation in the corrected estimator gives

```
G'_p(v') = (1/s) Q G_p(v) Q^T.
```

Symmetrization commutes with orthogonal conjugation. Because Kelvin
coordinates are orthonormal for the Frobenius inner product, the induced map
`K(Q)` is orthogonal:

```
kelvin(Q E Q^T) = K(Q) kelvin(E).
```

For the complete raw matrix this is exactly the registered law

```
R' = (1/s) K_N(Q) R T_N(Q)^T,
```

where `T_N(Q)` rotates the three input velocity coordinates of every packet.
Translation cancels from all relative offsets. Orthogonal left/right factors
preserve singular values, leaving only the dimensioned `1/s` scale.

## Why independent scalar row normalization is not covariant

Let `D(R)` contain the inverse norm of every scalar row. The sealed diagnostic
used `D(R)R`. For a general Kelvin rotation `K`,

```
D(KR) K R != K D(R) R.
```

The reason is structural: `K` mixes the six coordinates before the nonlinear
row-norm operation. Individual row norms are not a Kelvin tensor and do not
transform by `K`.

The independent oracle supplies two controls. First, an exact rational
orthogonal row-mixing example proves that the raw input Gram matrix is
unchanged while the row-normalized output Gram determinant changes. Second,
an actual three-dimensional rational proper rotation is evaluated in
`Q(sqrt(2))` and at 100 decimal digits. Its raw Gram relation is exact while
the scalar-row-normalized spectrum splits by a resolved amount.

## Rotationally invariant diagnostic scalar

For comparison only, the audit computes one Frobenius norm for each complete
`6 x 3N` packet-output block and divides all six block rows by that same
scalar. Orthogonal Kelvin/output and velocity/input transforms preserve the
block Frobenius norm; geometric scaling changes it by `1/s`. This makes the
block-normalized diagnostic covariant, but it remains a diagnostic coordinate
choice and has no physical or promotion status.

## Numerical approximation and failure modes

The C++ builder and matrix comparison use binary64, with long-double
accumulation in dense products and Gram construction. Singular values are
diagnostic eigenvalues of the smaller Gram matrix using deterministic cyclic
Jacobi sweeps. The complete `min(rows,columns)` spectrum is emitted; the audit
does not infer rank or discard a tail.

Failures preserved by the evidence include invalid rotations/scales,
unavailable corrected moments, nonfinite or zero Kelvin blocks, failure of
input/output orthogonality, raw operator mismatch, scaled spectrum mismatch,
block-scalar mismatch, nondeterministic twin bundles, checkpoint mismatch,
oracle disagreement, and formal trust failure. A numerical pass validates the
registered finite comparison only; it does not establish continuum physics,
mechanical observability, or material behavior.

## Independent/formal division

The Python oracle does not import or call the C++ implementation. It uses
exact `a+b sqrt(2)` arithmetic for the transform identities and a separate
100-digit symmetric eigenvalue path. Lean proves the finite algebraic raw
transform/Gram statements and a finite normalization counterexample. Neither
the oracle nor Lean certifies the binary64 corrected-moment inversion.
