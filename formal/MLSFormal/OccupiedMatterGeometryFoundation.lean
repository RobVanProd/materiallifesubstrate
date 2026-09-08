import MLSFormal.ConservativeForceConsistency
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Algebra.Module.LinearMap.Defs

set_option autoImplicit false
namespace MLSFormal.OccupiedGeometry

/-- A non-injective state encoding cannot uniquely reconstruct every domain.
This does not forbid selecting a new geometry convention. -/
theorem missing_information {Domain State : Type*} (encode : Domain → State)
    (a b : Domain) (same : encode a = encode b) (different : a ≠ b) :
    ¬ ∃ reconstruct : State → Domain, ∀ d, reconstruct (encode d) = d := by
  rintro ⟨reconstruct, correct⟩
  apply different
  calc
    a = reconstruct (encode a) := (correct a).symm
    _ = reconstruct (encode b) := congrArg reconstruct same
    _ = b := correct b

abbrev Vec := Fin 3 → ℝ

def dot (x y : Vec) : ℝ := x 0 * y 0 + x 1 * y 1 + x 2 * y 2
def squared (x : Vec) : ℝ := dot x x
def separationSquared (x y : Vec) : ℝ := squared (x-y)

theorem gap_squared_symmetry (x y : Vec) :
    separationSquared x y = separationSquared y x := by
  simp only [separationSquared, squared, dot, Pi.sub_apply]
  ring

theorem translation (x y b : Vec) :
    separationSquared (x+b) (y+b) = separationSquared x y := by
  simp only [separationSquared, squared, dot, Pi.sub_apply, Pi.add_apply]
  ring

theorem similarity (x y : Vec) (a : ℝ) :
    separationSquared (a • x) (a • y) = a^2 * separationSquared x y := by
  simp only [separationSquared, squared, dot, Pi.sub_apply, Pi.smul_apply,
    smul_eq_mul]
  ring

/-- Orthogonal linear maps preserve squared separation; proper rotations are
a subset. No executable arbitrary-rotation B96 parity is asserted. -/
theorem rotation (R : Vec →ₗ[ℝ] Vec)
    (orthogonal : ∀ v, squared (R v) = squared v) (x y : Vec) :
    separationSquared (R x) (R y) = separationSquared x y := by
  unfold separationSquared
  rw [← R.map_sub, orthogonal]

/-- Shared positive distance gives antisymmetric oriented unit-direction
formulae. Uniqueness and normalization of the underlying closest pair must be
established separately; this does not assign normals at corners. -/
theorem direction_antisymmetry (x y : Vec) (distance : ℝ) :
    (fun j => (x j-y j)/distance) = -(fun j => (y j-x j)/distance) := by
  funext j
  simp only [Pi.neg_apply]
  ring

theorem swept_quadratic (r v : Vec) (t radius : ℝ) :
    squared (r+t • v)-radius^2 =
      squared v*t^2 + 2*dot r v*t + squared r-radius^2 := by
  simp only [squared, dot, Pi.add_apply, Pi.smul_apply, smul_eq_mul]
  ring

theorem convex_vertex_minimum (a b c s t : ℝ) (ha : 0 ≤ a)
    (stationary : 2*a*s+b=0) :
    a*s^2+b*s+c ≤ a*t^2+b*t+c := by
  have h := mul_nonneg ha (sq_nonneg (t-s))
  have hzero := congrArg (fun z : ℝ => z * (t-s)) stationary
  nlinarith

theorem left_endpoint_minimum (a b c t : ℝ)
    (ha : 0 ≤ a) (hb : 0 ≤ b) (ht : 0 ≤ t) :
    c ≤ a*t^2+b*t+c := by
  have h1 := mul_nonneg ha (sq_nonneg t)
  have h2 := mul_nonneg hb ht
  linarith

/-- A certified minimum over the complete interval decides intersection.
It is not enough to check the two endpoints. -/
theorem swept_minimum_criterion (Q : ℝ → ℝ) (h s : ℝ)
    (inside : 0 ≤ s ∧ s ≤ h)
    (minimum : ∀ t, 0 ≤ t → t ≤ h → Q s ≤ Q t) :
    (∃ t, 0 ≤ t ∧ t ≤ h ∧ Q t ≤ 0) ↔ Q s ≤ 0 := by
  constructor
  · rintro ⟨t,ht0,hth,hit⟩
    exact le_trans (minimum t ht0 hth) hit
  · intro hit
    exact ⟨s,inside.1,inside.2,hit⟩

/-- Signed child weights partition the parent's exact encoded inventory.
Geometric validity and physical quadrature errors are separate obligations. -/
theorem weight_partition (w : ℝ) (shares : Fin 8 → ℝ)
    (partition : ∑ i, shares i = 1) : (∑ i, w*shares i) = w := by
  rw [← Finset.mul_sum, partition, mul_one]

end MLSFormal.OccupiedGeometry

#print axioms MLSFormal.OccupiedGeometry.missing_information
#print axioms MLSFormal.OccupiedGeometry.gap_squared_symmetry
#print axioms MLSFormal.OccupiedGeometry.translation
#print axioms MLSFormal.OccupiedGeometry.similarity
#print axioms MLSFormal.OccupiedGeometry.rotation
#print axioms MLSFormal.OccupiedGeometry.direction_antisymmetry
#print axioms MLSFormal.OccupiedGeometry.swept_quadratic
#print axioms MLSFormal.OccupiedGeometry.convex_vertex_minimum
#print axioms MLSFormal.OccupiedGeometry.left_endpoint_minimum
#print axioms MLSFormal.OccupiedGeometry.swept_minimum_criterion
#print axioms MLSFormal.OccupiedGeometry.weight_partition
