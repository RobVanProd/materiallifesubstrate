"""Exact global-transform decoding for presealed numerical input streams.

This contains no occupancy algorithm, search, fixture labels, or oracle access.
The output is the fully expanded canonical geometry wire, hashed without
retaining it. Order/relabel variants are deliberately rejected here: they need
their separate namespace-aware decoder, not a silently unchanged stream.
"""
import argparse
from fractions import Fraction as Q
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import resource
import struct
import time

from occupied_geometry_input_check import Reader
from occupied_geometry_input import rational, header


def raw_q(r):
    sign = r.read(1)
    n = r.read(4)
    ncount = int.from_bytes(n, 'little')
    assert ncount <= 1024
    numerator = r.read(ncount)
    d = r.read(4)
    dcount = int.from_bytes(d, 'little')
    assert 1 <= dcount <= 1024
    denominator = r.read(dcount)
    result = sign + n + numerator + d + denominator
    decode_q(result)
    return result


@lru_cache(maxsize=65536)
def decode_q(raw):
    r = Reader.__new__(Reader)
    r.f = io.BytesIO(raw)
    q = r.q()
    r.end()
    return q


@lru_cache(maxsize=65536)
def linear_coordinate(terms, shift):
    return rational(shift + sum(coefficient * decode_q(raw)
                                for coefficient, raw in terms))


@lru_cache(maxsize=65536)
def multiply_coordinate(raw, factor):
    return rational(decode_q(raw) * factor)


def load_transform(path):
    r = Reader(path, 9)
    assert r.count == 1
    identity = r.u(8)
    matrix = tuple(tuple(r.q() for _ in range(3)) for _ in range(3))
    translation = tuple(r.q() for _ in range(3))
    boost = tuple(r.q() for _ in range(3))
    scale = r.q()
    ordering = r.u(1)
    r.end()
    assert scale > 0 and ordering == 0, 'order variants require the separate decoder'
    return identity, matrix, translation, boost, scale


def expanded(source, transform):
    _, matrix, translation, boost, scale = transform
    with source.open('rb') as f:
        prefix = f.read(24)
    assert len(prefix) == 24 and prefix[:8] == b'MLSOMG01'
    schema, kind, count = struct.unpack('<IIQ', prefix[8:])
    assert schema == 1 and kind in (1, 5, 6, 7)
    r = Reader(source, kind)
    assert r.count == count
    yield header(kind, count)
    def vector(raw, shift):
        return b''.join(linear_coordinate(tuple((scale*c,raw[j])
                         for j,c in enumerate(row) if c), shift[i])
                         for i,row in enumerate(matrix))
    for _ in range(count):
        if kind == 6:
            yield multiply_coordinate(raw_q(r), scale**2) + multiply_coordinate(raw_q(r), scale**3)
            continue
        identifier = r.read(8)
        if kind == 7:
            binding = r.read(9)
            yield identifier + binding + vector(tuple(raw_q(r) for _ in range(3)), boost)
        else:
            record = identifier + vector(tuple(raw_q(r) for _ in range(3)), translation)
            if kind == 5:
                volume, amount = raw_q(r), raw_q(r)
                record += multiply_coordinate(volume,scale**3) + amount
            yield record
    r.end()


def digest(source, transform):
    start = time.monotonic()
    h = hashlib.sha256()
    size = 0
    pending = bytearray()
    for raw in expanded(source, load_transform(transform)):
        pending.extend(raw)
        if len(pending) >= 1 << 20:
            size += len(pending)
            h.update(pending)
            pending.clear()
            assert time.monotonic()-start <= 1800, 'input decoding wall-time ceiling'
    size += len(pending)
    h.update(pending)
    return dict(size=size, sha256=h.hexdigest(), candidate_evaluations=0,
                complete_input_seal=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('transform',type=Path)
    a = p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    print(json.dumps(digest(a.source,a.transform),sort_keys=True))
