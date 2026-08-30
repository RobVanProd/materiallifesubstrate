# Constitutive Expressivity Lab result

## Bounded decision

`retain_local_collective_relational_energy_for_research`

This is a representation-and-energy result only. It is **NO PROMOTION** to a
mechanics implementation or to dynamics. The lab adds no motion integration,
runtime force application, stress update, contact, damage, fracture, gravity,
chemistry, organism, renderer, or GPU path.

Within the preregistered finite controls, the retained central-distance
relations contain enough observable information for a positive, objective,
strictly local collective quadratic energy to distinguish volumetric and
deviatoric response without persistent affine, strain, tensor, or history
state. Every collective quantity is derived afresh from reference/current
packet positions and the explicit relation graph.

## Result summary

The pair-separable negative control used

```text
E_pair = (1/2) sum_a h_a e_a^2.
```

Both algebraically distinct preregistered symmetric cubatures reproduced the
expected three-dimensional isotropic Cauchy restriction: `lambda=G`,
`K/G=5/3`, and `nu=1/4`. The control therefore did not escape the registered
prior-art limitation.

The selectable incident-star evaluator used

```text
m_i = sum_j w_ij l_ij^2
q_i = sum_j w_ij l_ij e_ij
d_i = q_i/m_i

E_i = (A_i/2) q_i^2/m_i
    + (B_i/2) sum_j w_ij (e_ij-d_i l_ij)^2.
```

On each of two algebraically distinct symmetric controls it realized all four
registered positive ratios `K/G in {1/3, 1, 2, 10}`. The six Kelvin strain
directions and mixed affine strains separately checked volumetric response,
deviatoric response, cross coupling, tangent symmetry, and positive energy.

The bounded graph inventory contained K4, the octahedron, regular and BCC-like
bulk, jittered bulk, a free surface, a relation-deletion case, and deliberately
floppy K4-minus-edge. Across one pair row and four collective rows per graph:

- all 40 graph rows passed the registered positivity, locality, rank, and
  kernel gates;
- each graph that previously had only the rigid kernel retained only that
  kernel after the constitutive factor was applied;
- K4-minus-edge retained its one non-rigid floppy mode, so the energy did not
  fabricate missing geometric information;
- all off-diagonal collective couplings joined incident relations only, with
  graph-hop radius one and no nonlocal entries;
- no dense/global constitutive matrix was instantiated as evidence.

Finite actual-length energy passed common-frame covariance, current-only
translation/proper-rotation objectivity, uniform-scale dimension law,
packet-ID bijections, packet/relation permutations, and relation-endpoint
reversal. Stable IDs do not create orientation or chirality.

The deterministic full producer emitted 10 bulk rows, 40 graph rows, 2,140
basis-coordinate rows with complete packet coverage per exported vector, 240
metamorphic rows, and eight checkpoint rows, with zero registered failures.
Twin full runs were required to be byte-identical. The independent validator
reconstructs the finite operators from exported coordinates and topology
rather than accepting producer summary fields as premises. Its full registered
inventory performs 29,818 validator checks/assertions, including 25 direct
90-digit `L R` spectra: all five energy rows for each small exact graph and both
collective-coefficient extremes for every selected larger graph.

## Formal boundary

The finite Lean model defines `e=Ru`, `E=(1/2)e^THe`, and `K=R^THR`. It proves:

- every relation-kernel displacement, including every rigid displacement
  already hidden by `R`, is in `ker K`;
- if the quadratic form of `H` is strictly positive on every nonzero element
  of `im R`, then `ker K = ker R` without assuming either operator invertible;
- consequently, an observable `R` paired with that positivity condition has
  only the declared rigid zero modes;
- symmetry of `K` when `H` is symmetric, equal energy when objective extension
  coordinates are equal, and the conditional registered `s^2` extension-scale
  law.

These theorems establish finite algebraic contracts. They do not prove a
continuum limit, a material calibration, physical dynamics, numerical time
integration, or useful fracture/contact behavior.

Five pre-seal checkpoints remain public and immutable rather than being
discarded. Commit `11e6393` failed during the first proof integration; commit
`a8aea10` failed because matrix reassociation was followed by a rewrite in the
wrong direction; commit `e09dd99` used a nonexistent namespaced dot-product
theorem and still preceded the hardened evidence inventory; and commit
`acaeabf` compiled Lean and passed the exact oracle but exposed the stale
manifest inventory on all C++ jobs plus a Windows path-resolution defect in
the seal regression. Commit `9610083` passed the complete public CI matrix but
the final local seal audit correctly rejected a mismatch between the
producer's explicit `NO_PROMOTION` token and the sealer's spaced marker; it was
not relabeled as final evidence. Their tags are
`constitutive-expressivity-formal-failed-11e6393`,
`constitutive-expressivity-formal-failed-a8aea10`,
`constitutive-expressivity-formal-failed-e09dd99`, and
`constitutive-expressivity-ci-failed-acaeabf`, plus
`constitutive-expressivity-preseal-failed-9610083`. None of these checkpoints
is admissible evidence for the bounded decision.

## Interpretation and limitations

The result answers the lab's narrow question positively: collective local
functions of explicit distance-relation extensions can independently control
bulk-like and shear-like energy channels without adding hidden kinematic
state. Collective distance response is established ordinary/state-based
peridynamic prior art; the MLS-specific part is the retained explicit relation
graph and the declared finite incident-star weighting/calibration rule.

The tested finite graphs, unit weights, and two exact cubatures are not a
continuum-convergence study. Free surfaces and missing relations are not
silently renormalized to restore bulk stiffness. No force law was installed,
no equations of motion were integrated, and no claim of a viable material or
mechanics solver follows from a green energy-only test.

The evidence publication procedure requires the final sealed archive and public
CI run to identify the exact source commit, toolchain, commands, receipts,
formal axiom report, independent validation, and preserved failed pre-seal runs
used for external review.
