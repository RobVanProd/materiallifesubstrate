"""Independent exact validation of prescribed per-primitive motion input.

No imports from the motion writer. This checks the motion contract, not an
occupied-volume/contact result or the complete pre-data root.
"""
import argparse
from fractions import Fraction as Q
import json
from pathlib import Path
import resource
import time

from occupied_geometry_input_check import Reader


def check(source, motion, mode):
    resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    start = time.monotonic()
    m = Reader(motion, 7)
    total = 0
    counts = {}
    for kind, name in ((1, 'vertices'), (5, 'samples')):
        r = Reader(source / 'candidate' / (name + '.bin'), kind)
        counts[kind] = r.count
        for index in range(r.count):
            identity = r.u(8)
            assert identity == index + 1
            position = tuple(r.q() for _ in range(3))
            if kind == 5:
                assert r.q() > 0 and r.q() > 0
            total += 1
            assert (m.u(8), m.u(1), m.u(8)) == (total, kind, identity)
            velocity = tuple(m.q() for _ in range(3))
            if mode == 'u':
                assert 4 * velocity[0] == -position[0]
                assert velocity[1:] == (0, 0)
                # This is a global affine map, not separately moving arms.
                assert all(position[j] + 2 * velocity[j] ==
                           position[j] * (Q(1, 2) if j == 0 else 1)
                           for j in range(3))
            elif mode == 'pair':
                assert abs(position[0]) >= Q(1, 2)
                assert velocity[1:] == (0, 0)
                assert 2 * velocity[0] == (1 if position[0] < 0 else -1)
            elif mode == 'plane':
                assert velocity == (0, 0, -1)
            else:
                raise ValueError('unknown prescribed motion')
        r.end()
        assert time.monotonic() - start < 1800
    assert total == m.count
    m.end()
    print(json.dumps(dict(status='PASS', mode=mode, records=total,
                          target_counts=counts, candidate_evaluations=0,
                          complete_input_seal=False), sort_keys=True))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('motion', type=Path)
    p.add_argument('--mode', choices=('u', 'pair', 'plane'), required=True)
    a = p.parse_args()
    check(a.source, a.motion, a.mode)
