"""Materialize the frozen oracle-only domains, charts and search obligations.

No candidate geometry is evaluated here. Adaptive covers remain runtime work;
this file freezes their roots/rules, never precomputes candidate answers.
"""
import argparse
from fractions import Fraction as Q
import json
from pathlib import Path
import gmpy2 as g


def pair(q):
    q=Q(q);return [str(q.numerator),str(q.denominator)]


def atan(n):
    s=Q(0);k=0
    while True:
        s+=Q((-1)**k,(2*k+1)*n**(2*k+1));k+=1
        next_term=Q((-1)**k,(2*k+1)*n**(2*k+1))
        if abs(next_term)<=Q(1,2**608):return min(s,s+next_term),max(s,s+next_term),k


def build(out):
    out.mkdir(parents=True,exist_ok=False)
    a,b,na=atan(5);c,d,nb=atan(239)
    lo,hi=16*a-4*d,16*b-4*c
    assert hi-lo<=Q(1,2**600)
    def rounded(q,mode):
        with g.context(precision=512,round=mode):v=g.mpq(g.mpfr(g.mpq(q.numerator,q.denominator)))
        return Q(int(v.numerator),int(v.denominator))
    lower,upper=rounded(lo,g.RoundDown),rounded(hi,g.RoundUp)
    assert lower<=lo<=hi<=upper
    constants=dict(pi=dict(exact_series_enclosure=[pair(lo),pair(hi)],
        outward_512_enclosure=[pair(lower),pair(upper)],machin_terms=[na,nb]),
        oracle_precision=512,coordinate_grid_power=-256,weight_share_grid_power=-128)
    boxes={1:[[[-1,1],[-1,1],[-1,1]]],2:[[[-2,2],[-2,2],[Q(-1,4),Q(1,4)]]],
           7:[[[-1,1],[-1,Q(-3,4)],[Q(-1,4),Q(1,4)]],
              [[-1,Q(-3,4)],[Q(-3,4),1],[Q(-1,4),Q(1,4)]],
              [[Q(3,4),1],[Q(-3,4),1],[Q(-1,4),Q(1,4)]]]}
    domains=[]
    for fixture in range(1,8):
        row=dict(fixture=fixture,levels=list(range(5)),variants=list(range(33)))
        if fixture in boxes:
            row.update(kind='union_of_closed_boxes',boxes=[[[pair(x) for x in axis] for axis in box] for box in boxes[fixture]])
            row['motion']=dict(kind='affine',diagonal_constant=[pair(1)]*3,
                diagonal_time_coefficient=[pair(Q(-1,4) if fixture==7 else 0),pair(0),pair(0)])
        else:
            centres=([(0,0,0)] if fixture==3 else [(0,0,2)] if fixture==6 else [(Q(-3,2),0,0),(Q(3,2),0,0)])
            velocities=([(0,0,-1)] if fixture==6 else [(Q(1,2),0,0),(Q(-1,2),0,0)] if fixture==5 else [(0,0,0)]*len(centres))
            row.update(kind='union_of_closed_unit_balls',radius=pair(1),
                centres=[[pair(x) for x in p] for p in centres],
                velocities=[[pair(x) for x in p] for p in velocities])
            row['sphere_charts']=[dict(axis=j,sign=s,parameter_box=[[pair(-1),pair(1)]]*2,
                                      mapping='normalize(sign*e_axis+a*e_l+b*e_m); l<m')
                                  for j in range(3) for s in (-1,1)]
            row['union_boundary_rule']='Retain component boundary only outside every other component interior; retain all seam strata.'
        row['static_times']=[pair(Q(j,8)) for j in range(17)] if fixture in (5,6,7) else [pair(0)]
        row['swept_intervals']=[[pair(0),pair(2)]]+[[pair(Q(j,8)),pair(Q(j+1,8))] for j in range(16)] if fixture in (5,6,7) else []
        if fixture==6:row['external_plane']=[pair(0),pair(0),pair(1),pair(0),pair(0)]
        if fixture==7:row['invalid_identity_time']=pair(4)
        domains.append(row)
    search=dict(runtime_work_cap=2**22,memory_bytes=2**31,wall_seconds=1800,evidence_bytes=2**33,
        root_bounds=dict(A='sample bounds enlarged by outward maximum same-volume radius',
            B='vertex extrema',C='sample bounds enlarged by smallest positive integer R satisfying the registered strict Gaussian tail inequality'),
        spatial_split='exact midpoint of longest side; ties x,y,z',
        queue='depth then binary/Morton ancestry',
        children='closed children cover parent; disjoint interiors for volume',
        triangle_split='barycentric midpoint four-way',
        swept_split='longest spatial/time normalized side; time normalized by horizon; ties x,y,z,t',
        swept_queue='time lower endpoint then ancestry',
        boundary='outer covering alone is insufficient; require independent existence witnesses, including holes and union seams',
        closest_set='keep every cell with lower bound <= best certified upper bound; do not discard tied minima',
        volume_width=pair(Q(1,5000)),distance_time_location_width=pair(Q(1,2000)),normal_width=pair(Q(1,1000)),
        scope='Rules only; adaptive regions and candidate validity/search predicates remain charged runtime work.')
    for name,payload in (('constants.json',constants),('domains.json',domains),('search-obligations.json',search)):
        (out/name).write_text(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status='MATERIALIZED_NOT_YET_INDEPENDENTLY_CHECKED',domains=7,
        candidate_evaluations=0,complete_input_seal=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    a=p.parse_args();build(a.output)
