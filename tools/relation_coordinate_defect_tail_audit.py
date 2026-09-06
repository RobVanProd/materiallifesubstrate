"""Independent exact budget classification; no precision ratios or B256 truth."""
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import bounded_fractional_phase_state_oracle as f
from relation_coordinate_defect_tail_suite import gate

PARENT='99d979334f0b931401d451beba70029d6bca52d7'
DECISION='retain_b96_bounded_phase_state_for_research'


def load(directory):
    return [json.loads(p.read_text()) for p in sorted(directory.glob('k4*.json'))
            if not p.name.endswith('.receipt.json')]


def identical(a,b):
    files=[p for p in a.iterdir() if p.is_file()]
    assert {p.name for p in files}=={p.name for p in b.iterdir() if p.is_file()}
    for p in files:
        with p.open('rb') as x,(b/p.name).open('rb') as y:
            assert hashlib.file_digest(x,'sha256').digest()==hashlib.file_digest(y,'sha256').digest(),p.name


def check_receipts(directory):
    for p in directory.glob('*.receipt.json'):
        r=json.loads(p.read_text());out=directory/p.name.replace('.receipt.json','.json')
        assert r['exit_code']==0 and hashlib.sha256(out.read_bytes()).hexdigest()==r['output_sha256']
    assert all(not p.read_bytes() for p in directory.glob('*.stderr'))


def frames(directory,level,internal,boosted):
    maxima=dict(candidate_position=Q(),candidate_momentum=Q(),
                target_position_upper=Q(),target_momentum_upper=Q())
    count=0;hashes=[hashlib.sha256(),hashlib.sha256()]
    with (directory/f'k4_internal-L{level}.frames.jsonl').open('rb') as aa,\
         (directory/f'k4_boosted-L{level}.frames.jsonl').open('rb') as bb:
        import itertools
        for a,b in itertools.zip_longest(aa,bb):
            assert a is not None and b is not None
            hashes[0].update(a);hashes[1].update(b)
            ra,rb=json.loads(a),json.loads(b)
            assert ra['sample']==rb['sample']==count
            assert len(ra['frame'])==len(rb['frame'])==24
            for k,(x,y) in enumerate(zip(ra['frame'],rb['frame'])):
                delta=Q(y['candidate'])-Q(x['candidate'])
                xl,xh=map(Q,x['error']);yl,yh=map(Q,y['error'])
                assert xl<=xh and yl<=yh
                lo,hi=delta+yl-xh,delta+yh-xl
                kind='position' if k%6<3 else 'momentum'
                maxima['candidate_'+kind]=max(maxima['candidate_'+kind],abs(delta))
                maxima['target_'+kind+'_upper']=max(maxima['target_'+kind+'_upper'],abs(lo),abs(hi))
            count+=1
    assert count==16*f.STEP_COUNTS[level]+1
    assert [h.hexdigest() for h in hashes]==[internal['frame_stream_sha256'],boosted['frame_stream_sha256']]
    for key,value in maxima.items():
        budget=f.POSITION_BUDGET if 'position' in key else f.MOMENTUM_BUDGET
        assert value<=budget, 'frame budget not certified; not automatically a physical violation'
    return dict(samples=count,**{k:str(v) for k,v in maxima.items()})


def final_fields(r):
    assert len(r['packet_error'])==24 and len(r['relation_error'])==36
    pe=[tuple(map(Q,e)) for e in r['packet_error']]
    assert all(lo<=hi for lo,hi in pe)
    for kind,indices,unit in [('position',[k for k in range(24) if k%6<3],f.LQ),
                              ('momentum',[k for k in range(24) if k%6>=3],f.PQ)]:
        value=max(max(abs(pe[k][0]),abs(pe[k][1]))*unit for k in indices)
        final_key='final_position_upper_m' if kind=='position' else 'final_momentum_upper_SI'
        max_key='partial_position_upper_m' if kind=='position' else 'partial_momentum_upper_SI'
        assert Q(r[final_key])==value and value<=Q(r[max_key])
    lo,hi=map(Q,r['final_energy_error']);assert lo<=hi
    assert max(abs(lo),abs(hi))<=Q(r['partial_energy_upper_J'])


