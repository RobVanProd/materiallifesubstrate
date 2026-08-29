import MLSFormal.ConsistentProjection
import Mathlib.Algebra.Order.BigOperators.Ring.Finset

set_option autoImplicit false

namespace MLSFormal

open scoped BigOperators

/-!
# Consistent-projection Gram and nullspace contracts

This module isolates the singular-system reasoning required by the Projection
Exactness + Nullspace Lab from the larger affine-projection module.  It proves
properties of the actual finite MLS operators over exact rationals.  Strictly
positive particle masses are explicit where positivity is needed; no inverse,
pseudoinverse, regularization, or preferred grid representative is introduced.
-/

/--
Apply the particle-to-grid adjoint of interpolation after weighting particle
vectors by particle mass.  In matrix notation this is `Sᵀ W`; no solver is
part of this operator.
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
This is an equality of executable finite operators, not a Gram identity taken
as a premise.
-/
theorem consistentMass_is_gram_operator
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → ProjectionParticle)
    (weight : Particle → Grid → ℚ)
    (gridVelocity : Grid → Vec3) :
    consistentMassApply particles weight gridVelocity =
      weightedShapeTransposeApply particles weight
        (fun particle => consistentInterpolate weight gridVelocity particle) := by
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
  ac_rfl

/-- The componentwise quadratic identity induced by the finite Gram operator. -/
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
          ac_rfl
    _ = (∑ grid : Grid,
          (particles particle).mass * weight particle grid *
            gridVelocity grid component) *
          consistentInterpolate weight gridVelocity particle component := by
            rw [Finset.sum_mul]
    _ = (∑ grid : Grid,
          (particles particle).mass *
            (weight particle grid * gridVelocity grid component)) *
          consistentInterpolate weight gridVelocity particle component := by
            congr 1
            apply Finset.sum_congr rfl
            intro grid _
            ac_rfl
    _ = (particles particle).mass *
          (∑ grid : Grid,
            weight particle grid * gridVelocity grid component) *
          consistentInterpolate weight gridVelocity particle component := by
            rw [Finset.mul_sum]
    _ = (particles particle).mass *
          (consistentInterpolate weight gridVelocity particle component) ^ 2 := by
            simp only [consistentInterpolate, pow_two]
            ac_rfl

/-- A finite positive weighted sum of rational squares vanishes exactly pointwise. -/
private theorem positive_weighted_sum_sq_eq_zero_iff
    {Index : Type*} [Fintype Index]
    (scale value : Index → ℚ)
    (positiveScale : ∀ index, 0 < scale index) :
    (∑ index : Index, scale index * (value index) ^ 2) = 0 ↔ value = 0 := by
  constructor
  · intro sumZero
    funext index
    have everyTermZero :=
      (Finset.sum_eq_zero_iff_of_nonneg
        (fun candidate _ =>
          mul_nonneg (positiveScale candidate).le
            (sq_nonneg (value candidate)))).mp sumZero
    have termZero := everyTermZero index (Finset.mem_univ index)
    have squareZero : (value index) ^ 2 = 0 :=
      (mul_eq_zero.mp termZero).resolve_left (positiveScale index).ne'
    exact sq_eq_zero_iff.mp squareZero
  · intro valueZero
    simp only [valueZero, Pi.zero_apply, ne_eq, OfNat.ofNat_ne_zero,
      not_false_eq_true, zero_pow, mul_zero, Finset.sum_const_zero]

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
      (fun particle => consistentInterpolate weight gridVelocity particle) = 0 := by
  constructor
  · intro inMassKernel
    funext particle component
    let reconstruction : Particle → ℚ := fun candidate =>
      consistentInterpolate weight gridVelocity candidate component
    have weightedSquaresZero :
        (∑ candidate : Particle,
          (particles candidate).mass * (reconstruction candidate) ^ 2) = 0 := by
      rw [← consistentMass_gram_quadratic_component particles weight
        gridVelocity component]
      simp only [inMassKernel, Pi.zero_apply, mul_zero, Finset.sum_const_zero]
    have reconstructionZero :=
      (positive_weighted_sum_sq_eq_zero_iff
        (fun candidate => (particles candidate).mass)
        reconstruction positiveMass).mp weightedSquaresZero
    exact congrFun reconstructionZero particle
  · intro inInterpolationKernel
    rw [consistentMass_is_gram_operator]
    funext grid component
    simp only [weightedShapeTransposeApply, Pi.zero_apply]
    apply Finset.sum_eq_zero
    intro particle _
    have reconstructedZero :
        consistentInterpolate weight gridVelocity particle = 0 :=
      congrFun inInterpolationKernel particle
    simp only [congrFun reconstructedZero component, Pi.zero_apply, mul_zero]

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
    have leftEquationExpanded :
        (∑ column : Grid,
          consistentMassMatrix particles weight grid column *
            left column component) =
          consistentProjectionRhs particles weight grid component := by
      simpa only [consistentMassApply] using leftEquation
    have rightEquationExpanded :
        (∑ column : Grid,
          consistentMassMatrix particles weight grid column *
            right column component) =
          consistentProjectionRhs particles weight grid component := by
      simpa only [consistentMassApply] using rightEquation
    simp only [consistentMassApply, difference, Pi.zero_apply]
    simp_rw [Pi.sub_apply, mul_sub]
    rw [Finset.sum_sub_distrib, leftEquationExpanded, rightEquationExpanded,
      sub_self]
  have differenceInInterpolationKernel :=
    (consistentMass_kernel_eq_interpolation_kernel particles weight
      positiveMass difference).mp differenceInMassKernel
  funext particle component
  have reconstructedDifferenceZero :=
    congrFun (congrFun differenceInInterpolationKernel particle) component
  simp only [consistentInterpolate, difference, Pi.sub_apply, mul_sub,
    Finset.sum_sub_distrib, Pi.zero_apply] at reconstructedDifferenceZero
  exact sub_eq_zero.mp reconstructedDifferenceZero

end MLSFormal
