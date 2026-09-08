"""Candidate C global-amplitude certificate pilot, not a completed row runner.

Reads only I1 numeric input. If the global Gaussian envelope is <1/2, its
occupied set is rigorously empty. Otherwise this pilot makes no geometry claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import gmpy2 as g

from occupied_geometry_runtime_wire import Reader,Work,WorkLimit,WireError


def bound(volume,delta2):
    with g.context(precision=256,round=g.RoundDown):
        pi=g.const_pi();length=g.rootn(g.mpfr(volume),3)
        delta=g.sqrt(g.mpfr(delta2));h=g.sqrt(delta*length)
        normalizer=(2*pi)*g.sqrt(2*pi)*h*h*h
    if normalizer<=0:raise ArithmeticError('unresolved positive bandwidth')
    with g.context(precision=256,round=g.RoundUp):
        upper=g.mpfr(volume)/normalizer
    return dict(global_field_upper=str(g.mpq(upper)),
                positive_normalizer_lower=str(g.mpq(normalizer)))


def run(view):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    if set(p.name for p in view.iterdir())!={'5.bin','6.bin','7.bin','8.bin'}:
        raise WireError('I1 view contains unauthorized tables')
    work=Work();work.charge('global_bound_object')
    r=Reader(view/'6.bin',6)
    if r.count!=1:raise WireError('resolution count')
    delta2,volume=r.q(),r.q();r.end()
    if delta2<=0 or volume<=0:raise WireError('nonpositive descriptor')
    r=Reader(view/'5.bin',5);count=r.count
    try:
        # Each summand in this certified global envelope is charged, even
        # though exp(-distance^2/(2h^2)) <= 1 avoids a pointwise field search.
        work.charge('global_envelope_primitive_contributions',count)
    except WorkLimit:
        r.f.close()
        return dict(status='PILOT_RESOURCE_INCONCLUSIVE',work=work.used,pending=work.pending,
                    complete_row=False,candidate='C',precision=256)
    total=g.mpq(0);ids=set()
    for _ in range(count):
        identifier=r.uint(8)
        if not identifier or identifier in ids:raise WireError('sample identity')
        ids.add(identifier)
        for _ in range(3):r.q()
        weight,amount=r.q(),r.q()
        if weight<=0 or amount<=0:raise WireError('nonpositive sample weight')
        total+=weight
    r.end()
    if total!=volume:raise WireError('sample volume partition')
    envelope=bound(volume,delta2)
    empty=g.mpq(envelope['global_field_upper'])<g.mpq(1,2)
    files={}
    for path in sorted(view.iterdir()):
        with path.open('rb') as f:files[path.name]=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(status='PILOT_GLOBAL_EMPTY_CERTIFIED' if empty else 'PILOT_BOUND_NOT_DECISIVE',
        complete_row=False,candidate='C',information_tier='I1',precision=256,
        sample_count=count,work=work.used,inputs=files,**envelope,
        occupied_volume_interval=['0','0'] if empty else None,
        boundary='empty' if empty else 'not_evaluated',
        claim_scope='global amplitude only; no full row or lab disposition')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('view',type=Path)
    print(json.dumps(run(p.parse_args().view),sort_keys=True,separators=(',',':')))
