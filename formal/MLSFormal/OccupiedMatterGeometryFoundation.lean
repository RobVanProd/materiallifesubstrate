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

/-- Exact rectangular-parcel witness arithmetic. Half extents (e,e,e) and
(2e,e/2,e) have equal rectangular volume, while the axial point 3e/2 is in
the second box and outside the first. The executable witness separately checks
all unchanged packet centres, positive separation and the serialized state. -/
theorem equal_volume_distinct_box_witness (e : ℝ) (positive : 0 < e) :
    (2*e)*(2*e)*(2*e) = (4*e)*e*(2*e) ∧
    e < 3*e/2 ∧ 3*e/2 ≤ 2*e ∧ 4*e < 8*e := by
  constructor
  · ring
  constructor
  · linarith
  constructor <;> linarith

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

/-- Positive directional increments cannot cancel on a finite segment
partition. The executable input audit supplies cell-matrix positivity; the
construction argument supplies the segment partition, not a floating claim. -/
theorem positive_segment_partition (n : ℕ) (w q : Fin n → ℝ)
    (hw : ∀ i, 0 ≤ w i) (hq : ∀ i, 0 < q i)
    (active : ∃ i, 0 < w i) : 0 < ∑ i, w i * q i := by
  apply Finset.sum_pos'
  · intro i _
    exact mul_nonneg (hw i) (le_of_lt (hq i))
  · obtain ⟨i,hi⟩ := active
    exact ⟨i,Finset.mem_univ i,mul_pos hi (hq i)⟩

/-- Strict monotonicity is a sufficient injectivity certificate. Failure of
this sufficient premise does not imply non-injectivity of a mesh map. -/
theorem monotone_domain_injective (F : Vec → Vec) (domain : Set Vec)
    (strict : ∀ x ∈ domain, ∀ y ∈ domain, x ≠ y →
      0 < dot (y-x) (F y-F x)) : Set.InjOn F domain := by
  intro x hx y hy equal
  by_contra different
  have h := strict x hx y hy different
  rw [equal] at h
  simp [dot] at h

/-- The six weak coordinate orders cover the cube, including ties. Executable
template checks identify each order with its barycentric tetrahedron. -/
theorem cartesian_six_orders (a b c : ℝ) :
    (a ≥ b ∧ b ≥ c) ∨ (a ≥ c ∧ c ≥ b) ∨
    (b ≥ a ∧ a ≥ c) ∨ (b ≥ c ∧ c ≥ a) ∨
    (c ≥ a ∧ a ≥ b) ∨ (c ≥ b ∧ b ≥ a) := by
  rcases le_total b a with hba | hab
  · rcases le_total c b with hcb | hbc
    · exact Or.inl ⟨hba, hcb⟩
    · rcases le_total c a with hca | hac
      · exact Or.inr (Or.inl ⟨hca, hbc⟩)
      · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨hac, hba⟩))))
  · rcases le_total c a with hca | hac
    · exact Or.inr (Or.inr (Or.inl ⟨hab, hca⟩))
    · rcases le_total c b with hcb | hbc
      · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨hcb, hac⟩)))
      · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr ⟨hbc, hab⟩))))

/-- Nonnegative barycentric weights and exact reconstruction for a sorted
unit-cube coordinate triple. No floating arithmetic is involved. -/
theorem cartesian_chain_weights (a b c : ℝ)
    (ha : a ≤ 1) (hab : b ≤ a) (hbc : c ≤ b) (hc : 0 ≤ c) :
    0 ≤ 1-a ∧ 0 ≤ a-b ∧ 0 ≤ b-c ∧ 0 ≤ c ∧
    (1-a)+(a-b)+(b-c)+c = 1 ∧
    (a-b)+(b-c)+c = a ∧ (b-c)+c = b := by
  constructor
  · linarith
  constructor
  · linarith
  constructor
  · linarith
  exact ⟨hc, by ring, by ring, by ring⟩

/-- Distinct strict coordinate orders contain an inversion, checked over the
six finite permutations in the template certificate. -/
theorem cartesian_strict_inversion (a b : ℝ) (hab : a < b) : ¬ b < a := by
  exact not_lt_of_ge (le_of_lt hab)

/-- Different integer unit cells have disjoint interiors in a differing axis.
The finite grid checker supplies the distinct integer cell coordinates. -/
theorem cartesian_separated_cells (i j : ℤ) (hij : i < j) (x : ℝ)
    (hx : x < (i : ℝ)+1) : ¬ (j : ℝ) < x := by
  have step : i+1 ≤ j := hij
  have stepReal : (i : ℝ)+1 ≤ (j : ℝ) := by exact_mod_cast step
  linarith

end MLSFormal.OccupiedGeometry

#print axioms MLSFormal.OccupiedGeometry.missing_information
#print axioms MLSFormal.OccupiedGeometry.equal_volume_distinct_box_witness
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
#print axioms MLSFormal.OccupiedGeometry.positive_segment_partition
#print axioms MLSFormal.OccupiedGeometry.monotone_domain_injective
#print axioms MLSFormal.OccupiedGeometry.cartesian_six_orders
#print axioms MLSFormal.OccupiedGeometry.cartesian_chain_weights
#print axioms MLSFormal.OccupiedGeometry.cartesian_strict_inversion
#print axioms MLSFormal.OccupiedGeometry.cartesian_separated_cells
