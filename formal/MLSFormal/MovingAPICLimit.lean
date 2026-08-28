import MLSFormal.AffineAdvection
import MLSFormal.TransferLab
import Mathlib.Tactic.Module
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

open scoped BigOperators

/-!
Exact finite-stencil diagnosis of the force-free globally affine limit of the
moving particle/grid APIC update in Jiang--Schroeder--Teran (JCP 338, 2017),
especially their Eq. 38. This file models only transfer/advection algebra. It
does not model forces, stress, or constitutive mechanics.
-/

/-- Outer product `left rightᵀ`. -/
def outer3 (left right : Vec3) : Mat3 :=
  fun row column => left row * right column

/-- Three-dimensional matrix product. -/
def matMul3 (left right : Mat3) : Mat3 :=
  fun row column => ∑ axis : Fin 3, left row axis * right axis column

/-- Three-dimensional identity matrix. -/
def matIdentity3 : Mat3 :=
  fun row column => if row = column then 1 else 0

/-- Convert the concrete `Mat3` representation to a rational endomorphism. -/
def mat3End (matrix : Mat3) : Module.End ℚ Vec3 where
  toFun := matVec matrix
  map_add' left right := by
    funext row
    simp [matVec, mul_add, Finset.sum_add_distrib]
  map_smul' scale vector := by
    funext row
    change (∑ column : Fin 3,
      matrix row column * (scale * vector column)) =
      scale * (∑ column : Fin 3, matrix row column * vector column)
    rw [Finset.mul_sum]
    apply Finset.sum_congr rfl
    intro column _
    ring

