# Mechanical Observability Lab primary-source audit

**Audit date:** 2026-08-29  
**Scope:** kinematic observability only. No constitutive law, stabilization,
force, stress, energy, damage, or time integrator is imported from these
sources.

This audit separates published equations from MLS-specific operators and pass
rules. Affine reproduction or a literature pedigree cannot promote a
candidate.

## 1. Corrected particle gradients

J. Bonet and T.-S. L. Lok, “Variational and momentum preservation aspects of
Smooth Particle Hydrodynamic formulations,” *Computer Methods in Applied
Mechanics and Engineering* 180 (1999), 97–115,
[DOI 10.1016/S0045-7825(99)00051-1](https://doi.org/10.1016/S0045-7825(99)00051-1),
derive a corrected SPH formulation and connect correct linear-gradient
evaluation to angular-momentum preservation. Their Eqs. (42) and (45) write,
in the paper's convention,

\[
\nabla\widetilde W_{ab}=L_a\nabla W_{ab},\qquad
L_a=\left[\sum_b\frac{m_b}{\rho_b}
\nabla W_{ab}\otimes x_{ba}\right]^{-1}.
\]

G. C. Ganzenmüller, “An Hourglass Control Algorithm for Lagrangian Smooth
Particle Hydrodynamics,” *CMAME* 286 (2015), 87–106,
[DOI 10.1016/j.cma.2014.12.005](https://doi.org/10.1016/j.cma.2014.12.005),
[author preprint](https://arxiv.org/abs/1410.7221), supplies an open primary
implementation reference. Its Eqs. (12), (14)–(17) give

\[
\nabla_0f(X_i)=\sum_jV_j^0(f_j-f_i)\nabla W_i(X_{ij}),
\]

\[
\widetilde{\nabla}W_i=L_i^{-1}\nabla W_i,\qquad
L_i=\sum_jV_j^0\nabla W_i(X_{ij})\otimes(X_j-X_i),
\]

the first-order identity and its corrected deformation-gradient evaluation.

### MLS-specific choice

Candidate B uses the algebraically equivalent weighted least-squares form

\[
M_i=\sum_jw_{ij}r_{ij}r_{ij}^T,\qquad
B_i=\sum_jw_{ij}(v_j-v_i)r_{ij}^T,\qquad
G_i=B_iM_i^{-1}.
\]

The compact weight
`w=(1-||r||^2/H^2)^2` and the exact cutoff are MLS choices, not quotations
from Bonet–Lok. For `v=Ax+b`, `B_i=AM_i`, so `G_i=A` when `M_i` is
nonsingular. MLS refuses the inverse when the moment is singular or outside
the registered condition bound.

## 2. Why affine reproduction is insufficient

Ganzenmüller 2015 explicitly identifies rank deficiency in corrected total-
Lagrangian SPH: distinct particle arrangements can share the same averaged
deformation gradient. The paper introduces an hourglass control force to
suppress those modes and reports that such control can alter apparent
stiffness and inhibit localization. MLS imports the warning, not the repair.

Vignjevic, Campbell, and Libersky, “A treatment of zero-energy modes in the
smoothed particle hydrodynamics method,” *CMAME* 184 (2000), 67–85,
[DOI 10.1016/S0045-7825(99)00441-7](https://doi.org/10.1016/S0045-7825(99)00441-7),
is an earlier primary control. It identifies collocated evaluation as allowing
alternating fields with zero evaluated gradient and introduces distinct
velocity/stress points. MLS does not introduce those extra points.

S. A. Silling, “Stability of peridynamic correspondence material models and
their particle discretizations,” *CMAME* 322 (2017), 42–57,
[DOI 10.1016/j.cma.2017.03.043](https://doi.org/10.1016/j.cma.2017.03.043),
[official Sandia record](https://www.sandia.gov/research/publications/details/stability-of-peridynamic-correspondence-material-models-and-their-particle-2016-07-01/),
provides the correspondence-gradient control. Its Eqs. (14)–(15) use a shape
tensor to obtain one approximate deformation gradient. Proposition 2 and the
condition preceding Eq. (36) construct nonzero deformation increments whose
weighted first moment vanishes, hence `dF=0`. Eqs. (37)–(38) isolate a
nonuniform deformation state with zero approximate gradient.

These are primary reasons to compute the complete kernel of candidate B.
Linear-field reproduction is necessary, never sufficient, and no published
stabilization term is admissible evidence for representation observability.

## 3. Finite central-distance rigidity

R. Connelly, “Generic Global Rigidity,” *Discrete & Computational Geometry*
33 (2005), 549–563,
[DOI 10.1007/s00454-004-1124-4](https://doi.org/10.1007/s00454-004-1124-4),
[author manuscript](https://pi.math.cornell.edu/~connelly/global-6.pdf),
defines the squared-edge-length map in Eqs. (2)–(4). For an edge `{i,j}` its
differential is

\[
2(p_i-p_j)\mathbin{\cdot}(u_i-u_j).
\]

The associated rigidity-matrix row contains `(p_i-p_j)` in vertex `i`'s
columns, `(p_j-p_i)` in vertex `j`'s columns, and zero elsewhere. An
infinitesimal flex lies in this matrix's kernel. For a full-span framework in
three dimensions, the maximal rank is `3n-6` and the trivial kernel is the
rigid-motion space.

L. Asimow and B. Roth, “The Rigidity of Graphs,” *Transactions of the AMS* 245
(1978), 279–289,
[DOI 10.1090/S0002-9947-1978-0511410-9](https://doi.org/10.1090/S0002-9947-1978-0511410-9),
[official AMS manuscript](https://www.ams.org/journals/tran/1978-245-00/S0002-9947-1978-0511410-9/S0002-9947-1978-0511410-9.pdf),
is the foundational finite-framework rank reference.

MLS uses half the squared-length differential for exact rational rank checks.
Dividing by nonzero bond length gives actual length rate and does not change
the kernel. Zero-length relations are rejected.

## 4. Central relations versus bond-based material laws

S. A. Silling, “Reformulation of Elasticity Theory for Discontinuities and
Long-Range Forces,” *Journal of the Mechanics and Physics of Solids* 48
(2000), 175–209,
[DOI 10.1016/S0022-5096(99)00029-0](https://doi.org/10.1016/S0022-5096(99)00029-0),
[official Sandia report](https://doi.org/10.2172/1895), is representation prior
art only. Report Eqs. (7)–(9) impose angular admissibility

\[
(\xi+\eta)\times f(\eta,\xi)=0,
\]

so a pair force is central. This lab imports no pair force at all.

J. Trageser and P. Seleson, “Bond-Based Peridynamics: a Tale of Two Poisson's
Ratios,” *Journal of Peridynamics and Nonlocal Modeling* 2 (2020), 278–288,
[DOI 10.1007/s42102-019-00021-x](https://doi.org/10.1007/s42102-019-00021-x),
[official OSTI manuscript](https://www.osti.gov/servlets/purl/1649523), makes
the limitation precise. Its Eq. (11) uses the general linear microelastic
pair-potential energy; Eq. (13) yields a fully index-symmetric elasticity
tensor, and Eq. (14) imposes the Cauchy relation. Isotropic specialization
restricts the 3D Poisson ratio to `1/4` (with the paper's 2D distinctions).

That restriction applies to a later central pair-potential constitutive model.
It neither proves nor disproves that an explicit distance graph passes the
present kinematic observability gate. MLS records it so a candidate-C pass
cannot be misrepresented as arbitrary-material capability.

## 5. Objective geometric enrichment

Candidate D is an MLS-specific diagnostic. It adds the derivative of an
explicit ordered triple product

\[
\tau=\det(x_j-x_i,x_k-x_i,x_l-x_i),
\]

not a force or energy. The derivative follows directly from determinant
multilinearity. It is translation invariant and is invariant under proper
rotations because `det(Q)=1`. The relation is tested directly in binary64,
high precision, and selected exact rational configurations; no literature
theorem is used as its pass premise.

## 6. Attribution boundary

- Literature equations determine reference operator forms, not MLS tolerances.
- Candidate B is not promoted for affine exactness.
- Ganzenmüller and Silling stabilization terms are forbidden in this lab.
- Candidate C is a rigidity relation graph, not classical bond-based
  peridynamics.
- Candidate D is a preregistered MLS relation type, not a claimed novel
  rigidity theorem.
- All solid-like claims require the registered full-dimensional configuration
  and connectivity gates; planar and collinear controls do not have a generic
  six-dimensional realized rigid-motion image.
