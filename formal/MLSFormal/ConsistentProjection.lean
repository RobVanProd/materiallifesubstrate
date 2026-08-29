import MLSFormal.TransferLab
import Mathlib.Algebra.BigOperators.Pi
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

open scoped BigOperators

/-!
# Finite consistent particle/grid projection

This module models the full consistent-mass projection used by the Projection
Foundation Lab.  It is an exact-rational, finite model of the actual mass
matrix, right-hand side, solve equation, and interpolation operation.  The
grid solve is not made total: singular systems exist.  Affine grid recovery
takes an explicit uniqueness assumption, while the Gram/nullspace theorems
show without invertibility that all exact solutions reconstruct the same
particle-center velocities under strictly positive masses.  No particle
affine mode, force, constitutive law, time integrator, or kinetic-energy
conservation claim is present here.
-/

/-- Physical particle-center state admitted by the consistent projection. -/
structure ProjectionParticle where
  mass : ℚ
  position : Vec3
  velocity : Vec3

/-- Full consistent mass matrix `M_ij = sum_p m_p N_pi N_pj`. -/
def consistentMassMatrix
    {Particle Grid : Type*} [Fintype Particle]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (row column : Grid) : ℚ :=
  ∑ particle : Particle,
    (particles particle).mass * weight particle row * weight particle column

/-- Consistent projection right-hand side `q_i = sum_p m_p N_pi V_p`. -/
def consistentProjectionRhs
    {Particle Grid : Type*} [Fintype Particle]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (grid : Grid) : Vec3 :=
  fun component =>
    ∑ particle : Particle,
      (particles particle).mass * weight particle grid *
        (particles particle).velocity component

/-- Apply the actual full consistent matrix to a grid velocity field. -/
def consistentMassApply
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (gridVelocity : Grid → Vec3)
    (grid : Grid) : Vec3 :=
  fun component =>
    ∑ column : Grid,
      consistentMassMatrix particles weight grid column *
        gridVelocity column component

/-- Interpolate a transient grid velocity back to a particle center. -/
def consistentInterpolate
    {Particle Grid : Type*} [Fintype Grid]
    (weight : Particle → Grid → ℚ)
    (gridVelocity : Grid → Vec3)
    (particle : Particle) : Vec3 :=
  fun component =>
    ∑ grid : Grid, weight particle grid * gridVelocity grid component

/--
Apply the particle-to-grid adjoint of the interpolation map after weighting
particle vectors by their strictly physical particle masses.  In matrix
notation this is `Sᵀ W`; no inverse or solver is part of this operator.
-/
def weightedShapeTransposeApply
    {Particle Grid : Type*} [Fintype Particle]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (particleValue : Particle → Vec3)
    (grid : Grid) : Vec3 :=
  fun component =>
    ∑ particle : Particle,
      (particles particle).mass * weight particle grid *
        particleValue particle component

