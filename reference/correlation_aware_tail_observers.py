"""Noncausal polynomial-observer envelopes over shared phase symbols.

These primitives are not yet wired into a full-tail certificate. They retain
signed affine dependence and bound only the quadratic remainder independently.
"""
from dataclasses import dataclass
from fractions import Fraction as Q

from correlation_aware_tail import Affine
from bounded_phase_tail_interval import Box, directed


@dataclass(frozen=True)
class Envelope:
    linear: Affine
    radius: Q = Q()

    def __post_init__(self):
        assert self.radius >= 0

    @staticmethod
    def rounded(linear, radius=Q()):
        c = directed(linear.center, False)
        coefficients = {j: directed(v, False) for j, v in linear.coefficients}
        lost = abs(c-linear.center)
        for j, v in linear.coefficients:
            lost += abs(v-coefficients[j])
        return Envelope(Affine.make(c, coefficients), directed(radius+lost, True))

    def __add__(self, other):
        return Envelope.rounded(self.linear+other.linear, self.radius+other.radius)

    def scale(self, value):
        return Envelope.rounded(self.linear.scale(value), self.radius*abs(value))

    def bounds(self, domains):
        linear = self.linear.bounds(domains)
        return Box(directed(linear.lo-self.radius, False),
                   directed(linear.hi+self.radius, True))


def product(a, b):
    # (a0+da)(b0+db) = a0*b0 + a0*db+b0*da + da*db.
    da, db = a-Affine.make(a.center), b-Affine.make(b.center)
    linear = Affine.make(a.center*b.center)+db.scale(a.center)+da.scale(b.center)
    ra = sum((abs(c) for _, c in da.coefficients), Q())
    rb = sum((abs(c) for _, c in db.coefficients), Q())
    return Envelope.rounded(linear, ra*rb)


def kinetic(state, masses, momentum_quantum, mass_quantum):
    total = Envelope(Affine.make(0))
    for identifier, (_, momentum) in state.items():
        factor = momentum_quantum**2/(2*masses[identifier]*mass_quantum)
        for component in momentum:
            total = total+product(component, component).scale(factor)
    return total


def angular(state, length_quantum, momentum_quantum):
    total = [Envelope(Affine.make(0)) for _ in range(3)]
    for position, momentum in state.values():
        for axis, j, k in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
            cross = product(position[j], momentum[k])+product(position[k], momentum[j]).scale(-1)
            total[axis] = total[axis]+cross.scale(length_quantum*momentum_quantum)
    return total


def signed_weighted_sum(values, weights):
    assert len(values) == len(weights)
    linear, radius = Affine.make(0), Q()
    for value, weight in zip(values, weights):
        linear = linear+value.linear.scale(weight)
        radius += abs(weight)*value.radius
    # Combine the signed common coefficients before rounding the accumulator.
    return Envelope.rounded(linear, radius)


def slope(values, times):
    assert len(values) == len(times) and len(times) >= 2
    mean = sum(times, Q())/len(times)
    weights = [time-mean for time in times]
    denominator = sum((w*w for w in weights), Q())
    assert denominator > 0
    numerator = signed_weighted_sum(values, weights)
    return numerator.scale(1/denominator)
