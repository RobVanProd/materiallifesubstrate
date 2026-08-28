import Mathlib.Data.List.Basic

set_option autoImplicit false

namespace MLSFormal

/-- Apply a deterministic action sequence to a transition function. -/
def evolve {State Action : Type*}
    (step : State → Action → State) : State → List Action → State
  | state, [] => state
  | state, action :: rest => evolve step (step state action) rest

/--
Exact observational agreement for every initial fine state and legal action
sequence. This is an initial skeleton, not a complete affordance-preservation
criterion.
-/
def InterventionalAgreement
    {FineState CoarseState Action Observation : Type*}
    (fineStep : FineState → Action → FineState)
    (coarseStep : CoarseState → Action → CoarseState)
    (compress : FineState → CoarseState)
    (observeFine : FineState → Observation)
    (observeCoarse : CoarseState → Observation) : Prop :=
  ∀ initial actions,
    observeFine (evolve fineStep initial actions) =
      observeCoarse (evolve coarseStep (compress initial) actions)

/-- Identity compression is an exact interventional agreement. -/
theorem identityCompression_isSafe
    {State Action Observation : Type*}
    (step : State → Action → State)
    (observe : State → Observation) :
    InterventionalAgreement step step id observe observe := by
  intro initial actions
  rfl

/-- Agreement over all action sequences includes agreement after one action. -/
theorem interventionalAgreement_oneStep
    {FineState CoarseState Action Observation : Type*}
    {fineStep : FineState → Action → FineState}
    {coarseStep : CoarseState → Action → CoarseState}
    {compress : FineState → CoarseState}
    {observeFine : FineState → Observation}
    {observeCoarse : CoarseState → Observation}
    (agreement : InterventionalAgreement fineStep coarseStep compress
      observeFine observeCoarse)
    (initial : FineState) (action : Action) :
    observeFine (fineStep initial action) =
      observeCoarse (coarseStep (compress initial) action) := by
  have oneStep := agreement initial [action]
  simpa [evolve] using oneStep

end MLSFormal
