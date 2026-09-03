import MLSFormal.ExplicitFractionalPhaseState
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

/-!
# Exact accounting for a bounded approximate pair kick

These identities model endpoint update errors over exact rational vectors. They
give an interpretation for measured momentum, orbital-angular-momentum, and
centrality residuals, but make no statement about MPFR, rounding modes, or
floating-point error bounds.
-/

/-- Stored first-endpoint momentum after an ideal impulse and its endpoint
update error. -/
def approximatePairKickFirstMomentum
    (momentum idealImpulse endpointError : Vec3) : Vec3 :=
  momentum + idealImpulse + endpointError

/-- Stored second-endpoint momentum after the opposite ideal impulse and its
independently rounded endpoint update. -/
def approximatePairKickSecondMomentum
    (momentum idealImpulse endpointError : Vec3) : Vec3 :=
  momentum - idealImpulse + endpointError

/-- Independent endpoint update errors account exactly for the total-momentum
change of an approximate pair kick. -/
theorem approximatePairKick_totalMomentum_delta
    (firstMomentum secondMomentum idealImpulse
      firstError secondError : Vec3) :
    (approximatePairKickFirstMomentum
          firstMomentum idealImpulse firstError +
        approximatePairKickSecondMomentum
          secondMomentum idealImpulse secondError) -
      (firstMomentum + secondMomentum) =
        firstError + secondError := by
  funext axis
  simp [approximatePairKickFirstMomentum,
    approximatePairKickSecondMomentum]
  ring

/-- The orbital-angular-momentum change splits exactly into the ideal
centrality term and the two endpoint rounding-error moments. -/
theorem approximatePairKick_orbitalAngular_delta
    (firstPosition secondPosition firstMomentum secondMomentum idealImpulse
      firstError secondError : Vec3) :
    (orbitalAngularMomentum firstPosition
          (approximatePairKickFirstMomentum
            firstMomentum idealImpulse firstError) +
        orbitalAngularMomentum secondPosition
          (approximatePairKickSecondMomentum
            secondMomentum idealImpulse secondError)) -
      (orbitalAngularMomentum firstPosition firstMomentum +
        orbitalAngularMomentum secondPosition secondMomentum) =
      cross (firstPosition - secondPosition) idealImpulse +
        cross firstPosition firstError + cross secondPosition secondError := by
  funext component
  fin_cases component <;>
    simp [approximatePairKickFirstMomentum,
      approximatePairKickSecondMomentum, orbitalAngularMomentum, cross] <;>
    ring

/-- If the ideal impulse is central, only the endpoint update errors remain in
the exact angular-momentum accounting. -/
theorem centralIdealApproximatePairKick_orbitalAngular_delta
    (firstPosition secondPosition firstMomentum secondMomentum idealImpulse
      firstError secondError : Vec3)
    (idealCentral :
      cross (firstPosition - secondPosition) idealImpulse = 0) :
    (orbitalAngularMomentum firstPosition
          (approximatePairKickFirstMomentum
            firstMomentum idealImpulse firstError) +
        orbitalAngularMomentum secondPosition
          (approximatePairKickSecondMomentum
            secondMomentum idealImpulse secondError)) -
      (orbitalAngularMomentum firstPosition firstMomentum +
        orbitalAngularMomentum secondPosition secondMomentum) =
      cross firstPosition firstError + cross secondPosition secondError := by
  rw [approximatePairKick_orbitalAngular_delta, idealCentral]
  simp

/-- Opposite endpoint update errors preserve total momentum exactly. -/
theorem oppositeEndpointErrors_preserve_totalMomentum
    (firstMomentum secondMomentum idealImpulse endpointError : Vec3) :
    approximatePairKickFirstMomentum
          firstMomentum idealImpulse endpointError +
        approximatePairKickSecondMomentum
          secondMomentum idealImpulse (-endpointError) =
      firstMomentum + secondMomentum := by
  apply sub_eq_zero.mp
  rw [approximatePairKick_totalMomentum_delta]
  simp