/--
The actual finite consistent-mass operator factors exactly as `M = Sᵀ W S`.
This is an equality of the executable finite operators above, not a premise
about an abstract matrix.
-/
theorem consistentMass_is_gram_operator
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (gridVelocity : Grid → Vec3) :
    consistentMassApply particles weight gridVelocity =
      weightedShapeTransposeApply particles weight
        (fun particle =>
          consistentInterpolate weight gridVelocity particle) := by
  funext grid component
  simp only [consistentMassApply, consistentMassMatrix,
    weightedShapeTransposeApply, consistentInterpolate]
  simp_rw [Finset.sum_mul]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro particle _
  rw [Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro column _
  ring

/-- The quadratic form induced by the finite Gram operator, componentwise. -/
private theorem consistentMass_gram_quadratic_component
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (gridVelocity : Grid → Vec3)
    (component : Fin 3) :
    (∑ grid : Grid,
        gridVelocity grid component *
          consistentMassApply particles weight gridVelocity grid component) =
      ∑ particle : Particle,
        (particles particle).mass *
          (consistentInterpolate weight gridVelocity particle component) ^ 2 := by
  rw [consistentMass_is_gram_operator]
  simp only [weightedShapeTransposeApply]
  simp_rw [Finset.mul_sum]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro particle _
  calc
    ∑ grid : Grid,
        gridVelocity grid component *
          ((particles particle).mass * weight particle grid *
            consistentInterpolate weight gridVelocity particle component) =
        ∑ grid : Grid,
          ((particles particle).mass * weight particle grid *
            gridVelocity grid component) *
              consistentInterpolate weight gridVelocity particle component := by
          apply Finset.sum_congr rfl
          intro grid _
          ring
    _ = (∑ grid : Grid,
          (particles particle).mass * weight particle grid *
            gridVelocity grid component) *
          consistentInterpolate weight gridVelocity particle component := by
            rw [Finset.sum_mul]
    _ = (particles particle).mass *
          (∑ grid : Grid,
            weight particle grid * gridVelocity grid component) *
          consistentInterpolate weight gridVelocity particle component := by
            rw [Finset.mul_sum]
    _ = (particles particle).mass *
          (consistentInterpolate weight gridVelocity particle component) ^ 2 := by
            simp only [consistentInterpolate]
            ring

/--
With strictly positive particle masses, the nullspace of the actual consistent
mass operator is exactly the nullspace of particle-center interpolation:
`ker(Sᵀ W S) = ker(S)`.  No invertibility or uniqueness premise appears.
-/
theorem consistentMass_kernel_eq_interpolation_kernel
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (positiveMass : ∀ particle, 0 < (particles particle).mass)
    (gridVelocity : Grid → Vec3) :
    consistentMassApply particles weight gridVelocity = 0 ↔
      (fun particle =>
        consistentInterpolate weight gridVelocity particle) = 0 := by
  constructor
  · intro inMassKernel
    funext particle component
    have quadraticZero :
        (∑ candidate : Particle,
          (particles candidate).mass *
            (consistentInterpolate weight gridVelocity candidate component) ^ 2) = 0 := by
      rw [← consistentMass_gram_quadratic_component particles weight
        gridVelocity component]
      simp only [inMassKernel, Pi.zero_apply, mul_zero, Finset.sum_const_zero]
    have everyWeightedSquareZero :=
      (Finset.sum_eq_zero_iff_of_nonneg
        (fun candidate _ =>
          mul_nonneg (positiveMass candidate).le
            (sq_nonneg
              (consistentInterpolate weight gridVelocity candidate component)))).mp
        quadraticZero
    have weightedSquareZero :=
      everyWeightedSquareZero particle (Finset.mem_univ particle)
    have interpolationSquareZero :
        (consistentInterpolate weight gridVelocity particle component) ^ 2 = 0 :=
      (mul_eq_zero.mp weightedSquareZero).resolve_left
        (positiveMass particle).ne'
    exact sq_eq_zero_iff.mp interpolationSquareZero
  · intro inInterpolationKernel
    rw [consistentMass_is_gram_operator]
    funext grid component
    simp only [weightedShapeTransposeApply, Pi.zero_apply]
    apply Finset.sum_eq_zero
    intro particle _
    have reconstructedZero :
        consistentInterpolate weight gridVelocity particle = 0 :=
      congrFun inInterpolationKernel particle
    rw [congrFun reconstructedZero component]
    ring

/-- The exact finite normal equation `M v = q`. -/
def IsConsistentProjectionSolution
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (gridVelocity : Grid → Vec3) : Prop :=
  consistentMassApply particles weight gridVelocity =
    consistentProjectionRhs particles weight

/--
Explicit uniqueness contract for the finite normal equation.  This is an
assumption supplied for a particular matrix, never a project axiom and never a
silent regularization of a singular matrix.
-/
def ConsistentProjectionUnique
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ) : Prop :=
  ∀ left right : Grid → Vec3,
    IsConsistentProjectionSolution particles weight left →
    IsConsistentProjectionSolution particles weight right →
    left = right

