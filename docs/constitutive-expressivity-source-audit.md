# Constitutive Expressivity Lab primary-source audit

This audit distinguishes established peridynamic results from the finite MLS
experiment. Equations were read from the primary papers; the laboratory does
not infer a constitutive law from a secondary summary.

## Sources

1. Trageser, J. E. & Seleson, P., *Bond-Based Peridynamics: a Tale of Two
   Poisson's Ratios*, Journal of Peridynamics and Nonlocal Modeling 2,
   278--288 (2020), DOI
   [10.1007/s42102-019-00021-x](https://doi.org/10.1007/s42102-019-00021-x),
   [open manuscript](https://www.osti.gov/servlets/purl/1649523).
2. Silling, S. A., *Reformulation of Elasticity Theory for Discontinuities and
   Long-Range Forces*, Journal of the Mechanics and Physics of Solids 48,
   175--209 (2000), DOI
   [10.1016/S0022-5096(99)00029-0](https://doi.org/10.1016/S0022-5096(99)00029-0).
3. Silling, S. A., Epton, M., Weckner, O., Xu, J. & Askari, E., *Peridynamic
   States and Constitutive Modeling*, Journal of Elasticity 88, 151--184
   (2007), DOI
   [10.1007/s10659-007-9125-1](https://doi.org/10.1007/s10659-007-9125-1),
   [Sandia record](https://www.sandia.gov/research/publications/details/peridynamic-states-and-constitutive-modeling-2007-02-01/).

## Pair-separable central response

Trageser--Seleson Eq. (11) writes the linear microelastic pair energy about a
pairwise-equilibrated reference as

```
W^P = (1/4) integral_H lambda(xi) (xi . eta)^2 dxi.
```

Their Eqs. (12)--(13) give the corresponding local elastic tangent as an
integral of `xi_i xi_j xi_k xi_l`. Complete permutation symmetry of that
integrand yields the additional Cauchy relation in Eq. (14),
`C_ijkl=C_ikjl`; Eq. (15) lists its three-dimensional orthotropic component
forms. For isotropy this sets the Lamé coefficient `lambda_L=G`, and therefore

```
K/G = (lambda_L+2G/3)/G = 5/3,
nu  = lambda_L/(2(lambda_L+G)) = 1/4.
```

The MLS diagonal extension energy has the same fourth-order form under a
smooth affine strain:

```
e_a = l_a n_ai epsilon_ij n_aj,
E_pair = (1/2) sum_a h_a e_a^2.
```

The laboratory tests the restriction only on a preregistered isotropic
fourth-moment cubature. It does not demand that an arbitrary irregular finite
graph exhibit an isotropic Poisson ratio. Prestress, transverse/angle
response, and collective coupling are outside this negative control.

## Bond-based versus ordinary/state-based response

Silling et al. (2007) give the original pairwise central model in Eqs. (1)--
(3). Their Definition 8.4 and Eq. (44) define an ordinary state-based material
whose force direction follows the deformed bond. Eq. (47) shows that a bond-
based model is a special case. Definition 8.5 and Eq. (49) are the critical
expressivity distinction: the scalar response associated with one bond may
depend on the complete deformed-length state, so ordinary does not mean pair
separable. Proposition 8.2/Eq. (46) addresses angular-momentum balance for
ordinary response.

Definition 10.1/Eq. (61) defines elastic state energy. Equation (70) states
objectivity under a proper orthogonal transform, and Proposition 11.1/Eqs.
(71)--(72) show that an ordinary elastic material's energy can be expressed
collectively through deformed bond lengths.

This is the prior-art category of the MLS local candidate. Collective
distance response is not claimed as novel.

## Linear Peridynamic Solid reference

Silling et al. define extension, weighted volume, dilatation, and the
isotropic/deviatoric extension split in Eqs. (81)--(85):

```
e = y-x,
m = integral_H omega(xi) |xi|^2 dV_xi,
theta = (3/m) integral_H omega(xi) |xi| e(xi) dV_xi,
e^i = theta |xi|/3,
e^d = e-e^i.
```

Equation (104) gives the Linear Peridynamic Solid energy

```
W = (k/2) theta^2
  + (alpha/2) integral_H omega(xi) (e^d(xi))^2 dV_xi,
```

and Eqs. (108)--(112), for a complete spherical three-dimensional horizon,
derive `alpha=15G/m`. The resulting continuum calibration has independent
positive bulk and shear moduli.

The assumptions matter: three dimensions, ordinary elastic mobile material,
complete spherical integration/influence symmetry, homogeneous small strain,
and positive moduli. It is not a surface correction for a truncated or
damaged finite neighborhood, and this lab does not use the separate
deformation-gradient correspondence construction.

## MLS-specific finite rule

For relation weights `w`, the direct discrete LPS translation would compute

```
m_i     = sum_j w_ij l_ij^2 V_j,
theta_i = (3/m_i) sum_j w_ij l_ij e_ij V_j,
e^d_ij  = e_ij-theta_i l_ij/3.
```

Blindly recomputing that normalization on a truncated finite graph can make a
uniform dilatation appear unchanged after relations are deleted. The MLS lab
therefore preregisters a different finite energy:

```
E_i = (A_i/2) q_i^2/m_i
    + (B_i/2) sum_j w_ij (e_ij-(q_i/m_i)l_ij)^2,
q_i = sum_j w_ij l_ij e_ij.
```

This retains the established collective dilatational/deviatoric structure,
uses no deformation gradient, and has one incident-star locality. Its finite
normalization, unit weights on accepted graphs, double-endpoint assembly, and
`A,B` calibration are MLS-specific experimental choices. They are not
attributed to the papers. With positive coefficients the two terms are an
orthogonal decomposition of incident extension coordinates; strict global
positivity and kernel preservation remain formal/numerical MLS obligations.

For the preregistered isotropic seven-direction quadrature, the exact moments
give

```
m=60,
q=20 tr(epsilon),
sum w(e^d)^2=8 epsilon_dev:epsilon_dev.
```

Thus `A=3K/20`, `B=G/4` gives
`E=(K/2)(tr epsilon)^2+G epsilon_dev:epsilon_dev`. This is a finite algebraic
control, not a claim that arbitrary free-surface or deleted graphs reproduce
continuum isotropy.

## Explicit limitations

- Unique undirected MLS relations and directed per-point peridynamic horizons
  have different counting conventions; overall factors are declared.
- Recomputing `m_i` is part of the finite rule, but the `q_i^2/m_i` form makes
  uniform-dilation energy proportional to surviving weighted relation length
  rather than restoring the deleted response.
- Exact finite length extensions are translation/proper-rotation invariant
  and also reflection invariant; stable IDs cannot create chirality.
- With fixed finite coefficients in J/m2, scaling reference/current geometry
  by `s` makes the registered finite energy scale by `s^2`. This differs from
  scaling a fully volumetric three-dimensional continuum discretization,
  whose total energy would include volume quadrature and scale by `s^3`.
- Passing affine tangent controls does not establish boundary, damage,
  dynamics, or continuum-convergence behavior.
