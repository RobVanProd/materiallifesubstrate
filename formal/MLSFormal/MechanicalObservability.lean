import MLSFormal.TransitionModel
import Mathlib.Data.Fintype.BigOperators
import Mathlib.Data.Matrix.Basic
import Mathlib.Data.Matrix.Mul
import Mathlib.LinearAlgebra.FiniteDimensional.Lemmas
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

open scoped BigOperators

/-!
# Finite mechanical observability

This module defines an exact-rational central-distance rigidity operator over
packet positions and an explicit relation graph.  It contains no force,
stiffness, stress, constitutive response, time integration, or grid state.
The relation topology is physical input.
-/

/-- Oriented storage for an otherwise objective pair relation. -/
structure RelationEndpoints (Vertex Edge : Type*) where
  tail : Edge → Vertex
  head : Edge → Vertex

/-- Exact three-dimensional dot product. -/
def dot3 (left right : Vec3) : ℚ :=
  ∑ axis : Fin 3, left axis * right axis

private theorem dot3_add_left (left right vector : Vec3) :
    dot3 (left + right) vector = dot3 left vector + dot3 right vector := by
  simp [dot3, add_mul, Finset.sum_add_distrib]

private theorem dot3_add_right (vector left right : Vec3) :
    dot3 vector (left + right) = dot3 vector left + dot3 vector right := by
  simp [dot3, mul_add, Finset.sum_add_distrib]

private theorem dot3_smul_left (scale : ℚ) (left right : Vec3) :
    dot3 (scale • left) right = scale * dot3 left right := by
  simp [dot3, Finset.mul_sum, mul_assoc]

private theorem dot3_smul_right (scale : ℚ) (left right : Vec3) :
    dot3 left (scale • right) = scale * dot3 left right := by
  simp only [dot3, Pi.smul_apply, smul_eq_mul]
  calc
    ∑ axis : Fin 3, left axis * (scale * right axis) =
        ∑ axis : Fin 3, scale * (left axis * right axis) := by
      apply Finset.sum_congr rfl
      intro axis _
      ring
    _ = scale * ∑ axis : Fin 3, left axis * right axis := by
      rw [Finset.mul_sum]

private theorem dot3_comm (left right : Vec3) :
    dot3 left right = dot3 right left := by
  simp [dot3, mul_comm]

private theorem cross_sub_right_mechanical (rotation left right : Vec3) :
    cross rotation (left - right) = cross rotation left - cross rotation right := by
  funext component
  fin_cases component <;> simp [cross] <;> ring

private theorem cross_add_left_mechanical (left right vector : Vec3) :
    cross (left + right) vector = cross left vector + cross right vector := by
  funext component
  fin_cases component <;> simp [cross] <;> ring

private theorem cross_smul_left_mechanical
    (scale : ℚ) (rotation vector : Vec3) :
    cross (scale • rotation) vector = scale • cross rotation vector := by
  funext component
  fin_cases component <;> simp [cross] <;> ring

private theorem dot3_cross_self_zero (offset rotation : Vec3) :
    dot3 offset (cross rotation offset) = 0 := by
  simp [dot3, cross, Fin.sum_univ_succ]
  ring

/-- Current directed offset of one stored relation. -/
def relationOffset
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (edge : Edge) : Vec3 :=
  position (relations.head edge) - position (relations.tail edge)

/-- Relative packet motion across one stored relation. -/
def relationMotion
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (motion : Vertex → Vec3)
    (edge : Edge) : Vec3 :=
  motion (relations.head edge) - motion (relations.tail edge)

private theorem relationMotion_add
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (left right : Vertex → Vec3)
    (edge : Edge) :
    relationMotion relations (left + right) edge =
      relationMotion relations left edge + relationMotion relations right edge := by
  funext axis
  simp [relationMotion]
  ring

private theorem relationMotion_smul
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (scale : ℚ) (motion : Vertex → Vec3)
    (edge : Edge) :
    relationMotion relations (scale • motion) edge =
      scale • relationMotion relations motion edge := by
  funext axis
  simp [relationMotion]
  ring

/-- Squared relation length, kept rational and free of square roots. -/
def relationSquaredLength
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (edge : Edge) : ℚ :=
  dot3 (relationOffset relations position edge)
    (relationOffset relations position edge)

