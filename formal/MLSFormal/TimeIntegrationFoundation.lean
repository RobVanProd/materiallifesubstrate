import MLSFormal.AuthoritativeDriftStateBridge

set_option autoImplicit false

namespace MLSFormal

/-!
# Exact time-integration composition identities

These theorems concern algebraic preservation, signed inverse assumptions, and
atomic rejection only. They do not prove that the finite-lattice KDK map is
symplectic, convergent, accurate, or free of floating-point error.
-/

def Preserves {State Invariant : Type}
    (observable : State → Invariant) (map : State → State) : Prop :=
  ∀ state, observable (map state) = observable state

theorem preserves_comp
    {State Invariant : Type}
    (observable : State → Invariant)
    (first second : State → State)
    (firstPreserves : Preserves observable first)
    (secondPreserves : Preserves observable second) :
    Preserves observable (second ∘ first) := by
  intro state
  simp only [Function.comp_apply]
  rw [secondPreserves, firstPreserves]

def symmetricKDK {State : Type}
    (halfKick drift : State → State) : State → State :=
  halfKick ∘ drift ∘ halfKick

theorem symmetricKDK_preserves
    {State Invariant : Type}
    (observable : State → Invariant)
    (halfKick drift : State → State)
    (kickPreserves : Preserves observable halfKick)
    (driftPreserves : Preserves observable drift) :
    Preserves observable (symmetricKDK halfKick drift) := by
  intro state
  simp only [symmetricKDK, Function.comp_apply]
  rw [kickPreserves, driftPreserves, kickPreserves]

theorem quantizedKDK_preserves_totalMomentum
    {State : Type}
    (totalMomentum : State → Vec3)
    (centralHalfKick directionalDrift : State → State)
    (centralKickMomentum : Preserves totalMomentum centralHalfKick)
    (directionalDriftMomentum : Preserves totalMomentum directionalDrift) :
    Preserves totalMomentum
      (symmetricKDK centralHalfKick directionalDrift) := by
  exact symmetricKDK_preserves totalMomentum centralHalfKick directionalDrift
    centralKickMomentum directionalDriftMomentum

theorem quantizedKDK_preserves_orbitalAngularMomentum
    {State : Type}
    (orbitalAngularMomentumTotal : State → Vec3)
    (centralHalfKick directionalDrift : State → State)
    (centralKickAngular :
      Preserves orbitalAngularMomentumTotal centralHalfKick)
    (directionalDriftAngular :
      Preserves orbitalAngularMomentumTotal directionalDrift) :
    Preserves orbitalAngularMomentumTotal
      (symmetricKDK centralHalfKick directionalDrift) := by
  exact symmetricKDK_preserves orbitalAngularMomentumTotal centralHalfKick
    directionalDrift centralKickAngular directionalDriftAngular

theorem symmetricKDK_signedTime_reversible
    {State : Type}
    (positiveHalfKick negativeHalfKick positiveDrift negativeDrift :
      State → State)
    (kickInverse : Function.LeftInverse negativeHalfKick positiveHalfKick)
    (driftInverse : Function.LeftInverse negativeDrift positiveDrift) :
    Function.LeftInverse
      (symmetricKDK negativeHalfKick negativeDrift)
      (symmetricKDK positiveHalfKick positiveDrift) := by
  intro state
  simp only [symmetricKDK, Function.comp_apply]
  rw [kickInverse, driftInverse, kickInverse]

def atomicCandidate {State : Type}
    (accepted : Bool) (prior candidate : State) : State :=
  if accepted then candidate else prior

theorem atomicCandidate_rejection_unchanged
    {State : Type} (prior candidate : State) :
    atomicCandidate false prior candidate = prior := by
  rfl

theorem exactCentralKickPairMomentumWitness
    (firstMomentum secondMomentum impulse : Vec3) :
    (firstMomentum + impulse) + (secondMomentum - impulse) =
      firstMomentum + secondMomentum := by
  exact exactQuantizedPairImpulse_preserves_momentum
    firstMomentum secondMomentum impulse

theorem exactCentralKickPairAngularWitness
    (firstPosition secondPosition firstMomentum secondMomentum : Vec3)
    (multiple : ℚ) :
    let offset := firstPosition - secondPosition
    let impulse := mechanicsVecScale multiple offset
    orbitalAngularMomentum firstPosition (firstMomentum + impulse) +
        orbitalAngularMomentum secondPosition (secondMomentum - impulse) =
      orbitalAngularMomentum firstPosition firstMomentum +
        orbitalAngularMomentum secondPosition secondMomentum := by
  exact centralPrimitiveQuantizedPair_preserves_orbitalAngularMomentum
    firstPosition secondPosition firstMomentum secondMomentum multiple

end MLSFormal
