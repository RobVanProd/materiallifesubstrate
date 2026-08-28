import Mathlib.Tactic.Module

set_option autoImplicit false

namespace MLSFormal

/-!
This module is an exact algebraic model for the Affine Advection Lab. It
models only a force-free affine Eulerian velocity field and coordinate
advection. In particular, it does not model stress, forces, constitutive
response, or a numerical particle/grid transfer.

All inverse requirements are explicit data in `StepInverse`; no determinant,
matrix inverse, or invertibility axiom is hidden in the definitions.
-/

section AffineField

variable {V : Type*} [AddCommGroup V] [Module ℚ V]

/-- A force-free affine Eulerian velocity field `v(x) = A x + b`. -/
def forceFreeAffineVelocity
    (gradient : Module.End ℚ V) (offset position : V) : V :=
  gradient position + offset

/-- Explicit-Euler advection by a force-free affine field. -/
def forceFreeAffineAdvect
    (dt : ℚ) (gradient : Module.End ℚ V) (offset position : V) : V :=
  position + dt • forceFreeAffineVelocity gradient offset position

/-- The linear part `I + dt A` of the affine coordinate update. -/
def affineStepLinear
    (dt : ℚ) (gradient : Module.End ℚ V) : Module.End ℚ V :=
  LinearMap.id + dt • gradient

/--
An explicit two-sided inverse witness for `I + dt A`. The assumptions are
pointwise so the formal contract cannot acquire invertibility from an axiom or
from an unchecked matrix operation.
-/
structure StepInverse
    (dt : ℚ) (gradient inverse : Module.End ℚ V) : Prop where
  inverseAfterStep : ∀ position,
    inverse (affineStepLinear dt gradient position) = position
  stepAfterInverse : ∀ position,
    affineStepLinear dt gradient (inverse position) = position

/-- The exact convected gradient `A' = A (I + dt A)^{-1}`. -/
def convectedAffineGradient
    (gradient inverse : Module.End ℚ V) : Module.End ℚ V :=
  gradient.comp inverse

/-- The exact convected offset `b' = (I + dt A)^{-1} b`. -/
def convectedAffineOffset (inverse : Module.End ℚ V) (offset : V) : V :=
  inverse offset

private theorem affineStepLinear_apply
    (dt : ℚ) (gradient : Module.End ℚ V) (position : V) :
    affineStepLinear dt gradient position =
      position + dt • gradient position := by
  simp [affineStepLinear]

private theorem forceFreeAffineAdvect_as_step
    (dt : ℚ) (gradient : Module.End ℚ V) (offset position : V) :
    forceFreeAffineAdvect dt gradient offset position =
      affineStepLinear dt gradient position + dt • offset := by
  simp [forceFreeAffineAdvect, forceFreeAffineVelocity,
    affineStepLinear, smul_add]
  module

/--
The coefficient formulas requested by the lab preserve the material
particle's velocity exactly. Both inverse directions are used: the left
inverse recovers the old particle position, while the right inverse rewrites
`R b + dt A (R b)` as `b`.
-/
theorem convectedAffine_preserves_material_velocity
    (dt : ℚ) (gradient inverse : Module.End ℚ V) (offset position : V)
    (inverseLaw : StepInverse dt gradient inverse) :
    forceFreeAffineVelocity
        (convectedAffineGradient gradient inverse)
        (convectedAffineOffset inverse offset)
        (forceFreeAffineAdvect dt gradient offset position) =
      forceFreeAffineVelocity gradient offset position := by
  rw [forceFreeAffineAdvect_as_step]
  have recoveredPosition := inverseLaw.inverseAfterStep position
  have recoveredOffset := inverseLaw.stepAfterInverse offset
  rw [affineStepLinear_apply] at recoveredOffset
  simp only [forceFreeAffineVelocity, convectedAffineGradient,
    convectedAffineOffset, LinearMap.comp_apply, map_add, map_smul]
  rw [recoveredPosition]
  calc
    gradient position + dt • gradient (inverse offset) + inverse offset =
        gradient position +
          (inverse offset + dt • gradient (inverse offset)) := by
      module
    _ = gradient position + offset := by rw [recoveredOffset]

