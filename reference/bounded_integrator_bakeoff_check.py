"""Independent exact arithmetic for bakeoff cells, defects and compatibility.

No MPFR and no candidate-solver import. All inputs are wire dyadics/bit patterns.
"""
from fractions import Fraction as Q
import struct
import bounded_fractional_phase_state_oracle as f
from defect_recurrence_tail import decode_wire
from correlation_aware_binary64_cells import contains, decode


def rn(q, bits):
    q=Q(q)
    if not q: return q
    e=abs(q.numerator).bit_length()-q.denominator.bit_length()
    if abs(q)<Q(2)**e:e-=1
    assert -16382<=e<=16383
    unit=Q(2)**(e-bits+1)
    a,b=divmod(abs(q)/unit,1)
    a=int(a)
    if b>Q(1,2) or (b==Q(1,2) and a%2):a+=1
    return (-1 if q<0 else 1)*a*unit


def audit_operations(audit):
    bits=audit['bits']; assert bits in (256,384)
    for kind,args,value,inexact in audit['operations']:
        a=list(map(Q,args)); out=Q(value)
        if kind=='convert': exact=a[0]
        elif kind=='add': exact=a[0]+a[1]
        elif kind=='sub': exact=a[0]-a[1]
        elif kind=='mul': exact=a[0]*a[1]
        elif kind=='div': exact=a[0]/a[1]
        else: raise AssertionError('unknown primitive')
        assert out==rn(exact,bits),'independent rounded primitive mismatch'
        assert inexact==(out!=exact),'inexact flag mismatch'
    assert audit['sweeps']<=128
    return len(audit['operations'])


def norm(values):
    return max(abs(q)*(f.LQ if i%6<3 else f.PQ) for i,q in enumerate(values))


def outward(q,up,bits=384):
    if not q:return q
    e=abs(q.numerator).bit_length()-q.denominator.bit_length()
    if abs(q)<Q(2)**e:e-=1
    unit=Q(2)**(e-bits+1); scaled=q/unit
    k=scaled.numerator//scaled.denominator
    if up and scaled!=k:k+=1
    return k*unit


def audit_norms(audit,old):
    tau=Q(2)**(-180 if audit['bits']==256 else -300)
    row=audit['iterations'][-1]
    guess,new,res=([Q(x) for x in row[k]] for k in ('guess','new','residual_next'))
    D=norm([a-b for a,b in zip(new,guess)])
    R=norm([a-b for a,b in zip(res,new)])
    Z=max(Q(1),norm(old),norm(new))
    assert D<=tau*(1+Z) and R<=tau*(1+Z),'exact-unit tolerance not satisfied'
    return dict(D=str(D),R=str(R),Z=str(Z),bound=str(tau*(1+Z)))


def audit_counts(audit,packets,relations):
    iterations=len(audit['iterations'])
    assert audit['sweeps']==2*iterations==audit['force_calls']
    expected=20*packets+6+iterations*(60*packets+38*relations+2)
    assert len(audit['operations'])==expected,'omitted/false primitive inventory'
    return expected


def endpoint_geometry(model,wire):
    ids,_,_,values=decode_wire(wire); lookup={p:i for i,p in enumerate(ids)}
    lengths=[]; extensions=[]; relations=[]; bitcells=[]
    for rel in model.relations:
        i,j=lookup[rel.first_id],lookup[rel.second_id]
        raw=[values[6*j+a]-values[6*i+a] for a in range(3)]
        si=[float(rn(rn(r,96)*rn(f.LQ,96),96)) for r in raw]
        ref=[float(q*f.LQ) for q in f.reference_offset(model,rel)]
        length,e=f.path_b_geometry(si,ref,rel.rest_length)
        lengths.append(Q.from_float(length));extensions.append(Q.from_float(e))
        relations.append([v*f.LQ for v in raw]);bitcells.append([struct.pack('>d',v).hex() for v in si])
    gs=[]
    for row in model.h:
        total=0.0
        for h,e in zip(row,extensions):total+=h*float(e)
        gs.append(Q.from_float(total))
    twice=0.0
    for e,g in zip(extensions,gs):twice+=float(e)*float(g)
    return relations,lengths,extensions,gs,Q.from_float(0.5*twice),bitcells


def compatibility(model,old,new):
    r0,l0,e0,g0,u0,c0=endpoint_geometry(model,old)
    r1,l1,e1,g1,u1,c1=endpoint_geometry(model,new)
    de=[b-a for a,b in zip(e0,e1)]
    gb=[(a+b)/2 for a,b in zip(g0,g1)]
    geometric=[]
    for a,b,l,k,delta in zip(r0,r1,l0,l1,de):
        assert l+k>0
        geometric.append(sum(((x+y)*(y-x)/(l+k) for x,y in zip(a,b)),Q())-delta)
    def quadratic(e):
        return sum((Q.from_float(model.h[i][j])*e[i]*e[j]
                    for i in range(len(e)) for j in range(len(e))),Q())/2
    work=sum((a*b for a,b in zip(gb,de)),Q())
    conjugate=quadratic(e1)-quadratic(e0)-work
    potential=u1-u0-work
    first=next((i for i,q in enumerate(geometric) if q),None)
    subcode='extension_chain' if first is not None else ('conjugate_chain' if conjugate else ('potential_observer_chain' if potential else None))
    return dict(status='candidate_c_incompatible_with_frozen_path_b' if subcode else 'compatible',
        subcode=subcode,first_relation=first,extension_residuals=list(map(str,geometric)),
        conjugate_residual=str(conjugate),potential_residual=str(potential),
        work=str(work),old_potential=str(u0),new_potential=str(u1),old_cells=c0,new_cells=c1)