/--
One row of the central rigidity operator.  It is half the first-order rate of
squared relation length.  For a nonzero relation it has the same zero set as
the infinitesimal length rate, without introducing an irrational normalization.
-/
def centralRigidityRate
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3)
    (edge : Edge) : ℚ :=
  dot3 (relationOffset relations position edge)
    (relationMotion relations motion edge)

/-- The complete finite central-distance observability operator. -/
def centralRigidityOperator
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3) : Edge → ℚ :=
  fun edge ↦ centralRigidityRate relations position motion edge

/-- The central-distance operator as an actual rational linear map. -/
def centralRigidityLinearMap
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3) : (Vertex → Vec3) →ₗ[ℚ] (Edge → ℚ) where
  toFun := centralRigidityOperator relations position
  map_add' := by
    intro left right
    funext edge
    change centralRigidityRate relations position (left + right) edge =
      centralRigidityRate relations position left edge +
        centralRigidityRate relations position right edge
    simp only [centralRigidityRate]
    rw [relationMotion_add, dot3_add_right]
  map_smul' := by
    intro scale motion
    funext edge
    change centralRigidityRate relations position (scale • motion) edge =
      scale • centralRigidityRate relations position motion edge
    rw [centralRigidityRate, relationMotion_smul, dot3_smul_right]
    rfl

/-- Flatten a packet motion into the canonical `(vertex, axis)` degree ordering. -/
def flattenMotion
    {Vertex : Type*}
    (motion : Vertex → Vec3) : Vertex × Fin 3 → ℚ :=
  fun degree ↦ motion degree.1 degree.2

/--
The explicit finite rigidity matrix.  Each row contains `-d` at the stored
tail, `+d` at the stored head, and zero elsewhere.
-/
def centralRigidityMatrix
    {Vertex Edge : Type*} [DecidableEq Vertex]
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3) : Matrix Edge (Vertex × Fin 3) ℚ :=
  fun edge degree ↦
    let offset := relationOffset relations position edge
    (if degree.1 = relations.head edge then offset degree.2 else 0) -
      (if degree.1 = relations.tail edge then offset degree.2 else 0)

/-- The explicit rigidity matrix acts exactly as the defined finite operator. -/
theorem centralRigidityMatrix_mulVec
    {Vertex Edge : Type*} [Fintype Vertex] [DecidableEq Vertex]
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3) :
    (centralRigidityMatrix relations position).mulVec (flattenMotion motion) =
      centralRigidityOperator relations position motion := by
  funext edge
  classical
  simp only [Matrix.mulVec, dotProduct, Fintype.sum_prod_type,
    centralRigidityMatrix, flattenMotion, centralRigidityOperator,
    centralRigidityRate, dot3, relationMotion]
  simp only [sub_mul, Finset.sum_sub_distrib]
  simp
  rw [← Finset.sum_sub_distrib]
  apply Finset.sum_congr rfl
  intro axis _
  ring

/-- Exact polynomial expansion defining the central rigidity linearization. -/
theorem centralRigidity_exact_squared_length_expansion
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3)
    (edge : Edge) (epsilon : ℚ) :
    relationSquaredLength relations
        (fun vertex ↦ position vertex + epsilon • motion vertex) edge =
      relationSquaredLength relations position edge +
        2 * epsilon * centralRigidityRate relations position motion edge +
        epsilon ^ 2 * dot3 (relationMotion relations motion edge)
          (relationMotion relations motion edge) := by
  let offset := relationOffset relations position edge
  let relativeMotion := relationMotion relations motion edge
  have perturbedOffset :
      relationOffset relations
          (fun vertex ↦ position vertex + epsilon • motion vertex) edge =
        offset + epsilon • relativeMotion := by
    funext axis
    simp [relationOffset, relationMotion, offset, relativeMotion]
    ring
  rw [relationSquaredLength, perturbedOffset]
  rw [dot3_add_left, dot3_add_right, dot3_smul_right,
    dot3_add_right, dot3_smul_left, dot3_smul_right]
  rw [dot3_comm relativeMotion offset]
  rw [dot3_smul_left epsilon relativeMotion relativeMotion]
  simp only [relationSquaredLength, centralRigidityRate, offset,
    relativeMotion, pow_two]
  ring

/-- A translation plus infinitesimal rotation, parameterized by six scalars. -/
def rigidMotionField
    {Vertex : Type*}
    (position : Vertex → Vec3)
    (parameters : Vec3 × Vec3) : Vertex → Vec3 :=
  fun vertex ↦ parameters.1 + cross parameters.2 (position vertex)