/-- Old particle-to-grid displacement `x_i^n - x_p^n`. -/
def movingAPICOldOffset
    {Grid : Type*} (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (grid : Grid) : Vec3 :=
  oldGridPosition grid - oldParticlePosition

/-- Globally affine old-grid velocity `v_i = A x_i^n + b`. -/
def movingAPICOldGridVelocity
    {Grid : Type*} (oldGridPosition : Grid → Vec3)
    (gradient : Mat3) (offset : Vec3) (grid : Grid) : Vec3 :=
  affineVelocityField offset gradient (oldGridPosition grid)

/-- Force-free conceptual new grid position `x̃_i^{n+1} = x_i^n + dt v_i`. -/
def movingAPICNewGridPosition
    {Grid : Type*} (dt : ℚ) (oldGridPosition : Grid → Vec3)
    (gradient : Mat3) (offset : Vec3) (grid : Grid) : Vec3 :=
  oldGridPosition grid +
    vscale dt (movingAPICOldGridVelocity oldGridPosition gradient offset grid)

/-- JST Eq. 37 particle velocity interpolation with old weights. -/
def movingAPICNextParticleVelocity
    {Grid : Type*} [Fintype Grid]
    (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (gradient : Mat3) (offset : Vec3) : Vec3 :=
  fun component =>
    ∑ grid : Grid,
      weight grid *
        movingAPICOldGridVelocity oldGridPosition gradient offset grid component

/-- JST Eq. 39 particle position interpolation from conceptual new nodes. -/
def movingAPICNextParticlePosition
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (gradient : Mat3) (offset : Vec3) : Vec3 :=
  fun component =>
    ∑ grid : Grid,
      weight grid *
        movingAPICNewGridPosition dt oldGridPosition gradient offset grid component

/-- New Eq. 38 displacement `x̃_i^{n+1} - x_p^{n+1}`. -/
def movingAPICNewOffset
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (_oldParticlePosition : Vec3) (gradient : Mat3) (offset : Vec3)
    (grid : Grid) : Vec3 :=
  movingAPICNewGridPosition dt oldGridPosition gradient offset grid -
    movingAPICNextParticlePosition dt weight oldGridPosition gradient offset

/-- Explicit old second moment `D_old = Σ_i w_i r_i r_iᵀ`. -/
def movingAPICOldSecondMoment
    {Grid : Type*} [Fintype Grid]
    (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) : Mat3 :=
  fun row column =>
    ∑ grid : Grid,
      weight grid *
        movingAPICOldOffset oldGridPosition oldParticlePosition grid row *
        movingAPICOldOffset oldGridPosition oldParticlePosition grid column

/--
The full JST Eq. 38 update, including both old and new particle/grid offsets
and both orderings of the velocity/displacement outer products.
-/
def movingAPICEq38BNext
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (gradient : Mat3) (offset : Vec3) : Mat3 :=
  fun row column =>
    (1 / 2 : ℚ) * ∑ grid : Grid,
      weight grid *
        (movingAPICOldGridVelocity oldGridPosition gradient offset grid row *
            (movingAPICOldOffset oldGridPosition oldParticlePosition grid column +
              movingAPICNewOffset dt weight oldGridPosition oldParticlePosition
                gradient offset grid column) +
          (movingAPICOldOffset oldGridPosition oldParticlePosition grid row -
              movingAPICNewOffset dt weight oldGridPosition oldParticlePosition
                gradient offset grid row) *
            movingAPICOldGridVelocity oldGridPosition gradient offset grid column)

/-- Eq. 38 after naming `v_p`, old offsets `r_i`, and affine increments `q_i`. -/
def movingAPICEq38AffineForm
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (particleVelocity : Vec3)
    (oldDisplacement affineDisplacement : Grid → Vec3) : Mat3 :=
  fun row column =>
    (1 / 2 : ℚ) * ∑ grid : Grid,
      weight grid *
        ((particleVelocity row + affineDisplacement grid row) *
            (oldDisplacement grid column +
              (oldDisplacement grid column +
                dt * affineDisplacement grid column)) +
          (oldDisplacement grid row -
              (oldDisplacement grid row + dt * affineDisplacement grid row)) *
            (particleVelocity column + affineDisplacement grid column))

/--
Finite-support assumptions used by the derivation. No positivity, symmetry, or
result about `B_next` is assumed.
-/
structure MovingAPICAffineStencilAssumptions
    {Grid : Type*} [Fintype Grid]
    (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment : Mat3) : Prop where
  partitionUnity : ∑ grid : Grid, weight grid = 1
  zeroFirstMoment :
    (∑ grid : Grid,
      vscale (weight grid)
        (movingAPICOldOffset oldGridPosition oldParticlePosition grid)) = 0
  secondMoment :
    movingAPICOldSecondMoment weight oldGridPosition oldParticlePosition =
      oldSecondMoment

private theorem matVec_add3 (matrix : Mat3) (left right : Vec3) :
    matVec matrix (left + right) = matVec matrix left + matVec matrix right := by
  funext row
  simp [matVec, mul_add, Finset.sum_add_distrib]

private theorem oldPosition_plus_offset
    {Grid : Type*} (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (grid : Grid) :
    oldParticlePosition +
        movingAPICOldOffset oldGridPosition oldParticlePosition grid =
      oldGridPosition grid := by
  funext component
  simp [movingAPICOldOffset]

private theorem movingAPICOldGridVelocity_decomposition
    {Grid : Type*} (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (gradient : Mat3) (offset : Vec3)
    (grid : Grid) :
    movingAPICOldGridVelocity oldGridPosition gradient offset grid =
      affineVelocityField offset gradient oldParticlePosition +
        matVec gradient
          (movingAPICOldOffset oldGridPosition oldParticlePosition grid) := by
  simp only [movingAPICOldGridVelocity]
  rw [← oldPosition_plus_offset oldGridPosition oldParticlePosition grid]
  simp only [affineVelocityField, matVec_add3]
  funext component
  simp
  ring

private theorem weightedOldOffset_component_zero
    {Grid : Type*} [Fintype Grid]
    (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment : Mat3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment)
    (component : Fin 3) :
    (∑ grid : Grid,
      weight grid *
        movingAPICOldOffset oldGridPosition oldParticlePosition grid component) = 0 := by
  have componentEquality := congrFun assumptions.zeroFirstMoment component
  simpa [vscale] using componentEquality

private theorem weightedAffineOldOffset_component_zero
    {Grid : Type*} [Fintype Grid]
    (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment : Mat3)
    (gradient : Mat3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment)
    (component : Fin 3) :
    (∑ grid : Grid,
      weight grid *
        matVec gradient
          (movingAPICOldOffset oldGridPosition oldParticlePosition grid)
          component) = 0 := by
  simp only [matVec]
  simp_rw [Finset.mul_sum]
  rw [Finset.sum_comm]
  apply Finset.sum_eq_zero
  intro axis _
  calc
    (∑ grid : Grid,
      weight grid *
        (gradient component axis *
          movingAPICOldOffset oldGridPosition oldParticlePosition grid axis)) =
      gradient component axis *
        (∑ grid : Grid,
          weight grid *
            movingAPICOldOffset oldGridPosition oldParticlePosition grid axis) := by
      rw [Finset.mul_sum]
      apply Finset.sum_congr rfl
      intro grid _
      ring
    _ = 0 := by
      rw [weightedOldOffset_component_zero weight oldGridPosition
        oldParticlePosition oldSecondMoment assumptions axis]
      ring

private theorem weightedAffineOldOffset_moment
    {Grid : Type*} [Fintype Grid]
    (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment : Mat3)
    (gradient : Mat3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment)
    (row column : Fin 3) :
    (∑ grid : Grid,
      weight grid *
        matVec gradient
          (movingAPICOldOffset oldGridPosition oldParticlePosition grid) row *
        movingAPICOldOffset oldGridPosition oldParticlePosition grid column) =
      matMul3 gradient oldSecondMoment row column := by
  change
    (∑ grid : Grid,
      weight grid *
        (∑ axis : Fin 3,
          gradient row axis *
            movingAPICOldOffset oldGridPosition oldParticlePosition grid axis) *
        movingAPICOldOffset oldGridPosition oldParticlePosition grid column) =
      ∑ axis : Fin 3, gradient row axis * oldSecondMoment axis column
  simp_rw [Finset.mul_sum]
  simp_rw [Finset.sum_mul]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro axis _
  have selectedMoment := congrFun
    (congrFun assumptions.secondMoment axis) column
  simp only [movingAPICOldSecondMoment] at selectedMoment
  calc
    (∑ grid : Grid,
      weight grid *
          (gradient row axis *
            movingAPICOldOffset oldGridPosition oldParticlePosition grid axis) *
        movingAPICOldOffset oldGridPosition oldParticlePosition grid column) =
      gradient row axis *
        (∑ grid : Grid,
          weight grid *
            movingAPICOldOffset oldGridPosition oldParticlePosition grid axis *
            movingAPICOldOffset oldGridPosition oldParticlePosition grid column) := by
      rw [Finset.mul_sum]
      apply Finset.sum_congr rfl
      intro grid _
      ring
    _ = gradient row axis * oldSecondMoment axis column := by
      rw [selectedMoment]

/-- Eq. 37 exactly reproduces the material velocity of a global affine field. -/
theorem movingAPIC_nextParticleVelocity_affine
    {Grid : Type*} [Fintype Grid]
    (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment : Mat3)
    (gradient : Mat3) (offset : Vec3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment) :
    movingAPICNextParticleVelocity weight oldGridPosition gradient offset =
      affineVelocityField offset gradient oldParticlePosition := by
  funext component
  simp only [movingAPICNextParticleVelocity]
  simp_rw [movingAPICOldGridVelocity_decomposition oldGridPosition
    oldParticlePosition gradient offset]
  simp only [Pi.add_apply, mul_add]
  rw [Finset.sum_add_distrib]
  have constantPart :
      (∑ grid : Grid,
        weight grid * affineVelocityField offset gradient oldParticlePosition component) =
      affineVelocityField offset gradient oldParticlePosition component := by
    rw [← Finset.sum_mul, assumptions.partitionUnity]
    ring
  rw [constantPart, weightedAffineOldOffset_component_zero weight
    oldGridPosition oldParticlePosition oldSecondMoment gradient assumptions]
  ring

/-- Eq. 39 gives `x_p^{n+1} = x_p^n + dt v_p` in the affine limit. -/
theorem movingAPIC_nextParticlePosition_affine
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment : Mat3)
    (gradient : Mat3) (offset : Vec3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment) :
    movingAPICNextParticlePosition dt weight oldGridPosition gradient offset =
      oldParticlePosition +
        vscale dt (affineVelocityField offset gradient oldParticlePosition) := by
  funext component
  simp only [movingAPICNextParticlePosition, movingAPICNewGridPosition,
    Pi.add_apply, vscale, mul_add]
  rw [Finset.sum_add_distrib]
  have positionPart :
      (∑ grid : Grid, weight grid * oldGridPosition grid component) =
        oldParticlePosition component := by
    have firstMoment := weightedOldOffset_component_zero weight oldGridPosition
      oldParticlePosition oldSecondMoment assumptions component
    simp only [movingAPICOldOffset, Pi.sub_apply] at firstMoment
    have partition := assumptions.partitionUnity
    calc
      (∑ grid : Grid, weight grid * oldGridPosition grid component) =
          (∑ grid : Grid,
            weight grid *
              (oldParticlePosition component +
                (oldGridPosition grid component - oldParticlePosition component))) := by
            apply Finset.sum_congr rfl
            intro grid _
            ring
      _ = oldParticlePosition component * (∑ grid : Grid, weight grid) +
          (∑ grid : Grid,
            weight grid *
              (oldGridPosition grid component - oldParticlePosition component)) := by
            simp_rw [mul_add]
            rw [Finset.sum_add_distrib]
            congr 1
            rw [← Finset.sum_mul]
            ring
      _ = oldParticlePosition component := by
            rw [partition, firstMoment]
            ring
  have velocityPart := congrFun
    (movingAPIC_nextParticleVelocity_affine weight oldGridPosition
      oldParticlePosition oldSecondMoment gradient offset assumptions) component
  change
    (∑ grid : Grid, weight grid * oldGridPosition grid component) +
        (∑ grid : Grid,
          weight grid *
            (dt * movingAPICOldGridVelocity oldGridPosition gradient offset grid component)) =
      oldParticlePosition component +
        dt * affineVelocityField offset gradient oldParticlePosition component
  rw [positionPart]
  have scaledVelocity :
      (∑ grid : Grid,
        weight grid *
          (dt * movingAPICOldGridVelocity oldGridPosition gradient offset grid component)) =
        dt * movingAPICNextParticleVelocity weight oldGridPosition gradient offset component := by
    change
      (∑ grid : Grid,
        weight grid *
          (dt * movingAPICOldGridVelocity oldGridPosition gradient offset grid component)) =
      dt *
        (∑ grid : Grid,
          weight grid *
            movingAPICOldGridVelocity oldGridPosition gradient offset grid component)
    rw [Finset.mul_sum]
    apply Finset.sum_congr rfl
    intro grid _
    ring
  rw [scaledVelocity, velocityPart]

/-- New offsets convect as `(I + dt A) r_i` in the global affine limit. -/
theorem movingAPIC_newOffset_affine
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment : Mat3)
    (gradient : Mat3) (offset : Vec3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment)
    (grid : Grid) :
    movingAPICNewOffset dt weight oldGridPosition oldParticlePosition
        gradient offset grid =
      movingAPICOldOffset oldGridPosition oldParticlePosition grid +
        vscale dt
          (matVec gradient
            (movingAPICOldOffset oldGridPosition oldParticlePosition grid)) := by
  rw [movingAPICNewOffset, movingAPIC_nextParticlePosition_affine dt weight
    oldGridPosition oldParticlePosition oldSecondMoment gradient offset assumptions]
  rw [movingAPICNewGridPosition]
  rw [movingAPICOldGridVelocity_decomposition oldGridPosition
    oldParticlePosition gradient offset grid]
  funext component
  simp [movingAPICOldOffset, vscale]
  ring

private theorem movingAPICEq38_reduces_to_affine_form
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment : Mat3)
    (gradient : Mat3) (offset : Vec3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment) :
    movingAPICEq38BNext dt weight oldGridPosition oldParticlePosition
        gradient offset =
      movingAPICEq38AffineForm dt weight
        (affineVelocityField offset gradient oldParticlePosition)
        (movingAPICOldOffset oldGridPosition oldParticlePosition)
        (fun grid => matVec gradient
          (movingAPICOldOffset oldGridPosition oldParticlePosition grid)) := by
  funext row column
  apply congrArg (fun value : ℚ => (1 / 2 : ℚ) * value)
  apply Finset.sum_congr rfl
  intro grid _
  rw [movingAPICOldGridVelocity_decomposition oldGridPosition
    oldParticlePosition gradient offset grid]
  rw [movingAPIC_newOffset_affine dt weight oldGridPosition
    oldParticlePosition oldSecondMoment gradient offset assumptions grid]
  rfl

private theorem movingAPICEq38AffineForm_eq_moment
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (particleVelocity : Vec3)
    (oldDisplacement affineDisplacement : Grid → Vec3)
    (targetMoment : Mat3)
    (oldDisplacementZero : ∀ component,
      ∑ grid : Grid, weight grid * oldDisplacement grid component = 0)
    (affineDisplacementZero : ∀ component,
      ∑ grid : Grid, weight grid * affineDisplacement grid component = 0)
    (affineMoment : ∀ row column,
      ∑ grid : Grid,
        weight grid * affineDisplacement grid row *
          oldDisplacement grid column = targetMoment row column) :
    movingAPICEq38AffineForm dt weight particleVelocity oldDisplacement
        affineDisplacement = targetMoment := by
  funext row column
  simp only [movingAPICEq38AffineForm]
  have reducedSummand : ∀ grid : Grid,
      (1 / 2 : ℚ) *
          (weight grid *
            ((particleVelocity row + affineDisplacement grid row) *
                (oldDisplacement grid column +
                  (oldDisplacement grid column +
                    dt * affineDisplacement grid column)) +
              (oldDisplacement grid row -
                  (oldDisplacement grid row +
                    dt * affineDisplacement grid row)) *
                (particleVelocity column + affineDisplacement grid column))) =
        weight grid * affineDisplacement grid row * oldDisplacement grid column +
          particleVelocity row * (weight grid * oldDisplacement grid column) +
          (dt / 2) * particleVelocity row *
            (weight grid * affineDisplacement grid column) -
          (dt / 2) * particleVelocity column *
            (weight grid * affineDisplacement grid row) := by
    intro grid
    ring
  rw [Finset.mul_sum]
  simp_rw [reducedSummand]
  rw [Finset.sum_sub_distrib]
  rw [Finset.sum_add_distrib]
  rw [Finset.sum_add_distrib]
  rw [affineMoment row column]
  rw [← Finset.mul_sum, oldDisplacementZero column]
  rw [← Finset.mul_sum, affineDisplacementZero column]
  rw [← Finset.mul_sum, affineDisplacementZero row]
  ring

/--
The full moving-grid Eq. 38 evaluates to `B_next = A D_old`; this is derived
from the concrete old/new offsets rather than assumed.
-/
theorem movingAPIC_eq38_affine_BNext
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment : Mat3)
    (gradient : Mat3) (offset : Vec3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment) :
    movingAPICEq38BNext dt weight oldGridPosition oldParticlePosition
        gradient offset =
      matMul3 gradient oldSecondMoment := by
  rw [movingAPICEq38_reduces_to_affine_form dt weight oldGridPosition
    oldParticlePosition oldSecondMoment gradient offset assumptions]
  exact movingAPICEq38AffineForm_eq_moment dt weight
    (affineVelocityField offset gradient oldParticlePosition)
    (movingAPICOldOffset oldGridPosition oldParticlePosition)
    (fun grid => matVec gradient
      (movingAPICOldOffset oldGridPosition oldParticlePosition grid))
    (matMul3 gradient oldSecondMoment)
    (weightedOldOffset_component_zero weight oldGridPosition
      oldParticlePosition oldSecondMoment assumptions)
    (weightedAffineOldOffset_component_zero weight oldGridPosition
      oldParticlePosition oldSecondMoment gradient assumptions)
    (weightedAffineOldOffset_moment weight oldGridPosition
      oldParticlePosition oldSecondMoment gradient assumptions)

