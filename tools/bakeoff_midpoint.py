"""Preregistered Picard midpoint. Scratch is discarded at every step.

This module is causal proposal generation only. Exact root/cell verification
is in reference/bounded_integrator_bakeoff_check.py and can only veto.
"""
import hashlib
import struct
import gmpy2 as g
import run_bounded_fractional_phase_state_lab as frozen


class Rejected(Exception):
    pass


def textq(value):
    return str(g.mpq(value))


class Scratch:
    def __init__(self, bits):
        assert bits in (256, 384)
        self.bits = bits
        self.context = g.context(precision=bits, round=g.RoundToNearest,
            emin=-16381, emax=16384, subnormalize=False,
            trap_underflow=True, trap_overflow=True, trap_invalid=True,
            trap_erange=True, trap_divzero=True)
        self.records = []
        self.force_calls = 0

    def op(self, kind, *args):
        ctx = g.get_context()
        assert ctx.precision == self.bits and ctx.round == g.RoundToNearest
        ctx.clear_flags()
        try:
            if kind == 'convert': out = g.mpfr(args[0])
            elif kind == 'add': out = args[0]+args[1]
            elif kind == 'sub': out = args[0]-args[1]
            elif kind == 'mul': out = args[0]*args[1]
            elif kind == 'div': out = args[0]/args[1]
            else: raise ValueError(kind)
        except ArithmeticError as exc:
            raise Rejected('arithmetic:'+kind) from exc
        inexact = bool(ctx.inexact)
        if not g.is_finite(out) or any((ctx.underflow,ctx.overflow,ctx.invalid,ctx.erange,ctx.divzero)):
            raise Rejected('arithmetic_flags:'+kind)
        if out and not -16382 <= g.get_exp(out)-1 <= 16383:
            raise Rejected('exponent_range')
        if not out: out = g.mpfr(0)
        # Noncausal exact wire audit, never read by subsequent operations.
        self.records.append([kind, [textq(a) for a in args], textq(out), inexact])
        return out


def packet_values(state):
    return [v for p in frozen.canonical_packets(state) for v in p.x+p.p]


def check_chord(model, state, values, bits):
    lookup = {p.identifier:i for i,p in enumerate(frozen.canonical_packets(state))}
    for rel in model.relations:
        i,j=lookup[rel.first_id],lookup[rel.second_id]
        initial=frozen.exact_stored_relation_offset(state,rel)
        final=[g.mpq(values[6*j+a])-g.mpq(values[6*i+a]) for a in range(3)]
        reference=frozen.exact_reference_offset(model,rel)
        # Same exact chord predicate; explicit extension of its scratch bound
        # to verifier S=384, without modifying the frozen B96 implementation.
        limit=4*(bits+16383+16382)+64
        d=[y-x for x,y in zip(initial,final)]
        aa=sum((x*x for x in initial),g.mpq(0))
        ad=sum((x*y for x,y in zip(initial,d)),g.mpq(0))
        dd=sum((x*x for x in d),g.mpq(0))
        ref=sum((x*x for x in reference),g.mpq(0))/2**48
        if dd==0 or ad>=0:lhs,rhs=aa,ref
        elif ad<=-dd:lhs,rhs=sum((x*x for x in final),g.mpq(0)),ref
        else:lhs,rhs=aa*dd-ad*ad,ref*dd
        for q in (*initial,*final,*d,aa,ad,dd,ref,lhs,rhs):
            if max(abs(int(q.numerator)).bit_length(),int(q.denominator).bit_length())>limit:
                raise Rejected('domain_scratch_bound')
        if lhs<rhs: raise Rejected('unsafe_trial_chord:'+str(rel.index))