/-- The six-parameter rigid-motion generator as an exact linear map. -/
def rigidMotionGenerator
    {Vertex : Type*}
    (position : Vertex → Vec3) : (Vec3 × Vec3) →ₗ[ℚ] (Vertex → Vec3) where
  toFun := rigidMotionField position
  map_add' := by
    intro left right
    rcases left with ⟨leftTranslation, leftRotation⟩
    rcases right with ⟨rightTranslation, rightRotation⟩
    funext vertex component
    change
      (leftTranslation component + rightTranslation component) +
          cross (leftRotation + rightRotation) (position vertex) component =
        (leftTranslation component +
            cross leftRotation (position vertex) component) +
          (rightTranslation component +
            cross rightRotation (position vertex) component)
    rw [cross_add_left_mechanical]
    simp only [Pi.add_apply]
    ring
  map_smul' := by
    intro scale parameters
    rcases parameters with ⟨translation, rotation⟩
    funext vertex component
    change
      scale * translation component +
          cross (scale • rotation) (position vertex) component =
        scale * (translation component + cross rotation (position vertex) component)
    rw [cross_smul_left_mechanical]
    simp only [Pi.smul_apply, smul_eq_mul]
    ring

/-- All packet motions induced by global translations and rotations. -/
def rigidMotionSubspace
    {Vertex : Type*}
    (position : Vertex → Vec3) : Submodule ℚ (Vertex → Vec3) :=
  LinearMap.range (rigidMotionGenerator position)

/-- Mechanical observability means that only sampled rigid motions are hidden. -/
def MechanicallyObservable
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3) : Prop :=
  LinearMap.ker (centralRigidityLinearMap relations position) =
    rigidMotionSubspace position

/-- Every global translation is invisible to objective central-distance rows. -/
theorem centralRigidity_translation_in_kernel
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (translation : Vec3) :
    (fun _vertex : Vertex ↦ translation) ∈
      LinearMap.ker (centralRigidityLinearMap relations position) := by
  rw [LinearMap.mem_ker]
  funext edge
  change centralRigidityRate relations position
    (fun _vertex : Vertex ↦ translation) edge = 0
  simp [centralRigidityRate, relationMotion, dot3]

/-- Every global infinitesimal rotation is in the central-distance kernel. -/
theorem centralRigidity_infinitesimal_rotation_in_kernel
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (rotation : Vec3) :
    (fun vertex ↦ cross rotation (position vertex)) ∈
      LinearMap.ker (centralRigidityLinearMap relations position) := by
  rw [LinearMap.mem_ker]
  funext edge
  change centralRigidityRate relations position
      (fun vertex ↦ cross rotation (position vertex)) edge = 0
  have relativeRotation :
      relationMotion relations
          (fun vertex ↦ cross rotation (position vertex)) edge =
        cross rotation (relationOffset relations position edge) := by
    simpa only [relationMotion, relationOffset] using
      (cross_sub_right_mechanical rotation
        (position (relations.head edge)) (position (relations.tail edge))).symm
  rw [centralRigidityRate, relativeRotation]
  exact dot3_cross_self_zero _ _

/-- The complete rigid-motion image lies in every central rigidity kernel. -/
theorem rigidMotionSubspace_le_centralRigidity_kernel
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3) :
    rigidMotionSubspace position ≤
      LinearMap.ker (centralRigidityLinearMap relations position) := by
  intro motion inRigidRange
  rcases inRigidRange with ⟨⟨translation, rotation⟩, rfl⟩
  let translationMotion : Vertex → Vec3 := fun _vertex ↦ translation
  let rotationMotion : Vertex → Vec3 :=
    fun vertex ↦ cross rotation (position vertex)
  have decomposition :
      rigidMotionGenerator position (translation, rotation) =
        translationMotion + rotationMotion := by
    rfl
  rw [decomposition, LinearMap.mem_ker, LinearMap.map_add]
  have translationZero := LinearMap.mem_ker.mp
    (centralRigidity_translation_in_kernel relations position translation)
  have rotationZero := LinearMap.mem_ker.mp
    (centralRigidity_infinitesimal_rotation_in_kernel relations position rotation)
  rw [translationZero, rotationZero, add_zero]

