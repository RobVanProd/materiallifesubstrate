import MLSFormal.CorrelationAwareTailCertification
import Mathlib.Tactic.Abel

set_option autoImplicit false
namespace MLSFormal

/-- The candidate is arbitrary. This is an error-coordinate identity, not an
assumption that a candidate trace equals the target. Additivity suffices, so
in particular every linear part of an affine stage satisfies the hypothesis. -/
theorem defectTail_identity {V : Type*} [AddCommGroup V]
    (A : V →+ V) (b target candidate targetNext candidateNext : V)
    (step : targetNext = A target + b) :
    targetNext - candidateNext =
      A (target - candidate) + ((A candidate + b) - candidateNext) := by
  rw [step, map_sub]
  abel

/-- An outward enclosure of the image plus the exact stage defect encloses
the next true error; no candidate-exactness hypothesis is present. -/
theorem defectTail_enclosure_step {V : Type*} [AddCommGroup V]
    (A : V →+ V) (b target candidate targetNext candidateNext : V)
    (E nextE : Set V) (step : targetNext = A target + b)
    (inside : target - candidate ∈ E)
    (outward : ∀ e ∈ E, A e + ((A candidate + b) - candidateNext) ∈ nextE) :
    targetNext - candidateNext ∈ nextE := by
  rw [defectTail_identity A b target candidate targetNext candidateNext step]
  exact outward _ inside

/-- Finite prefixes follow from this stage induction. A KDK step is three
successive affine stages, conditioned on independently certified force cells. -/
theorem defectTail_sequence {V : Type*} [AddCommGroup V]
    (A : ℕ → V →+ V) (b target candidate : ℕ → V) (E : ℕ → Set V)
    (initial : target 0 - candidate 0 ∈ E 0)
    (steps : ∀ n, target (n+1) = A n (target n) + b n)
    (outward : ∀ n e, e ∈ E n →
      A n e + ((A n (candidate n) + b n) - candidate (n+1)) ∈ E (n+1)) :
    ∀ n, target n - candidate n ∈ E n := by
  intro n
  induction n with
  | zero => exact initial
  | succ n ih =>
    exact defectTail_enclosure_step (A n) (b n) (target n) (candidate n)
      (target (n+1)) (candidate (n+1)) (E n) (E (n+1)) (steps n) ih (outward n)

/-- The streaming observer retains the sign of each weighted sample. -/
theorem defectTail_signed_accumulator (w error sumNext sumNow : ℚ)
    (recurrence : sumNext = sumNow + w * error)
    (lo hi sampleLo sampleHi : ℚ)
    (current : lo ≤ sumNow ∧ sumNow ≤ hi)
    (sample : sampleLo ≤ w * error ∧ w * error ≤ sampleHi) :
    lo + sampleLo ≤ sumNext ∧ sumNext ≤ hi + sampleHi := by
  rw [recurrence]
  exact ⟨add_le_add current.1 sample.1, add_le_add current.2 sample.2⟩

/-- Rounding slack belongs outside the exact image, never inward. -/
theorem defectTail_rounding_slack (value lo hi roundedLo roundedHi : ℚ)
    (inside : lo ≤ value ∧ value ≤ hi)
    (outwardLo : roundedLo ≤ lo) (outwardHi : hi ≤ roundedHi) :
    roundedLo ≤ value ∧ value ≤ roundedHi :=
  ⟨le_trans outwardLo inside.1, le_trans inside.2 outwardHi⟩

end MLSFormal