/--
Any two exact solutions of the same finite consistent normal equation have the
same particle-center reconstruction when all particle masses are strictly
positive.  Grid solutions may differ by a singular null mode; invertibility,
a pseudoinverse, and a preferred representative are deliberately absent.
-/
theorem consistentProjection_solutions_have_equal_reconstruction
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (positiveMass : ∀ particle, 0 < (particles particle).mass)
    (left right : Grid → Vec3)
    (leftSolution : IsConsistentProjectionSolution particles weight left)
    (rightSolution : IsConsistentProjectionSolution particles weight right) :
    (fun particle => consistentInterpolate weight left particle) =
      fun particle => consistentInterpolate weight right particle := by
  let difference : Grid → Vec3 := fun grid => left grid - right grid
  have differenceInMassKernel :
      consistentMassApply particles weight difference = 0 := by
    funext grid component
    have leftEquation := congrFun (congrFun leftSolution grid) component
    have rightEquation := congrFun (congrFun rightSolution grid) component
    simp only [consistentMassApply, difference, Pi.zero_apply]
    simp_rw [Pi.sub_apply, mul_sub]
    rw [Finset.sum_sub_distrib, leftEquation, rightEquation, sub_self]
  have differenceInInterpolationKernel :=
    (consistentMass_kernel_eq_interpolation_kernel particles weight
      positiveMass difference).mp differenceInMassKernel
  funext particle component
  have reconstructedDifferenceZero :=
    congrFun (congrFun differenceInInterpolationKernel particle) component
  simp only [consistentInterpolate, difference, Pi.sub_apply, mul_sub,
    Finset.sum_sub_distrib, Pi.zero_apply] at reconstructedDifferenceZero
  exact sub_eq_zero.mp reconstructedDifferenceZero

/-- Explicit finite basis properties used by the projection proofs. -/
structure ConsistentBasisAssumptions
    {Particle Grid : Type*} [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ) : Prop where
  partitionUnity : ∀ particle,
    ∑ grid : Grid, weight particle grid = 1
  linearReproduction : ∀ particle axis,
    ∑ grid : Grid,
      weight particle grid * gridPosition grid axis =
        (particles particle).position axis

/-- Particle centers sample one globally affine velocity field. -/
def ParticleVelocitiesAreAffine
    {Particle : Type*}
    (particles : Particle → ProjectionParticle)
    (offset : Vec3) (gradient : Mat3) : Prop :=
  ∀ particle,
    (particles particle).velocity =
      affineVelocityField offset gradient (particles particle).position

/-- Total center-particle momentum before projection. -/
def projectionParticleMomentum
    {Particle : Type*} [Fintype Particle]
    (particles : Particle → ProjectionParticle) : Vec3 :=
  fun component =>
    ∑ particle : Particle,
      (particles particle).mass * (particles particle).velocity component

/-- Total center-particle momentum after grid reconstruction. -/
def reconstructedParticleMomentum
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (gridVelocity : Grid → Vec3) : Vec3 :=
  fun component =>
    ∑ particle : Particle,
      (particles particle).mass *
        consistentInterpolate weight gridVelocity particle component

/-- Total orbital angular momentum of the particle centers before projection. -/
def projectionParticleAngularMomentum
    {Particle : Type*} [Fintype Particle]
    (particles : Particle → ProjectionParticle) : Vec3 :=
  fun component =>
    ∑ particle : Particle,
      cross (particles particle).position
        (vscale (particles particle).mass (particles particle).velocity) component

/-- Orbital angular momentum after reconstructing center velocities. -/
def reconstructedParticleAngularMomentum
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (gridVelocity : Grid → Vec3) : Vec3 :=
  fun component =>
    ∑ particle : Particle,
      cross (particles particle).position
        (vscale (particles particle).mass
          (consistentInterpolate weight gridVelocity particle)) component