/--
Expanded-statement form of the Eq. 38 result. The finite sum appears directly
in the theorem so traceability does not rely on treating a named transfer as a
premise.
-/
theorem movingAPIC_eq38_affine_BNext_expanded
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment : Mat3)
    (gradient : Mat3) (offset : Vec3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment) :
    (fun row column =>
      (1 / 2 : ℚ) * ∑ grid : Grid,
        weight grid *
          (movingAPICOldGridVelocity oldGridPosition gradient offset grid row *
              (movingAPICOldOffset oldGridPosition oldParticlePosition grid column +
                movingAPICNewOffset dt weight oldGridPosition oldParticlePosition
                  gradient offset grid column) +
            (movingAPICOldOffset oldGridPosition oldParticlePosition grid row -
                movingAPICNewOffset dt weight oldGridPosition oldParticlePosition
                  gradient offset grid row) *
              movingAPICOldGridVelocity oldGridPosition gradient offset grid column)) =
      matMul3 gradient oldSecondMoment := by
  exact movingAPIC_eq38_affine_BNext dt weight oldGridPosition
    oldParticlePosition oldSecondMoment gradient offset assumptions

/-- Explicit two-sided inverse witness for a concrete second moment. -/
structure Mat3Inverse (matrix inverse : Mat3) : Prop where
  matrixAfterInverse : matMul3 matrix inverse = matIdentity3
  inverseAfterMatrix : matMul3 inverse matrix = matIdentity3

