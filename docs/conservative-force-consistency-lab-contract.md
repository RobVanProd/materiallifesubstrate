# Conservative Force Consistency Lab contract

## Scope and stop boundary

This laboratory asks whether the accepted finite local collective relational
energy has a deterministic spatial gradient that is objective, conservative,
and internally balanced.  The evaluator is experimental and read-only.  It is
not installed in `World`, does not advance time, and does not authorize a
mechanics implementation or dynamics.

The accepted Constitutive Expressivity Lab at
`2de8843faf76a75d16b3a3012897e719291c52cf` and its public evidence tag
`constitutive-expressivity-lab-evidence-v1` are immutable inputs.  No damping,
contact, damage, fracture, gravity, chemistry, organisms, rendering, GPU work,
or thermal conversion is in scope.  Every outcome is `NO_PROMOTION` to
dynamics.

## State, units, and frozen reference data

For an explicit relation `a=(i,j)`:

```text
X_i, X_j       reference packet positions                         [m]
x_i, x_j       supplied current packet positions                  [m]
l0_a           |X_j-X_i|, strictly positive                       [m]
r_a            |x_j-x_i|, required strictly positive              [m]
n_a            (x_j-x_i)/r_a                                      [1]
e_a            r_a-l0_a                                           [m]
H               accepted symmetric relation operator              [J/m^2]
g               H e, conjugate relation force                     [J/m = N]
f_i, f_j        packet forces                                      [N]
K, df/dx        reference energy Hessian / finite force Jacobian   [N/m]
```

Packet IDs are labels only.  Graph topology, canonical relation coordinates,
reference lengths, relation weights, coefficients, and `H` are reference
constitutive data.  They are created from the reference configuration and
then frozen.  A force evaluation may not rebuild or renormalise them from the
current geometry.  A semantic relation permutation acts through an explicit
coordinate permutation of `e`, `g`, and `H`; it is not permission to create a
different constitutive operator.

The evaluator has no persistent current strain, dilatation, direction,
gradient, tensor, force, or history state.  All current quantities are derived
afresh from the supplied positions and frozen reference data.

## Energy and analytic force law

The frozen scalar energy is

```text
U(x) = (1/2) e(x)^T H e(x).
```

The evaluator computes `g=H e` once in canonical relation coordinates.  For
each noncoincident relation it then assembles

```text
f_i +=  g_a n_a
f_j += -g_a n_a.
```

With the current central rigidity operator `R(x)` mapping packet velocity to
length rate, this is

```text
f = -R(x)^T H e = -grad_x U.
```

Although each packet contribution is central, `g_a` is generally collective:
an extension on another relation sharing an endpoint can affect `g_a` through
an off-diagonal entry of `H`.  The implementation must not replace the
collective operator by independent springs.

## Continuous identities, not dynamics claims

The following are instantaneous force-law identities only:

```text
sum_i f_i = 0
sum_i (x_i-o) cross f_i = 0          for any origin o
dot(U) = g dot (R(x) v) = -f dot v.
```

They support continuous linear/angular momentum accounting if a future
integrator respects them.  This lab makes no discrete-time conservation claim.
Numerical residuals are diagnostics and are never deposited in heat or any
physical reservoir.

## Reference and finite tangents

At reference, `e=0`, `g=0`, and `f=0`.  Therefore the geometric contribution
vanishes and

```text
d^2 U/dx^2 at X = R0^T H R0,
df/dx at X       = -R0^T H R0.
```

Away from reference, the energy Hessian has two terms:

```text
K_material  = R(x)^T H R(x)
K_geometric = sum_a g_a B_a^T ((I-n_a n_a^T)/r_a) B_a
K_total     = K_material + K_geometric
df/dx       = -K_total,
```

where `B_a` is the signed packet-difference operator for relation `a`.
`K_material` and `K_geometric` are reported separately.  A nonsymmetric force
Jacobian or an implementation that silently drops the geometric term is not
the gradient of the registered finite energy.

## Objectivity and dimension law

For a proper orthogonal `Q` and translation `t`, with the frozen operator
transformed only by semantic relation-coordinate permutations:

```text
x'_i = Q x_i+t,       U'=U,       f'_i=Q f_i.
```

Under the accepted common reference/current similarity `X'=sX`, `x'=sx`,
with positive `s` and fixed coefficients in `J/m^2`:

```text
e'=s e,  U'=s^2 U,  g'=s g,  f'=s f,
torque'=s^2 torque,  K_total'=K_total.
```

If velocities are scaled as `v'=s v`, power scales as `s^2`.  Stable packet
IDs, packet order, relation order, and endpoint orientation cannot change any
physical output.

## Noncoincident domain and failure behavior

The coordinate `|x_j-x_i|` is differentiable only for `r_a>0`.  The evaluator
must validate every current relation length before emitting energy, `g`, or
force.  At exact coincidence it fails closed with a deterministic domain
status and no partial physical output.  It may not select an arbitrary
direction, epsilon-normalise the offset, add repulsion, alter `H`, or
regularise the tangent.

Positive approaches to coincidence are diagnostics.  The geometric tangent
may grow like `|g_a|/r_a`; that is recorded, not hidden.  A future collapse or
contact treatment requires a separate authorised experiment.

## Numerical approximation and failure modes

The C++ reference evaluator uses deterministic binary64 arithmetic and a
canonical accumulation order.  The independent Python implementation rebuilds
the energy and gradient from exported reference/current coordinates and the
complete exported `H`; it never calls the C++ force routine.  Registered
subsets use at least 90 decimal digits for directional derivatives and tangent
checks.

Known failure modes include stale or current-recomputed reference data,
incorrect relation-coordinate permutation, double-counted collective terms,
sign errors, partial output at coincidence, cancellation in force/torque
sums, dropped geometric tangent terms, hidden ID orientation, and loss of
resolution near collapse.  A unit test alone does not establish physical
validity.

