import MLSFormal.DefectRecurrenceTailCertification

set_option autoImplicit false
namespace MLSFormal

/-- Oriented incidence observable, with second-minus-first orientation. -/
def relationTail_difference {P E V : Type*} [AddCommGroup V]
    (first second : E → P) : (P → V) →+ (E → V) where
  toFun x a := x (second a) - x (first a)
  map_zero' := by ext a; simp
  map_add' x y := by ext a; simp only [Pi.add_apply]; abel

theorem relationTail_common_mode {P E V : Type*} [AddCommGroup V]
    (first second : E → P) (v : V) :
    relationTail_difference first second (fun _ => v) = 0 := by
  ext a
  exact sub_self v

/-- Translation of position and common boost of velocity vanish identically. -/
theorem relationTail_translation_boost {P E V : Type*} [AddCommGroup V]
    (first second : E → P) (x : P → V) (v : V) :
    relationTail_difference first second (x + fun _ => v) =
      relationTail_difference first second x := by
  rw [map_add, relationTail_common_mode, add_zero]

/-- R is incidence transpose; W is inverse mass; K is the signed endpoint
kick operator INCLUDING duration and fixed rational force coefficients.
For r = R x and s = R (W p), a kick closes on r and s alone. -/
theorem relationTail_kick_closure {X P R : Type*}
    [AddCommGroup X] [AddCommGroup P] [AddCommGroup R]
    (incidence : X →+ R) (inverseMass : P →+ X) (kick : R →+ P)
    (x : X) (p : P) :
    incidence (inverseMass (p + kick (incidence x))) =
      incidence (inverseMass p) + incidence (inverseMass (kick (incidence x))) := by
  rw [map_add, map_add]

/-- A scalar duration map commutes with incidence. This explicit hypothesis
is satisfied by rational scalar multiplication; no smooth force is assumed. -/
theorem relationTail_drift_closure {X R : Type*}
    [AddCommGroup X] [AddCommGroup R]
    (incidence : X →+ R) (durationX : X →+ X) (durationR : R →+ R)
    (commutes : ∀ v, incidence (durationX v) = durationR (incidence v))
    (x v : X) :
    incidence (x + durationX v) = incidence x + durationR (incidence v) := by
  rw [map_add, commutes]

theorem relationTail_observable_error {X R : Type*}
    [AddCommGroup X] [AddCommGroup R] (observe : X →+ R) (target center : X) :
    observe target - observe center = observe (target - center) := by
  rw [map_sub]

/-- Direct observable errors follow the closed recurrence for arbitrary
candidate centers; packet interval subtraction is not an assumption. -/
theorem relationTail_error_induction {R : Type*} [AddCommGroup R]
    (A : ℕ → R →+ R) (b target candidate : ℕ → R) (E : ℕ → Set R)
    (initial : target 0 - candidate 0 ∈ E 0)
    (steps : ∀ n, target (n+1) = A n (target n) + b n)
    (outward : ∀ n e, e ∈ E n →
      A n e + ((A n (candidate n) + b n) - candidate (n+1)) ∈ E (n+1)) :
    ∀ n, target n - candidate n ∈ E n :=
  defectTail_sequence A b target candidate E initial steps outward

/-- The cell is the preimage of an actual single-valued conversion. An
enclosure must lie wholly in it; the candidate is never declared truth. -/
theorem relationTail_unique_cell {R Bits : Type*} (round : R → Bits)
    (target : R) (enclosure : Set R) (bits : Bits)
    (inside : target ∈ enclosure)
    (cell : ∀ v ∈ enclosure, round v = bits) : round target = bits :=
  cell target inside

end MLSFormal
