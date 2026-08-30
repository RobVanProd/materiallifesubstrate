import MLSFormal.ConstitutiveExpressivity
import MLSFormal.MechanicalObservability
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

open scoped BigOperators Matrix

/-!
# Conservative relational-force algebra

This module contains the exact finite algebra used by the Conservative Force
Consistency Lab.  It deliberately separates two claims:

* the linearized conjugate-force model uses `g = H e` and
  `f = -Rᵀ g`; and
* a finite collection of equal-and-opposite forces parallel to relation
  offsets has zero resultant force and torque.

There is no square-root differentiation, force installation, time evolution,
or claim about a floating-point nonlinear evaluator in this file.
-/

/-- The relation-coordinate conjugate quantity `g = H e`. -/
def relationConjugate
    {Relation : Type*} [Fintype Relation]
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (extension : Relation → ℚ) : Relation → ℚ :=
  constitutiveOperator *ᵥ extension

/-- Packet-coordinate force assembled from one relation-coordinate `g`. -/
def packetForceFromRelationConjugate
    {Relation Degree : Type*} [Fintype Relation]
    (relationOperator : Matrix Relation Degree ℚ)
    (conjugate : Relation → ℚ) : Degree → ℚ :=
  -(relationOperator.transpose *ᵥ conjugate)

/-- The complete finite linearized force definition `f = -Rᵀ H e`. -/
def linearizedRelationalForce
    {Relation Degree : Type*} [Fintype Relation]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (extension : Relation → ℚ) : Degree → ℚ :=
  packetForceFromRelationConjugate relationOperator
    (relationConjugate constitutiveOperator extension)

/-- The executable relation conjugate is literally `H e`. -/
theorem relationConjugate_eq_constitutive_mul_extension
    {Relation : Type*} [Fintype Relation]
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (extension : Relation → ℚ) :
    relationConjugate constitutiveOperator extension =
      constitutiveOperator *ᵥ extension :=
  rfl

/-- Substitution of `g = H e` into `f = -Rᵀ g` gives `f = -Rᵀ H e`. -/
theorem linearizedRelationalForce_eq_negative_transpose_constitutive_extension
    {Relation Degree : Type*} [Fintype Relation]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (extension : Relation → ℚ) :
    linearizedRelationalForce relationOperator constitutiveOperator extension =
      -(relationOperator.transpose *ᵥ
        (constitutiveOperator *ᵥ extension)) :=
  rfl

/-- For an extension made by a displacement, force is exactly `-K u`. -/
theorem linearizedRelationalForce_of_displacement_eq_negative_stiffness
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (displacement : Degree → ℚ) :
    linearizedRelationalForce relationOperator constitutiveOperator
        (relationExtension relationOperator displacement) =
      -(relationalStiffness relationOperator constitutiveOperator *ᵥ displacement) := by
  rw [linearizedRelationalForce_eq_negative_transpose_constitutive_extension,
    relationExtension, relationalStiffness, ← Matrix.mulVec_mulVec,
    ← Matrix.mulVec_mulVec]

/-- Zero relation extension produces zero linearized internal force. -/
theorem linearizedRelationalForce_zero_extension
    {Relation Degree : Type*} [Fintype Relation]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ) :
    linearizedRelationalForce relationOperator constitutiveOperator 0 = 0 := by
  simp [linearizedRelationalForce, packetForceFromRelationConjugate,
    relationConjugate]

/-- Exact finite virtual-power identity for the negative-transpose assembly. -/
theorem packetForceFromRelationConjugate_power_identity
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (conjugate : Relation → ℚ)
    (velocity : Degree → ℚ) :
    conjugate ⬝ᵥ (relationOperator *ᵥ velocity) =
      -(packetForceFromRelationConjugate relationOperator conjugate ⬝ᵥ velocity) := by
  rw [packetForceFromRelationConjugate, neg_dotProduct, neg_neg]
  calc
    conjugate ⬝ᵥ relationOperator *ᵥ velocity =
        velocity ⬝ᵥ relationOperator.transpose *ᵥ conjugate :=
      (Matrix.dotProduct_transpose_mulVec
        relationOperator velocity conjugate).symm
    _ = relationOperator.transpose *ᵥ conjugate ⬝ᵥ velocity :=
      dotProduct_comm _ _

/-- The force derived from `H e` obeys the same exact virtual-power identity. -/
theorem linearizedRelationalForce_power_identity
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (extension : Relation → ℚ)
    (velocity : Degree → ℚ) :
    relationConjugate constitutiveOperator extension ⬝ᵥ
        (relationOperator *ᵥ velocity) =
      -(linearizedRelationalForce relationOperator constitutiveOperator extension ⬝ᵥ
        velocity) :=
  packetForceFromRelationConjugate_power_identity relationOperator
    (relationConjugate constitutiveOperator extension) velocity

/-- A virtual motion hidden by `R` performs exactly zero internal virtual work. -/
theorem rigidVirtualMotion_zero_internal_work
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (extension : Relation → ℚ)
    (rigidVelocity : Degree → ℚ)
    (rigidInRelationKernel : relationOperator *ᵥ rigidVelocity = 0) :
    linearizedRelationalForce relationOperator constitutiveOperator extension ⬝ᵥ
      rigidVelocity = 0 := by
  have powerIdentity := linearizedRelationalForce_power_identity
    relationOperator constitutiveOperator extension rigidVelocity
  rw [rigidInRelationKernel] at powerIdentity
  simpa using powerIdentity.symm

