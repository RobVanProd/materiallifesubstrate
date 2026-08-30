import Mathlib.Data.Matrix.Basic
import Mathlib.Data.Matrix.Mul
import Mathlib.LinearAlgebra.FiniteDimensional.Basic
import Mathlib.Tactic.Linarith

set_option autoImplicit false

namespace MLSFormal

open scoped BigOperators Matrix

/-!
# Finite relational constitutive-energy contracts

This module gives the exact finite algebra used by the Constitutive
Expressivity Lab.  `R` maps packet displacement coordinates to objective
relation-extension coordinates.  `H` acts only on those relation coordinates;
it is constitutive data, not packet state.  No force application or time
evolution is defined here.
-/

/-- Relation-extension coordinates `e = R u`. -/
def relationExtension
    {Relation Degree : Type*} [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (displacement : Degree → ℚ) : Relation → ℚ :=
  relationOperator *ᵥ displacement

/-- The experimental relation-coordinate quadratic energy. -/
def relationalQuadraticEnergy
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (displacement : Degree → ℚ) : ℚ :=
  (1 / 2 : ℚ) *
    (relationExtension relationOperator displacement ⬝ᵥ
      constitutiveOperator *ᵥ relationExtension relationOperator displacement)

/-- The literal finite stiffness composition `K = Rᵀ H R`. -/
def relationalStiffness
    {Relation Degree : Type*} [Fintype Relation]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ) :
    Matrix Degree Degree ℚ :=
  relationOperator.transpose * constitutiveOperator * relationOperator

/-- Symmetry of the relation-coordinate constitutive operator. -/
def SymmetricConstitutiveOperator
    {Relation : Type*}
    (constitutiveOperator : Matrix Relation Relation ℚ) : Prop :=
  constitutiveOperator.transpose = constitutiveOperator

/-- Strict positivity is required only on nonzero extensions that `R` can make. -/
def StrictlyPositiveOnRelationImage
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ) : Prop :=
  ∀ extension : Relation → ℚ,
    extension ∈ Set.range relationOperator.mulVec →
      extension ≠ 0 →
        0 < extension ⬝ᵥ constitutiveOperator *ᵥ extension

/-- A finite relation operator is observable relative to a declared rigid subspace. -/
def RelationOperatorMechanicallyObservable
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (rigidMotions : Submodule ℚ (Degree → ℚ)) : Prop :=
  ∀ displacement : Degree → ℚ,
    relationOperator *ᵥ displacement = 0 ↔ displacement ∈ rigidMotions

/-- `uᵀ K u` is exactly the constitutive quadratic form evaluated at `R u`. -/
theorem relationalStiffness_quadratic_identity
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (displacement : Degree → ℚ) :
    displacement ⬝ᵥ
        relationalStiffness relationOperator constitutiveOperator *ᵥ displacement =
      relationExtension relationOperator displacement ⬝ᵥ
        constitutiveOperator *ᵥ relationExtension relationOperator displacement := by
  rw [relationalStiffness, Matrix.mul_assoc, Matrix.mulVec_mulVec,
    Matrix.mulVec_mulVec, Matrix.dotProduct_transpose_mulVec]
  rfl

/-- The packet-coordinate and relation-coordinate energy formulas agree. -/
theorem relationalQuadraticEnergy_eq_stiffness_quadratic
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (displacement : Degree → ℚ) :
    relationalQuadraticEnergy relationOperator constitutiveOperator displacement =
      (1 / 2 : ℚ) *
        (displacement ⬝ᵥ
          relationalStiffness relationOperator constitutiveOperator *ᵥ displacement) := by
  rw [relationalQuadraticEnergy, relationalStiffness_quadratic_identity]

/-- A symmetric `H` produces a symmetric packet-coordinate `K = Rᵀ H R`. -/
theorem relationalStiffness_symmetric
    {Relation Degree : Type*} [Fintype Relation]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (symmetric : SymmetricConstitutiveOperator constitutiveOperator) :
    (relationalStiffness relationOperator constitutiveOperator).transpose =
      relationalStiffness relationOperator constitutiveOperator := by
  unfold SymmetricConstitutiveOperator at symmetric
  simp only [relationalStiffness, Matrix.transpose_mul,
    Matrix.transpose_transpose, symmetric, Matrix.mul_assoc]

/-- Every displacement hidden by `R` is also hidden by `K = Rᵀ H R`. -/
theorem relationKernel_le_relationalStiffnessKernel
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (displacement : Degree → ℚ)
    (inRelationKernel : relationOperator *ᵥ displacement = 0) :
    relationalStiffness relationOperator constitutiveOperator *ᵥ displacement = 0 := by
  rw [relationalStiffness, Matrix.mul_assoc, Matrix.mulVec_mulVec,
    Matrix.mulVec_mulVec, inRelationKernel]
  simp

