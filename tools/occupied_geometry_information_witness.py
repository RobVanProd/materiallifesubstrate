"""Exact missing-domain-information witness on an authenticated parent state.

Hypothetical domains are noncausal logical extensions, not candidate fixtures,
World mutations, density laws or a selected geometry convention.
"""
import argparse
from fractions import Fraction as Q
import hashlib
import itertools
import json
from pathlib import Path
from material_phase_checkpoint import fnv


def phase_value(raw):
    assert len(raw)==17 and raw[0] in (0,1) and int.from_bytes(raw[1:3],'little')==96
    exponent=int.from_bytes(raw[3:5],'little',signed=True)
    mantissa=int.from_bytes(raw[5:],'big')
    if not mantissa:
        assert raw[0]==0 and exponent==0;return Q(0)
    assert -16382<=exponent<=16383 and 1<<95<=mantissa<1<<96
    shift=exponent-95
    value=Q(mantissa)*(Q(2**shift) if shift>=0 else Q(1,2**-shift))
    return -value if raw[0] else value


def run(baseline,case):
    result=json.loads((baseline/'result.json').read_text());assert result['status']=='PASS'
    row=next(r for r in result['rows'] if r['case']==case)
    raw=(baseline/(case+'.checkpoint')).read_bytes();sha=hashlib.sha256(raw).hexdigest()
    assert sha==row['checkpoint_sha256']
    magic=b'MLS-MATERIAL-PHASE-v1\n';assert raw.startswith(magic)
    assert int.from_bytes(raw[-8:],'little')==fnv(raw[:-8])
    pos=len(magic);fields=[]
    for _ in range(4):
        size=int.from_bytes(raw[pos:pos+8],'little');pos+=8
        fields.append(raw[pos:pos+size]);pos+=size
    assert pos==len(raw)-8
    words=iter(fields[1].decode().split());trajectory=next(words);path=next(words)
    level,dt,step,count=[int(next(words)) for _ in range(4)];points=[];identities=[]
    for _ in range(count):
        ident,generation,mechanics,mass,heat,structural,stored,thermal,mixtures=[int(next(words)) for _ in range(9)]
        assert mass>0
        for _ in range(mixtures):
            next(words);next(words)
        phase=bytes.fromhex(next(words));assert len(phase)==102
        points.append(tuple(phase_value(phase[17*j:17*(j+1)]) for j in range(3)))
        identities.append([ident,generation,mechanics])
    assert count>1 and len(set(points))==count
    separation=min(max(abs(a[j]-b[j]) for j in range(3)) for a,b in itertools.combinations(points,2))
    assert separation>0;epsilon=separation/8
    a=(epsilon,epsilon,epsilon);b=(2*epsilon,epsilon/2,epsilon)
    def volume(extents):return 8*extents[0]*extents[1]*extents[2]
    assert volume(a)==volume(b)>0 and 4*epsilon<separation
    witness=tuple(points[0][j]+(3*epsilon/2 if j==0 else 0) for j in range(3))
    def member(point,centre,extents):return all(abs(x-c)<=e for x,c,e in zip(point,centre,extents))
    assert not any(member(witness,p,a) for p in points)
    assert member(witness,points[0],b)
    # Both families consist of pairwise disjoint parcels: in an axis where
    # centres differ by at least separation, summed half-widths are <=4 epsilon.
    for x,y in itertools.combinations(points,2):
        assert any(abs(x[j]-y[j])>4*epsilon for j in range(3))
    return dict(finding='current_state_does_not_determine_occupied_geometry',
        state_checkpoint_sha256=sha,case=case,material_identities=identities,
        state_fields_and_relations_identical=True,
        hypothetical_domain_class='disjoint axis-aligned parcels centered on the unchanged phase positions',
        centres_raw=[[str(x) for x in p] for p in points],
        family_a_half_extents_raw=list(map(str,a)),family_b_half_extents_raw=list(map(str,b)),
        equal_per_packet_volume_raw=str(volume(a)),minimum_centre_separation_linf_raw=str(separation),
        equal_centroid=True,distinguishing_point_raw=list(map(str,witness)),
        membership_a=False,membership_b=True,
        units='raw B96 position units; SI lengths multiply unchanged Lq and volumes Lq^3',
        claim_limit='nonuniqueness in this domain class, not impossibility of choosing a new convention or a density law',
        candidate_input=False,world_state_modified=False,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('case')
    p.add_argument('output',type=Path);args=p.parse_args();assert not args.output.exists()
    result=run(args.baseline,args.case)
    args.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(finding=result['finding'],state_checkpoint_sha256=result['state_checkpoint_sha256'],
                         packets=len(result['centres_raw']),promotion='NO_PROMOTION')))
