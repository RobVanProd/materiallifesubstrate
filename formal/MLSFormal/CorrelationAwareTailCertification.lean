import MLSFormal.BoundedPhaseTailCertification
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Tactic.Ring
import Mathlib.Tactic.Linarith

set_option autoImplicit false
namespace MLSFormal

/-- This applies to an affine map in particular. Neither the center nor the
candidate is required to be the target point. -/
theorem correlatedTail_image_inclusion {α β : Type*} (f : α → β)
    (target : α) (enclosure : Set α) (h : target ∈ enclosure) :
    f target ∈ f '' enclosure := ⟨target, h, rfl⟩

/-- Shared noise cancels; replacing the two occurrences by independent noise
would not establish this identity. -/
theorem correlatedTail_shared_subtraction (c d g eta : ℚ) :
    (c + g * eta) - (d + g * eta) = c - d := by ring

/-- Closed bisection children cover the entire parent, including their common
midpoint. A verifier must keep both children. -/
theorem correlatedTail_bisection_coverage (lo hi mid eta : ℚ)
    (hlo : lo ≤ eta) (hhi : eta ≤ hi) :
    (lo ≤ eta ∧ eta ≤ mid) ∨ (mid ≤ eta ∧ eta ≤ hi) := by
  rcases le_total eta mid with h | h
  · exact Or.inl ⟨hlo, h⟩
  · exact Or.inr ⟨h, hhi⟩

/-- Scalar component form of a fixed-coefficient kick-drift-kick stage.
The force-cell certification is a separate executable obligation. -/
theorem correlatedTail_fixed_scalar_kdk (x p a b t : ℚ) :
    (x + t * (p + a*x), (p + a*x) + b*(x + t*(p + a*x))) =
    ((1+t*a)*x+t*p, (a+b+b*t*a)*x+(1+b*t)*p) := by
  apply Prod.ext <;> dsimp <;> ring

/-- Induction carries inclusion through a union of branch cells. The local
hypothesis must produce a child for every point, not just a nominal trace. -/
theorem correlatedTail_branch_induction {α ι : Type*} (target : ℕ → α)
    (step : ℕ → α → α) (cells : ℕ → ι → Set α)
    (initial : ∃ i, target 0 ∈ cells 0 i)
    (recurrence : ∀ n, target (n+1) = step n (target n))
    (coverage : ∀ n i x, x ∈ cells n i → ∃ j, step n x ∈ cells (n+1) j) :
    ∀ n, ∃ i, target n ∈ cells n i := by
  intro n
  induction n with
  | zero => exact initial
  | succ n ih =>
    obtain ⟨i, hi⟩ := ih
    rw [recurrence]
    exact coverage n i (target n) hi

/-- Signed weighted observations retain a common affine dependency. No
absolute value is inserted before the common coefficient is summed. -/
theorem correlatedTail_signed_affine_sum {ι : Type*} (s : Finset ι)
    (w c g : ι → ℚ) (eta : ℚ) :
    (∑ i ∈ s, w i * (c i + g i * eta)) =
    (∑ i ∈ s, w i * c i) + (∑ i ∈ s, w i * g i) * eta := by
  simp only [mul_add, Finset.sum_add_distrib, Finset.sum_mul, mul_assoc]

/-- Replacing a nominal center leaves the represented value unchanged only
when its exact offset is retained. -/
theorem correlatedTail_recenter (center replacement residual : ℚ) :
    replacement + ((center - replacement) + residual) = center + residual := by ring

/-- A containing interval inside the candidate-centered budget proves the
requested bound. This does not infer a bound from a measured error ratio. -/
theorem correlatedTail_budget_slack (target candidate lo hi budget : ℝ)
    (containsLo : lo ≤ target) (containsHi : target ≤ hi)
    (budgetLo : candidate - budget ≤ lo) (budgetHi : hi ≤ candidate + budget) :
    |candidate - target| ≤ budget := by
  apply abs_le.mpr
  constructor <;> linarith

/-- Bound a signed numerator after common coefficients have been combined.
This keeps cancellation in G rather than summing absolute sample slopes. -/
theorem correlatedTail_signed_numerator_envelope (c g eta residual radius : ℝ)
    (noise : |eta| ≤ 1) (remainder : |residual| ≤ radius) :
    |(c + g * eta + residual) - c| ≤ |g| + radius := by
  have hmul : |g * eta| ≤ |g| := by
    rw [abs_mul]
    calc
      |g| * |eta| ≤ |g| * 1 := mul_le_mul_of_nonneg_left noise (abs_nonneg g)
      _ = |g| := mul_one _
  have h : (c + g * eta + residual) - c = g * eta + residual := by ring
  rw [h]
  exact le_trans (abs_add_le _ _) (add_le_add hmul remainder)

end MLSFormal
