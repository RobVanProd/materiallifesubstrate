# Constitutive Expressivity Lab contract

## Scope and stop boundary

This laboratory asks whether the accepted explicit central-distance relation
state can support an objective, conservative, local elastic **energy** with
independently controllable volumetric and deviatoric channels. It does not
integrate motion and does not expose an authoritative force API.

The accepted Candidate-C relation representation and its sealed evidence at
`101296f936f8473effb316b1f9ae4040b5768349` are read-only inputs. No force,
runtime stress, pressure, damping, contact, damage, fracture, gravity,
chemistry, organism, rendering, or GPU subsystem is in scope. Every outcome
is `NO PROMOTION` to mechanics or dynamics.

## State, units, and derived variables

Authoritative input is limited to packet IDs, reference/current packet
positions, and explicit undirected relations. IDs are labels only. For edge
`a=(i,j)`:

```
xi_a = X_j-X_i                 [m]
l_a  = |xi_a|                  [m]
n_a  = xi_a/l_a                [1]
e_a  = n_a . (u_j-u_i)         [m]  (linearized displacement test)
e_a^f= |x_j-x_i|-l_a           [m]  (finite-length test)
```

The retained rigidity operator stacks `e=R u`. Constitutive coefficients and
relation quadrature weights are experimental read-only inputs. They are not
packet state. The local scalar, deviatoric extension, energy, gradient, and
Hessian are recomputed for every evaluation; none is persistent history or a
hidden kinematic state.

## Energy laws

The pair-separable negative control is

```
E_pair(e) = (1/2) sum_a h_a e_a^2,   h_a > 0.
```

For the selectable local collective evaluator, packet `i` sees only incident
relations `I(i)`. With declared positive dimensionless relation weights
`w_ia`, define

```
m_i = sum_(a in I(i)) w_ia l_a^2,
q_i = sum_(a in I(i)) w_ia l_a e_a,
d_i = q_i/m_i,
e^d_ia = e_a-d_i l_a,

E_i = (A_i/2) q_i^2/m_i
    + (B_i/2) sum_(a in I(i)) w_ia (e^d_ia)^2,

E_collective = sum_i E_i,            A_i,B_i > 0.
```

`q_i` is an unnormalised local dilatational moment, `d_i` its dimensionless
projection coefficient, and `e^d` the weighted-orthogonal residual. This is a
finite-graph rule inspired by ordinary/state-based peridynamic collective
extension response; it is not a verbatim continuum quadrature formula.

Unit weights are used on accepted finite graphs. A relation deletion removes
its terms from both `q_i` and `m_i`. Under uniform infinitesimal dilation
`e_a=c l_a`, the local energy is proportional to the surviving
`m_i`; missing relations therefore reduce response and are not silently
renormalised away to preserve stiffness.

The relation-space constitutive operator `H` is the Hessian of an energy:

```
E(u) = (1/2) (R u)^T H (R u),
K    = R^T H R.
```

For positive `A_i`, `B_i`, and positive incident weights, the dilation and
deviatoric terms form an orthogonal decomposition of every incident extension
vector. Since every relation has an endpoint, `H` is strictly positive on
nonzero relation-extension coordinates. The formal layer states the exact
assumptions rather than importing numerical positivity.

## Locality

Pair response has diagonal `H`. Local collective response couples two
relation coordinates only when their relations share a packet. Its graph
radius is one incident-relation star. Its Euclidean support diagnostic is the
maximum distance between any endpoints of each relation-coordinate pair with
a nonzero `H` entry, including diagonal entries. A dense global `H` is allowed
only as an algebraic upper-bound diagnostic and is permanently ineligible for
the decision.

The bounded finite-graph inputs are provenance-bound twice: first to the
complete accepted parent tables, then to frozen SHA-256 commitments for the
exact selected producer-format configuration, packet, and relation payloads.
The evidence exports the complete rigid and accepted `R`-null bases used by
its energy residual checks so independent review can recompute those claims
without trusting summary fields.

## Conservation, objectivity, and dimension law

The evaluator creates no physical energy and performs no transition. It
computes a scalar stored-energy candidate from a supplied configuration.
Because the finite evaluator depends only on actual/reference lengths,
translation and proper rotation of current geometry leave it invariant while
the reference geometry remains fixed. A separate common reference/current
transform checks coordinate covariance. Packet-ID renaming and packet/relation
permutation cannot change energy.

When reference and current coordinates are both scaled by positive `s`, every
length and extension scales by `s`, `m_i` and `q_i` scale by `s^2`, and both
energy channels scale by `s^2` while fixed `A_i,B_i` carry units J/m^2. Pair
energy with fixed `h_a` in J/m^2 has the same `s^2` law.

## Numerical approximation and failure modes

Binary64 evaluation is checked against an independently implemented exact or
high-precision reference on the registered bounded controls. Algebraic
gradients/Hessians may be formed only for verification. Numerical residuals
remain diagnostics and are never converted to heat or another reservoir.

Known failure modes include a mistaken isotropic cubature/Cauchy control,
surface-biased finite quadrature, zero-length relations, nonpositive
constitutive coefficients, relation-coordinate modes not covered by a local
star, hidden ID-dependent orientation, incorrect double counting, and
loss of positive semidefiniteness through roundoff. Intentionally floppy
graphs must remain floppy; energy cannot fabricate absent observables.