/--
Exact stale-gradient fingerprint: retaining `(A,b)` after moving the particle
changes its sampled velocity by `dt A v(x)`. It vanishes for translations
(`A = 0`) but need not vanish for rotation or a general affine field.
-/
theorem staleAffineGradient_exact_defect
    (dt : ℚ) (gradient : Module.End ℚ V) (offset position : V) :
    forceFreeAffineVelocity gradient offset
          (forceFreeAffineAdvect dt gradient offset position) -
        forceFreeAffineVelocity gradient offset position =
      dt • gradient (forceFreeAffineVelocity gradient offset position) := by
  simp only [forceFreeAffineVelocity, forceFreeAffineAdvect, map_add, map_smul]
  module

/--
Direct material-trajectory refinement for the affine formulas. Under explicit
inverse witnesses at both half steps and at the full step, the twice-advected
position equals the once-advected position, and both updated affine fields
assign that material particle exactly the original velocity. This is the
particle-level affine corollary of the global generator semigroup theorem
below; it does not assume a numerical remap.
-/
theorem convectedAffine_two_half_steps_material_refinement
    (halfDt : ℚ)
    (gradient inverseHalf inverseSecond inverseFull : Module.End ℚ V)
    (offset position : V)
    (firstInverse : StepInverse halfDt gradient inverseHalf)
    (secondInverse : StepInverse halfDt
      (convectedAffineGradient gradient inverseHalf) inverseSecond)
    (fullInverse : StepInverse (2 * halfDt) gradient inverseFull) :
    let firstGradient := convectedAffineGradient gradient inverseHalf
    let firstOffset := convectedAffineOffset inverseHalf offset
    let firstPosition :=
      forceFreeAffineAdvect halfDt gradient offset position
    let secondGradient :=
      convectedAffineGradient firstGradient inverseSecond
    let secondOffset := convectedAffineOffset inverseSecond firstOffset
    let secondPosition :=
      forceFreeAffineAdvect halfDt firstGradient firstOffset firstPosition
    let fullGradient := convectedAffineGradient gradient inverseFull
    let fullOffset := convectedAffineOffset inverseFull offset
    let fullPosition :=
      forceFreeAffineAdvect (2 * halfDt) gradient offset position
    secondPosition = fullPosition ∧
      forceFreeAffineVelocity secondGradient secondOffset secondPosition =
        forceFreeAffineVelocity fullGradient fullOffset fullPosition := by
  dsimp only
  have firstPreserved := convectedAffine_preserves_material_velocity
    halfDt gradient inverseHalf offset position firstInverse
  have secondPreserved := convectedAffine_preserves_material_velocity
    halfDt (convectedAffineGradient gradient inverseHalf) inverseSecond
      (convectedAffineOffset inverseHalf offset)
      (forceFreeAffineAdvect halfDt gradient offset position) secondInverse
  have fullPreserved := convectedAffine_preserves_material_velocity
    (2 * halfDt) gradient inverseFull offset position fullInverse
  constructor
  · calc
      forceFreeAffineAdvect halfDt
          (convectedAffineGradient gradient inverseHalf)
          (convectedAffineOffset inverseHalf offset)
          (forceFreeAffineAdvect halfDt gradient offset position) =
        forceFreeAffineAdvect halfDt gradient offset position +
          halfDt •
            forceFreeAffineVelocity
              (convectedAffineGradient gradient inverseHalf)
              (convectedAffineOffset inverseHalf offset)
              (forceFreeAffineAdvect halfDt gradient offset position) := rfl
      _ = forceFreeAffineAdvect halfDt gradient offset position +
          halfDt • forceFreeAffineVelocity gradient offset position := by
        rw [firstPreserved]
      _ = forceFreeAffineAdvect (2 * halfDt) gradient offset position := by
        simp only [forceFreeAffineAdvect]
        module
  · rw [secondPreserved, firstPreserved, fullPreserved]