private theorem affine_interpolation_exact
    {Particle Grid : Type*} [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (basis : ConsistentBasisAssumptions particles gridPosition weight)
    (offset : Vec3) (gradient : Mat3) (particle : Particle) :
    consistentInterpolate weight
        (affineVelocityField offset gradient ∘ gridPosition) particle =
      affineVelocityField offset gradient (particles particle).position := by
  funext component
  simp only [consistentInterpolate, Function.comp_apply, affineVelocityField,
    Pi.add_apply, matVec]
  simp_rw [mul_add, Finset.sum_add_distrib, Finset.mul_sum]
  rw [Finset.sum_comm]
  calc
    (∑ grid : Grid, weight particle grid * offset component) +
          ∑ column : Fin 3,
            ∑ grid : Grid,
              weight particle grid *
                (gradient component column * gridPosition grid column) =
        offset component +
          ∑ column : Fin 3,
            gradient component column * (particles particle).position column := by
      congr 1
      · rw [← Finset.sum_mul, basis.partitionUnity]
        ring
      · apply Finset.sum_congr rfl
        intro column _
        calc
          ∑ grid : Grid,
              weight particle grid *
                (gradient component column * gridPosition grid column) =
              gradient component column *
                (∑ grid : Grid,
                  weight particle grid * gridPosition grid column) := by
                rw [Finset.mul_sum]
                apply Finset.sum_congr rfl
                intro grid _
                ring
          _ = gradient component column *
              (particles particle).position column := by
                rw [basis.linearReproduction]
    _ = _ := rfl

/-!
The following finite-sum identities connect the normal equation to arbitrary
grid test functions.  Constants yield linear momentum; coordinate functions
yield the mixed position--momentum moments needed for orbital angular momentum.
-/

private theorem exact_solution_test_identity
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (gridVelocity : Grid → Vec3)
    (solution : IsConsistentProjectionSolution particles weight gridVelocity)
    (test : Grid → ℚ) (component : Fin 3) :
    (∑ grid : Grid,
        test grid * consistentProjectionRhs particles weight grid component) =
      ∑ particle : Particle,
        (particles particle).mass *
          (∑ grid : Grid, weight particle grid * test grid) *
          consistentInterpolate weight gridVelocity particle component := by
  have massApplyAsParticleSum : ∀ grid,
      consistentMassApply particles weight gridVelocity grid component =
        ∑ particle : Particle,
          (particles particle).mass * weight particle grid *
            consistentInterpolate weight gridVelocity particle component := by
    intro grid
    simp only [consistentMassApply, consistentMassMatrix,
      consistentInterpolate]
    simp_rw [Finset.sum_mul]
    rw [Finset.sum_comm]
    apply Finset.sum_congr rfl
    intro particle _
    rw [Finset.mul_sum]
    apply Finset.sum_congr rfl
    intro column _
    ring
  have normalAt : ∀ grid,
      consistentProjectionRhs particles weight grid component =
        ∑ particle : Particle,
          (particles particle).mass * weight particle grid *
            consistentInterpolate weight gridVelocity particle component := by
    intro grid
    rw [← massApplyAsParticleSum grid]
    exact (congrFun (congrFun solution grid) component).symm
  simp_rw [normalAt, Finset.mul_sum]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro particle _
  rw [Finset.sum_mul]
  apply Finset.sum_congr rfl
  intro grid _
  ring

private theorem rhs_test_identity
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (test : Grid → ℚ) (component : Fin 3) :
    (∑ grid : Grid,
        test grid * consistentProjectionRhs particles weight grid component) =
      ∑ particle : Particle,
        (particles particle).mass *
          (∑ grid : Grid, weight particle grid * test grid) *
          (particles particle).velocity component := by
  simp only [consistentProjectionRhs]
  simp_rw [Finset.mul_sum]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro particle _
  rw [Finset.sum_mul]
  apply Finset.sum_congr rfl
  intro grid _
  ring

/--
For affine particle data, the actual consistent right-hand side equals the
actual full mass matrix applied to the affine grid field: `q = M g`.
-/
theorem consistentProjection_affine_rhs_relation
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (basis : ConsistentBasisAssumptions particles gridPosition weight)
    (offset : Vec3) (gradient : Mat3)
    (affineParticles : ParticleVelocitiesAreAffine particles offset gradient) :
    consistentProjectionRhs particles weight =
      consistentMassApply particles weight
        (affineVelocityField offset gradient ∘ gridPosition) := by
  funext grid component
  have massApplyAsParticleSum :
      consistentMassApply particles weight
          (affineVelocityField offset gradient ∘ gridPosition) grid component =
        ∑ particle : Particle,
          (particles particle).mass * weight particle grid *
            consistentInterpolate weight
              (affineVelocityField offset gradient ∘ gridPosition)
              particle component := by
    simp only [consistentMassApply, consistentMassMatrix,
      consistentInterpolate]
    simp_rw [Finset.sum_mul]
    rw [Finset.sum_comm]
    apply Finset.sum_congr rfl
    intro particle _
    rw [Finset.mul_sum]
    apply Finset.sum_congr rfl
    intro column _
    ring
  rw [massApplyAsParticleSum]
  simp only [consistentProjectionRhs]
  apply Finset.sum_congr rfl
  intro particle _
  have interpolated := affine_interpolation_exact particles gridPosition weight
    basis offset gradient particle
  have velocityEquality := affineParticles particle
  have componentEquality := congrFun (velocityEquality.trans interpolated.symm) component
  rw [componentEquality]

/--
If the finite normal equation has a unique solution, every exact solve recovers
the represented affine grid field.  Uniqueness is an explicit premise because
particle quadrature can make the consistent matrix singular.
-/
theorem consistentProjection_unique_grid_recovery
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (basis : ConsistentBasisAssumptions particles gridPosition weight)
    (offset : Vec3) (gradient : Mat3)
    (affineParticles : ParticleVelocitiesAreAffine particles offset gradient)
    (unique : ConsistentProjectionUnique particles weight)
    (gridVelocity : Grid → Vec3)
    (solution : IsConsistentProjectionSolution particles weight gridVelocity) :
    gridVelocity = affineVelocityField offset gradient ∘ gridPosition := by
  apply unique gridVelocity
      (affineVelocityField offset gradient ∘ gridPosition) solution
  exact (consistentProjection_affine_rhs_relation particles gridPosition weight
    basis offset gradient affineParticles).symm

/--
Under the same explicit uniqueness and basis assumptions, full consistent
projection followed by interpolation recovers every affine particle velocity.
-/
theorem consistentProjection_affine_particle_recovery
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (basis : ConsistentBasisAssumptions particles gridPosition weight)
    (offset : Vec3) (gradient : Mat3)
    (affineParticles : ParticleVelocitiesAreAffine particles offset gradient)
    (unique : ConsistentProjectionUnique particles weight)
    (gridVelocity : Grid → Vec3)
    (solution : IsConsistentProjectionSolution particles weight gridVelocity)
    (particle : Particle) :
    consistentInterpolate weight gridVelocity particle =
      (particles particle).velocity := by
  rw [consistentProjection_unique_grid_recovery particles gridPosition weight
    basis offset gradient affineParticles unique gridVelocity solution]
  rw [affine_interpolation_exact particles gridPosition weight basis]
  exact (affineParticles particle).symm

/--
Every exact solution of the actual normal equation preserves total center
linear momentum after interpolation, using partition of unity only.
-/
theorem consistentProjection_preserves_linear_momentum
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (partitionUnity : ∀ particle,
      ∑ grid : Grid, weight particle grid = 1)
    (gridVelocity : Grid → Vec3)
    (solution : IsConsistentProjectionSolution particles weight gridVelocity) :
    reconstructedParticleMomentum particles weight gridVelocity =
      projectionParticleMomentum particles := by
  funext component
  have normalTest := exact_solution_test_identity particles weight gridVelocity
    solution (fun _ => (1 : ℚ)) component
  have rhsTest := rhs_test_identity particles weight (fun _ => (1 : ℚ)) component
  simp only [one_mul, mul_one] at normalTest rhsTest
  simp only [reconstructedParticleMomentum, projectionParticleMomentum]
  calc
    ∑ particle : Particle,
        (particles particle).mass *
          consistentInterpolate weight gridVelocity particle component =
        ∑ particle : Particle,
          (particles particle).mass *
            (∑ grid : Grid, weight particle grid) *
            consistentInterpolate weight gridVelocity particle component := by
      apply Finset.sum_congr rfl
      intro particle _
      rw [partitionUnity particle]
      ring
    _ = ∑ grid : Grid,
          consistentProjectionRhs particles weight grid component := by
      exact normalTest.symm
    _ = ∑ particle : Particle,
          (particles particle).mass *
            (∑ grid : Grid, weight particle grid) *
            (particles particle).velocity component := by
      exact rhsTest
    _ = ∑ particle : Particle,
          (particles particle).mass *
            (particles particle).velocity component := by
      apply Finset.sum_congr rfl
      intro particle _
      rw [partitionUnity particle]
      ring

private theorem consistentProjection_preserves_mixed_moment
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (linearReproduction : ∀ particle axis,
      ∑ grid : Grid,
        weight particle grid * gridPosition grid axis =
          (particles particle).position axis)
    (gridVelocity : Grid → Vec3)
    (solution : IsConsistentProjectionSolution particles weight gridVelocity)
    (positionAxis velocityAxis : Fin 3) :
    (∑ particle : Particle,
        (particles particle).mass * (particles particle).position positionAxis *
          consistentInterpolate weight gridVelocity particle velocityAxis) =
      ∑ particle : Particle,
        (particles particle).mass * (particles particle).position positionAxis *
          (particles particle).velocity velocityAxis := by
  have normalTest := exact_solution_test_identity particles weight gridVelocity
    solution (fun grid => gridPosition grid positionAxis) velocityAxis
  have rhsTest := rhs_test_identity particles weight
    (fun grid => gridPosition grid positionAxis) velocityAxis
  calc
    ∑ particle : Particle,
        (particles particle).mass * (particles particle).position positionAxis *
          consistentInterpolate weight gridVelocity particle velocityAxis =
        ∑ particle : Particle,
          (particles particle).mass *
            (∑ grid : Grid,
              weight particle grid * gridPosition grid positionAxis) *
            consistentInterpolate weight gridVelocity particle velocityAxis := by
      apply Finset.sum_congr rfl
      intro particle _
      rw [linearReproduction particle positionAxis]
    _ = ∑ grid : Grid,
          gridPosition grid positionAxis *
            consistentProjectionRhs particles weight grid velocityAxis := by
      exact normalTest.symm
    _ = ∑ particle : Particle,
          (particles particle).mass *
            (∑ grid : Grid,
              weight particle grid * gridPosition grid positionAxis) *
            (particles particle).velocity velocityAxis := by
      exact rhsTest
    _ = ∑ particle : Particle,
        (particles particle).mass * (particles particle).position positionAxis *
          (particles particle).velocity velocityAxis := by
      apply Finset.sum_congr rfl
      intro particle _
      rw [linearReproduction particle positionAxis]

/--
Every exact normal-equation solution preserves three-dimensional orbital
angular momentum of point-particle centers at fixed positions when the basis
reproduces all three coordinate functions.  This theorem introduces no hidden
spin or affine angular reservoir.
-/
theorem consistentProjection_preserves_orbital_angular_momentum
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (linearReproduction : ∀ particle axis,
      ∑ grid : Grid,
        weight particle grid * gridPosition grid axis =
          (particles particle).position axis)
    (gridVelocity : Grid → Vec3)
    (solution : IsConsistentProjectionSolution particles weight gridVelocity) :
    reconstructedParticleAngularMomentum particles weight gridVelocity =
      projectionParticleAngularMomentum particles := by
  funext component
  fin_cases component
  · simp [reconstructedParticleAngularMomentum,
      projectionParticleAngularMomentum, cross, vscale]
    ring_nf
    have first := consistentProjection_preserves_mixed_moment
      particles gridPosition weight linearReproduction gridVelocity solution 1 2
    have second := consistentProjection_preserves_mixed_moment
      particles gridPosition weight linearReproduction gridVelocity solution 2 1
    have firstReordered :
        (∑ particle : Particle,
          (particles particle).position 1 * (particles particle).mass *
            consistentInterpolate weight gridVelocity particle 2) =
        ∑ particle : Particle,
          (particles particle).position 1 * (particles particle).mass *
            (particles particle).velocity 2 := by
      simpa only [mul_assoc, mul_left_comm, mul_comm] using first
    have secondReordered :
        (∑ particle : Particle,
          (particles particle).position 2 * (particles particle).mass *
            consistentInterpolate weight gridVelocity particle 1) =
        ∑ particle : Particle,
          (particles particle).position 2 * (particles particle).mass *
            (particles particle).velocity 1 := by
      simpa only [mul_assoc, mul_left_comm, mul_comm] using second
    rw [firstReordered, secondReordered]
  · simp [reconstructedParticleAngularMomentum,
      projectionParticleAngularMomentum, cross, vscale]
    ring_nf
    have first := consistentProjection_preserves_mixed_moment
      particles gridPosition weight linearReproduction gridVelocity solution 2 0
    have second := consistentProjection_preserves_mixed_moment
      particles gridPosition weight linearReproduction gridVelocity solution 0 2
    have firstReordered :
        (∑ particle : Particle,
          (particles particle).position 2 * (particles particle).mass *
            consistentInterpolate weight gridVelocity particle 0) =
        ∑ particle : Particle,
          (particles particle).position 2 * (particles particle).mass *
            (particles particle).velocity 0 := by
      simpa only [mul_assoc, mul_left_comm, mul_comm] using first
    have secondReordered :
        (∑ particle : Particle,
          (particles particle).position 0 * (particles particle).mass *
            consistentInterpolate weight gridVelocity particle 2) =
        ∑ particle : Particle,
          (particles particle).position 0 * (particles particle).mass *
            (particles particle).velocity 2 := by
      simpa only [mul_assoc, mul_left_comm, mul_comm] using second
    rw [firstReordered, secondReordered]
  · simp [reconstructedParticleAngularMomentum,
      projectionParticleAngularMomentum, cross, vscale]
    ring_nf
    have first := consistentProjection_preserves_mixed_moment
      particles gridPosition weight linearReproduction gridVelocity solution 0 1
    have second := consistentProjection_preserves_mixed_moment
      particles gridPosition weight linearReproduction gridVelocity solution 1 0
    have firstReordered :
        (∑ particle : Particle,
          (particles particle).position 0 * (particles particle).mass *
            consistentInterpolate weight gridVelocity particle 1) =
        ∑ particle : Particle,
          (particles particle).position 0 * (particles particle).mass *
            (particles particle).velocity 1 := by
      simpa only [mul_assoc, mul_left_comm, mul_comm] using first
    have secondReordered :
        (∑ particle : Particle,
          (particles particle).position 1 * (particles particle).mass *
            consistentInterpolate weight gridVelocity particle 0) =
        ∑ particle : Particle,
          (particles particle).position 1 * (particles particle).mass *
            (particles particle).velocity 0 := by
      simpa only [mul_assoc, mul_left_comm, mul_comm] using second
    rw [firstReordered, secondReordered]

end MLSFormal
