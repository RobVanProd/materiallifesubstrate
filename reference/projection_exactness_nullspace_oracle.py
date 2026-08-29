#!/usr/bin/env python3
"""Independent exact/high-precision oracle for the projection nullspace lab.

This module intentionally shares no production implementation.  It builds a
small tensor-product quadratic B-spline experiment from rational arithmetic,
checks the affine witness and Gram identities exactly, computes an exact
sampling nullspace, and solves the exact binary64 full-rank matrix with a
separate Decimal complete-pivot path.

The generated CSV fixture is only for exercising the independent evidence
validator.  It is explicitly promotion-ineligible and is not C++ evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal, getcontext, localcontext
from fractions import Fraction as Q
from pathlib import Path
from typing import Iterable, Sequence


SEED = 260828
SCHEMA = "mls.projection-exactness-nullspace.summary.v1"
MANIFEST_SCHEMA = "mls.projection-exactness-nullspace.manifest.v1"
ORACLE_IMPLEMENTATION = "independent Fraction + Decimal complete-pivot reference"
DECIMAL_DIGITS = 100
getcontext().prec = DECIMAL_DIGITS
PRECISION_BITS_LOWER_BOUND = 332
HP_PIVOT_RELATIVE = Decimal("1e-80")
HP_FORWARD_LIMIT = Decimal("5e-10")
HP_RECONSTRUCTION_LIMIT = Decimal("5e-10")
NULL_LIMIT = Q(0)
GRADIENT_VISIBILITY_FLOOR = Q(1, 10**12)

Vec3Q = tuple[Q, Q, Q]
MatrixQ = list[list[Q]]
Vec3D = tuple[Decimal, Decimal, Decimal]
MatrixD = list[list[Decimal]]


SYSTEM_FIELDS = tuple(
    "system_id,case_class,field,phase,orientation,level,time_quanta,"
    "time_quantum_numerator_s,time_quantum_denominator_s,time_s,h_m,dx_p_m,"
    "kg_per_mass_quantum,exact_mass_quanta,grid_origin_x_m,grid_origin_y_m,"
    "grid_origin_z_m,particle_count,node_count,matrix_nnz,rank_upper_bound,"
    "max_stencil_size,max_particle_contributions_per_node,max_matrix_row_nnz,"
    "a00_per_s,a01_per_s,a02_per_s,a10_per_s,a11_per_s,a12_per_s,a20_per_s,"
    "a21_per_s,a22_per_s,b0_m_per_s,b1_m_per_s,b2_m_per_s,"
    "full_solve_applicable,high_precision_applicable,nullspace_applicable,"
    "assembly_exported,assembly_payload_sha256,"
    "input_checkpoint_sha256_before,input_checkpoint_sha256_after,"
    "diagnostics_read_only_exact"
    .split(",")
)
PARTICLE_FIELDS = tuple(
    "system_id,particle_index,particle_id,mass_kg,x_m,y_m,z_m,vx_m_per_s,"
    "vy_m_per_s,vz_m_per_s".split(",")
)
NODE_FIELDS = tuple(
    "system_id,node_index,grid_i,grid_j,grid_k,x_m,y_m,z_m,"
    "analytic_gx_m_per_s,analytic_gy_m_per_s,analytic_gz_m_per_s,"
    "pcg_available,pcg_vhat_x_m_per_s,pcg_vhat_y_m_per_s,"
    "pcg_vhat_z_m_per_s,hp_available,hp_vhat_x_m_per_s,"
    "hp_vhat_y_m_per_s,hp_vhat_z_m_per_s".split(",")
)
STENCIL_FIELDS = tuple(
    "system_id,particle_index,node_index,weight,grad_x_per_m,grad_y_per_m,"
    "grad_z_per_m".split(",")
)
MATRIX_FIELDS = tuple("system_id,row_node_index,column_node_index,value_kg".split(","))
RHS_FIELDS = tuple("system_id,node_index,component,value_kg_m_per_s".split(","))
WITNESS_FIELDS = tuple(
    "system_id,component,mg_minus_q_l2_kg_m_per_s,mgq_denominator_kg_m_per_s,"
    "normalized_mg_minus_q,mgq_roundoff_bound,mgq_pass,sg_minus_v_l2_m_per_s,"
    "sgv_denominator_m_per_s_sqrt_kg,normalized_sg_minus_v,"
    "sgv_roundoff_bound,sgv_pass,partition_max_residual,partition_roundoff_bound,"
    "partition_pass,linear_reproduction_max_residual_m,"
    "linear_reproduction_roundoff_bound_m,linear_reproduction_pass,"
    "gradient_partition_max_residual_per_m,"
    "gradient_partition_roundoff_bound_per_m,gradient_partition_pass,pass"
    .split(",")
)
SOLVE_FIELDS = tuple(
    "system_id,component,status,solver,iterations,"
    "backward_residual_l2_kg_m_per_s,backward_denominator_kg_m_per_s,"
    "normalized_backward_residual,grid_forward_lumped_numerator_m_per_s_sqrt_kg,"
    "grid_forward_lumped_denominator_m_per_s_sqrt_kg,normalized_forward_error,"
    "reconstruction_mass_numerator_m_per_s_sqrt_kg,"
    "reconstruction_mass_denominator_m_per_s_sqrt_kg,"
    "normalized_reconstruction_error,raw_condition_value,raw_condition_kind,"
    "preconditioned_condition_value,preconditioned_condition_kind,"
    "condition_times_normalized_residual".split(",")
)
HIGH_PRECISION_FIELDS = tuple(
    "system_id,component,status,method,precision_bits,decimal_digits,rank,"
    "rank_method,rank_is_certified,regularization,node_dropping,basis_altered,"
    "promotion_eligible,pivot_threshold_relative,smallest_pivot_abs_kg,"
    "largest_pivot_abs_kg,backward_residual_l2_kg_m_per_s,"
    "backward_denominator_kg_m_per_s,normalized_backward_residual,"
    "grid_forward_lumped_numerator_m_per_s_sqrt_kg,"
    "grid_forward_lumped_denominator_m_per_s_sqrt_kg,normalized_forward_error,"
    "reconstruction_mass_numerator_m_per_s_sqrt_kg,"
    "reconstruction_mass_denominator_m_per_s_sqrt_kg,"
    "normalized_reconstruction_error,condition_value,condition_kind".split(",")
)
NULLSPACE_MODE_FIELDS = tuple(
    "system_id,mode_index,node_index,z_value_m_per_s,method,singular_value_kg,"
    "representative_value_m_per_s,shifted_value_m_per_s".split(",")
)
NULLSPACE_METRIC_FIELDS = tuple(
    "system_id,mode_index,rank,rank_method,rank_is_certified,"
    "mz_l2_kg_m_per_s,mz_denominator_kg_m_per_s,mz_normalized,"
    "sz_l2_m_per_s,sz_denominator_m_per_s,sz_normalized,"
    "gradient_max_per_s,gradient_rms_per_s,gradient_roundoff_bound_per_s,"
    "visibility_ratio,gradient_visible,alpha_m_per_s,representative_component,"
    "representative_kind,base_residual_normalized,shifted_residual_normalized,"
    "reconstruction_delta_normalized,phase,orientation,promotion_eligible,pass"
    .split(",")
)

CSV_SCHEMAS = {
    "systems.csv": SYSTEM_FIELDS,
    "particles.csv": PARTICLE_FIELDS,
    "nodes.csv": NODE_FIELDS,
    "stencils.csv": STENCIL_FIELDS,
    "matrix.csv": MATRIX_FIELDS,
    "rhs.csv": RHS_FIELDS,
    "witness.csv": WITNESS_FIELDS,
    "solve_diagnostics.csv": SOLVE_FIELDS,
    "high_precision.csv": HIGH_PRECISION_FIELDS,
    "nullspace_modes.csv": NULLSPACE_MODE_FIELDS,
    "nullspace_metrics.csv": NULLSPACE_METRIC_FIELDS,
}


AFFINE_A: tuple[Vec3Q, Vec3Q, Vec3Q] = (
    (Q(1, 8), Q(1, 4), Q(-3, 8)),
    (Q(-1, 4), Q(1, 8), Q(1, 2)),
    (Q(3, 8), Q(-1, 8), Q(1, 4)),
)
AFFINE_B: Vec3Q = (Q(1, 2), Q(-1, 4), Q(3, 4))


def qsum(values: Iterable[Q]) -> Q:
    return sum(values, Q(0))


def qsqrt_text(value: Q, digits: int = 80) -> str:
    with localcontext() as context:
        context.prec = digits
        return format((Decimal(value.numerator) / Decimal(value.denominator)).sqrt(), "e")


def qtext(value: Q) -> str:
    return f"{value.numerator}/{value.denominator}"


def hexfloat(value: Q | float) -> str:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite binary64 fixture value")
    return result.hex()


def gamma64(operations: int) -> float:
    epsilon = 2.0**-52
    denominator = 1.0 - operations * epsilon
    if operations <= 0 or denominator <= 0.0:
        raise ValueError("invalid roundoff operation count")
    return operations * epsilon / denominator


def decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("non-finite Decimal fixture value")
    return format(value, "e")


def affine(point: Vec3Q) -> Vec3Q:
    return tuple(
        qsum(AFFINE_A[row][column] * point[column] for column in range(3))
        + AFFINE_B[row]
        for row in range(3)
    )  # type: ignore[return-value]


def axis_samples(position: Q) -> list[tuple[int, Q, Q]]:
    """Return (node, weight, dweight/dx) for h=1, origin=0."""
    base = (position - Q(1, 2)).numerator // (position - Q(1, 2)).denominator
    coordinate = position - base
    left = Q(3, 2) - coordinate
    middle = coordinate - 1
    right = coordinate - Q(1, 2)
    weights = (Q(1, 2) * left * left, Q(3, 4) - middle * middle, Q(1, 2) * right * right)
    gradients = (-left, -2 * middle, right)
    assert qsum(weights) == 1
    assert qsum(gradients) == 0
    return [(base + index, weights[index], gradients[index]) for index in range(3)]


def particle_stencil(point: Vec3Q) -> list[tuple[tuple[int, int, int], Q, Vec3Q]]:
    axes = [axis_samples(value) for value in point]
    result: list[tuple[tuple[int, int, int], Q, Vec3Q]] = []
    for nx, wx, gx in axes[0]:
        for ny, wy, gy in axes[1]:
            for nz, wz, gz in axes[2]:
                result.append(((nx, ny, nz), wx * wy * wz, (gx * wy * wz, wx * gy * wz, wx * wy * gz)))
    assert qsum(entry[1] for entry in result) == 1
    for component in range(3):
        assert qsum(entry[2][component] for entry in result) == 0
    return result


def matvec(matrix: Sequence[Sequence[Q]], vector: Sequence[Q]) -> list[Q]:
    return [qsum(value * vector[column] for column, value in enumerate(row)) for row in matrix]


def transpose(matrix: Sequence[Sequence[Q]]) -> MatrixQ:
    return [list(column) for column in zip(*matrix, strict=True)]


def rref(matrix: Sequence[Sequence[Q]]) -> tuple[MatrixQ, list[int]]:
    work = [list(row) for row in matrix]
    if not work:
        return [], []
    row_count, column_count = len(work), len(work[0])
    pivots: list[int] = []
    row = 0
    for column in range(column_count):
        pivot = next((candidate for candidate in range(row, row_count) if work[candidate][column] != 0), None)
        if pivot is None:
            continue
        work[row], work[pivot] = work[pivot], work[row]
        scale = work[row][column]
        work[row] = [value / scale for value in work[row]]
        for other in range(row_count):
            if other == row:
                continue
            factor = work[other][column]
            if factor:
                work[other] = [left - factor * right for left, right in zip(work[other], work[row], strict=True)]
        pivots.append(column)
        row += 1
        if row == row_count:
            break
    return work, pivots


def nullspace(matrix: Sequence[Sequence[Q]]) -> list[list[Q]]:
    reduced, pivots = rref(matrix)
    column_count = len(matrix[0]) if matrix else 0
    free = [column for column in range(column_count) if column not in set(pivots)]
    result: list[list[Q]] = []
    for free_column in free:
        vector = [Q(0)] * column_count
        vector[free_column] = Q(1)
        for row, pivot_column in enumerate(pivots):
            vector[pivot_column] = -reduced[row][free_column]
        assert all(value == 0 for value in matvec(matrix, vector))
        result.append(vector)
    return result


@dataclass(frozen=True)
class ExactSystem:
    system_id: str
    case_class: str
    points: tuple[Vec3Q, ...]
    nodes: tuple[tuple[int, int, int], ...]
    sampling: tuple[tuple[Q, ...], ...]
    gradients: tuple[tuple[Vec3Q, ...], ...]
    matrix: tuple[tuple[Q, ...], ...]
    rhs: tuple[tuple[Q, ...], tuple[Q, ...], tuple[Q, ...]]
    nodal_affine: tuple[tuple[Q, ...], tuple[Q, ...], tuple[Q, ...]]
    particle_velocity: tuple[Vec3Q, ...]
    rank: int


def build_system(system_id: str, case_class: str, coordinates: Sequence[Q]) -> ExactSystem:
    points = tuple((x, y, z) for x in coordinates for y in coordinates for z in coordinates)
    raw_stencils = [particle_stencil(point) for point in points]
    nodes = tuple(sorted({entry[0] for stencil in raw_stencils for entry in stencil}))
    lookup = {node: index for index, node in enumerate(nodes)}
    sampling: MatrixQ = [[Q(0) for _ in nodes] for _ in points]
    gradients: list[list[Vec3Q]] = [[(Q(0), Q(0), Q(0)) for _ in nodes] for _ in points]
    for particle, stencil in enumerate(raw_stencils):
        for node, weight, gradient in stencil:
            index = lookup[node]
            sampling[particle][index] = weight
            gradients[particle][index] = gradient

    matrix: MatrixQ = [[Q(0) for _ in nodes] for _ in nodes]
    for row in range(len(nodes)):
        for column in range(len(nodes)):
            matrix[row][column] = qsum(sampling[p][row] * sampling[p][column] for p in range(len(points)))
    particle_velocity = tuple(affine(point) for point in points)
    rhs = tuple(
        tuple(qsum(sampling[p][node] * particle_velocity[p][component] for p in range(len(points))) for node in range(len(nodes)))
        for component in range(3)
    )
    nodal_affine = tuple(
        tuple(affine(tuple(Q(value) for value in node))[component] for node in nodes)
        for component in range(3)
    )
    rank = len(rref(sampling)[1])
    system = ExactSystem(
        system_id, case_class, points, nodes,
        tuple(tuple(row) for row in sampling),
        tuple(tuple(row) for row in gradients),
        tuple(tuple(row) for row in matrix),
        rhs, nodal_affine, particle_velocity, rank,
    )
    verify_exact_system(system)
    return system


def verify_exact_system(system: ExactSystem) -> None:
    for particle, point in enumerate(system.points):
        assert qsum(system.sampling[particle]) == 1
        for component in range(3):
            assert qsum(system.sampling[particle][node] * Q(system.nodes[node][component]) for node in range(len(system.nodes))) == point[component]
            assert qsum(system.gradients[particle][node][component] for node in range(len(system.nodes)) ) == 0
    for component in range(3):
        assert matvec(system.matrix, system.nodal_affine[component]) == list(system.rhs[component])
        assert matvec(system.sampling, system.nodal_affine[component]) == [value[component] for value in system.particle_velocity]


def decimal_from_q(value: Q) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def decimal_dot(lhs: Sequence[Decimal], rhs: Sequence[Decimal]) -> Decimal:
    return sum((a * b for a, b in zip(lhs, rhs, strict=True)), Decimal(0))


def decimal_l2(values: Iterable[Decimal]) -> Decimal:
    return sum((value * value for value in values), Decimal(0)).sqrt()


def projection_metrics_decimal(
    matrix: Sequence[Sequence[Decimal]],
    sampling: Sequence[Sequence[Decimal]],
    masses: Sequence[Decimal],
    rhs: Sequence[Decimal],
    solution: Sequence[Decimal],
    analytic: Sequence[Decimal],
    particles: Sequence[Decimal],
) -> dict[str, Decimal]:
    residual = [decimal_dot(row, solution) - rhs[row_index] for row_index, row in enumerate(matrix)]
    matrix_frobenius = decimal_l2(value for row in matrix for value in row)
    backward_denominator = matrix_frobenius * decimal_l2(solution) + decimal_l2(rhs)
    lumped = [sum((masses[p] * sampling[p][node] for p in range(len(sampling))), Decimal(0)) for node in range(len(matrix))]
    forward = [solution[index] - analytic[index] for index in range(len(analytic))]
    forward_numerator = sum((lumped[i] * forward[i] * forward[i] for i in range(len(lumped))), Decimal(0)).sqrt()
    forward_reference = sum((lumped[i] * analytic[i] * analytic[i] for i in range(len(lumped))), Decimal(0)).sqrt()
    forward_floor = sum(lumped, Decimal(0)).sqrt()
    forward_denominator = max(forward_reference, forward_floor)
    reconstructed = [decimal_dot(row, solution) for row in sampling]
    reconstruction = [reconstructed[index] - particles[index] for index in range(len(particles))]
    reconstruction_numerator = sum((masses[p] * reconstruction[p] * reconstruction[p] for p in range(len(masses))), Decimal(0)).sqrt()
    reconstruction_reference = sum((masses[p] * particles[p] * particles[p] for p in range(len(masses))), Decimal(0)).sqrt()
    reconstruction_floor = sum(masses, Decimal(0)).sqrt()
    reconstruction_denominator = max(reconstruction_reference, reconstruction_floor)
    return {
        "backward": decimal_l2(residual),
        "backward_denominator": backward_denominator,
        "normalized_backward": decimal_l2(residual) / backward_denominator,
        "forward": forward_numerator,
        "forward_denominator": forward_denominator,
        "normalized_forward": forward_numerator / forward_denominator,
        "reconstruction": reconstruction_numerator,
        "reconstruction_denominator": reconstruction_denominator,
        "normalized_reconstruction": reconstruction_numerator / reconstruction_denominator,
    }


@dataclass(frozen=True)
class DenseSolve:
    solution: tuple[Decimal, ...]
    rank: int
    smallest_pivot: Decimal
    largest_pivot: Decimal


def decimal_complete_pivot_solve(matrix: Sequence[Sequence[Decimal]], rhs: Sequence[Decimal]) -> DenseSolve:
    size = len(matrix)
    if size == 0 or len(rhs) != size or any(len(row) != size for row in matrix):
        raise ValueError("invalid dense system")
    work = [list(row) for row in matrix]
    value = list(rhs)
    permutation = list(range(size))
    initial_max = max(abs(entry) for row in work for entry in row)
    threshold = initial_max * HP_PIVOT_RELATIVE
    pivots: list[Decimal] = []
    rank = 0
    for index in range(size):
        pivot_row, pivot_column = max(
            ((row, column) for row in range(index, size) for column in range(index, size)),
            key=lambda item: abs(work[item[0]][item[1]]),
        )
        pivot_abs = abs(work[pivot_row][pivot_column])
        if pivot_abs <= threshold:
            break
        work[index], work[pivot_row] = work[pivot_row], work[index]
        value[index], value[pivot_row] = value[pivot_row], value[index]
        for row in range(size):
            work[row][index], work[row][pivot_column] = work[row][pivot_column], work[row][index]
        permutation[index], permutation[pivot_column] = permutation[pivot_column], permutation[index]
        pivot = work[index][index]
        pivots.append(abs(pivot))
        for row in range(index + 1, size):
            factor = work[row][index] / pivot
            work[row][index] = Decimal(0)
            for column in range(index + 1, size):
                work[row][column] -= factor * work[index][column]
            value[row] -= factor * value[index]
        rank += 1
    if rank != size:
        raise ValueError(f"rank-deficient high-precision matrix: {rank}/{size}")
    permuted = [Decimal(0)] * size
    for row in range(size - 1, -1, -1):
        tail = sum((work[row][column] * permuted[column] for column in range(row + 1, size)), Decimal(0))
        permuted[row] = (value[row] - tail) / work[row][row]
    solution = [Decimal(0)] * size
    for position, original_column in enumerate(permutation):
        solution[original_column] = permuted[position]
    return DenseSolve(tuple(solution), rank, min(pivots), max(pivots))


def float_assembled(system: ExactSystem) -> tuple[list[list[float]], list[list[float]], list[list[float]]]:
    sampling = [[float(value) for value in row] for row in system.sampling]
    particle_velocity = [[float(value) for value in velocity] for velocity in system.particle_velocity]
    node_count = len(system.nodes)
    matrix = [[0.0] * node_count for _ in range(node_count)]
    rhs = [[0.0] * node_count for _ in range(3)]
    for particle, row in enumerate(sampling):
        for i, wi in enumerate(row):
            if wi == 0.0:
                continue
            for component in range(3):
                rhs[component][i] += wi * particle_velocity[particle][component]
            for j, wj in enumerate(row):
                if wj != 0.0:
                    matrix[i][j] += wi * wj
    return sampling, matrix, rhs


def high_precision_solutions(system: ExactSystem) -> tuple[list[DenseSolve], list[dict[str, Decimal]]]:
    sampling_f, matrix_f, rhs_f = float_assembled(system)
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        matrix = [[Decimal.from_float(value) for value in row] for row in matrix_f]
        sampling = [[Decimal.from_float(value) for value in row] for row in sampling_f]
        solves: list[DenseSolve] = []
        metrics: list[dict[str, Decimal]] = []
        for component in range(3):
            rhs = [Decimal.from_float(value) for value in rhs_f[component]]
            solve = decimal_complete_pivot_solve(matrix, rhs)
            analytic = [Decimal.from_float(float(value)) for value in system.nodal_affine[component]]
            particles = [Decimal.from_float(float(value[component])) for value in system.particle_velocity]
            metric = projection_metrics_decimal(
                matrix, sampling, [Decimal(1)] * len(sampling), rhs,
                solve.solution, analytic, particles,
            )
            solves.append(solve)
            metrics.append(metric)
        return solves, metrics


def float_pcg(matrix: Sequence[Sequence[float]], rhs: Sequence[float], limit: int = 10000) -> tuple[list[float], int, str]:
    size = len(matrix)
    x = [rhs[i] / matrix[i][i] for i in range(size)]
    apply = lambda v: [sum(row[j] * v[j] for j in range(size)) for row in matrix]
    applied = apply(x)
    r = [rhs[i] - applied[i] for i in range(size)]
    diagonal = [matrix[i][i] for i in range(size)]
    z = [r[i] / diagonal[i] for i in range(size)]
    p = list(z)
    rz = sum(r[i] * z[i] for i in range(size))
    rhs_norm = math.sqrt(sum(value * value for value in rhs))
    for iteration in range(1, limit + 1):
        ap = apply(p)
        denominator = sum(p[i] * ap[i] for i in range(size))
        if denominator <= 0.0 or not math.isfinite(denominator):
            return x, iteration, "breakdown"
        alpha = rz / denominator
        x = [x[i] + alpha * p[i] for i in range(size)]
        r = [r[i] - alpha * ap[i] for i in range(size)]
        if math.sqrt(sum(value * value for value in r)) / max(rhs_norm, 1.0) <= 5.0e-12:
            return x, iteration, "solved"
        z = [r[i] / diagonal[i] for i in range(size)]
        next_rz = sum(r[i] * z[i] for i in range(size))
        beta = next_rz / rz
        p = [z[i] + beta * p[i] for i in range(size)]
        rz = next_rz
    return x, limit, "iteration_limit"


def decimal_metric_rows(system: ExactSystem, solutions: Sequence[Sequence[float]]) -> list[dict[str, Decimal]]:
    sampling_f, matrix_f, rhs_f = float_assembled(system)
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        matrix = [[Decimal.from_float(value) for value in row] for row in matrix_f]
        sampling = [[Decimal.from_float(value) for value in row] for row in sampling_f]
        rows = []
        for component in range(3):
            solution = [Decimal.from_float(value) for value in solutions[component]]
            rhs = [Decimal.from_float(value) for value in rhs_f[component]]
            analytic = [Decimal.from_float(float(value)) for value in system.nodal_affine[component]]
            particles = [Decimal.from_float(float(value[component])) for value in system.particle_velocity]
            rows.append(projection_metrics_decimal(
                matrix, sampling, [Decimal(1)] * len(sampling), rhs,
                solution, analytic, particles,
            ))
        return rows


def nullspace_probe(system: ExactSystem) -> tuple[list[Q], dict[str, Q]]:
    modes = nullspace(system.sampling)
    if not modes:
        raise AssertionError("singular oracle system unexpectedly has no nullspace")
    best_mode: list[Q] | None = None
    best_gradient_squared = Q(-1)
    best_values: list[Vec3Q] = []
    for mode in modes:
        gradient_values = [tuple(
            qsum(system.gradients[p][node][component] * mode[node] for node in range(len(system.nodes)))
            for component in range(3)
        ) for p in range(len(system.points))
        ]
        maximum_squared = max(qsum(value * value for value in gradient) for gradient in gradient_values)
        if maximum_squared > best_gradient_squared:
            best_mode, best_gradient_squared, best_values = mode, maximum_squared, gradient_values
    assert best_mode is not None
    assert all(value == 0 for value in matvec(system.sampling, best_mode))
    assert all(value == 0 for value in matvec(system.matrix, best_mode))
    assert best_gradient_squared > GRADIENT_VISIBILITY_FLOOR * GRADIENT_VISIBILITY_FLOOR
    rms_squared = qsum(qsum(value * value for value in gradient) for gradient in best_values) / len(best_values)
    return best_mode, {
        "gradient_max_squared": best_gradient_squared,
        "gradient_rms_squared": rms_squared,
        "nullity": Q(len(modes)),
    }


def build_oracle() -> tuple[ExactSystem, ExactSystem, dict, list[DenseSolve], list[dict[str, Decimal]], list[Q], dict[str, Q]]:
    full = build_system("oracle_full_27", "full_rank_affine", (Q(5, 8), Q(1), Q(11, 8)))
    singular = build_system("oracle_singular_8", "rank_deficient_affine", (Q(3, 4), Q(5, 4)))
    if full.rank != len(full.nodes):
        raise AssertionError(f"full fixture rank {full.rank}/{len(full.nodes)}")
    if singular.rank != len(singular.points) or singular.rank >= len(singular.nodes):
        raise AssertionError("singular fixture does not have registered sampling rank")
    hp_solves, hp_metrics = high_precision_solutions(full)
    hp_backward_limit = Decimal(2) ** 12 * Decimal(len(full.nodes)) * (Decimal(2) ** -104)
    for metric in hp_metrics:
        assert metric["normalized_backward"] <= hp_backward_limit
        assert metric["normalized_forward"] <= HP_FORWARD_LIMIT
        assert metric["normalized_reconstruction"] <= HP_RECONSTRUCTION_LIMIT
    mode, mode_metrics = nullspace_probe(singular)
    result = {
        "arithmetic": "fractions.Fraction exact; decimal.Decimal complete pivot",
        "decimal_digits": DECIMAL_DIGITS,
        "full_rank": full.rank,
        "full_nodes": len(full.nodes),
        "full_particles": len(full.points),
        "full_witness_component_checks": 6,
        "gradient_partition_exact_checks": len(full.points) * 3 + len(singular.points) * 3,
        "high_precision_component_checks": 3,
        "high_precision_backward_limit": decimal_text(hp_backward_limit),
        "high_precision_max_normalized_backward": max(decimal_text(row["normalized_backward"]) for row in hp_metrics),
        "high_precision_max_normalized_forward": max(decimal_text(row["normalized_forward"]) for row in hp_metrics),
        "high_precision_max_normalized_reconstruction": max(decimal_text(row["normalized_reconstruction"]) for row in hp_metrics),
        "implementation": ORACLE_IMPLEMENTATION,
        "nullspace_center_invisible_exact": True,
        "nullspace_gradient_max_squared_exact": qtext(mode_metrics["gradient_max_squared"]),
        "nullspace_gradient_max_decimal": qsqrt_text(mode_metrics["gradient_max_squared"]),
        "nullspace_gradient_rms_squared_exact": qtext(mode_metrics["gradient_rms_squared"]),
        "nullspace_gradient_visible": True,
        "nullspace_nullity": int(mode_metrics["nullity"]),
        "schema": SCHEMA,
        "scope": "small independent algebra/numerics control; not production evidence",
        "seed": SEED,
        "singular_rank": singular.rank,
        "singular_nodes": len(singular.nodes),
        "singular_particles": len(singular.points),
    }
    payload = json.dumps(result, indent=2, sort_keys=True)
    result["result_sha256_before_hash_field"] = hashlib.sha256(payload.encode()).hexdigest()
    return full, singular, result, hp_solves, hp_metrics, mode, mode_metrics


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def norm_fraction(values: Iterable[Q]) -> Decimal:
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        return sum((decimal_from_q(value) ** 2 for value in values), Decimal(0)).sqrt()


def manifest_payload(hashes: dict[str, str]) -> bytes:
    lines = ["{", '  "algorithm": "SHA-256",', '  "files": {']
    names = sorted(hashes)
    for index, name in enumerate(names):
        comma = "," if index + 1 < len(names) else ""
        lines.append(f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}")
    lines.extend(("  },", f'  "schema": {json.dumps(MANIFEST_SCHEMA)}', "}"))
    return "\n".join(lines).encode()


def write_fixture(target: Path) -> None:
    full, singular, oracle_result, hp_solves, hp_metrics, mode, mode_metrics = build_oracle()
    if target.exists():
        raise FileExistsError(f"fixture target already exists: {target}")
    target.mkdir(parents=True)
    systems = (full, singular)
    tables: dict[str, list[dict[str, str]]] = {name: [] for name in CSV_SCHEMAS}
    pcg_values: dict[str, list[list[float]] | None] = {}
    pcg_iterations: dict[str, list[int]] = {}
    pcg_status: dict[str, list[str]] = {}
    for system in systems:
        sampling_f, matrix_f, rhs_f = float_assembled(system)
        if system is full:
            triples = [float_pcg(matrix_f, rhs_f[c]) for c in range(3)]
            pcg_values[system.system_id] = [entry[0] for entry in triples]
            pcg_iterations[system.system_id] = [entry[1] for entry in triples]
            pcg_status[system.system_id] = [entry[2] for entry in triples]
        else:
            pcg_values[system.system_id] = None
            pcg_iterations[system.system_id] = [0, 0, 0]
            pcg_status[system.system_id] = ["structurally_rank_deficient"] * 3
        nonzero = sum(value != 0 for row in system.matrix for value in row)
        max_stencil = max(sum(value != 0 for value in row) for row in system.sampling)
        max_contributions = max(
            sum(system.sampling[p][node] != 0 for p in range(len(system.points)))
            for node in range(len(system.nodes))
        )
        max_row_nnz = max(sum(value != 0 for value in row) for row in system.matrix)
        A = [value for row in AFFINE_A for value in row]
        tables["systems.csv"].append(dict(zip(SYSTEM_FIELDS, (
            system.system_id, system.case_class, "general_affine", "oracle_dyadic", "identity", "0",
            "0", "1", "160", hexfloat(0), hexfloat(1),
            hexfloat(Q(3, 8) if system is full else Q(1, 2)),
            hexfloat(1), str(len(system.points)), hexfloat(0), hexfloat(0), hexfloat(0),
            str(len(system.points)), str(len(system.nodes)), str(nonzero), str(min(len(system.points), len(system.nodes))),
            str(max_stencil), str(max_contributions), str(max_row_nnz),
            *(hexfloat(value) for value in A), *(hexfloat(value) for value in AFFINE_B),
            "true", "true" if system is full else "false", "true" if system is singular else "false",
            "true", "PENDING",
            hashlib.sha256((system.system_id + "-input-checkpoint").encode()).hexdigest(),
            hashlib.sha256((system.system_id + "-input-checkpoint").encode()).hexdigest(), "true",
        ), strict=True)))
        for p, point in enumerate(system.points):
            velocity = system.particle_velocity[p]
            tables["particles.csv"].append(dict(zip(PARTICLE_FIELDS, (
                system.system_id, str(p), str(p + 1), hexfloat(1), *(hexfloat(value) for value in point),
                *(hexfloat(value) for value in velocity),
            ), strict=True)))
        hp_by_component = hp_solves if system is full else None
        for node_index, node in enumerate(system.nodes):
            analytic = [system.nodal_affine[c][node_index] for c in range(3)]
            pcg = pcg_values[system.system_id]
            pcg_fields = [hexfloat(pcg[c][node_index]) for c in range(3)] if pcg is not None else ["NA"] * 3
            hp_fields = [decimal_text(hp_by_component[c].solution[node_index]) for c in range(3)] if hp_by_component is not None else ["NA"] * 3
            tables["nodes.csv"].append(dict(zip(NODE_FIELDS, (
                system.system_id, str(node_index), *(str(value) for value in node), *(hexfloat(value) for value in node),
                *(hexfloat(value) for value in analytic), "true" if pcg is not None else "false", *pcg_fields,
                "true" if hp_by_component is not None else "false", *hp_fields,
            ), strict=True)))
        for p, row in enumerate(system.sampling):
            for node, weight in enumerate(row):
                if weight == 0:
                    continue
                gradient = system.gradients[p][node]
                tables["stencils.csv"].append(dict(zip(STENCIL_FIELDS, (
                    system.system_id, str(p), str(node), hexfloat(weight), *(hexfloat(value) for value in gradient),
                ), strict=True)))
        for row, values in enumerate(matrix_f):
            for column, value in enumerate(values):
                if value != 0.0:
                    tables["matrix.csv"].append(dict(zip(MATRIX_FIELDS, (
                        system.system_id, str(row), str(column), float(value).hex(),
                    ), strict=True)))
        for component in range(3):
            for node, value in enumerate(rhs_f[component]):
                tables["rhs.csv"].append(dict(zip(RHS_FIELDS, (
                    system.system_id, str(node), str(component), float(value).hex(),
                ), strict=True)))
            with localcontext() as context:
                context.prec = DECIMAL_DIGITS
                matrix_d = [[Decimal.from_float(value) for value in row] for row in matrix_f]
                sampling_d = [[Decimal.from_float(value) for value in row] for row in sampling_f]
                rhs_d = [Decimal.from_float(value) for value in rhs_f[component]]
                analytic_d = [Decimal.from_float(float(value)) for value in system.nodal_affine[component]]
                particles_d = [Decimal.from_float(float(value[component])) for value in system.particle_velocity]
                mg = [decimal_dot(row, analytic_d) for row in matrix_d]
                mg_residual = decimal_l2(mg[i] - rhs_d[i] for i in range(len(rhs_d)))
                abs_m_g = [sum((abs(matrix_d[row][column]) * abs(analytic_d[column]) for column in range(len(system.nodes))), Decimal(0)) for row in range(len(system.nodes))]
                mgq_denominator = decimal_l2(abs_m_g) + decimal_l2(rhs_d)
                reconstructed = [decimal_dot(row, analytic_d) for row in sampling_d]
                sg_residual = decimal_l2(reconstructed[p] - particles_d[p] for p in range(len(particles_d)))
                particle_reference = decimal_l2(particles_d)
                sgv_denominator = max(particle_reference, Decimal(len(system.points)).sqrt())
            maximum_point_norm = max(math.sqrt(sum(float(value) ** 2 for value in point)) for point in system.points)
            partition_bound = 32.0 * gamma64(max_stencil)
            linear_bound = 64.0 * gamma64(max_stencil) * max(1.0, maximum_point_norm)
            gradient_partition_bound = 64.0 * gamma64(3 * max_stencil)
            sgv_bound = 128.0 * gamma64(max_stencil)
            mgq_bound = 128.0 * gamma64(max(max_row_nnz, max_contributions, 2 * max_stencil))
            tables["witness.csv"].append(dict(zip(WITNESS_FIELDS, (
                system.system_id, str(component), decimal_text(mg_residual), decimal_text(mgq_denominator),
                decimal_text(mg_residual / mgq_denominator), hexfloat(mgq_bound), "true",
                decimal_text(sg_residual), decimal_text(sgv_denominator), decimal_text(sg_residual / sgv_denominator), hexfloat(sgv_bound), "true",
                hexfloat(0), hexfloat(partition_bound), "true", hexfloat(0), hexfloat(linear_bound), "true",
                hexfloat(0), hexfloat(gradient_partition_bound), "true", "true",
            ), strict=True)))
        if system is full:
            pcg_metrics = decimal_metric_rows(system, pcg_values[system.system_id] or [])
            for component in range(3):
                metric = pcg_metrics[component]
                raw_condition = Decimal("1e0")
                tables["solve_diagnostics.csv"].append(dict(zip(SOLVE_FIELDS, (
                    system.system_id, str(component), pcg_status[system.system_id][component], "pcg_control",
                    str(pcg_iterations[system.system_id][component]), *(decimal_text(metric[name]) for name in (
                        "backward", "backward_denominator", "normalized_backward", "forward", "forward_denominator",
                        "normalized_forward", "reconstruction", "reconstruction_denominator", "normalized_reconstruction")),
                    decimal_text(raw_condition), "dense_numerical_estimate", "1e0", "dense_numerical_estimate",
                    decimal_text(raw_condition * metric["normalized_backward"]),
                ), strict=True)))
                hp = hp_solves[component]
                metric_hp = hp_metrics[component]
                tables["high_precision.csv"].append(dict(zip(HIGH_PRECISION_FIELDS, (
                    system.system_id, str(component), "solved", "decimal_complete_pivot", str(PRECISION_BITS_LOWER_BOUND),
                    str(DECIMAL_DIGITS), str(hp.rank), "dense_complete_pivot_high_precision", "false", "none", "false",
                    "false", "false", decimal_text(HP_PIVOT_RELATIVE), decimal_text(hp.smallest_pivot),
                    decimal_text(hp.largest_pivot), *(decimal_text(metric_hp[name]) for name in (
                        "backward", "backward_denominator", "normalized_backward", "forward", "forward_denominator",
                        "normalized_forward", "reconstruction", "reconstruction_denominator",
                        "normalized_reconstruction")), "1e0", "high_precision_inverse_norm_estimate",
                ), strict=True)))
        else:
            for component in range(3):
                tables["solve_diagnostics.csv"].append(dict(zip(SOLVE_FIELDS, (
                    system.system_id, str(component), "structurally_rank_deficient", "pcg_control", "0",
                    *("NA" for _ in range(14)),
                ), strict=True)))
        if system is singular:
            component = 0
            representative = list(system.nodal_affine[component])
            shifted = [representative[i] + mode[i] for i in range(len(mode))]
            for node_index in range(len(mode)):
                tables["nullspace_modes.csv"].append(dict(zip(NULLSPACE_MODE_FIELDS, (
                    system.system_id, "0", str(node_index), hexfloat(mode[node_index]), "exact_sampling_rref", "NA",
                    hexfloat(representative[node_index]), hexfloat(shifted[node_index]),
                ), strict=True)))
            matrix_d = [[Decimal.from_float(value) for value in row] for row in matrix_f]
            sampling_d = [[Decimal.from_float(value) for value in row] for row in sampling_f]
            gradient_d = [[[Decimal.from_float(float(value)) for value in system.gradients[p][node]] for node in range(len(system.nodes))] for p in range(len(system.points))]
            z_d = [Decimal.from_float(float(value)) for value in mode]
            representative_d = [Decimal.from_float(float(value)) for value in representative]
            shifted_d = [Decimal.from_float(float(value)) for value in shifted]
            mz = [decimal_dot(row, z_d) for row in matrix_d]
            sz = [decimal_dot(row, z_d) for row in sampling_d]
            gradient_vectors = [[sum((z_d[node] * gradient_d[p][node][c] for node in range(len(z_d))), Decimal(0)) for c in range(3)] for p in range(len(system.points))]
            gradient_norms = [decimal_l2(values) for values in gradient_vectors]
            gradient_rms = (sum((value * value for value in gradient_norms), Decimal(0)) / Decimal(len(gradient_norms))).sqrt()
            gradient_max = max(gradient_norms)
            matrix_frobenius = decimal_l2(value for row in matrix_d for value in row)
            sampling_frobenius = decimal_l2(value for row in sampling_d for value in row)
            z_l2 = decimal_l2(z_d)
            mz_denominator = matrix_frobenius * z_l2
            sz_denominator = sampling_frobenius * z_l2
            max_gradient_sum = max(sum((abs(z_d[node]) * decimal_l2(gradient_d[p][node]) for node in range(len(z_d))), Decimal(0)) for p in range(len(system.points)))
            gradient_bound_d = Decimal(128) * (Decimal(3 * max_stencil) * (Decimal(2) ** -52) / (Decimal(1) - Decimal(3 * max_stencil) * (Decimal(2) ** -52))) * max_gradient_sum
            visibility_ratio_d = gradient_max / gradient_bound_d
            rhs_component_d = [Decimal.from_float(value) for value in rhs_f[component]]
            particle_component_d = [Decimal.from_float(float(value[component])) for value in system.particle_velocity]
            base_metrics = projection_metrics_decimal(matrix_d, sampling_d, [Decimal(1)] * len(system.points), rhs_component_d, representative_d, representative_d, particle_component_d)
            shifted_metrics = projection_metrics_decimal(matrix_d, sampling_d, [Decimal(1)] * len(system.points), rhs_component_d, shifted_d, representative_d, particle_component_d)
            recon_base = [decimal_dot(row, representative_d) for row in sampling_d]
            recon_shift = [decimal_dot(row, shifted_d) for row in sampling_d]
            recon_delta = decimal_l2(recon_shift[p] - recon_base[p] for p in range(len(recon_base))) / sz_denominator
            tables["nullspace_metrics.csv"].append(dict(zip(NULLSPACE_METRIC_FIELDS, (
                system.system_id, "0", str(system.rank), "exact_sampling_rref", "true",
                decimal_text(decimal_l2(mz)), decimal_text(mz_denominator), decimal_text(decimal_l2(mz) / mz_denominator),
                decimal_text(decimal_l2(sz)), decimal_text(sz_denominator), decimal_text(decimal_l2(sz) / sz_denominator),
                decimal_text(gradient_max), decimal_text(gradient_rms), decimal_text(gradient_bound_d),
                decimal_text(visibility_ratio_d), "true", hexfloat(1), str(component), "analytic_affine",
                decimal_text(base_metrics["normalized_backward"]), decimal_text(shifted_metrics["normalized_backward"]), decimal_text(recon_delta),
                "oracle_dyadic", "identity", "false", "true",
            ), strict=True)))

    raw_tables = ("particles.csv", "nodes.csv", "stencils.csv", "matrix.csv", "rhs.csv")
    for system_row in tables["systems.csv"]:
        digest = hashlib.sha256()
        digest.update(b"MLS-PROJECTION-EXACTNESS-ASSEMBLY-v1\n")
        system_id = system_row["system_id"]
        for name in raw_tables:
            fields = CSV_SCHEMAS[name]
            for row in tables[name]:
                if row["system_id"] != system_id:
                    continue
                digest.update(name.encode("ascii"))
                for field in fields:
                    digest.update(b"\0")
                    digest.update(row[field].encode("utf-8"))
                digest.update(b"\n")
        system_row["assembly_payload_sha256"] = digest.hexdigest()

    for name, fields in CSV_SCHEMAS.items():
        write_csv(target / name, fields, tables[name])
    summary = {
        "schema": SCHEMA,
        "mode": "oracle_fixture",
        "producer": "python_independent_fixture",
        "seed": SEED,
        "source_sha": "0" * 40,
        "branch": "projection-exactness-nullspace-lab",
        "registered_system_ids": [system.system_id for system in systems],
        "analytic_witness_all_pass": True,
        "high_precision_all_pass": True,
        "pcg_miss_observed": any(
            row["normalized_forward_error"] != "NA"
            and (
                Decimal(row["normalized_forward_error"]) > HP_FORWARD_LIMIT
                or Decimal(row["normalized_reconstruction_error"]) > HP_RECONSTRUCTION_LIMIT
            )
            for row in tables["solve_diagnostics.csv"]
        ),
        "singular_center_invariant": True,
        "singular_gradient_visible": True,
        "diagnostic_pseudoinverse_promotion_eligible": False,
        "decision": "stop_center_state_gradient_nullspace_blocker",
        "promotion": False,
        "oracle": oracle_result,
        "row_counts": {name: len(rows) for name, rows in tables.items()},
        "tolerances": {
            "high_precision_normalized_backward_formula": "2^12*n*2^-104",
            "high_precision_normalized_forward": decimal_text(HP_FORWARD_LIMIT),
            "high_precision_normalized_reconstruction": decimal_text(HP_RECONSTRUCTION_LIMIT),
            "null_normalized_formula": "512*max(P,N)*2^-52",
            "gradient_absolute_floor_per_s": "1e-10",
            "gradient_visible_bound_multiplier": "1e4",
        },
    }
    (target / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifested = [*CSV_SCHEMAS, "summary.json"]
    hashes = {name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in manifested}
    manifest = {
        "algorithm": "SHA-256", "files": hashes, "schema": MANIFEST_SCHEMA,
        "pre_hash_sha256": hashlib.sha256(manifest_payload(hashes)).hexdigest(),
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run() -> dict:
    return build_oracle()[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--write-fixture", type=Path)
    args = parser.parse_args()
    result = run()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.verify:
        if args.verify.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"projection exactness/nullspace oracle mismatch: {args.verify}")
    if args.write_fixture:
        write_fixture(args.write_fixture)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