end AffineField

section GeneratorRefinement

variable {W : Type*} [AddCommGroup W] [Module ℚ W]

/-!
The refinement proof is stated for a linear generator on an arbitrary module.
An affine field is made linear by homogeneous coordinates `(x, 1)`, so this is
the exact algebraic core of the affine two-half-step law rather than an
assumption that the law holds.
-/

/-- One force-free coordinate step generated by a linear velocity field. -/
def generatorStep
    (dt : ℚ) (generator : Module.End ℚ W) (state : W) : W :=
  state + dt • generator state

/-- The convected generator after one coordinate step. -/
def convectedGenerator
    (generator inverse : Module.End ℚ W) : Module.End ℚ W :=
  generator.comp inverse

/-- Explicit two-sided inverse contract for a generator step. -/
structure GeneratorStepInverse
    (dt : ℚ) (generator inverse : Module.End ℚ W) : Prop where
  inverseAfterStep : ∀ state,
    inverse (generatorStep dt generator state) = state
  stepAfterInverse : ∀ state,
    generatorStep dt generator (inverse state) = state

/-- The convected generator preserves every material state's velocity. -/
theorem convectedGenerator_preserves_material_velocity
    (dt : ℚ) (generator inverse : Module.End ℚ W) (state : W)
    (inverseLaw : GeneratorStepInverse dt generator inverse) :
    convectedGenerator generator inverse
        (generatorStep dt generator state) = generator state := by
  simp only [convectedGenerator, LinearMap.comp_apply]
  rw [inverseLaw.inverseAfterStep]

private theorem two_half_generator_steps_eq_full
    (halfDt : ℚ) (generator inverseHalf : Module.End ℚ W)
    (state : W)
    (firstInverse : GeneratorStepInverse halfDt generator inverseHalf) :
    generatorStep halfDt (convectedGenerator generator inverseHalf)
        (generatorStep halfDt generator state) =
      generatorStep (2 * halfDt) generator state := by
  change
    generatorStep halfDt generator state +
        halfDt • convectedGenerator generator inverseHalf
          (generatorStep halfDt generator state) =
      state + (2 * halfDt) • generator state
  rw [convectedGenerator_preserves_material_velocity
    halfDt generator inverseHalf state firstInverse]
  simp only [generatorStep]
  module

private theorem composed_half_inverse_eq_full_inverse
    (halfDt : ℚ)
    (generator inverseHalf inverseSecond inverseFull : Module.End ℚ W)
    (firstInverse : GeneratorStepInverse halfDt generator inverseHalf)
    (secondInverse : GeneratorStepInverse halfDt
      (convectedGenerator generator inverseHalf) inverseSecond)
    (fullInverse : GeneratorStepInverse (2 * halfDt) generator inverseFull) :
    inverseHalf.comp inverseSecond = inverseFull := by
  ext state
  have twoHalf := two_half_generator_steps_eq_full
    halfDt generator inverseHalf (inverseFull state) firstInverse
  have fullRecovered := fullInverse.stepAfterInverse state
  simp only [LinearMap.comp_apply]
  calc
    inverseHalf (inverseSecond state) =
        inverseHalf (inverseSecond
          (generatorStep (2 * halfDt) generator (inverseFull state))) := by
      rw [fullRecovered]
    _ = inverseHalf (inverseSecond
          (generatorStep halfDt (convectedGenerator generator inverseHalf)
            (generatorStep halfDt generator (inverseFull state)))) := by
      rw [twoHalf]
    _ = inverseHalf
          (generatorStep halfDt generator (inverseFull state)) := by
      rw [secondInverse.inverseAfterStep]
    _ = inverseFull state := by
      rw [firstInverse.inverseAfterStep]