/-- APIC affine coefficient reconstructed as `C_next = B_next D_next^{-1}`. -/
def movingAPICCNext (bNext inverseNextMoment : Mat3) : Mat3 :=
  matMul3 bNext inverseNextMoment

private theorem matMul3_assoc (first second third : Mat3) :
    matMul3 (matMul3 first second) third =
      matMul3 first (matMul3 second third) := by
  funext row column
  simp only [matMul3]
  simp_rw [Finset.sum_mul]
  simp_rw [Finset.mul_sum]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro axis _
  apply Finset.sum_congr rfl
  intro middle _
  ring

private theorem matMul3_identity_right (matrix : Mat3) :
    matMul3 matrix matIdentity3 = matrix := by
  funext row column
  simp [matMul3, matIdentity3]

/--
If `D_next = D_old` and its inverse is explicitly witnessed, Eq. 38 reconstructs
the stale old gradient exactly: `C_next = A`.
-/
theorem movingAPIC_CNext_eq_oldGradient_when_moment_fixed
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment nextSecondMoment : Mat3)
    (inverseNextMoment gradient : Mat3) (offset : Vec3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment)
    (momentFixed : nextSecondMoment = oldSecondMoment)
    (momentInverse : Mat3Inverse nextSecondMoment inverseNextMoment) :
    movingAPICCNext
        (movingAPICEq38BNext dt weight oldGridPosition oldParticlePosition
          gradient offset)
        inverseNextMoment = gradient := by
  rw [movingAPIC_eq38_affine_BNext dt weight oldGridPosition
    oldParticlePosition oldSecondMoment gradient offset assumptions]
  simp only [movingAPICCNext]
  rw [matMul3_assoc]
  have rightInverse :
      matMul3 oldSecondMoment inverseNextMoment = matIdentity3 := by
    rw [← momentFixed]
    exact momentInverse.matrixAfterInverse
  rw [rightInverse, matMul3_identity_right]

