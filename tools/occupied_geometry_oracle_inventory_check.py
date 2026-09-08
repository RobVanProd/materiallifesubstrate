"""Independent exact-rational check of the pre-data analytical oracle inputs."""
import argparse
from fractions import Fraction as Q
import json
from pathlib import Path


def q(value):
    assert isinstance(value,list) and len(value)==2
    a,b=map(int,value);v=Q(a,b)
    assert [str(v.numerator),str(v.denominator)]==value
    return v


def dyadic512(value,up):
    assert value>0
    exponent=value.numerator.bit_length()-value.denominator.bit_length()
    power=lambda e:Q(2**e) if e>=0 else Q(1,2**(-e))
    if power(exponent)>value:exponent-=1
    assert power(exponent)<=value<2*power(exponent)
    unit=power(exponent-511);scaled=value/unit
    integer=scaled.numerator//scaled.denominator
    if up and scaled.denominator!=1:integer+=1
    return integer*unit


def check(root):
    assert set(p.name for p in root.iterdir())=={'constants.json','domains.json','search-obligations.json'}
    constants=json.loads((root/'constants.json').read_text())
    assert constants['oracle_precision']==512
    assert constants['coordinate_grid_power']==-256 and constants['weight_share_grid_power']==-128
    terms=constants['pi']['machin_terms'];bounds=[]
    for base,count in zip((5,239),terms):
        assert type(count) is int and count>1
        total=sum((Q((-1)**i,(2*i+1)*base**(2*i+1)) for i in range(count)),Q(0))
        next_value=Q((-1)**count,(2*count+1)*base**(2*count+1))
        assert abs(next_value)<=Q(1,2**608)<Q(1,(2*count-1)*base**(2*count-1))
        bounds.append((min(total,total+next_value),max(total,total+next_value)))
    a,b=bounds[0];c,d=bounds[1];lo,hi=16*a-4*d,16*b-4*c
    assert list(map(q,constants['pi']['exact_series_enclosure']))==[lo,hi]
    assert hi-lo<=Q(1,2**600)
    assert list(map(q,constants['pi']['outward_512_enclosure']))==[dyadic512(lo,False),dyadic512(hi,True)]
    domains=json.loads((root/'domains.json').read_text());assert len(domains)==7
    totals={}
    for f,row in enumerate(domains,1):
        assert row['fixture']==f and row['levels']==list(range(5)) and row['variants']==list(range(33))
        times=[Q(j,8) for j in range(17)] if f in (5,6,7) else [Q(0)]
        assert list(map(q,row['static_times']))==times
        sweeps=[[Q(0),Q(2)]]+[[Q(j,8),Q(j+1,8)] for j in range(16)] if f in (5,6,7) else []
        assert [[q(x) for x in p] for p in row['swept_intervals']]==sweeps
        if f in (1,2,7):
            assert row['kind']=='union_of_closed_boxes'
            boxes=[[[q(x) for x in axis] for axis in box] for box in row['boxes']]
            expected={1:[[[-1,1],[-1,1],[-1,1]]],2:[[[-2,2],[-2,2],[Q(-1,4),Q(1,4)]]],
                7:[[[-1,1],[-1,Q(-3,4)],[Q(-1,4),Q(1,4)]],
                   [[-1,Q(-3,4)],[Q(-3,4),1],[Q(-1,4),Q(1,4)]],
                   [[Q(3,4),1],[Q(-3,4),1],[Q(-1,4),Q(1,4)]]]}[f]
            assert boxes==expected
            total=Q(0)
            for i,box in enumerate(boxes):
                volume=Q(1)
                for low,high in box:assert high>low;volume*=high-low
                total+=volume
                for other in boxes[:i]:
                    assert any(min(a[1],b[1])<=max(a[0],b[0]) for a,b in zip(box,other))
            assert total==(Q(11,16) if f==7 else 8);totals[f]=str(total)
            motion=row['motion'];assert motion['kind']=='affine'
            assert list(map(q,motion['diagonal_constant']))==[1,1,1]
            assert list(map(q,motion['diagonal_time_coefficient']))==[Q(-1,4) if f==7 else 0,0,0]
            if f==7:assert q(row['invalid_identity_time'])==4
        else:
            assert row['kind']=='union_of_closed_unit_balls' and q(row['radius'])==1
            centres=[tuple(map(q,p)) for p in row['centres']]
            velocities=[tuple(map(q,p)) for p in row['velocities']]
            assert centres==([(0,0,0)] if f==3 else [(0,0,2)] if f==6 else [(Q(-3,2),0,0),(Q(3,2),0,0)])
            assert velocities==([(0,0,-1)] if f==6 else [(Q(1,2),0,0),(Q(-1,2),0,0)] if f==5 else [(0,0,0)]*len(centres))
            assert [(p['axis'],p['sign']) for p in row['sphere_charts']]==[(i,s) for i in range(3) for s in (-1,1)]
            assert all([[q(x) for x in axis] for axis in p['parameter_box']]==[[-1,1],[-1,1]] for p in row['sphere_charts'])
            assert row['union_boundary_rule']=='Retain component boundary only outside every other component interior; retain all seam strata.'
            if f==6:assert list(map(q,row['external_plane']))==[0,0,1,0,0]
    search=json.loads((root/'search-obligations.json').read_text())
    assert [search[k] for k in ('runtime_work_cap','memory_bytes','wall_seconds','evidence_bytes')]==[2**22,2**31,1800,2**33]
    assert q(search['volume_width'])==Q(1,5000)
    assert q(search['distance_time_location_width'])==Q(1,2000) and q(search['normal_width'])==Q(1,1000)
    assert search['spatial_split']=='exact midpoint of longest side; ties x,y,z'
    assert search['queue']=='depth then binary/Morton ancestry'
    assert search['triangle_split']=='barycentric midpoint four-way'
    print(json.dumps(dict(status='PASS',domains=7,exact_box_volumes=totals,
        exact_directed_constant_rounding=True,candidate_evaluations=0,complete_input_seal=False),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path)
    a=p.parse_args();check(a.directory)