/--
Semigroup/refinement theorem for the analytic convected generator: where the
two half-step inverses and full-step inverse exist explicitly, two half-step
coordinate updates and generator updates equal one full-step update.
-/
theorem convectedGenerator_two_half_steps_equal_full_step
    (halfDt : ℚ)
    (generator inverseHalf inverseSecond inverseFull : Module.End ℚ W)
    (firstInverse : GeneratorStepInverse halfDt generator inverseHalf)
    (secondInverse : GeneratorStepInverse halfDt
      (convectedGenerator generator inverseHalf) inverseSecond)
    (fullInverse : GeneratorStepInverse (2 * halfDt) generator inverseFull)
    (state : W) :
    generatorStep halfDt
          (convectedGenerator generator inverseHalf)
          (generatorStep halfDt generator state) =
        generatorStep (2 * halfDt) generator state ∧
      convectedGenerator
          (convectedGenerator generator inverseHalf) inverseSecond =
        convectedGenerator generator inverseFull := by
  constructor
  · exact two_half_generator_steps_eq_full
      halfDt generator inverseHalf state firstInverse
  · have inverseComposition := composed_half_inverse_eq_full_inverse
      halfDt generator inverseHalf inverseSecond inverseFull
      firstInverse secondInverse fullInverse
    simp only [convectedGenerator]
    rw [LinearMap.comp_assoc, inverseComposition]

end GeneratorRefinement

section HomogeneousAffineReduction

variable {V : Type*} [AddCommGroup V] [Module ℚ V]

/-- Homogeneous-coordinate generator for `(x,s) ↦ (A x + s b, 0)`. -/
def homogeneousAffineGenerator
    (gradient : Module.End ℚ V) (offset : V) : Module.End ℚ (V × ℚ) where
  toFun state := (gradient state.1 + state.2 • offset, 0)
  map_add' left right := by
    ext
    · simp only [Prod.fst_add, Prod.snd_add, map_add, add_smul]
      module
    · simp
  map_smul' scale state := by
    ext <;> simp [mul_smul, smul_add]

/-- Embed a physical position in the homogeneous affine slice `s = 1`. -/
def homogeneousPosition (position : V) : V × ℚ := (position, 1)

/--
Explicit homogeneous-coordinate inverse of an affine coordinate step. Its
first component is `R (y - dt s b)` and its homogeneous coordinate is fixed.
-/
def homogeneousAffineStepInverse
    (dt : ℚ) (inverse : Module.End ℚ V) (offset : V) :
    Module.End ℚ (V × ℚ) where
  toFun state :=
    (inverse state.1 - (dt * state.2) • inverse offset, state.2)
  map_add' left right := by
    ext
    · change inverse (left.1 + right.1) -
          (dt * (left.2 + right.2)) • inverse offset =
        (inverse left.1 - (dt * left.2) • inverse offset) +
          (inverse right.1 - (dt * right.2) • inverse offset)
      rw [map_add]
      module
    · rfl
  map_smul' scale state := by
    ext
    · change inverse (scale • state.1) -
          (dt * (scale * state.2)) • inverse offset =
        scale •
          (inverse state.1 - (dt * state.2) • inverse offset)
      rw [map_smul]
      module
    · rfl

private theorem homogeneousGeneratorStep_apply
    (dt : ℚ) (gradient : Module.End ℚ V) (offset : V)
    (state : V × ℚ) :
    generatorStep dt (homogeneousAffineGenerator gradient offset) state =
      (affineStepLinear dt gradient state.1 +
          (dt * state.2) • offset,
        state.2) := by
  ext
  · change state.1 +
        dt • (gradient state.1 + state.2 • offset) =
      (state.1 + dt • gradient state.1) +
        (dt * state.2) • offset
    module
  · change state.2 + dt * 0 = state.2
    ring