/--
Exact stale-versus-convected gradient discrepancy:
`A - A(I + dt A)^{-1} = dt A²(I + dt A)^{-1}`.
-/
theorem movingAPIC_staleGradient_exact_discrepancy
    {V : Type*} [AddCommGroup V] [Module ℚ V]
    (dt : ℚ) (gradient inverse : Module.End ℚ V)
    (inverseLaw : StepInverse dt gradient inverse) :
    gradient - convectedAffineGradient gradient inverse =
      dt • gradient.comp (gradient.comp inverse) := by
  ext vector
  have recovered := inverseLaw.stepAfterInverse vector
  simp only [affineStepLinear, LinearMap.add_apply, LinearMap.id_apply,
    LinearMap.smul_apply] at recovered
  have mappedRecovered := congrArg gradient recovered
  simp only [map_add, map_smul] at mappedRecovered
  simp only [LinearMap.sub_apply, convectedAffineGradient,
    LinearMap.comp_apply, LinearMap.smul_apply]
  calc
    gradient vector - gradient (inverse vector) =
        (gradient (inverse vector) +
          dt • gradient (gradient (inverse vector))) -
          gradient (inverse vector) := by
      rw [mappedRecovered]
    _ =
        dt • gradient (gradient (inverse vector)) := by
      module