def audit(work,parent):
    identity=json.loads((parent/'manifest.json').read_text())
    assert identity['source_sha']==PARENT
    inherited=json.loads((parent/'evidence/result.json').read_text())
    assert inherited['new_blocks_passed']==60 and inherited['new_withheld_stage_checks']==1320
    assert inherited['failed_time_zero_blocks']==30 and inherited['exact_target_escape_events']==0
    assert inherited['parent_affine_blocks']==90 and inherited['parent_affine_checks']==1890
    assert inherited['selected_precision'] is None and inherited['promotion']=='NO_PROMOTION'
    authentication=json.loads((work/'parent-authentication.json').read_text())
    assert authentication['identity']['source_sha']==PARENT and authentication['identity']['status']=='PASS'
    assert authentication['candidate_stage_wires_authenticated']==1930
    short=load(work/'withheld');short_gate=gate(short)
    assert short_gate==dict(eligible=True,blocks_passed=90,blocks_total=90,stage_checks=1890,promotion='NO_PROMOTION')
    identical(work/'withheld',work/'repeat')
    identical(work/'full',work/'full-repeat')
    for name in ('withheld','repeat','full','full-repeat'):check_receipts(work/name)
    full=load(work/'full');assert len(full)==10
    cases={(r['scenario'],r['level']):r for r in full}
    assert set(cases)=={(s,l) for s in ('k4_internal','k4_boosted') for l in range(5)}
    budgets=dict(partial_position_upper_m=f.POSITION_BUDGET,partial_momentum_upper_SI=f.MOMENTUM_BUDGET,
        partial_energy_upper_J=f.ENERGY_BUDGET,candidate_momentum_residual_max=f.MOMENTUM_BUDGET,
        candidate_angular_residual_max=f.ANGULAR_BUDGET,candidate_centrality_residual_max=f.ANGULAR_BUDGET)
    maximum={k:Q() for k in budgets};maximum_slope=Q()
    for r in full:
        final_fields(r)
        n=16*f.STEP_COUNTS[r['level']]
        assert r['status']=='state_horizon_enclosed_observers_pending' and r['reason'] is None
        assert r['horizon_seconds']==16 and r['complete_steps']==r['requested_steps']==n
        assert r['certified_stages']==3*n and r['authenticated_candidate_wires']==4*n+1
        assert (r['precision'],r['verifier_bits'],r['packet_intervals'],r['relation_intervals'],r['matrix_slots'])==(96,512,24,36,1872)
        assert r['historical_noise_symbols']==0 and r['promotion']=='NO_PROMOTION'
        for key,budget in budgets.items():
            value=Q(r[key]);assert 0<=value<=budget, f'{key} inclusion unresolved, not proved exceedance'
            maximum[key]=max(maximum[key],value)
        lo,hi=map(Q,r['partial_signed_slope']);assert lo<=hi
        value=max(abs(lo),abs(hi));assert value<=f.ENERGY_SLOPE_BUDGET
        maximum_slope=max(maximum_slope,value)
    frame=[frames(work/'full',l,cases[('k4_internal',l)],cases[('k4_boosted',l)]) for l in range(5)]
    return dict(schema='mls.relation-coordinate-defect.result.v1',parent_sha=PARENT,
        decision=DECISION,selected_precision=96,promotion='NO_PROMOTION',
        short_gate=short_gate,full_tails_certified=10,full_steps=sum(r['complete_steps'] for r in full),
        full_stages=sum(r['certified_stages'] for r in full),
        candidate_wires_authenticated=sum(r['authenticated_candidate_wires'] for r in full),
        maximum_certified_errors={k:str(v) for k,v in maximum.items()},
        maximum_signed_energy_slope_upper=str(maximum_slope),
        frozen_budgets={k:str(v) for k,v in budgets.items()},
        frozen_slope_budget=str(f.ENERGY_SLOPE_BUDGET),frame_certificates=frame,
        independent_repeat_byte_identical=True,bit_exact_reversal_claimed=False,
        exact_bounded_invariants_claimed=False,unbounded_horizon_claimed=False)