/--
An explicit inverse of `I + dt A` induces, without an axiom, a two-sided
inverse of the complete affine homogeneous coordinate update.
-/
theorem homogeneousAffineStepInverse_is_inverse
    (dt : ℚ) (gradient inverse : Module.End ℚ V) (offset : V)
    (inverseLaw : StepInverse dt gradient inverse) :
    GeneratorStepInverse dt
      (homogeneousAffineGenerator gradient offset)
      (homogeneousAffineStepInverse dt inverse offset) := by
  constructor
  · intro state
    rw [homogeneousGeneratorStep_apply]
    ext
    · change inverse
          (affineStepLinear dt gradient state.1 +
            (dt * state.2) • offset) -
          (dt * state.2) • inverse offset = state.1
      rw [map_add, map_smul]
      rw [inverseLaw.inverseAfterStep]
      module
    · rfl
  · intro state
    rw [homogeneousGeneratorStep_apply]
    ext
    · change affineStepLinear dt gradient
          (inverse state.1 - (dt * state.2) • inverse offset) +
          (dt * state.2) • offset = state.1
      rw [map_sub, map_smul]
      rw [inverseLaw.stepAfterInverse, inverseLaw.stepAfterInverse]
      module
    · rfl

/--
The homogeneous generator update reduces exactly to the requested coefficient
formulas `A' = A R` and `b' = R b`, where `R` is the explicitly witnessed
inverse of `I + dt A`.
-/
theorem convectedHomogeneousAffineGenerator_formula
    (dt : ℚ) (gradient inverse : Module.End ℚ V) (offset : V)
    (inverseLaw : StepInverse dt gradient inverse) :
    convectedGenerator
        (homogeneousAffineGenerator gradient offset)
        (homogeneousAffineStepInverse dt inverse offset) =
      homogeneousAffineGenerator
        (convectedAffineGradient gradient inverse)
        (convectedAffineOffset inverse offset) := by
  have recoveredOffset := inverseLaw.stepAfterInverse offset
  rw [affineStepLinear_apply] at recoveredOffset
  ext state
  · change gradient
          (inverse state.1 - (dt * state.2) • inverse offset) +
          state.2 • offset =
        gradient (inverse state.1) + state.2 • inverse offset
    rw [map_sub, map_smul]
    calc
      gradient (inverse state.1) -
            (dt * state.2) • gradient (inverse offset) +
          state.2 • offset =
        gradient (inverse state.1) -
            (dt * state.2) • gradient (inverse offset) +
          state.2 •
            (inverse offset + dt • gradient (inverse offset)) := by
        rw [recoveredOffset]
      _ = gradient (inverse state.1) + state.2 • inverse offset := by
        module
  · simp [convectedGenerator, homogeneousAffineGenerator,
      homogeneousAffineStepInverse]