/-- The inherited material tangent `Rᵀ H R` remains symmetric for symmetric `H`. -/
theorem linearizedForceMaterialTangent_symmetric
    {Relation Degree : Type*} [Fintype Relation]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (symmetric : SymmetricConstitutiveOperator constitutiveOperator) :
    (relationalStiffness relationOperator constitutiveOperator).transpose =
      relationalStiffness relationOperator constitutiveOperator :=
  relationalStiffness_symmetric relationOperator constitutiveOperator symmetric

/-- Positivity on `im R` gives positive packet-coordinate quadratic work. -/
theorem linearizedForceQuadratic_positive_on_observable_extension
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (positiveOnImage :
      StrictlyPositiveOnRelationImage relationOperator constitutiveOperator)
    (displacement : Degree → ℚ)
    (visible : relationOperator *ᵥ displacement ≠ 0) :
    0 < displacement ⬝ᵥ
      relationalStiffness relationOperator constitutiveOperator *ᵥ displacement := by
  rw [relationalStiffness_quadratic_identity]
  exact positiveOnImage (relationExtension relationOperator displacement)
    ⟨displacement, rfl⟩ visible

/-- The accepted strict-positivity boundary still rules out new zero modes. -/
theorem linearizedForceMaterialTangent_kernel_eq_relationKernel
    {Relation Degree : Type*} [Fintype Relation] [Fintype Degree]
    (relationOperator : Matrix Relation Degree ℚ)
    (constitutiveOperator : Matrix Relation Relation ℚ)
    (positiveOnImage :
      StrictlyPositiveOnRelationImage relationOperator constitutiveOperator)
    (displacement : Degree → ℚ) :
    relationalStiffness relationOperator constitutiveOperator *ᵥ displacement = 0 ↔
      relationOperator *ᵥ displacement = 0 :=
  relationalStiffness_kernel_eq_relationKernel relationOperator
    constitutiveOperator positiveOnImage displacement

/-! ## Explicit finite central-force collection -/

/-- Force on the stored tail: a scalar multiple of the current relation offset. -/
def centralRelationTailForce
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (magnitude : Edge → ℚ)
    (edge : Edge) : Vec3 :=
  magnitude edge • relationOffset relations position edge

/-- Force on the stored head is definitionally equal and opposite. -/
def centralRelationHeadForce
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (magnitude : Edge → ℚ)
    (edge : Edge) : Vec3 :=
  -centralRelationTailForce relations position magnitude edge

/-- Total force of the explicit finite relation collection. -/
def finiteCentralRelationTotalForce
    {Vertex Edge : Type*} [Fintype Edge]
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (magnitude : Edge → ℚ) : Vec3 :=
  ∑ edge : Edge, (
    centralRelationTailForce relations position magnitude edge +
      centralRelationHeadForce relations position magnitude edge)

/-- Total torque about an arbitrary origin for the same finite collection. -/
def finiteCentralRelationTotalTorqueAbout
    {Vertex Edge : Type*} [Fintype Edge]
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (magnitude : Edge → ℚ)
    (origin : Vec3) : Vec3 :=
  ∑ edge : Edge, (
    cross (position (relations.tail edge) - origin)
        (centralRelationTailForce relations position magnitude edge) +
      cross (position (relations.head edge) - origin)
        (centralRelationHeadForce relations position magnitude edge))

/-- The first endpoint force is explicitly parallel to its relation offset. -/
theorem centralRelationTailForce_parallel_offset
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (magnitude : Edge → ℚ)
    (edge : Edge) :
    centralRelationTailForce relations position magnitude edge =
      magnitude edge • relationOffset relations position edge :=
  rfl

/-- Each stored relation contributes exactly equal-and-opposite endpoint forces. -/
theorem centralRelationForces_equal_opposite
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (magnitude : Edge → ℚ)
    (edge : Edge) :
    centralRelationTailForce relations position magnitude edge +
      centralRelationHeadForce relations position magnitude edge = 0 := by
  simp [centralRelationHeadForce]

private theorem centralRelationTorqueAbout_zero
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (magnitude : Edge → ℚ)
    (origin : Vec3)
    (edge : Edge) :
    cross (position (relations.tail edge) - origin)
          (centralRelationTailForce relations position magnitude edge) +
        cross (position (relations.head edge) - origin)
          (centralRelationHeadForce relations position magnitude edge) = 0 := by
  funext component
  fin_cases component <;>
    simp [centralRelationTailForce, centralRelationHeadForce,
      relationOffset, cross] <;>
    ring

/-- Any finite collection of the explicit equal/opposite forces has zero resultant. -/
theorem finiteCentralRelationForces_total_force_zero
    {Vertex Edge : Type*} [Fintype Edge]
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (magnitude : Edge → ℚ) :
    finiteCentralRelationTotalForce relations position magnitude = 0 := by
  classical
  simp [finiteCentralRelationTotalForce, centralRelationForces_equal_opposite]

/-- Centrality derives zero total torque about every origin, including translated ones. -/
theorem finiteCentralRelationForces_total_torque_zero
    {Vertex Edge : Type*} [Fintype Edge]
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (magnitude : Edge → ℚ)
    (origin : Vec3) :
    finiteCentralRelationTotalTorqueAbout relations position magnitude origin = 0 := by
  classical
  simp [finiteCentralRelationTotalTorqueAbout,
    centralRelationTorqueAbout_zero]

end MLSFormal