/-- For an ideal central kick with opposite endpoint errors, the complete
angular defect is the moment of the first endpoint error about the relative
position. -/
theorem centralIdealOppositeEndpointErrors_orbitalAngular_delta
    (firstPosition secondPosition firstMomentum secondMomentum idealImpulse
      endpointError : Vec3)
    (idealCentral :
      cross (firstPosition - secondPosition) idealImpulse = 0) :
    (orbitalAngularMomentum firstPosition
          (approximatePairKickFirstMomentum
            firstMomentum idealImpulse endpointError) +
        orbitalAngularMomentum secondPosition
          (approximatePairKickSecondMomentum
            secondMomentum idealImpulse (-endpointError))) -
      (orbitalAngularMomentum firstPosition firstMomentum +
        orbitalAngularMomentum secondPosition secondMomentum) =
      cross (firstPosition - secondPosition) endpointError := by
  rw [centralIdealApproximatePairKick_orbitalAngular_delta
    firstPosition secondPosition firstMomentum secondMomentum idealImpulse
      endpointError (-endpointError) idealCentral]
  funext component
  fin_cases component <;> simp [cross] <;> ring

/-- Writing one stored approximate impulse as `J + epsilon` and applying it
with exactly opposite signs preserves total momentum, while a central ideal
`J` leaves precisely the angular defect `r cross epsilon`. -/
theorem centralIdealEqualOppositeApproximateImpulse_accounting
    (firstPosition secondPosition firstMomentum secondMomentum
      idealImpulse impulseError : Vec3)
    (idealCentral :
      cross (firstPosition - secondPosition) idealImpulse = 0) :
    ((firstMomentum + (idealImpulse + impulseError)) +
          (secondMomentum - (idealImpulse + impulseError)) =
        firstMomentum + secondMomentum) ∧
      ((orbitalAngularMomentum firstPosition
            (firstMomentum + (idealImpulse + impulseError)) +
          orbitalAngularMomentum secondPosition
            (secondMomentum - (idealImpulse + impulseError))) -
        (orbitalAngularMomentum firstPosition firstMomentum +
          orbitalAngularMomentum secondPosition secondMomentum) =
        cross (firstPosition - secondPosition) impulseError) := by
  constructor
  · exact exactQuantizedPairImpulse_preserves_momentum
      firstMomentum secondMomentum (idealImpulse + impulseError)
  · calc
      (orbitalAngularMomentum firstPosition
              (firstMomentum + (idealImpulse + impulseError)) +
            orbitalAngularMomentum secondPosition
              (secondMomentum - (idealImpulse + impulseError))) -
          (orbitalAngularMomentum firstPosition firstMomentum +
            orbitalAngularMomentum secondPosition secondMomentum) =
          cross (firstPosition - secondPosition)
            (idealImpulse + impulseError) :=
        pairImpulse_orbitalAngular_delta firstPosition secondPosition
          firstMomentum secondMomentum (idealImpulse + impulseError)
      _ = cross (firstPosition - secondPosition) idealImpulse +
            cross (firstPosition - secondPosition) impulseError := by
        funext component
        fin_cases component <;> simp [cross] <;> ring
      _ = cross (firstPosition - secondPosition) impulseError := by
        rw [idealCentral]
        simp

/-- For a stored drift equal to an ideal displacement plus a position update
error, the exact orbital-angular-momentum change splits into the ideal drift
moment and the error moment. -/
theorem approximateDrift_orbitalAngular_delta
    (position momentum idealDisplacement positionError : Vec3) :
    orbitalAngularMomentum
          (position + idealDisplacement + positionError) momentum -
        orbitalAngularMomentum position momentum =
      cross idealDisplacement momentum + cross positionError momentum := by
  funext component
  fin_cases component <;>
    simp [orbitalAngularMomentum, cross] <;>
    ring

/-- If the ideal force-free displacement is parallel to momentum, the stored
position error accounts for the complete orbital-angular-momentum change. -/
theorem parallelIdealApproximateDrift_orbitalAngular_delta
    (position momentum idealDisplacement positionError : Vec3)
    (idealParallel : cross idealDisplacement momentum = 0) :
    orbitalAngularMomentum
          (position + idealDisplacement + positionError) momentum -
        orbitalAngularMomentum position momentum =
      cross positionError momentum := by
  rw [approximateDrift_orbitalAngular_delta, idealParallel]
  simp

end MLSFormal