/--
Combined JST diagnosis: after the full Eq. 38 update and a fixed second moment,
the reconstructed coefficient differs from exact affine convection by
`dt A²(I + dt A)^{-1}`. Numerical inversion is not assumed; both moment and
affine-step inverses are explicit witnesses.
-/
theorem movingAPIC_CNext_minus_exactAffineGradient
    {Grid : Type*} [Fintype Grid]
    (dt : ℚ) (weight : Grid → ℚ) (oldGridPosition : Grid → Vec3)
    (oldParticlePosition : Vec3) (oldSecondMoment nextSecondMoment : Mat3)
    (inverseNextMoment gradient : Mat3) (offset : Vec3)
    (inverseAffineStep : Module.End ℚ Vec3)
    (assumptions : MovingAPICAffineStencilAssumptions weight oldGridPosition
      oldParticlePosition oldSecondMoment)
    (momentFixed : nextSecondMoment = oldSecondMoment)
    (momentInverse : Mat3Inverse nextSecondMoment inverseNextMoment)
    (stepInverse : StepInverse dt (mat3End gradient) inverseAffineStep) :
    mat3End
          (movingAPICCNext
            (movingAPICEq38BNext dt weight oldGridPosition oldParticlePosition
              gradient offset)
            inverseNextMoment) -
        convectedAffineGradient (mat3End gradient) inverseAffineStep =
      dt • (mat3End gradient).comp
        ((mat3End gradient).comp inverseAffineStep) := by
  rw [movingAPIC_CNext_eq_oldGradient_when_moment_fixed dt weight
    oldGridPosition oldParticlePosition oldSecondMoment nextSecondMoment
    inverseNextMoment gradient offset assumptions momentFixed momentInverse]
  exact movingAPIC_staleGradient_exact_discrepancy dt
    (mat3End gradient) inverseAffineStep stepInverse

end MLSFormal
