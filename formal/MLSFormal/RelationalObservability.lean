import MLSFormal.MechanicalObservability
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

/-!
# Relational observability confirmation

This module leaves the accepted central-distance representation in
`MechanicalObservability` unchanged.  It proves two representation-level
contracts needed by the bounded Candidate-C confirmation:

* packet identifiers are labels, so consistently relabeling vertices by a
  bijection preserves the actual rigidity operator, its kernel, the rigid
  subspace, and mechanical observability; and
* central-distance observations transform objectively under finite spatial
  similarities.  Squared lengths scale by `s²`, the unnormalised exact-rational
  rigidity row scales by `s`, and its zero set is unchanged for `s ≠ 0`.

There is no force, stiffness, constitutive response, rank premise, numerical
gauge, or stabilization in this module.
-/

/-! ## Vertex-label bijection invariance -/

/-- Consistently replace every stored relation endpoint by a bijective label. -/
def relabelRelationEndpoints
    {Vertex RenamedVertex Edge : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (relations : RelationEndpoints Vertex Edge) :
    RelationEndpoints RenamedVertex Edge where
  tail := fun edge ↦ rename (relations.tail edge)
  head := fun edge ↦ rename (relations.head edge)

/-- Pull a vertex field through the inverse label bijection. -/
def relabelVertexField
    {Vertex RenamedVertex Value : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (field : Vertex → Value) : RenamedVertex → Value :=
  fun renamedVertex ↦ field (rename.symm renamedVertex)

/-- Relabeling and then evaluating at the corresponding new label recovers the
original field value exactly. -/
theorem relabelVertexField_apply_rename
    {Vertex RenamedVertex Value : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (field : Vertex → Value)
    (vertex : Vertex) :
    relabelVertexField rename field (rename vertex) = field vertex := by
  simp [relabelVertexField]

/-- A consistently relabeled relation has the exact same directed offset. -/
theorem relationOffset_vertex_relabel
    {Vertex RenamedVertex Edge : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (edge : Edge) :
    relationOffset (relabelRelationEndpoints rename relations)
        (relabelVertexField rename position) edge =
      relationOffset relations position edge := by
  simp [relationOffset, relabelRelationEndpoints, relabelVertexField]

/-- Relative motion is independent of the chosen packet labels. -/
theorem relationMotion_vertex_relabel
    {Vertex RenamedVertex Edge : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (relations : RelationEndpoints Vertex Edge)
    (motion : Vertex → Vec3)
    (edge : Edge) :
    relationMotion (relabelRelationEndpoints rename relations)
        (relabelVertexField rename motion) edge =
      relationMotion relations motion edge := by
  simp [relationMotion, relabelRelationEndpoints, relabelVertexField]

/-- Actual squared relation lengths are vertex-label invariant. -/
theorem relationSquaredLength_vertex_relabel
    {Vertex RenamedVertex Edge : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (edge : Edge) :
    relationSquaredLength (relabelRelationEndpoints rename relations)
        (relabelVertexField rename position) edge =
      relationSquaredLength relations position edge := by
  rw [relationSquaredLength, relationOffset_vertex_relabel]

/-- Every exact central-distance row is vertex-label invariant. -/
theorem centralRigidityRate_vertex_relabel
    {Vertex RenamedVertex Edge : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3)
    (edge : Edge) :
    centralRigidityRate (relabelRelationEndpoints rename relations)
        (relabelVertexField rename position)
        (relabelVertexField rename motion) edge =
      centralRigidityRate relations position motion edge := by
  rw [centralRigidityRate, relationOffset_vertex_relabel,
    relationMotion_vertex_relabel]

/-- The complete finite rigidity operator is unchanged by packet-ID renaming. -/
theorem centralRigidityOperator_vertex_relabel
    {Vertex RenamedVertex Edge : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3) :
    centralRigidityOperator (relabelRelationEndpoints rename relations)
        (relabelVertexField rename position)
        (relabelVertexField rename motion) =
      centralRigidityOperator relations position motion := by
  funext edge
  exact centralRigidityRate_vertex_relabel rename relations position motion edge

/-- The explicit matrix coefficient at corresponding vertex/axis degrees is
identical after a label bijection. -/
theorem centralRigidityMatrix_vertex_relabel
    {Vertex RenamedVertex Edge : Type*}
    [DecidableEq Vertex] [DecidableEq RenamedVertex]
    (rename : Vertex ≃ RenamedVertex)
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (edge : Edge) (vertex : Vertex) (axis : Fin 3) :
    centralRigidityMatrix (relabelRelationEndpoints rename relations)
        (relabelVertexField rename position) edge (rename vertex, axis) =
      centralRigidityMatrix relations position edge (vertex, axis) := by
  simp [centralRigidityMatrix, relationOffset_vertex_relabel,
    relabelRelationEndpoints]

/-- Corresponding motions have exactly equivalent kernel membership. -/
theorem centralRigidity_kernel_vertex_relabel_iff
    {Vertex RenamedVertex Edge : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3) :
    relabelVertexField rename motion ∈
        LinearMap.ker
          (centralRigidityLinearMap
            (relabelRelationEndpoints rename relations)
            (relabelVertexField rename position)) ↔
      motion ∈ LinearMap.ker
        (centralRigidityLinearMap relations position) := by
  simp only [LinearMap.mem_ker]
  change
    centralRigidityOperator (relabelRelationEndpoints rename relations)
        (relabelVertexField rename position)
        (relabelVertexField rename motion) = 0 ↔
      centralRigidityOperator relations position motion = 0
  rw [centralRigidityOperator_vertex_relabel]

/-- Relabeling carries the sampled rigid-motion subspace bijectively. -/
theorem relabelVertexField_mem_rigidMotionSubspace_iff
    {Vertex RenamedVertex : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (position motion : Vertex → Vec3) :
    relabelVertexField rename motion ∈
        rigidMotionSubspace (relabelVertexField rename position) ↔
      motion ∈ rigidMotionSubspace position := by
  constructor
  · rintro ⟨parameters, rigidEquality⟩
    refine ⟨parameters, ?_⟩
    funext vertex axis
    have atRenamedVertex :=
      congrFun (congrFun rigidEquality (rename vertex)) axis
    simpa [rigidMotionGenerator, rigidMotionField, relabelVertexField] using
      atRenamedVertex
  · rintro ⟨parameters, rigidEquality⟩
    refine ⟨parameters, ?_⟩
    funext renamedVertex axis
    have atOriginalVertex :=
      congrFun (congrFun rigidEquality (rename.symm renamedVertex)) axis
    simpa [rigidMotionGenerator, rigidMotionField, relabelVertexField] using
      atOriginalVertex

/-- Mechanical observability is a property of geometry/topology, never of the
chosen packet-ID names. -/
theorem mechanicallyObservable_vertex_relabel_iff
    {Vertex RenamedVertex Edge : Type*}
    (rename : Vertex ≃ RenamedVertex)
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3) :
    MechanicallyObservable (relabelRelationEndpoints rename relations)
        (relabelVertexField rename position) ↔
      MechanicallyObservable relations position := by
  rw [mechanicallyObservable_iff_every_kernel_motion_rigid,
    mechanicallyObservable_iff_every_kernel_motion_rigid]
  constructor
  · intro relabeledObservable motion motionKernel
    have relabeledKernel :
        centralRigidityLinearMap
            (relabelRelationEndpoints rename relations)
            (relabelVertexField rename position)
            (relabelVertexField rename motion) = 0 := by
      change
        centralRigidityOperator (relabelRelationEndpoints rename relations)
            (relabelVertexField rename position)
            (relabelVertexField rename motion) = 0
      rw [centralRigidityOperator_vertex_relabel]
      exact motionKernel
    exact (relabelVertexField_mem_rigidMotionSubspace_iff rename position motion).mp
      (relabeledObservable (relabelVertexField rename motion) relabeledKernel)
  · intro originalObservable relabeledMotion relabeledKernel
    let originalMotion : Vertex → Vec3 :=
      fun vertex ↦ relabeledMotion (rename vertex)
    have relabelRoundTrip :
        relabelVertexField rename originalMotion = relabeledMotion := by
      funext renamedVertex
      simp [relabelVertexField, originalMotion]
    have originalKernel :
        centralRigidityLinearMap relations position originalMotion = 0 := by
      change centralRigidityOperator relations position originalMotion = 0
      rw [← centralRigidityOperator_vertex_relabel rename relations position
        originalMotion, relabelRoundTrip]
      exact relabeledKernel
    have originalRigid := originalObservable originalMotion originalKernel
    have relabeledRigid :=
      (relabelVertexField_mem_rigidMotionSubspace_iff rename position
        originalMotion).mpr originalRigid
    rwa [relabelRoundTrip] at relabeledRigid

/-! ## Exact finite similarity and objectivity -/

/-- A three-dimensional rational similarity `x' = s Q x + t`. -/
structure CentralSimilarity3 where
  scale : ℚ
  rotation : Matrix (Fin 3) (Fin 3) ℚ
  translation : Vec3

/-- Matrix action on one exact three-vector. -/
def rotateVec3
    (rotation : Matrix (Fin 3) (Fin 3) ℚ)
    (vector : Vec3) : Vec3 :=
  rotation *ᵥ vector

/-- Orthogonality contract for an exact rational three-dimensional action. -/
def CentralOrthogonal3
    (rotation : Matrix (Fin 3) (Fin 3) ℚ) : Prop :=
  rotation.transpose * rotation = 1

/-- Transform packet positions by a finite spatial similarity. -/
def transformCentralPosition
    {Vertex : Type*}
    (similarity : CentralSimilarity3)
    (position : Vertex → Vec3) : Vertex → Vec3 :=
  fun vertex ↦ similarity.scale •
      rotateVec3 similarity.rotation (position vertex) +
    similarity.translation

/-- Rotate a motion field without silently rescaling its physical units. -/
def rotateCentralMotion
    {Vertex : Type*}
    (rotation : Matrix (Fin 3) (Fin 3) ℚ)
    (motion : Vertex → Vec3) : Vertex → Vec3 :=
  fun vertex ↦ rotateVec3 rotation (motion vertex)

private theorem dot3_rotateVec3_formula
    (rotation : Matrix (Fin 3) (Fin 3) ℚ)
    (left right : Vec3) :
    dot3 (rotateVec3 rotation left) (rotateVec3 rotation right) =
      dot3 left ((rotation.transpose * rotation) *ᵥ right) := by
  change
    (rotation *ᵥ left) ⬝ᵥ (rotation *ᵥ right) =
      left ⬝ᵥ ((rotation.transpose * rotation) *ᵥ right)
  calc
    (rotation *ᵥ left) ⬝ᵥ (rotation *ᵥ right) =
        (rotation *ᵥ right) ⬝ᵥ (rotation *ᵥ left) :=
      dotProduct_comm _ _
    _ = left ⬝ᵥ rotation.transpose *ᵥ (rotation *ᵥ right) :=
      (Matrix.dotProduct_transpose_mulVec rotation left
        (rotation *ᵥ right)).symm
    _ = left ⬝ᵥ ((rotation.transpose * rotation) *ᵥ right) := by
      rw [Matrix.mulVec_mulVec]

/-- An orthogonal matrix preserves the exact three-dimensional dot product. -/
theorem centralOrthogonal3_preserves_dot3
    (rotation : Matrix (Fin 3) (Fin 3) ℚ)
    (orthogonal : CentralOrthogonal3 rotation)
    (left right : Vec3) :
    dot3 (rotateVec3 rotation left) (rotateVec3 rotation right) =
      dot3 left right := by
  rw [dot3_rotateVec3_formula, orthogonal]
  simp [dot3]

private theorem dot3_smul_both_relational
    (scale : ℚ) (left right : Vec3) :
    dot3 (scale • left) (scale • right) = scale ^ 2 * dot3 left right := by
  simp only [dot3, Pi.smul_apply, smul_eq_mul, pow_two]
  rw [Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro axis _
  ring

private theorem dot3_smul_left_relational
    (scale : ℚ) (left right : Vec3) :
    dot3 (scale • left) right = scale * dot3 left right := by
  simp [dot3, Finset.mul_sum, mul_assoc]

/-- Similarity translation cancels, leaving a scaled rotated relation offset. -/
theorem relationOffset_similarity
    {Vertex Edge : Type*}
    (similarity : CentralSimilarity3)
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (edge : Edge) :
    relationOffset relations (transformCentralPosition similarity position) edge =
      similarity.scale •
        rotateVec3 similarity.rotation
          (relationOffset relations position edge) := by
  funext axis
  simp [relationOffset, transformCentralPosition, rotateVec3,
    Matrix.mulVec, dotProduct, Fin.sum_univ_succ]
  ring

/-- Relative motion rotates covariantly and is independent of translation. -/
theorem relationMotion_rotation
    {Vertex Edge : Type*}
    (rotation : Matrix (Fin 3) (Fin 3) ℚ)
    (relations : RelationEndpoints Vertex Edge)
    (motion : Vertex → Vec3)
    (edge : Edge) :
    relationMotion relations (rotateCentralMotion rotation motion) edge =
      rotateVec3 rotation (relationMotion relations motion edge) := by
  funext axis
  simp [relationMotion, rotateCentralMotion, rotateVec3,
    Matrix.mulVec, dotProduct, Fin.sum_univ_succ]
  ring

/-- Finite squared central distances scale exactly by `s²`.  At `s = 1` this
is the finite rigid-translation/rotation objectivity contract. -/
theorem relationSquaredLength_similarity
    {Vertex Edge : Type*}
    (similarity : CentralSimilarity3)
    (orthogonal : CentralOrthogonal3 similarity.rotation)
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (edge : Edge) :
    relationSquaredLength relations
        (transformCentralPosition similarity position) edge =
      similarity.scale ^ 2 *
        relationSquaredLength relations position edge := by
  rw [relationSquaredLength, relationOffset_similarity,
    dot3_smul_both_relational,
    centralOrthogonal3_preserves_dot3 similarity.rotation orthogonal,
    relationSquaredLength]

/-- With motion units unchanged, an exact central rigidity row scales by `s`. -/
theorem centralRigidityRate_similarity
    {Vertex Edge : Type*}
    (similarity : CentralSimilarity3)
    (orthogonal : CentralOrthogonal3 similarity.rotation)
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3)
    (edge : Edge) :
    centralRigidityRate relations
        (transformCentralPosition similarity position)
        (rotateCentralMotion similarity.rotation motion) edge =
      similarity.scale *
        centralRigidityRate relations position motion edge := by
  rw [centralRigidityRate, relationOffset_similarity, relationMotion_rotation,
    dot3_smul_left_relational,
    centralOrthogonal3_preserves_dot3 similarity.rotation orthogonal,
    centralRigidityRate]

/-- The complete rigidity operator obeys the same explicit similarity law. -/
theorem centralRigidityOperator_similarity
    {Vertex Edge : Type*}
    (similarity : CentralSimilarity3)
    (orthogonal : CentralOrthogonal3 similarity.rotation)
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3) :
    centralRigidityOperator relations
        (transformCentralPosition similarity position)
        (rotateCentralMotion similarity.rotation motion) =
      similarity.scale • centralRigidityOperator relations position motion := by
  funext edge
  change
    centralRigidityRate relations
        (transformCentralPosition similarity position)
        (rotateCentralMotion similarity.rotation motion) edge =
      similarity.scale * centralRigidityRate relations position motion edge
  exact centralRigidityRate_similarity similarity orthogonal relations position
    motion edge

/-- A nonzero spatial scale preserves exactly which corresponding motions are
hidden by the central-distance representation. -/
theorem centralRigidity_kernel_similarity_iff
    {Vertex Edge : Type*}
    (similarity : CentralSimilarity3)
    (orthogonal : CentralOrthogonal3 similarity.rotation)
    (scaleNonzero : similarity.scale ≠ 0)
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3) :
    rotateCentralMotion similarity.rotation motion ∈
        LinearMap.ker
          (centralRigidityLinearMap relations
            (transformCentralPosition similarity position)) ↔
      motion ∈ LinearMap.ker
        (centralRigidityLinearMap relations position) := by
  simp only [LinearMap.mem_ker]
  change
    centralRigidityOperator relations
        (transformCentralPosition similarity position)
        (rotateCentralMotion similarity.rotation motion) = 0 ↔
      centralRigidityOperator relations position motion = 0
  rw [centralRigidityOperator_similarity similarity orthogonal]
  constructor
  · intro scaledZero
    funext edge
    have atEdge := congrFun scaledZero edge
    change similarity.scale *
      centralRigidityOperator relations position motion edge = 0 at atEdge
    exact (mul_eq_zero.mp atEdge).resolve_left scaleNonzero
  · intro operatorZero
    rw [operatorZero, smul_zero]

/-- Exact finite objectivity under a unit-scale orthogonal motion. -/
theorem relationSquaredLength_rigid_objective
    {Vertex Edge : Type*}
    (rotation : Matrix (Fin 3) (Fin 3) ℚ)
    (translation : Vec3)
    (orthogonal : CentralOrthogonal3 rotation)
    (relations : RelationEndpoints Vertex Edge)
    (position : Vertex → Vec3)
    (edge : Edge) :
    relationSquaredLength relations
        (transformCentralPosition ⟨1, rotation, translation⟩ position) edge =
      relationSquaredLength relations position edge := by
  simpa using relationSquaredLength_similarity
    (similarity := CentralSimilarity3.mk 1 rotation translation)
    orthogonal relations position edge

/-- The exact central rigidity observation is objective under simultaneous
finite rotation/translation of geometry and rotation of motion. -/
theorem centralRigidityOperator_rigid_objective
    {Vertex Edge : Type*}
    (rotation : Matrix (Fin 3) (Fin 3) ℚ)
    (translation : Vec3)
    (orthogonal : CentralOrthogonal3 rotation)
    (relations : RelationEndpoints Vertex Edge)
    (position motion : Vertex → Vec3) :
    centralRigidityOperator relations
        (transformCentralPosition ⟨1, rotation, translation⟩ position)
        (rotateCentralMotion rotation motion) =
      centralRigidityOperator relations position motion := by
  simpa using centralRigidityOperator_similarity
    (similarity := CentralSimilarity3.mk 1 rotation translation)
    orthogonal relations position motion

/-! ## Relabeled exact controls -/

/-- Every bijective packet-ID renaming of the exact rational K4 control remains
mechanically observable, without a numerical rank premise. -/
theorem relabeledRationalTetraK4_mechanicallyObservable
    {RenamedVertex : Type*}
    (rename : Fin 4 ≃ RenamedVertex) :
    MechanicallyObservable
        (relabelRelationEndpoints rename rationalTetraRelations)
        (relabelVertexField rename rationalTetraPosition) := by
  exact (mechanicallyObservable_vertex_relabel_iff rename
    rationalTetraRelations rationalTetraPosition).mpr
      rationalTetraK4_mechanicallyObservable

/-- Every bijective packet-ID renaming of the exact missing-edge control keeps
its explicit non-rigid floppy mode and remains non-observable. -/
theorem relabeledRationalTetraMissingRelation_not_mechanicallyObservable
    {RenamedVertex : Type*}
    (rename : Fin 4 ≃ RenamedVertex) :
    ¬ MechanicallyObservable
        (relabelRelationEndpoints rename rationalTetraMissingRelation)
        (relabelVertexField rename rationalTetraPosition) := by
  intro relabeledObservable
  exact rationalTetraMissingRelation_not_mechanicallyObservable
    ((mechanicallyObservable_vertex_relabel_iff rename
      rationalTetraMissingRelation rationalTetraPosition).mp
        relabeledObservable)

end MLSFormal
