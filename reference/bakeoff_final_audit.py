"""Closed-inventory audit of the bakeoff, with explicit rejected candidates.

No B256 reference, trajectory substitution, ratio relaxation, or promotion.
The optional deep mode reconstructs all new short stages and implicit solver
graphs. The independent parent full-tail replay is a separate explicit mode.
"""
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import itertools
import bounded_integrator_bakeoff_check as c
import bakeoff_control_audit as controls
import bakeoff_evidence_audit as evidence
import bakeoff_short_analysis as analysis

f=c.f
PARENT='a5f83d13c276bd1f41f6121e4d3bc50dc7287983'
DECISION='retain_existing_b96_kdk_baseline_for_research'


def read(p):return json.loads(p.read_text())


def phase(wire):
    raw=bytes.fromhex(wire);ids,masses,t,v=c.decode_wire(raw)
    state=f.PhaseState(96,t,[f.PacketState(pid,m,v[6*i:6*i+3],v[6*i+3:6*i+6]) for i,(pid,m) in enumerate(zip(ids,masses))])
    assert f.encode_phase_state(state)==raw,'noncanonical checkpoint'
    return state


def difference(a,b,relative=None):
    aa,bb=phase(a),phase(b)
    assert [(p.identifier,p.mass_raw) for p in aa.packets]==[(p.identifier,p.mass_raw) for p in bb.packets]
    def values(state):
        if relative=='com':
            mass=sum(p.mass_raw for p in state.packets)
            x=[sum((p.mass_raw*p.x[k] for p in state.packets),Q())/mass for k in range(3)]
            velocity=[sum((p.p[k] for p in state.packets),Q())/mass for k in range(3)]
            return [([p.x[k]-x[k] for k in range(3)],[p.p[k]-p.mass_raw*velocity[k] for k in range(3)]) for p in state.packets]
        if relative=='first':
            first=state.packets[0]
            return [([p.x[k]-first.x[k] for k in range(3)],[p.p[k]-first.p[k] for k in range(3)]) for p in state.packets]
        return [(p.x,p.p) for p in state.packets]
    av,bv=values(aa),values(bb)
    return (max(abs(a[0][k]-b[0][k])*f.LQ for a,b in zip(av,bv) for k in range(3)),
            max(abs(a[1][k]-b[1][k])*f.PQ for a,b in zip(av,bv) for k in range(3)))


def require_budget(x,p):
    assert x<=f.POSITION_BUDGET and p<=f.MOMENTUM_BUDGET,'frame/recovery budget failure'


