# Dynamic similarity, not literal Earth

MLS aims for a computationally tractable mesoscale universe. Changing a single
constant until motion “looks right” can destroy causal balances. A scale transform
must instead preserve declared dimensionless groups relevant to a scenario.

Let spatial and temporal coordinates transform as

\[
x'=\alpha x, \qquad t'=\beta t.
\]

Then choose

\[
U'=\frac{\alpha}{\beta}U,\quad
L'=\alpha L,\quad
g'=\frac{\alpha}{\beta^2}g,\quad
\nu'=\frac{\alpha^2}{\beta}\nu,\quad
D'=\frac{\alpha^2}{\beta}D,\quad
k'=\frac{1}{\beta}k,
\]

where `U` is characteristic velocity, `L` length, `g` acceleration, `nu`
kinematic viscosity, `D` diffusivity, and `k` a first-order or effective reaction
rate constant under an unchanged concentration convention.

These transformations preserve:

| Ratio | Definition | Causal balance |
|---|---|---|
| Reynolds | \(Re=UL/\nu\) | inertia versus viscosity |
| Froude squared | \(Fr^2=U^2/(gL)\) | inertia versus gravity |
| Peclet | \(Pe=UL/D\) | advection versus diffusion |
| Damkohler | \(Da=kL/U\) | reaction versus transport |

The algebraic equalities are represented in the pinned, kernel-built Lean module
[`formal/MLSFormal/Scaling.lean`](../formal/MLSFormal/Scaling.lean).

## Scope limits

Preserving these four ratios is not a proof of general physical equivalence.
Depending on the experiment, MLS may also need to control Mach, Weber, capillary,
Prandtl, Schmidt, Biot, optical-depth, or other ratios. Non-first-order kinetics,
concentration scaling, phase boundaries, fracture length scales, stochastic noise,
and discrete bond graphs require separate analysis.

Every scaled scenario therefore records:

1. base and transformed units/constants;
2. characteristic scales and all dimensionless groups considered material;
3. groups deliberately not preserved and the reason;
4. expected regime and admissible range;
5. numerical resolution relative to the physical scales; and
6. benchmark evidence that the intended causal response survives.

Dynamic similarity is an engineering tool for designing the substrate, not a
license to claim that MLS reproduces Earth chemistry or biology.