def solve(model, state, n, bits):
    """Returns a scratch proposal and audit; never mutates the input state."""
    s=Scratch(bits)
    packets=frozen.canonical_packets(state)
    ids={p.identifier:i for i,p in enumerate(packets)}
    with g.context(s.context):
        op=s.op
        old=[op('convert',v) for v in packet_values(state)]
        lq=op('convert',frozen.LQ); pq=op('convert',frozen.PQ)
        one=op('convert',1); two=op('convert',2)
        kick=op('convert',g.mpq(n)*frozen.TQ*frozen.LQ/frozen.PQ)
        drift=[op('convert',g.mpq(n,2*p.mass_raw)) for p in packets]
        ballistic=[op('convert',g.mpq(n,p.mass_raw)) for p in packets]
        guess=list(old)
        for i in range(len(packets)):
            for a in range(3): guess[6*i+a]=op('add',old[6*i+a],op('mul',ballistic[i],old[6*i+a+3]))
        tau=op('convert',g.mpq(1,2**(180 if bits==256 else 300)))
        units=[lq if a<3 else pq for _ in packets for a in range(6)]
        def norm(v):
            return max(abs(op('mul',u,x)) for u,x in zip(units,v))
        norm_old=norm(old)

        def sweep(guess):
            check_chord(model,state,guess,bits)
            out=list(old)
            midpoint=list(old)
            for i in range(len(packets)):
                for a in range(3):
                    k=6*i+a
                    out[k]=op('add',old[k],op('mul',drift[i],op('add',old[k+3],guess[k+3])))
                    midpoint[k]=op('div',op('add',old[k],guess[k]),two)
            geometry=[]; cells=[]
            for rel in model.relations:
                i,j=ids[rel.first_id],ids[rel.second_id]
                raw=[op('sub',midpoint[6*j+a],midpoint[6*i+a]) for a in range(3)]
                if max(abs(x) for x in raw)>=2**49: raise Rejected('relation_range')
                si=[float(op('mul',v,lq)) for v in raw]
                ref=[float(v*frozen.LQ) for v in frozen.exact_reference_offset(model,rel)]
                length,e=frozen._path_b_from_si(si,ref,rel.rest_length)
                geometry.append((raw,length,e))
                cells.append([struct.pack('>d',v).hex() for v in si])
            gs=[]
            for row in model.h:
                val=0.0
                for h,(_,_,e) in zip(row,geometry): val+=h*e
                gs.append(val)
            s.force_calls+=1
            impulses=[]
            for rel,(raw,length,_),gv in zip(model.relations,geometry,gs):
                alpha=op('div',op('mul',kick,op('convert',gv)),op('convert',length))
                i,j=ids[rel.first_id],ids[rel.second_id]
                impulse=[]
                for a in range(3):
                    impulse.append(op('mul',alpha,raw[a]))
                    if abs(impulse[-1])>=2**40: raise Rejected('impulse_range')
                    out[6*i+a+3]=op('add',out[6*i+a+3],impulse[-1])
                    out[6*j+a+3]=op('sub',out[6*j+a+3],impulse[-1])
                impulses.append([textq(q) for q in impulse])
            return out,dict(cells=cells,lengths=[struct.pack('>d',v[1]).hex() for v in geometry],
                conjugates=[struct.pack('>d',v).hex() for v in gs],impulses=impulses)

        sweeps=0; iterations=[]
        while sweeps+2<=128:
            new,_=sweep(guess); sweeps+=1
            residual_next,force=sweep(new); sweeps+=1
            delta=[op('sub',a,b) for a,b in zip(new,guess)]
            residual=[op('sub',a,b) for a,b in zip(residual_next,new)]
            d=norm(delta); r=norm(residual)
            z=max(one,norm_old,norm(new)); tolerance=op('add',tau,op('mul',tau,z))
            iterations.append(dict(sweeps=sweeps,D=textq(d),R=textq(r),Z=textq(z),
                tolerance=textq(tolerance),guess=[textq(v) for v in guess],
                new=[textq(v) for v in new],residual_next=[textq(v) for v in residual_next]))
            if d<=tolerance and r<=tolerance:
                check_chord(model,state,new,bits)
                return new,dict(bits=bits,status='converged',sweeps=sweeps,
                    force_calls=s.force_calls,operations=s.records,iterations=iterations,force=force)
            guess=new
        raise Rejected('iteration_ceiling')


def proposal96(state, values, n):
    out=state.clone()
    out.packets=frozen.canonical_packets(out)
    with frozen.profile_for(96).activate() as ctx:
        for i,p in enumerate(out.packets):
            for a in range(3):
                p.x[a]=frozen.rounded_fraction(ctx,96,g.mpq(values[6*i+a]),'midpoint_output')
                p.p[a]=frozen.rounded_fraction(ctx,96,g.mpq(values[6*i+a+3]),'midpoint_output')
    out.time_raw+=n
    frozen.validate_state(out)
    return out