def audit_metamorphic(work):
    baseline=work/'short';other=work/'additional'
    base={(s,l):read(baseline/f'{s}-L{l}-{f.KDK}.json') for s in f.SCENARIOS for l in range(5)}
    rotations=read(baseline/'metamorphic-controls.json');assert len(rotations)==120
    seen=set()
    for row in rotations:
        perm=row['perm'];sign=row['sign'];level=row['level'];key=(level,tuple(perm),tuple(sign))
        assert key not in seen;seen.add(key)
        assert sorted(perm)==[0,1,2] and all(s in (-1,1) for s in sign)
        assert (-1)**sum(perm[i]>perm[j] for i in range(3) for j in range(i+1,3))*sign[0]*sign[1]*sign[2]==1
        original=base[('k4_internal',level)]['wires'];assert len(row['wires'])==len(original)
        ex=ep=Q();errors=[]
        for rotated,target in zip(row['wires'],original):
            state=phase(rotated)
            for packet in state.packets:
                for field in ('x','p'):
                    old=getattr(packet,field);new=list(old)
                    for axis in range(3):new[perm[axis]]=sign[axis]*old[axis]
                    setattr(packet,field,new)
            x,p=difference(f.encode_phase_state(state).hex(),target)
            ex=max(ex,x);ep=max(ep,p);errors.append([str(x),str(p)])
        assert row['errors']==errors and Q(row['position'])==ex and Q(row['momentum'])==ep
        require_budget(ex,ep);assert row['passed'] is True
    assert {k[0] for k in seen}==set(range(5))
    rows=read(other/'controls.json');assert len(rows)==70
    keys=set();exact_reverse=0
    for row in rows:
        kind=row['kind'];level=row['level'];scenario=row.get('scenario','k4_internal')
        key=(kind,scenario,level);assert key not in keys;keys.add(key)
        if kind=='reverse':
            target=base[(scenario,level)]['wires'][0]
            x,p=difference(row['recovered_wire'],target)
            exact_reverse+=row['recovered_wire']==target
            assert (x,p)==(Q(row['x']),Q(row['p']));require_budget(x,p)
        elif kind=='checkpoint':
            wires=base[(scenario,level)]['wires'];N=len(wires)-1
            assert row['state_suffix_sha256']==hashlib.sha256(b''.join(bytes.fromhex(w) for w in wires[N//2:])).hexdigest()
        elif kind=='domain_crossing':
            assert row['dt_raw']==1000000000 and row['status']!='accepted'
            assert row['prior_wire']==row['returned_wire']
        else:
            relative=None;name=kind
            if kind.endswith('-com'):relative='com';name=kind[:-4]
            elif kind.endswith('-first-packet'):relative='first';name=kind[:-13]
            wires=read(other/f'{name}-L{level}.json')['wires'];target=base[('k4_internal',level)]['wires']
            assert len(wires)==len(target)
            values=[difference(a,b,relative) for a,b in zip(wires,target)]
            x=max(v[0] for v in values);p=max(v[1] for v in values)
            assert (x,p)==(Q(row['x']),Q(row['p']));require_budget(x,p)
        assert row['passed'] is True
    expected={(kind,s,l) for kind in ('reverse','checkpoint') for s in f.SCENARIOS for l in range(5)}
    expected|={(kind,'k4_internal',l) for kind in ('domain_crossing','packet_permutation','relation_permutation','endpoint_reversal',
        'k4_translated-com','k4_translated-first-packet','k4_boosted-com','k4_boosted-first-packet') for l in range(5)}
    assert keys==expected,'incomplete metamorphic inventory'
    return dict(rotations=120,additional=70,bit_exact_reverse_cases=exact_reverse,reversal_cases=15)


def check_result(result):
    assert result['decision']==DECISION and result['promotion']=='NO_PROMOTION','disposition/promotion changed'
    assert result['selected_precision']==96 and result['pareto_set']==['A']
    assert result['B']['eligible'] is False and result['C']['eligible'] is False
    assert result['B']['tails_run']==result['C']['tails_run']==0
    assert result['B']['disposition']=='reject_integrator_solver'
    assert result['B']['root_certified_controls']==5 and result['B']['output_mismatches']==5 and result['B']['cell_inconclusive']==5
    assert result['C']['disposition']=='candidate_c_incompatible_with_frozen_path_b'
    assert result['C']['solver_implemented'] is False and result['C']['tested_endpoint_pairs']==1
    assert result['A']['tails']==10 and result['A']['short_KDK']==15 and result['A']['first_order_controls']==15
    assert result['A']['steps']==15872 and result['A']['stages']==47616
    assert result['exact_conservation_claimed'] is False and result['production_integrator_selected'] is False
    return True


def audit(work,parent,deep=False):
    assert read(parent/'manifest.json')['source_sha']==PARENT
    summary=read(work/'controls-a/control-summary.json')
    assert summary['promotion']=='NO_PROMOTION' and summary['A_controls']==15 and summary['B_controls']==15
    assert summary['B_full_tails_run']==0 and summary['C_attempted']==1
    if deep:
        independent=controls.audit(parent,work/'controls-a',work/'controls-b')
        assert independent==read(work/'midpoint-independent.json')
        assert evidence.short(parent,work/'short')==read(work/'short-audit.json')
    else:
        independent=read(work/'midpoint-independent.json')
        assert independent['passed'] and independent['scientific_twin_identical']
    # Twins are compared in either mode, not merely trusted from a Boolean.
    names={p.name for p in (work/'controls-a').iterdir() if p.name!='external-resources.json'}
    assert names=={p.name for p in (work/'controls-b').iterdir() if p.name!='external-resources.json'}
    for name in names:assert (work/'controls-a'/name).read_bytes()==(work/'controls-b'/name).read_bytes()
    order=analysis.analyse(work/'short',work/'exact',work/'smooth.json')
    assert order==read(work/'short-analysis.json') and order['passed'],'false order/energy gate'
    exact=read(work/'exact-independent.json')
    assert exact['passed'] and exact['backend']=='Python integer Fraction; independent reference KDK'
    assert len(exact['rows'])==15
    for row in exact['rows']:
        assert row==read(work/f"exact/{row['scenario']}-L{row['level']}.json")
    assert {(r['scenario'],r['level']) for r in exact['rows']}=={(s,l) for s in f.SCENARIOS for l in range(5)}
    long=evidence.long(parent,work/'tails')
    assert long==read(work/'long-audit.json') and long['passed'],'false long energy gate'
    metamorphic=audit_metamorphic(work)
    for file,scenarios in (('external-short-timing.json',f.SCENARIOS),('tails/external-timing.json',('k4_internal','k4_boosted'))):
        timings=read(work/file)
        assert {(r['scenario'],r['level']) for r in timings}=={(s,l) for s in scenarios for l in range(5)}
        assert len(timings)==5*len(scenarios)
        for r in timings:
            values=r['seconds'];assert len(values)==5 and r['warmups']==1 and all(v>0 for v in values)
            assert r['median']==sorted(values)[2] and r['range']==[min(values),max(values)]
    # Literal canonical candidate wires are bound to the parent at every sample.
    inputs=parent/'parent/parent/parent/inputs'
    expected={(r['scenario_id'],r['path'],int(r['level']),int(r['sample'])):r['candidate_state_hash']
        for r in f.rows(inputs/'raw-a/representation_error.csv') if r['scope']=='short' and int(r['precision'])==96}
    for s in f.SCENARIOS:
        for level in range(5):
            for path in (f.KDK,f.CONTROL):
                row=read(work/f'short/{s}-L{level}-{path}.json');assert len(row['wires'])==f.STEP_COUNTS[level]+1
                for k,w in enumerate(row['wires']):assert hashlib.sha256(bytes.fromhex(w)).hexdigest()==expected[(s,path,level,k)]
    auth={}
    for r in f.rows(parent/'parent/evidence/candidate-auth/invariants.csv'):
        if r['stage'] in ('initial','committed'):auth[(r['trajectory_id'],int(r['step']))]=r['state_hash']
    models=f.load_models(inputs/'raw-a')
    for s in ('k4_internal','k4_boosted'):
        for level in range(5):
            row=read(work/f'tails/{s}-L{level}.json');assert row['checkpoint_suffix'] is True
            for k,(wire,energy) in enumerate(zip(row['wires'],row['energy'])):
                assert hashlib.sha256(bytes.fromhex(wire)).hexdigest()==auth[(f'long:{s}:B96:L{level}',k)]
                state=phase(wire);assert state.time_raw==k*f.TIMESTEPS_RAW[level]
                if deep:assert f.mechanical_energy(models['k4'],state)[2]==Q(energy),'changed energy semantics'
    replay=json.loads((work/'parent-full-replay.log').read_text().splitlines()[-1])
    assert replay['new_short_blocks_replayed']==90 and replay['new_full_tails_replayed']==10 and replay['records_only'] is False
    rows=independent['rows'];assert len(rows)==15
    B=dict(disposition='reject_integrator_solver',eligible=False,tails_run=0,
        output_mismatches=sum(r['status']=='reject_integrator_solver' for r in rows),
        cell_inconclusive=sum(r['status']=='solver_certificate_inconclusive' for r in rows),
        root_certified_controls=sum(r['status']=='root_certified' for r in rows),
        secondary_disposition='stop_integrator_certification_inconclusive',physical_budget_violation_proved=False)
    result=dict(schema='mls.bounded-integrator-bakeoff.result.v1',parent_sha=PARENT,decision=DECISION,
        selected_precision=96,promotion='NO_PROMOTION',pareto_set=['A'],
        A=dict(disposition='retain_existing_b96_kdk_baseline_for_research',short_KDK=15,first_order_controls=15,
            tails=10,steps=15872,stages=47616,parent_short_blocks=90,metamorphic=metamorphic),B=B,
        C=dict(disposition=independent['C']['status'],eligible=False,tested_endpoint_pairs=1,
            tails_run=0,solver_implemented=False,subcode=independent['C']['subcode']),
        exact_conservation_claimed=False,production_integrator_selected=False,
        scope='registered small systems and finite one/16-second horizons only')
    check_result(result)
    return result
