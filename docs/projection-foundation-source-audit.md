# Projection Foundation Lab primary-source audit

**Audit date:** 2026-08-28  
**Scope:** force-free particle/grid projection only. No constitutive mechanics,
forces, boundaries, persistent affine or polynomial particle state, or
production promotion is introduced here.

This audit freezes what is taken from the primary literature before the MLS
experiment is preregistered or run. Established results and MLS-specific
contracts are separated deliberately. A source result is not an MLS pass.

## Sources inspected

1. E. Love and D. L. Sulsky, “An unconditionally stable, energy–momentum
   consistent implementation of the material-point method,” *Computer Methods
   in Applied Mechanics and Engineering* 195 (2006), 3903–3925,
   [DOI 10.1016/j.cma.2005.06.027](https://doi.org/10.1016/j.cma.2005.06.027).
   Equation and printed-page references below use the authors’
   [primary report](https://www.math.unm.edu/~sulsky/papers/LoveSulskyHPC.pdf),
   dated 2004-09-09.
2. J. A. Nairn and C. C. Hammerquist, “Material point method simulations using
   an approximate full mass matrix inverse,” *Computer Methods in Applied
   Mechanics and Engineering* 377 (2021), 113667,
   [DOI 10.1016/j.cma.2021.113667](https://doi.org/10.1016/j.cma.2021.113667).
   Equations below were checked in the authors’
   [primary manuscript](https://www.cof.orst.edu/cof/wse/faculty/Nairn/papers/FMPMPaper.pdf).
3. J. A. Nairn, “Improved Implementation of Approximate Full Mass Matrix
   Inverse Methods into Material Point Method Simulations,” arXiv:2604.07307
   (version inspected: v1, 2026-04-08),
   [primary manuscript](https://arxiv.org/pdf/2604.07307).
4. The authors' public NairnMPM implementation was inspected at pinned commit
   [`554c5c67c87318e8e36f155c62cf7b879517fbec`](https://github.com/nairnj/nairn-mpm-fea/tree/554c5c67c87318e8e36f155c62cf7b879517fbec).
   In particular, the recurrence loop is in
   [`XPICExtrapolationTask.cpp`](https://github.com/nairnj/nairn-mpm-fea/blob/554c5c67c87318e8e36f155c62cf7b879517fbec/NairnMPM/src/NairnMPM_Class/XPICExtrapolationTask.cpp)
   and its nodal update storage is in
   [`MatVelocityField.cpp`](https://github.com/nairnj/nairn-mpm-fea/blob/554c5c67c87318e8e36f155c62cf7b879517fbec/NairnMPM/src/Nodes/MatVelocityField.cpp).

The inspected PDF SHA-256 values are
`6950c7708f7fdc8d3b20ebb9ddc0af37f823cf452e6a8d3e0eaeb92b73b69c83`
for the 2021 author manuscript and
`7b78482cb155779b74415a9851a20f948b0f2366bf00e60fc77cae30fea5b42a`
for arXiv:2604.07307v1. The 2026 bibliography prints the 2021 journal volume
as 337; the published volume is 377.

The Love–Sulsky paper studies an energy–momentum consistent MPM algorithm, and
the Nairn papers study FMPM inside broader MPM algorithms. MLS extracts only
the equations identified below. It does not claim to implement either full
published algorithm.

## Notation used by this lab

For particles `p` and deterministically ordered active nodes `i`, define

\[
S_{pi}=N_i(x_p),\qquad W=\operatorname{diag}(m_p),
\]

where the MLS reference uses the complete unbounded tensor-product quadratic
B-spline point-particle stencil. Particle velocity is `V`, nodal velocity is
`v`, and all three Cartesian components use the same scalar mass matrix.

The physical input state of every candidate is exactly particle center
position `x_p`, exact mass quanta `m_p`, and center velocity `V_p`. Grid state
is transient. No `B_p`, `C_p`, spin, affine reservoir, or persistent
polynomial mode is permitted.

## Love–Sulsky consistent mass

### Equations actually adopted

Love–Sulsky define constant point mass and momentum as
`m_p = rho_0(x_p) Omega^p_0 > 0` and `pi_p=m_p v_p` (printed p. 8).
Their Eq. (24), printed p. 9, is

\[
M_{ij}=\sum_p m_p N_i(x_p)N_j(x_p)=S^TWS.
\]

Eq. (25) is the row-sum lumped matrix

\[
\bar M_{ij}=\delta_{ij}\sum_p m_pN_i(x_p)
            =\delta_{ij}\sum_jM_{ij}.
\]

Eq. (26) introduces the paper’s effective matrix
`M_tilde=(1-epsilon)M+epsilon Mbar`. Eq. (27) reassembles the matrix at current
particle positions. Eq. (28), printed p. 10, solves

\[
\sum_j \widetilde M_{ij}v_j
  =\sum_pN_i(x_p)\pi_p.
\]

The requested MLS full reference fixes `epsilon=0`, hence

\[
q=S^TWV,\qquad Mv=q.
\]

The MLS lumped/PIC negative control uses `v_i=q_i/m_i` with
`m_i=sum_p m_pN_i(x_p)`, followed by direct reconstruction `V'=Sv`.

### Established conservation and energy statements

Love–Sulsky Proposition 3.2/Eq. (42), printed p. 14, proves P2G linear
momentum transfer using partition of unity. Proposition 3.3/Eq. (43), printed
p. 15, proves P2G orbital angular momentum transfer using coordinate
reproduction

\[
\sum_iN_i(x_p)x_i=x_p.
\]

Proposition 3.4 and Eqs. (44)–(49), printed pp. 15–16, give

\[
2T_p=2T_g+\epsilon v^T(\bar M-M)v+E_v,
\qquad
E_v=\sum_pm_p\lVert V_p-(Sv)_p\rVert^2\ge0.
\]

Consequently, even the full consistent P2G projection does **not** generically
conserve particle kinetic energy: at `epsilon=0`, `T_p-T_g=E_v/2`. Equality
requires the particle field to be represented by the grid basis.

The paper’s Eq. (32), printed p. 11, updates particles incrementally:

\[
x_p^{n+1}=x_p^n+\Delta\varphi^h(x_p^n),\qquad
V_p^{n+1}=V_p^n+\Delta v^h(x_p^n).
\]

Propositions 3.8, 3.10, and 3.12 establish properties of that incremental
update coupled to the paper’s grid integrator. Direct replacement `V'=Sv` is
not Eq. (32). Therefore this lab calls its path **MLS full consistent-mass
projection with PIC reconstruction**. It does not attribute the direct cycle,
or generic kinetic-energy conservation, to Love–Sulsky.

### Singularity and conditioning

Love–Sulsky Remark 3.1 states that particle quadrature can make `M` singular;
`M` is positive semidefinite rather than guaranteed positive definite. The
paper restores positive definiteness by choosing `epsilon>0`. That is a
published design choice, but it is forbidden as an implicit fallback here.
MLS records active-node ordering, dimensions, rank/condition diagnostics,
absolute and relative solve residuals, and solver termination. A singular or
ill-conditioned row fails explicitly. It is never dropped, silently lumped,
regularized, or pseudoinverted.

Algebraically, `rank(M)=rank(W^(1/2)S)<=min(P,n)`. Removing zero-support nodes
does not guarantee full rank. A small residual also does not prove accurate
recovery when the system is ill-conditioned. The source specifies no rank
tolerance, condition threshold, pivoting rule, or regularization recipe; all
such choices are MLS-specific and must be preregistered.

## Nairn–Hammerquist full and approximate inverse

### Full mass-weighted least-squares map

Section 2.1 defines grid-to-particle interpolation `V=Sv` and reverse mapping

\[
v=S^+V=\widetilde m^{-1}S^TWV,
\qquad \widetilde m=S^TWS.
\]

This is the same full matrix and right-hand side used by the MLS reference.
For nonsingular `M`, the direct round trip `S M^{-1}S^TWV` is the
mass-weighted least-squares projection onto `range(S)`.

The lumped reverse map in the paper is

\[
S^+=m^{-1}S^TW,
\qquad m=\operatorname{diag}(S^TW\mathbf 1),
\]

where `m` is row-sum lumped mass, not the diagonal of the consistent matrix.

### FMPM(k) recurrence

Section 2.2 writes

\[
\widetilde m=m(I-A),\qquad A=I-S^+S,
\]

and expands

\[
\widetilde m^{-1}
  =(I-A)^{-1}m^{-1}
  =\left(I+A+A^2+\cdots\right)m^{-1}.
\]

FMPM(k) truncates this series after the `A^(k-1)` term:

\[
v^{+(k)}=\sum_{\ell=1}^{k}A^{\ell-1}m^{-1}q.
\]

The 2021 paper’s Eq. (1), printed p. 2, gives an algebraically rearranged
binomial recurrence

\[
\widetilde m_k^{-1}q
 =\sum_{\ell=1}^k(-1)^{\ell+1}v^*_{\ell},
\]

\[
v^*_{\ell}
 =\binom{k}{\ell}(S^+S)^{\ell-1}m^{-1}q
 =\frac{k+1-\ell}{\ell}S^+S v^*_{\ell-1},
\qquad v^*_1=k m^{-1}q.
\]

The 2026 update, Eqs. (5)–(6) and Table 1, implements the same finite series
incrementally:

\[
\Delta v^{(1)}=m^{-1}q,
\qquad
\Delta v^{(\ell)}=A\Delta v^{(\ell-1)}
 =\Delta v^{(\ell-1)}-S^+S\Delta v^{(\ell-1)},
\]

\[
v^{+(k)}=\sum_{\ell=1}^{k}\Delta v^{(\ell)}.
\]

At the component level, the Table 1 multiplication is

\[
(S^+Sz)_i
 =\frac{1}{m_i}\sum_p m_pS_{pi}\sum_jS_{pj}z_j.
\]

The updated paper states that this recurrence is mathematically identical to
the 2021 one, while making each order increment explicit. MLS implements this
2026 recurrence directly and cross-checks it against an independently coded
finite-series/matrix oracle on small systems. No boundary/contact correction
from Table 1 is present because this lab is force-free and unconstrained.

The pinned public implementation contains the same recurrence within a larger
parallel MPM code, including ghost-node reduction, boundary/contact, and
optional gradient paths. Its reduction order is not the MLS deterministic
contract, and those surrounding pathways are not copied into this lab.

Order has a precise meaning: FMPM(1) is exactly the lumped/PIC map. The finite
selection `k=1,2,3,4` is therefore one negative-control identity plus three
successive approximation orders, not four independent methods.

### Particle update adopted by MLS

Nairn–Hammerquist Table 1 maps `V^(n+1)=S v+` and advances position with

\[
X^{n+1}=X^n+\frac{V^{n+1}+V^n}{2}\Delta t.
\]

The 2026 paper Eq. (7) generalizes this using an `alpha` parameter. The MLS
force-free lab fixes the published FMPM choice `alpha=1/2` for all three paths
so the projection is the only candidate-dependent operation. This is still an
MLS experimental composition, not a claim to reproduce either paper’s full
MPM algorithm.

### Stability guidance and limits of attribution

The primary papers report that useful FMPM order depends on interpolation,
time step, boundary/contact treatment, and the surrounding MPM algorithm;
higher `k` can require smaller stable time steps, and improvement may plateau.
Those experiments contain forces and constitutive updates outside this lab.
They justify inspecting a small finite order set but cannot supply MLS pass
tolerances, an MLS convergence verdict, or a production choice.

The Neumann series approaches the full inverse only when its spectral
conditions hold. For the symmetric scaled matrix

\[
H=m^{-1/2}Mm^{-1/2},
\]

the error iteration is `I-H`. MLS therefore reports an estimated spectral
radius as well as rank/condition and measures every FMPM(k) result directly
against the accurately solved full reference. Finite order is never assumed
to improve monotonically.

Two exact audit identities follow from the published recurrence. With
`r_k=q-Mv^(k)` and full solution `v_*`,

\[
r_k=D A^kD^{-1}q=D\,\Delta v^{(k+1)},
\]

and, when `M` is nonsingular,

\[
v^{(k)}=(I-A^k)v_*,\qquad v^{(k)}-v_*=-A^kv_*.
\]

These are MLS deductions, not quotations from either paper. The first is an
independent implementation check: lumped mass times the next recurrence
increment must equal the consistent-system residual.

## MLS deductions to be formalized and tested

The statements in this section are deductions from the displayed equations,
not explicit theorems quoted from the sources.

For an affine field `V_p=A x_p+b`, partition of unity and linear reproduction
give nodal samples `g_i=A x_i+b` and

\[
q_i=\sum_pm_pN_i(x_p)(Ax_p+b)
    =\sum_jM_{ij}(Ax_j+b)=(Mg)_i.
\]

With an explicit unique-solution/inverse assumption, the full solve recovers
`v=g` and `Sv=V`. This yields exact affine particle recovery and, at unchanged
positions, exact particle linear and center orbital angular momentum. It also
gives kinetic-energy equality for this represented field only.

For a general particle field, the normal equation is

\[
S^TW(V-Sv)=0.
\]

If constants and coordinate fields are in `range(S)`, this equation preserves
particle linear and orbital angular moments through direct reconstruction.
It does not preserve arbitrary particle kinetic energy. The projected field is
non-expansive in the mass norm, with equality only when the discarded
component is zero.

During a time step, these static projection identities do not by themselves
prove trajectory, angular-momentum, or energy conservation. Those are measured
separately. Numerical loss or gain is always a diagnostic residual and is
never converted to heat, stored, chemical, structural, or other physical
energy.

Finite FMPM has a narrower angular statement. For the grid rotational test
field `w_i=omega cross x_i`,

\[
\omega\mathbin{\cdot}(L_{out}-L_{in})=-w^Tr_k.
\]

Thus a solved full system preserves center orbital angular momentum, whereas
finite FMPM does so only if the rotational moment of its residual vanishes.
Neither primary source proves a generic finite-order angular invariant.

## Frozen attribution and implementation rules

- Candidate input is center `x,m,V` only; candidate output contains no
  persistent numerical mode beyond updated center state.
- Active nodes are ordered lexicographically by integer grid index before
  matrix assembly, iteration, reduction, serialization, or hashing.
- The full reference solves the unregularized consistent system. Singular,
  rank-deficient, ill-conditioned, nonconverged, or inaccurate solves are
  preserved as failed evidence.
- FMPM uses the 2026 incremental recurrence and orders 1–4. FMPM(1) must agree
  with the separately labeled lumped/PIC control to roundoff.
- Full-mass direct `V'=Sv` is called an MLS consistent projection, not the
  Love–Sulsky Eq. (32) update.
- No generic kinetic-energy conservation claim is permitted.
- Literature results do not determine the lab verdict. The preregistered MLS
  gates and independent verification do.
