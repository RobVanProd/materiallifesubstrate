# Time and canonical-checkpoint contract

**Status:** bounded Time + Transfer laboratory infrastructure. This contract
does not validate continuum mechanics or promote any particle/grid transfer
candidate.

## Physical-time state and units

`Tick` remains an unsigned deterministic ballistic-step sequence counter.
Other low-level world transitions can share a Tick; it is not a total operation
counter, is not a physical unit, and is never converted to seconds.
Authoritative physical time is the distinct signed fixed-point `Time` quantity:

| State/configuration | Representation | Unit and constraint |
|---|---|---|
| `World::physical_time()` | signed 64-bit `Time` quanta | nonnegative; initially zero |
| `WorldConfig::physical_timestep` | signed 64-bit `Time` quanta | strictly positive |
| `seconds_per_time_quantum_numerator` | unsigned 64-bit integer | strictly positive |
| `seconds_per_time_quantum_denominator` | unsigned 64-bit integer | strictly positive |
| `World::tick()` | unsigned 64-bit sequence count | ballistic-step ordering/debugging only |

One raw time quantum is exactly

\[
T_q = \frac{N_t}{D_t}\;\mathrm{s}.
\]

The reference default is `Nt=1`, `Dt=1,000,000,000`, so one `Time` quantum is
one nanosecond. No authoritative update converts this rational through floating
point.

The raw momentum/mass-to-velocity relationship is also explicit. If `Lq`,
`Pq`, and `Mq` are the configured length, momentum, and mass quanta, then

\[
\frac{P_q T_q}{M_q L_q}=\frac{N_v}{D_v},
\]

where `Nv` and `Dv` are
`momentum_mass_to_velocity_scale.length_quanta_numerator` and
`length_quanta_denominator`. Both must be positive. The default `Nv/Dv=1/1`
and `dt=1` preserve the accepted MLS-0 displacement explicitly; this is not an
implicit interpretation of one `Tick` as one unit of physical time.

## Update law

One `World::step()` performs one ordered transition and advances

\[
t' = t + dt,
\qquad
x'_i = x_i +
\frac{p_i\,dt\,N_v}{m\,D_v}.
\]

All products, sums, and divisions use checked integers. The current
deterministic reference mode accepts a ballistic update only if each displacement
is exactly representable in length quanta. It does not round or silently store a
fractional error. `step(count)` is repeated application of this physical update;
`Tick` increments separately to preserve deterministic event ordering.

For `dt`, `dt/2`, and `dt/4` experiments, choose a base duration divisible by
four in `Time` quanta (for example 4, 2, and 1) and compare states at a common
physical horizon. Changing only the sequence count is not a timestep refinement.

## Conservation contract

The ballistic time update changes only packet position and the two clock fields.
It does not change mass, element inventory, composition, momentum, or any
physical-energy channel. Because accepted displacement is the same scalar
multiple of each packet momentum vector, a free point packet's orbital angular
momentum is unchanged. The existing exact world ledger is audited after each
step when audit mode is enabled.

No truncation loss, transfer loss, or floating-point residual is converted into
thermal, stored, structural, chemical, or any other physical energy. Transfer
experiments must report such differences through their separate numerical
residual diagnostics.

## Numerical approximation and limits

The reference clock is exact fixed point. The ballistic update is an exact
integer witness, not a general integrator. Its representability restriction is
deliberately severe so that a refinement test cannot pass by hiding rounding in
packet state. This contract makes no accuracy claim for nonlinear motion,
forces, constitutive response, or particle/grid transfer.

Failure modes are rejected transactionally:

- zero or negative timestep;
- zero seconds numerator or denominator;
- zero or negative raw velocity-conversion numerator or denominator;
- physical-time, displacement-product, denominator, or position overflow;
- a displacement not exactly representable in configured length quanta;
- `Tick` overflow; and
- a checkpoint clock inconsistent with its stored `Tick`, timestep, and
  zero-time origin.

## Canonical checkpoint v2

`serialize_canonical_checkpoint` emits versioned little-endian bytes. The image
contains every authoritative state field used by this laboratory:

- all physical configuration and exact time-scale values;
- `Tick` and physical time;
- element and bond-energy catalogues;
- canonical compound graphs and their verified structural IDs;
- each live packet's stable ID/generation, position, exact integration state,
  momentum, composition, element inventory, mass, heat capacity, and physical
  energy channels;
- the next packet ID, including the effect of removed packets; and
- the exact conservation baseline and signed world-boundary ledger.

Maps and live packets are encoded in strictly increasing key order. Integers
have fixed widths. Signed integers use a specified 64-bit two's-complement byte
encoding. A trailing FNV-1a checksum detects accidental corruption; it is not a
cryptographic authenticity mechanism. The header records the byte-format
version separately from the authoritative physics ABI. A change that can alter
continued evolution from identical state must increment the physics ABI even
when the byte layout itself does not change. Evidence also binds checkpoints to
the exact source SHA.

The v2 byte order is fixed as follows. Every field is little endian; every
`count` and `size` is `u64` regardless of host `size_t`.

| Section | Fields in order |
|---|---|
| Header | eight bytes `MLSTTLAB`, `u32 format_version=2`, `u32 physics_abi_version=1` |
| Configuration | `i64 voxel_edge`, `i64 interaction_radius`, `i64 kinetic_energy_scale_denominator`, `i64 physical_timestep`, `u64 seconds numerator`, `u64 seconds denominator`, `i64 velocity-scale numerator`, `i64 velocity-scale denominator`, `u64 history_limit`, `u8 audit` |
| Clock | `u64 Tick`, `i64 physical_time` |
| Element catalogue | count, then sorted `(u16 id, i64 mass, i64 heat_capacity, i64 isolated_energy)` |
| Bond catalogue | count, then sorted `(u16 first, u16 second, u8 order, i64 energy)` |
| Compound registry | count, then sorted structural ID, atom vector, and bond vector for each canonical graph |
| Packets | `u64 next_id`, live count, then packets sorted by stable handle; each packet contains its handle, position, integration state, momentum, mixture, inventory, and extensive material/energy fields |
| Ledger | exact baseline totals, then signed boundary balance |
| Trailer | `u64` FNV-1a of every preceding byte |

The sparse voxel grid is omitted because it is a disposable index rebuilt from
packet positions. Packet event history and dead-packet tombstone payloads are
omitted because they are debug metadata and are never read by an authoritative
transition. The next unused packet ID is retained, so omitting tombstone payloads
does not change future live packet identity.

Decoding rejects bad magic, unknown format or physics-ABI versions, checksum failure,
truncation, trailing payload bytes, noncanonical/duplicate map order, invalid
compound encodings, inconsistent derived packet material fields, bad IDs,
invalid unit configuration, clock inconsistency, and a reconstructed world that
does not close its exact conservation ledger. Re-encoding the decoded world
must reproduce the input bytes exactly; otherwise decoding fails as
noncanonical.

## Tests

The Time + Transfer suite must cover:

1. The accepted default trajectory remains identical while physical time now
   advances independently of `Tick`.
2. Equal-horizon `dt=4`, `dt/2=2`, and `dt/4=1` exact ballistic cases agree,
   while overflow and fractional-displacement cases reject without mutation.
3. An empty world and a populated world serialize/deserialise byte-for-byte.
4. Boundary ledger state, removed-packet next-ID state, packet handles, and all
   exact quantities survive restart.
5. Continued operations on the original and restored worlds produce identical
   authoritative hashes and canonical checkpoints.
6. Bad magic/version, every truncation boundary, appended payload, altered
   checksum, duplicate/reordered maps, inconsistent packet fields, and invalid
   clock/configuration are rejected.
7. Serialization is identical across supported compilers and repeated runs.

The focused suite implements these checks in `tests/time_checkpoint_tests.cpp`.
It also rebuilds a valid checksum around deliberately malformed payloads so bad
magic/format/physics-ABI versions, invalid time and packet state, duplicate/reordered keys,
and trailing payload rejection exercise the decoder rather than merely failing
the checksum preflight.

Passing these tests proves exact representation and deterministic restart for
the stated reference state. It does not prove that a transfer method or future
mechanics update is physically valid.