/-- Observability is equivalently the absence of non-rigid kernel motions. -/
theorem mechanicallyObservable_iff_every_kernel_motion_rigid
    {Vertex Edge : Type*}
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3) :
    MechanicallyObservable relations position ↔
      ∀ motion : Vertex → Vec3,
        centralRigidityLinearMap relations position motion = 0 →
          motion ∈ rigidMotionSubspace position := by
  constructor
  · intro observable motion inKernel
    rw [← observable]
    exact inKernel
  · intro everyKernelMotionIsRigid
    apply le_antisymm
    · intro motion inKernel
      exact everyKernelMotionIsRigid motion (LinearMap.mem_ker.mp inKernel)
    · exact rigidMotionSubspace_le_centralRigidity_kernel relations position

/-!
The following rational tetrahedron is a selected exact configuration.  Its
four packet positions are affinely independent and all six unordered pairs are
present.  The proof below derives a rigid-motion witness directly from the six
defined relation equations; it does not take a rank or nullity premise.
-/

/-- Exact rational positions of the selected unit tetrahedron. -/
def rationalTetraPosition : Fin 4 → Vec3 :=
  ![![0, 0, 0], ![1, 0, 0], ![0, 1, 0], ![0, 0, 1]]

/-- All six central relations of the selected rational tetrahedron. -/
def rationalTetraRelations : RelationEndpoints (Fin 4) (Fin 6) where
  tail := ![0, 0, 0, 1, 1, 2]
  head := ![1, 2, 3, 2, 3, 3]

/-- The selected rational K4 tetrahedron has no non-rigid kernel motion. -/
theorem rationalTetraK4_mechanicallyObservable :
    MechanicallyObservable rationalTetraRelations rationalTetraPosition := by
  rw [mechanicallyObservable_iff_every_kernel_motion_rigid]
  intro motion inKernel
  change centralRigidityOperator rationalTetraRelations rationalTetraPosition
    motion = 0 at inKernel
  have edge01 := congrFun inKernel 0
  have edge02 := congrFun inKernel 1
  have edge03 := congrFun inKernel 2
  have edge12 := congrFun inKernel 3
  have edge13 := congrFun inKernel 4
  have edge23 := congrFun inKernel 5
  simp [centralRigidityOperator, centralRigidityRate, relationOffset,
    relationMotion, rationalTetraRelations, rationalTetraPosition, dot3,
    Fin.sum_univ_succ] at edge01 edge02 edge03 edge12 edge13 edge23
  let rotation : Vec3 :=
    ![motion 2 2 - motion 0 2,
      -(motion 1 2 - motion 0 2),
      motion 1 1 - motion 0 1]
  refine ⟨(motion 0, rotation), ?_⟩
  funext vertex component
  fin_cases vertex <;> fin_cases component <;>
    simp [rigidMotionGenerator, rigidMotionField, rationalTetraPosition,
      rotation, cross] <;> linarith

/-- The six rigid parameters are independent on the selected tetrahedron. -/
theorem rationalTetra_rigidMotionGenerator_injective :
    Function.Injective (rigidMotionGenerator rationalTetraPosition) := by
  intro left right equalMotion
  rcases left with ⟨leftTranslation, leftRotation⟩
  rcases right with ⟨rightTranslation, rightRotation⟩
  have translationX := congrFun (congrFun equalMotion 0) 0
  have translationY := congrFun (congrFun equalMotion 0) 1
  have translationZ := congrFun (congrFun equalMotion 0) 2
  have rotationX := congrFun (congrFun equalMotion 2) 2
  have rotationY := congrFun (congrFun equalMotion 1) 2
  have rotationZ := congrFun (congrFun equalMotion 1) 1
  simp [rigidMotionGenerator, rigidMotionField, rationalTetraPosition, cross] at translationX translationY translationZ rotationX rotationY rotationZ
  apply Prod.ext
  · funext component
    fin_cases component
    · exact translationX
    · exact translationY
    · exact translationZ
  · funext component
    fin_cases component
    · change leftRotation 0 = rightRotation 0
      linarith
    · change leftRotation 1 = rightRotation 1
      linarith
    · change leftRotation 2 = rightRotation 2
      linarith

/-- The sampled rigid-motion image has exact dimension six for this tetrahedron. -/
theorem rationalTetra_rigidMotionSubspace_finrank :
    Module.finrank ℚ (rigidMotionSubspace rationalTetraPosition) = 6 := by
  change Module.finrank ℚ
    (LinearMap.range (rigidMotionGenerator rationalTetraPosition)) = 6
  have kernelBot :
      LinearMap.ker (rigidMotionGenerator rationalTetraPosition) = ⊥ :=
    LinearMap.ker_eq_bot.mpr rationalTetra_rigidMotionGenerator_injective
  have rankNullity :=
    (rigidMotionGenerator rationalTetraPosition).finrank_range_add_finrank_ker
  have parameterRank : Module.finrank ℚ (Vec3 × Vec3) = 6 := by
    simp [Vec3, Module.finrank_prod, Module.finrank_fintype_fun_eq_card]
  rw [kernelBot] at rankNullity
  simpa only [finrank_bot, add_zero, parameterRank] using rankNullity

