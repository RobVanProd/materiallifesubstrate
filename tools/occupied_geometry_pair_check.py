"""Independent streaming join check for the frozen doubled sphere inputs.

The already checked single-complex input is the reference. This checker does
not import the pair writer or a candidate geometry implementation.
"""
import argparse
from fractions import Fraction as Q
import json
from pathlib import Path
import resource
import time

from occupied_geometry_input_check import Reader


def check(single, pair):
    resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    start = time.monotonic()
    names = ('vertices', 'tetrahedra', 'facets', 'incidence', 'samples', 'resolution')
    counts = {}
    for kind, name in enumerate(names, 1):
        r = Reader(single / 'candidate' / (name + '.bin'), kind)
        counts[kind] = r.count
        r.f.close()
    for kind, name in enumerate(names, 1):
        target = Reader(pair / 'candidate' / (name + '.bin'), kind)
        assert target.count == counts[kind] * (1 if kind == 6 else 2)
        for side in range(1 if kind == 6 else 2):
            src = Reader(single / 'candidate' / (name + '.bin'), kind)
            for index in range(src.count):
                if kind == 6:
                    assert target.q() == src.q()
                    assert target.q() == 2 * src.q()
                    continue
                identity, original = target.u(8), src.u(8)
                namespace = 2 if kind == 4 else kind
                assert identity == original + side * counts[namespace]
                if kind in (1, 5):
                    x = tuple(src.q() for _ in range(3))
                    y = tuple(target.q() for _ in range(3))
                    assert y[0] - x[0] == (Q(3, 2) if side else Q(-3, 2))
                    assert y[1:] == x[1:]
                    if kind == 5:
                        assert target.q() == src.q()
                        assert 2 * target.q() == src.q()
                elif kind in (2, 3):
                    for _ in range(4 if kind == 2 else 3):
                        assert target.u(8) - src.u(8) == side * counts[1]
                else:
                    assert target.u(1) == src.u(1)
                    assert target.u(8) - src.u(8) == side * counts[3]
                    assert target.u(1) == src.u(1)
            src.end()
        target.end()
        assert time.monotonic() - start < 1800
    print(json.dumps(dict(status='PASS', source_counts=counts,
                          exact_translation_and_identity_joins=True,
                          candidate_evaluations=0, complete_input_seal=False), sort_keys=True))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('single', type=Path)
    p.add_argument('pair', type=Path)
    a = p.parse_args()
    check(a.single, a.pair)
