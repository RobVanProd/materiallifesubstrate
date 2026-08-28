# Prior-art debts and claim discipline

MLS combines established ideas and research questions. The project must cite the
lineage below and must not imply that a borrowed technique or nearby question is
novel. This is a working map, not a complete literature review or patent search.

## Numerical substrate

- **Material Point Method (MPM):** the proposed packet/grid split owes directly to
  MPM-family methods: Lagrangian material points carry state while a background
  grid supports force computation and transfer. See the [University of New Mexico
  MPM overview](https://math.unm.edu/~sulsky/research/mpm.html). MLS has not yet
  validated MPM as its solver.
- **Continuum-damage MPM:** fracture ambitions owe to work such as Wolper et al.,
  *CD-MPM: Continuum Damage Material Point Methods for Dynamic Fracture
  Animation*, [DOI 10.1145/3306346.3322949](https://doi.org/10.1145/3306346.3322949).
  A graphics result is evidence of a candidate technique, not validation of MLS
  cutting, energy accounting, or isotropy.
- **Sparse volumes:** sparse brick storage owes to Museth's VDB/OpenVDB work,
  [DOI 10.1145/2487228.2487235](https://doi.org/10.1145/2487228.2487235), which
  separates sparse topology/value storage from applications. A hierarchical data
  structure is not automatically a physically safe adaptive grid.
- **Continuum mechanics, thermodynamics, reaction kinetics, stoichiometric
  balance, transport equations, dimensional analysis, and convergence testing**
  are established scientific machinery. MLS claims no invention of them.

## Artificial-life design

- **Stringmol and automata chemistries:** the fixed-physics/evolvable-structure
  separation and the goal of minimizing fixed functionality owe especially to
  Hickinbotham et al., *Maximizing the Adjacent Possible in Automata Chemistries*,
  [DOI 10.1162/ARTL_a_00180](https://doi.org/10.1162/ARTL_a_00180). MLS extends a
  design question into embodied 3D matter; that extension is a proposal, not a
  novelty finding.
- **ALIEN:** large GPU particle worlds, particle-network bodies, genomes, neural
  control, and ecosystem-scale experimentation are demonstrated by
  [ALIEN](https://github.com/chrxh/alien). Its documented sensors, muscles,
  weapons, and constructors are also a useful contrast: MLS deliberately forbids
  those named affordances in its authoritative ABI. This is a difference in
  research constraint, not a judgment that one system supersedes the other.
- **DigiHive:** structure-encoded operations, bonded particle complexes, universal
  constructor/copying demonstrations, and cell-wall growth/division owe to
  Sienkiewicz and Jędruch, *DigiHive: Artificial Chemistry Environment for
  Modeling of Self-Organization Phenomena*,
  [DOI 10.1162/artl_a_00398](https://doi.org/10.1162/artl_a_00398). Its published
  scope is a two-dimensional abstract artificial chemistry; MLS must not claim
  those results as its own or as proof that 3D material grounding will work.
- **Flow-Lenia:** explicit mass conservation and localization of parameters within
  evolving dynamics owe to Flow-Lenia; see the [Google DeepMind publication
  record](https://deepmind.google/research/publications/106327/). MLS borrows the
  pressure to keep state and parameters inside evolvable dynamics where possible,
  not its cellular-automaton equations.

## Coarse/fine reasoning

The proposed interventional coarse/fine condition overlaps established model
reduction, behavioral equivalence, simulation, approximate simulation, and
bisimulation relations. See, for example, Chen and Haesaert's work on
[control refinement via simulation relations](https://arxiv.org/abs/1703.04822).
“Affordance-preserving coarse graining under unknown future evolutionary
interventions” is currently an MLS research framing, not a demonstrated new
mathematical field or solved theorem.

## Citation rules

Before publication:

1. replace this map with a versioned bibliography assembled from primary sources;
2. distinguish inspiration, reused method, comparison system, and empirical
   baseline;
3. cite software versions and configurations, not only papers;
4. run a dedicated literature and prior-art review before any novelty language;
5. state negative differences without implying superiority; and
6. never use the existence of a formal proof candidate as evidence of scientific
   novelty.