/--
Coefficient-level affine semigroup theorem. With explicit inverse witnesses
for the first half step, the second convected half step, and the full step,
the twice-updated gradient and offset equal the once-updated full-step
gradient and offset. The proof passes through the actual homogeneous update
definitions and the generator semigroup theorem; equality is not assumed.
-/
theorem convectedAffine_two_half_steps_equal_full_update
    (halfDt : ℚ)
    (gradient inverseHalf inverseSecond inverseFull : Module.End ℚ V)
    (offset : V)
    (firstInverse : StepInverse halfDt gradient inverseHalf)
    (secondInverse : StepInverse halfDt
      (convectedAffineGradient gradient inverseHalf) inverseSecond)
    (fullInverse : StepInverse (2 * halfDt) gradient inverseFull) :
    convectedAffineGradient
          (convectedAffineGradient gradient inverseHalf) inverseSecond =
        convectedAffineGradient gradient inverseFull ∧
      convectedAffineOffset inverseSecond
          (convectedAffineOffset inverseHalf offset) =
        convectedAffineOffset inverseFull offset := by
  let firstGradient := convectedAffineGradient gradient inverseHalf
  let firstOffset := convectedAffineOffset inverseHalf offset
  let generator := homogeneousAffineGenerator gradient offset
  let inverseFirstHomogeneous :=
    homogeneousAffineStepInverse halfDt inverseHalf offset
  let inverseSecondHomogeneous :=
    homogeneousAffineStepInverse halfDt inverseSecond firstOffset
  let inverseFullHomogeneous :=
    homogeneousAffineStepInverse (2 * halfDt) inverseFull offset
  have firstHomogeneousInverse : GeneratorStepInverse halfDt
      generator inverseFirstHomogeneous := by
    exact homogeneousAffineStepInverse_is_inverse
      halfDt gradient inverseHalf offset firstInverse
  have firstFormula :
      convectedGenerator generator inverseFirstHomogeneous =
        homogeneousAffineGenerator firstGradient firstOffset := by
    exact convectedHomogeneousAffineGenerator_formula
      halfDt gradient inverseHalf offset firstInverse
  have secondHomogeneousInverse : GeneratorStepInverse halfDt
      (convectedGenerator generator inverseFirstHomogeneous)
      inverseSecondHomogeneous := by
    rw [firstFormula]
    exact homogeneousAffineStepInverse_is_inverse
      halfDt firstGradient inverseSecond firstOffset secondInverse
  have fullHomogeneousInverse : GeneratorStepInverse (2 * halfDt)
      generator inverseFullHomogeneous := by
    exact homogeneousAffineStepInverse_is_inverse
      (2 * halfDt) gradient inverseFull offset fullInverse
  have generatorEquality :=
    (convectedGenerator_two_half_steps_equal_full_step
      halfDt generator inverseFirstHomogeneous inverseSecondHomogeneous
      inverseFullHomogeneous firstHomogeneousInverse secondHomogeneousInverse
      fullHomogeneousInverse (0 : V × ℚ)).2
  have secondFormula := convectedHomogeneousAffineGenerator_formula
    halfDt firstGradient inverseSecond firstOffset secondInverse
  have fullFormula := convectedHomogeneousAffineGenerator_formula
    (2 * halfDt) gradient inverseFull offset fullInverse
  rw [firstFormula, secondFormula, fullFormula] at generatorEquality
  constructor
  · ext position
    have atLinearSlice := congrArg
      (fun affineGenerator : Module.End ℚ (V × ℚ) =>
        (affineGenerator (position, 0)).1)
      generatorEquality
    simpa [homogeneousAffineGenerator, firstGradient, firstOffset] using
      atLinearSlice
  · have atOffsetSlice := congrArg
      (fun affineGenerator : Module.End ℚ (V × ℚ) =>
        (affineGenerator (0, 1)).1)
      generatorEquality
    simpa [homogeneousAffineGenerator, firstGradient, firstOffset] using
      atOffsetSlice

/-- The homogeneous generator evaluates to `(A x + b, 0)` on `s = 1`. -/
theorem homogeneousAffineGenerator_on_position
    (gradient : Module.End ℚ V) (offset position : V) :
    homogeneousAffineGenerator gradient offset (homogeneousPosition position) =
      (forceFreeAffineVelocity gradient offset position, 0) := by
  simp [homogeneousAffineGenerator, homogeneousPosition,
    forceFreeAffineVelocity]

/-- Homogeneous stepping reduces exactly to affine particle advection. -/
theorem homogeneousGeneratorStep_on_position
    (dt : ℚ) (gradient : Module.End ℚ V) (offset position : V) :
    generatorStep dt (homogeneousAffineGenerator gradient offset)
        (homogeneousPosition position) =
      homogeneousPosition
        (forceFreeAffineAdvect dt gradient offset position) := by
  ext <;> simp [generatorStep, homogeneousAffineGenerator,
    homogeneousPosition, forceFreeAffineAdvect, forceFreeAffineVelocity]

end HomogeneousAffineReduction

end MLSFormal
