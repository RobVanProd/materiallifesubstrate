# Conservative Force Consistency derivation audit

## Established input versus this lab

The scalar energy and local incident-relation constitutive operator are frozen
outputs of the accepted Constitutive Expressivity Lab.  This lab does not
change that energy or claim a new constitutive model.  Its new question is
whether the ordinary spatial derivative of that finite energy can be evaluated
without hidden state while retaining the symmetries implied by a scalar
objective potential.

The derivations below are elementary finite-dimensional calculus and central
force accounting.  They are recorded so that implementation signs and finite
tangent terms can be reviewed independently.

## Length derivative and force sign

For relation `a=(i,j)`, let

```text
d_a=x_j-x_i,  r_a=|d_a|,  n_a=d_a/r_a,  e_a=r_a-l0_a.
```

On the declared domain `r_a>0`, a virtual displacement gives

```text
delta e_a = n_a dot (delta x_j-delta x_i).
```

Stacking these rows defines `R(x)`.  With the canonical symmetric reference
operator `H_force`, abbreviated `H` below,

```text
U=(1/2)e^THe,  g=He,
```

symmetry of `H` gives

```text
delta U = g^T delta e = g^T R delta x.
```

Thus `grad U=R^Tg` and physical force is

```text
f=-R^Tg.
```

In endpoint form the `i` packet receives `+g_a n_a` and `j` receives
`-g_a n_a`.  This sign convention is checked directly rather than inferred
from a test tolerance.

The parent builder's two stored triangles can differ by binary64 accumulation
roundoff.  The force lab records those parent entries and freezes
`H_force=(H_parent+H_parent^T)/2` once.  For any real vector `e`,

```text
e^T H_parent e = e^T H_force e,
```

because `H_parent-H_force` is antisymmetric.  This makes the stored matrix
match the symmetric mathematical operator required by the derivative without
changing the quadratic form or introducing a current-state correction.

## Internal force, torque, and power

Every relation contributes equal and opposite packet forces, so its net force
is zero.  Its torque about any origin `o` is

```text
(x_i-o) cross (g_a n_a) + (x_j-o) cross (-g_a n_a)
= g_a (x_i-x_j) cross n_a
= 0,
```

because `n_a` is parallel to `x_j-x_i`.  Summing relations preserves both
identities.  This proof uses the actual spatial offsets and does not rely on
packet IDs or graph symmetry.

For supplied packet velocity `v`, length rate is `dot e=R v`, hence

```text
dot U = g dot (R v) = -(f dot v).
```

These are continuous virtual-work identities.  A future discrete integrator
could still violate momentum or energy, which is outside this lab.

## Finite Hessian

Direction variation is

```text
delta n_a = ((I-n_a n_a^T)/r_a)
            (delta x_j-delta x_i).
```

Differentiating `grad U=R^Tg` produces

```text
K_material  = R^T H R,
K_geometric = sum_a g_a B_a^T ((I-n_a n_a^T)/r_a) B_a,
K_total     = K_material+K_geometric.
```

Both terms are symmetric.  At reference, `e=g=0`, so `K_geometric=0` and the
accepted linearised Hessian `R0^T H R0` is recovered.  Away from reference,
calling `R^T H R` the complete tangent would omit the direction derivative
and generally fail the scalar-potential Jacobian check.

## Similarity scaling

Under a common positive similarity `X'=sX`, `x'=sx`:

```text
l0'=s l0,  r'=s r,  e'=s e,  n'=n.
```

For the accepted fixed coefficients `H` in `J/m^2`:

```text
U'=s^2U,  g'=s g,  f'=s f.
```

Differentiation with respect to `x'=sx` leaves the finite tangent unchanged.
Torque scales as `s^2`; power also scales as `s^2` when velocity is scaled by
`s`.  These are the preregistered metamorphic expectations.

## Coincidence

At `r_a=0`, the unit direction and length gradient do not exist.  The scalar
length energy remains evaluable as a number, but it has no unique spatial
gradient there.  Returning an arbitrary force direction would therefore add
an unregistered constitutive choice.  The force evaluator fails closed before
physical output at exact coincidence and only reports positive approaches as
conditioning diagnostics.
