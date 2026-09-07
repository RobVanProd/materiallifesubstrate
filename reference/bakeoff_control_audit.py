"""Independent integer-rounder reconstruction of every midpoint Picard sweep.

This module imports neither MPFR nor the candidate solver. A log of individually
correct primitives is insufficient: the complete operation graph and iteration
state dependency are reconstructed here as well.
"""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import struct
import bounded_integrator_bakeoff_check as c

f=c.f


def read(p):return json.loads(p.read_text())


def sweep(model,old,guess,masses,ids,n,bits):
    rn=lambda v:c.rn(v,bits)
    lq=rn(f.LQ);coef=rn(n*f.TQ*f.LQ/f.PQ)
    midpoint=list(old);out=list(old);lookup={pid:i for i,pid in enumerate(ids)}
    for i,m in enumerate(masses):
        drift=rn(Q(n,2*m))
        for a in range(3):
            k=6*i+a
            out[k]=rn(old[k]+rn(drift*rn(old[k+3]+guess[k+3])))
            midpoint[k]=rn(rn(old[k]+guess[k])/2)
    geometry=[];cells=[]
    for rel in model.relations:
        i,j=lookup[rel.first_id],lookup[rel.second_id]
        raw=[rn(midpoint[6*j+a]-midpoint[6*i+a]) for a in range(3)]
        si=[float(rn(v*lq)) for v in raw]
        ref=[float(q*f.LQ) for q in f.reference_offset(model,rel)]
        length,e=f.path_b_geometry(si,ref,rel.rest_length)
        geometry.append((raw,length,e));cells.append([struct.pack('>d',v).hex() for v in si])
    gs=[]
    for row in model.h:
        total=0.0
        for h,(_,_,e) in zip(row,geometry):total+=h*e
        gs.append(total)
    impulses=[]
    for rel,(raw,length,_),g in zip(model.relations,geometry,gs):
        alpha=rn(rn(coef*Q.from_float(g))/Q.from_float(length))
        impulse=[rn(alpha*v) for v in raw];impulses.append(list(map(str,impulse)))
        i,j=lookup[rel.first_id],lookup[rel.second_id]
        for a,J in enumerate(impulse):
            out[6*i+3+a]=rn(out[6*i+3+a]+J)
            out[6*j+3+a]=rn(out[6*j+3+a]-J)
    return out,dict(cells=cells,lengths=[struct.pack('>d',v[1]).hex() for v in geometry],
        conjugates=[struct.pack('>d',v).hex() for v in gs],impulses=impulses)


def audit_solver(model,wire,audit):
    ids,masses,_,old=c.decode_wire(wire);bits=audit['bits'];n=audit['n']
    assert bits in (256,384),'scratch precision changed'
    c.audit_operations(audit);c.audit_counts(audit,len(ids),len(model.relations))
    c.audit_norms(audit,old)
    rn=lambda v:c.rn(v,bits)
    guess=list(old)
    for i,m in enumerate(masses):
        for a in range(3):
            k=6*i+a;guess[k]=rn(old[k]+rn(rn(Q(n,m))*old[k+3]))
    for j,item in enumerate(audit['iterations']):
        assert list(map(Q,item['guess']))==guess,'warm start or wrong iteration dependency'
        new,_=sweep(model,old,guess,masses,ids,n,bits)
        residual,force=sweep(model,old,new,masses,ids,n,bits)
        assert new==list(map(Q,item['new'])),'midpoint operation graph changed'
        assert residual==list(map(Q,item['residual_next'])),'fresh residual graph changed'
        delta=[rn(a-b) for a,b in zip(new,guess)]
        defect=[rn(a-b) for a,b in zip(residual,new)]
        units=[rn(f.LQ) if k%6<3 else rn(f.PQ) for k in range(len(old))]
        norm=lambda v:max(abs(rn(u*x)) for u,x in zip(units,v))
        D,R=norm(delta),norm(defect);Z=max(Q(1),norm(old),norm(new))
        tau=Q(2)**(-180 if bits==256 else -300);threshold=rn(tau+rn(tau*Z))
        assert [D,R,Z,threshold]==[Q(item[k]) for k in ('D','R','Z','tolerance')],'norm record changed'
        passed=D<=threshold and R<=threshold
        assert passed==(j==len(audit['iterations'])-1),'not the first passing iterate'
        if passed:assert force==audit['force'],'accepted force/impulse trace changed'
        guess=new
    return guess