/--
Strict positivity of `H` on `im R` rules out every additional stiffness-kernel
mode.  This derives equality from the finite operators and the visible
positivity boundary; it does not require either matrix to be invertible.
-/
theorem relationalStiffness_kernel_eq_relationKernel
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (positiveOnImage :
      StrictlyPositiveOnRelationImage relationOperator constitutiveOperator)
    (displacement : Degree → ℚ) :
    relationalStiffness relationOperator constitutiveOperator *ᵥ displacement = 0 ↔
      relationOperator *ᵥ displacement = 0 := by
  constructor
  · intro inStiffnessKernel
    let extension := relationExtension relationOperator displacement
    by_contra extensionNonzero
    have extensionInRange :
        extension ∈ Set.range relationOperator.mulVec := by
      exact ⟨displacement, rfl⟩
    have extensionPositive :
        0 < extension ⬝ᵥ constitutiveOperator *ᵥ extension :=
      positiveOnImage extension extensionInRange extensionNonzero
    have extensionQuadraticZero :
        extension ⬝ᵥ constitutiveOperator *ᵥ extension = 0 := by
      rw [← relationalStiffness_quadratic_identity relationOperator
        constitutiveOperator displacement, inStiffnessKernel]
      simp
    linarith
  · intro inRelationKernel
    exact relationKernel_le_relationalStiffnessKernel relationOperator
      constitutiveOperator displacement inRelationKernel

/-- In particular, every rigid motion already hidden by `R` stays in `ker K`. -/
theorem rigidRelationMotion_in_relationalStiffnessKernel
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (rigidMotion : Degree → ℚ)
    (rigidInRelationKernel : relationOperator *ᵥ rigidMotion = 0) :
    relationalStiffness relationOperator constitutiveOperator *ᵥ rigidMotion = 0 :=
  relationKernel_le_relationalStiffnessKernel relationOperator
    constitutiveOperator rigidMotion rigidInRelationKernel

/--
An observable relation operator paired with a constitutive quadratic form that
is strictly positive on its image has exactly the declared rigid zero modes.
-/
theorem observableRelationalStiffness_has_only_rigid_kernel
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (rigidMotions : Submodule ℚ (Degree → ℚ))
    (observable :
      RelationOperatorMechanicallyObservable relationOperator rigidMotions)
    (positiveOnImage :
      StrictlyPositiveOnRelationImage relationOperator constitutiveOperator)
    (displacement : Degree → ℚ) :
    relationalStiffness relationOperator constitutiveOperator *ᵥ displacement = 0 ↔
      displacement ∈ rigidMotions := by
  rw [relationalStiffness_kernel_eq_relationKernel relationOperator
    constitutiveOperator positiveOnImage displacement]
  exact observable displacement

/-- Equal objective extension coordinates give exactly equal finite energies. -/
theorem relationalQuadraticEnergy_objective_of_extension_eq
    {Relation DegreeLeft DegreeRight : Type*}
    [Fintype Relation] [Fintype DegreeLeft] [Fintype DegreeRight]
    (leftOperator : Matrix Relation DegreeLeft ℚ)
    (rightOperator : Matrix Relation DegreeRight ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (leftDisplacement : DegreeLeft → ℚ)
    (rightDisplacement : DegreeRight → ℚ)
    (objectiveExtensions :
      relationExtension leftOperator leftDisplacement =
        relationExtension rightOperator rightDisplacement) :
    relationalQuadraticEnergy leftOperator constitutiveOperator leftDisplacement =
      relationalQuadraticEnergy rightOperator constitutiveOperator rightDisplacement := by
  simp only [relationalQuadraticEnergy, objectiveExtensions]

/-- Scaling every relation extension by `s` scales this quadratic energy by `s²`. -/
theorem relationalQuadraticEnergy_extension_scale
    {Relation DegreeLeft DegreeRight : Type*}
    [Fintype Relation] [Fintype DegreeLeft] [Fintype DegreeRight]
    (leftOperator : Matrix Relation DegreeLeft ℚ)
    (rightOperator : Matrix Relation DegreeRight ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (leftDisplacement : DegreeLeft → ℚ)
    (rightDisplacement : DegreeRight → ℚ)
    (scale : ℚ)
    (scaledExtensions :
      relationExtension rightOperator rightDisplacement =
        scale • relationExtension leftOperator leftDisplacement) :
    relationalQuadraticEnergy rightOperator constitutiveOperator rightDisplacement =
      scale ^ 2 *
        relationalQuadraticEnergy leftOperator constitutiveOperator leftDisplacement := by
  rw [relationalQuadraticEnergy, scaledExtensions, relationalQuadraticEnergy]
  rw [Matrix.mulVec_smul, smul_dotProduct, dotProduct_smul]
  simp only [smul_eq_mul]
  ring

end MLSFormal