def fixed_cell_root(model,wire,proposal_wire,audit):
    """Certifies T_exact, not the rounded iteration. Stops on first cell ambiguity."""
    ids,masses,_,old=decode_wire(wire)
    _,_,_,proposed=decode_wire(proposal_wire)
    center=list(map(Q,audit['iterations'][-1]['new']))
    radius=[Q(2)**-160/(f.LQ if i%6<3 else f.PQ) for i in range(len(old))]
    lookup={p:i for i,p in enumerate(ids)}
    force=audit['force']
    geometry=[]
    for a,rel in enumerate(model.relations):
        values=[struct.unpack('>d',bytes.fromhex(x))[0] for x in force['cells'][a]]
        ref=[float(q*f.LQ) for q in f.reference_offset(model,rel)]
        length,e=f.path_b_geometry(values,ref,rel.rest_length)
        assert struct.pack('>d',length).hex()==force['lengths'][a],'wrong frozen length scalar'
        geometry.append(e)
    for a,row in enumerate(model.h):
        total=0.0
        for h,e in zip(row,geometry):total+=h*e
        assert struct.pack('>d',total).hex()==force['conjugates'][a],'wrong frozen conjugate scalar'
    for a,rel in enumerate(model.relations):
        i,j=lookup[rel.first_id],lookup[rel.second_id]
        for axis in range(3):
            # Midpoint relative coordinate with exact old B96 input.
            c=(old[6*j+axis]+center[6*j+axis]-old[6*i+axis]-center[6*i+axis])/2*f.LQ
            rad=(radius[6*i+axis]+radius[6*j+axis])/2*f.LQ
            bits=int(force['cells'][a][axis],16)
            lo,hi=outward(c-rad,False),outward(c+rad,True)
            if not contains(lo,hi,bits):
                return dict(status='solver_certificate_inconclusive',reason='root_box_force_cell',
                    relation=a,axis=axis,lo=str(lo),hi=str(hi),bits=force['cells'][a][axis],
                    center=str(c),radius=str(rad),target_escape=False,budget_violation=False)
    # Exact affine coefficients, in raw coordinates, with all repeated terms collected.
    size=len(old); A=[[Q() for _ in old] for _ in old]; b=list(old)
    n=Q(audit['n'])
    for i,m in enumerate(masses):
        for axis in range(3):
            k=6*i+axis; A[k][k+3]=n/(2*m); b[k]+=n*old[k+3]/(2*m)
    for a,rel in enumerate(model.relations):
        i,j=lookup[rel.first_id],lookup[rel.second_id]
        alpha=n*f.TQ*f.LQ/f.PQ*decode(int(force['conjugates'][a],16))/decode(int(force['lengths'][a],16))/2
        for axis in range(3):
            u,v=6*i+axis,6*j+axis
            for row,sgn in ((u+3,1),(v+3,-1)):
                A[row][v]+=sgn*alpha;A[row][u]-=sgn*alpha
                b[row]+=sgn*alpha*(old[v]-old[u])
    scale=[f.LQ if i%6<3 else f.PQ for i in range(size)]
    contraction=max(sum((abs(A[i][j])*scale[i]/scale[j] for j in range(size)),Q()) for i in range(size))
    if contraction>Q(1,2):return dict(status='solver_certificate_inconclusive',reason='contraction',bound=str(contraction))
    for i in range(size):
        c=b[i]+sum((a*z for a,z in zip(A[i],center)),Q())
        rad=sum((abs(a)*r for a,r in zip(A[i],radius)),Q())
        if abs(c-center[i])+rad>radius[i]:return dict(status='solver_certificate_inconclusive',reason='not_self_mapping')
    mat=[[(Q(int(i==j))-A[i][j]) for j in range(size)]+[b[i]] for i in range(size)]
    for k in range(size):
        pivot=next((i for i in range(k,size) if mat[i][k]),None)
        if pivot is None:return dict(status='solver_certificate_inconclusive',reason='singular')
        mat[k],mat[pivot]=mat[pivot],mat[k]
        divisor=mat[k][k];mat[k]=[q/divisor for q in mat[k]]
        for i in range(size):
            if i!=k:
                coeff=mat[i][k];mat[i]=[q-coeff*r for q,r in zip(mat[i],mat[k])]
            for q in mat[i]:
                if max(abs(q.numerator).bit_length(),q.denominator.bit_length())>262144:
                    return dict(status='solver_certificate_inconclusive',reason='rational_resource')
    root=[row[-1] for row in mat]
    assert all(abs(z-c)<=r for z,c,r in zip(root,center,radius))
    assert all(root[i]==b[i]+sum((A[i][j]*root[j] for j in range(size)),Q()) for i in range(size))
    if any(rn(z,96)!=p for z,p in zip(root,proposed)):
        return dict(status='solver_certificate_inconclusive',reason='exact_root_output_mismatch')
    return dict(status='root_certified',contraction=str(contraction),root=list(map(str,root)))