def audit_case(model,row,audit256,audit384):
    wire=bytes.fromhex(row['prior_wire']);ids,masses,t,old=c.decode_wire(wire)
    assert row['completed_steps']==0 and row['returned_prior_wire']==row['prior_wire'] and row['atomic_prior_unchanged'],'partial rejection'
    proposals=[]
    for audit,key in ((audit256,'proposed_wire'),(audit384,'verifier_proposed_wire')):
        assert audit['n']==f.TIMESTEPS_RAW[row['level']],'wrong timestep'
        values=audit_solver(model,wire,audit)
        pi,pm,pt,pv=c.decode_wire(bytes.fromhex(row[key]))
        assert pi==ids and pm==masses and pt==t+audit['n'],'proposal metadata changed'
        assert pv==[c.rn(q,96) for q in values],'proposal is not frozen RN96 output'
        proposals.append(pv)
    mismatch=proposals[0]!=proposals[1]
    if mismatch:
        assert row['status']=='reject_integrator_solver' and row['reason']=='256_384_output_mismatch'
        assert row['output_agreement'] is False
        differences=[]
        for k,(a,b) in enumerate(zip(*proposals)):
            if a!=b:differences.append(dict(packet=ids[k//6],component=k%6,
                solver256=str(a),verifier384=str(b),signed_SI_difference=str((a-b)*(f.LQ if k%6<3 else f.PQ))))
        return dict(status=row['status'],reason=row['reason'],output_differences=differences)
    assert row['output_agreement'] is True
    certificate=c.fixed_cell_root(model,wire,bytes.fromhex(row['proposed_wire']),audit384)
    assert certificate==row['certificate'],'exact root/cell certificate changed'
    assert row['status']==certificate['status']
    return dict(status=row['status'],reason=certificate.get('reason'))


def audit(parent,records,twin=None):
    models=f.load_models(parent/'parent/parent/parent/inputs/raw-a')
    inventory=read(records/'b-short-control-inventory.json')
    assert [(r['scenario'],r['level']) for r in inventory]==[(s,l) for s in f.SCENARIOS for l in range(5)],'incomplete inventory'
    results=[]
    for row in inventory:
        label=f"{row['scenario']}-L{row['level']}"
        assert row==read(records/f'{label}-control.json')
        model=models['octahedron' if row['scenario']=='octahedron_deformation' else 'k4']
        result=audit_case(model,row,read(records/f'{label}-solver256.json'),read(records/f'{label}-verifier384.json'))
        result.update(scenario=row['scenario'],level=row['level']);results.append(result)
        print(label+' independent midpoint graph PASS',flush=True)
    cs=read(records/'c-compatibility.json')
    assert len(cs)==1 and cs[0]['scenario']=='k4_breathing' and cs[0]['level']==0
    row=cs[0];old,new=map(bytes.fromhex,(row['old_wire'],row['new_wire']))
    expected=c.compatibility(models['k4'],old,new)
    assert all(row[k]==v for k,v in expected.items()),'C identity misreported'
    assert row['identical_endpoint']==c.compatibility(models['k4'],old,old)
    if twin is not None:
        names={p.name for p in records.iterdir() if p.is_file() and p.name!='external-resources.json'}
        assert names=={p.name for p in twin.iterdir() if p.is_file() and p.name!='external-resources.json'}
        for name in names:assert (records/name).read_bytes()==(twin/name).read_bytes(),'scientific twin mismatch: '+name
    return dict(passed=True,rows=results,C=expected,scientific_twin_identical=twin is not None,
        bounded_trajectories_run=0,scope='independent first-step graph audit; no B or C eligibility claimed')


if __name__=='__main__':
    import resource # Linux evidence runner; arithmetic module is platform independent
    p=argparse.ArgumentParser()
    for name in ('parent','records','output'):p.add_argument(name,type=Path)
    p.add_argument('--twin',type=Path);a=p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    result=audit(a.parent,a.records,a.twin)
    with a.output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'));stream.write('\n')
