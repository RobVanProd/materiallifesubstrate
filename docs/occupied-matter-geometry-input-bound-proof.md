# A-priori bound for the frozen spherical construction

This supplies the construction argument required by the accepted pre-data
amendment. It changes no fixture or candidate and uses no candidate measurement.
The statement concerns the exact radial construction, with the finite encoding
floor accounted for separately. **NO_PROMOTION.**

Write `s(x)=||x||_1`, `r(x)=||x||_2`, and
`F(x)=s(x)x/r(x)` for nonzero x, with `F(0)=0`.
For nonzero x,y, exchange their names if necessary so `r(x)>=r(y)`.

The exact decomposition

    x/r(x) - y/r(y)
      = (x-y)/r(x) + y*(1/r(x)-1/r(y))

and the reverse triangle inequality imply

    ||x/r(x)-y/r(y)||_2 <= 2 ||x-y||_2 / r(x).

Also `|s(x)-s(y)|<=sqrt(3)||x-y||_2` and
`s(y)<=sqrt(3)r(y)<=sqrt(3)r(x)`. Decomposing

    F(x)-F(y) = (s(x)-s(y))*x/r(x)
                + s(y)*(x/r(x)-y/r(y))

therefore gives the global bound

    ||F(x)-F(y)||_2 <= 3 sqrt(3) ||x-y||_2.

If either point is zero, the stronger inequality
`||F(x)||_2=s(x)<=sqrt(3)||x||_2` closes that case. No differentiability across
orthant boundaries and no assumption about a sampled set is needed.

The independently checked eight-child template has a closed six-element set of
scaled ordered Gram matrices. Starting at `G=I`, each child has scaled Gram
`C^T G C` in that same set; all six classes have squared vertex-pair distances
at most 3. Induction over the fixed subdivision depth d yields

    diam(T_ref,d) <= sqrt(3) 2^(-d).

Applying the global bound to every pair of vertices gives the preregistered
level-independent exact-construction bound

    max mapped edge length <= 9 * 2^(-d).

A straight tetrahedron's diameter equals its maximum vertex-pair distance, so
the same bound applies to the exact mapped straight cell. This is not an
empirical extrapolation from the five registered levels.

For the actual nearest-even `2^(-256)` coordinate encoding, each vertex has
Euclidean error at most `sqrt(3)*2^(-257)`. Thus a separate conservative bound is

    encoded cell diameter <= 9 * 2^(-d) + sqrt(3)*2^(-256).

The constant encoding term is not claimed to vanish in an infinite fixed-bit
sequence. Candidate C receives neither of these upper bounds as its resolution
descriptor: its `DeltaSquared` remains the **exact maximum squared edge length
of the actual encoded straight tetrahedra**, independently checked from bytes.

This norm argument does not prove mapped straight-cell injectivity, conformity,
or positive orientation. Those are separate input obligations checked by the
incidence/orientation and strict-monotonicity certificates. Nor does it prove
any candidate's occupied-domain, normal, gap, or refinement gate.