/-- The selected K4 rigidity kernel has exact nullity six. -/
theorem rationalTetraK4_kernel_finrank :
    Module.finrank ℚ
        (LinearMap.ker
          (centralRigidityLinearMap rationalTetraRelations rationalTetraPosition)) = 6 := by
  rw [rationalTetraK4_mechanicallyObservable]
  exact rationalTetra_rigidMotionSubspace_finrank

/-- The selected K4 rigidity operator has exact rank six. -/
theorem rationalTetraK4_range_finrank :
    Module.finrank ℚ
        (LinearMap.range
          (centralRigidityLinearMap rationalTetraRelations rationalTetraPosition)) = 6 := by
  have rankNullity :=
    (centralRigidityLinearMap rationalTetraRelations rationalTetraPosition).finrank_range_add_finrank_ker
  have sourceRank : Module.finrank ℚ (Fin 4 → Vec3) = 12 := by
    rw [Module.finrank_pi_fintype]
    norm_num [Vec3, Module.finrank_fintype_fun_eq_card]
  rw [rationalTetraK4_kernel_finrank, sourceRank] at rankNullity
  omega

/-- Five relations obtained by deleting the `(2,3)` tetrahedron relation. -/
def rationalTetraMissingRelation : RelationEndpoints (Fin 4) (Fin 5) where
  tail := ![0, 0, 0, 1, 1]
  head := ![1, 2, 3, 2, 3]

/-- An explicit motion hidden by the underconnected five-relation graph. -/
def rationalTetraMissingRelationFloppyMotion : Fin 4 → Vec3 :=
  ![![0, 0, 0], ![0, 0, 0], ![0, 0, 0], ![0, 1, 0]]

/-- The explicit underconnected motion is in the central-distance kernel. -/
theorem rationalTetraMissingRelation_floppy_in_kernel :
    rationalTetraMissingRelationFloppyMotion ∈
      LinearMap.ker
        (centralRigidityLinearMap rationalTetraMissingRelation
          rationalTetraPosition) := by
  rw [LinearMap.mem_ker]
  funext edge
  fin_cases edge <;>
    simp [centralRigidityLinearMap, centralRigidityOperator,
      centralRigidityRate, relationOffset, relationMotion,
      rationalTetraMissingRelation, rationalTetraMissingRelationFloppyMotion,
      rationalTetraPosition, dot3, Fin.sum_univ_succ]

/-- The explicit underconnected kernel motion is not a sampled rigid motion. -/
theorem rationalTetraMissingRelation_floppy_not_rigid :
    rationalTetraMissingRelationFloppyMotion ∉
      rigidMotionSubspace rationalTetraPosition := by
  intro inRigid
  rcases inRigid with ⟨⟨translation, rotation⟩, rigidEquality⟩
  have atZeroX := congrFun (congrFun rigidEquality 0) 0
  have atZeroY := congrFun (congrFun rigidEquality 0) 1
  have atZeroZ := congrFun (congrFun rigidEquality 0) 2
  have atTwoZ := congrFun (congrFun rigidEquality 2) 2
  have atThreeY := congrFun (congrFun rigidEquality 3) 1
  simp [rigidMotionGenerator, rigidMotionField, rationalTetraPosition,
    rationalTetraMissingRelationFloppyMotion, cross] at atZeroX atZeroY atZeroZ atTwoZ atThreeY
  linarith

/-- The selected underconnected relation graph is not mechanically observable. -/
theorem rationalTetraMissingRelation_not_mechanicallyObservable :
    ¬ MechanicallyObservable rationalTetraMissingRelation rationalTetraPosition := by
  rw [mechanicallyObservable_iff_every_kernel_motion_rigid]
  intro everyKernelMotionRigid
  exact rationalTetraMissingRelation_floppy_not_rigid
    (everyKernelMotionRigid rationalTetraMissingRelationFloppyMotion
      (LinearMap.mem_ker.mp rationalTetraMissingRelation_floppy_in_kernel))

end MLSFormal
