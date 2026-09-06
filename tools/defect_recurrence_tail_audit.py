"""Closed negative-control audit; never certifies uncomputed physical tails."""
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
from defect_recurrence_tail_check import full_tail_eligible
from correlation_aware_tail_gate import check as parent_gate
import correlation_aware_binary64_cells as cells

PARENT='171066fc15d6096739c7aeb2e99da7313f447d3f'
DECISION='stop_inconclusive_or_wrong_parent'


def load(directory):
    cases=json.loads((directory/'inventory.json').read_text())
    reports=[]
    for s,l,t,n in cases:
        name=f'{s}-L{l}-start{t}-steps{n}'
        raw=(directory/(name+'.json')).read_bytes()
        receipt=json.loads((directory/(name+'.receipt.json')).read_text())
        assert receipt['exit_code']==0 and receipt['case']==[s,l,t,n]
        assert receipt['output_sha256']==hashlib.sha256(raw).hexdigest()
        reports.append(json.loads(raw))
    assert full_tail_eligible(reports)==json.loads((directory/'gate.json').read_text())
    return reports


def audit(work,parent):
    config=json.loads((work/'toolchain.json').read_text())
    for key,value in dict(verifier_significand_bits=512,verifier_exponent_min=-16384,
                          verifier_exponent_max=16384,candidate_precision=96,
                          address_space_limit_bytes=2147483648,wall_seconds_per_case=900,
                          max_case_subprocesses=4,full_tails_launched=0,historical_noise_symbols=0).items():
        assert config[key]==value
    parent_boxes=json.loads((work/'parent-box-replay.json').read_text())
    assert parent_boxes['withheld_stage_checks']==1320 and parent_boxes['record_samples_checked']==4018
    accepted=json.loads((work/'accepted-parent-fresh-verification.json').read_text())
    assert accepted['identity']['source_sha']==PARENT and accepted['identity']['status']=='PASS'
    assert accepted['new_withheld_stage_checks_replayed']==1890 and accepted['records_only'] is False
    inherited=parent_gate(parent/'evidence/withheld')
    assert inherited['joint_stage_checks']==1890
    reports=load(work/'withheld');repeat=load(work/'repeat')
    assert reports==repeat, 'scientific repeat differs'
    assert sorted(p.name for p in (work/'withheld').glob('*.json'))==sorted(p.name for p in (work/'repeat').glob('*.json'))
    for p in (work/'withheld').glob('*.json'):
        assert p.read_bytes()==(work/'repeat'/p.name).read_bytes()
    gate=full_tail_eligible(reports)
    assert not gate['eligible'] and gate['blocks_passed']==60 and gate['stage_checks']==1320
    diagnostics=[]
    for r in reports:
        if r['start_step']:
            assert r['status']=='withheld_block_contained'
            continue
        assert r['status']=='certificate_inconclusive' and r['reason']=='force_cell'
        assert (r['step'],r['stage'],r['withheld_checks'])==(1,'second_kick',2)
        v=r['details'];lo,hi=Q(v['lo_si']),Q(v['hi_si'])
        assert v['relation']==5 and v['axis']==0
        assert v['current_target_contained'] and Q(v['withheld_exact_relative_si'])==0
        assert lo<0<hi and not cells.contains(lo,hi,0)
        if r['block_steps']==1:
            diagnostics.append(dict(scenario=r['scenario'],level=r['level'],
                                    relative_si_interval=[str(lo),str(hi)],exact_relative_si='0'))
    assert len(diagnostics)==10
    stage_auth=json.loads((work/'stage-auth.json').read_text())
    assert stage_auth['authenticated_stage_wires']==1930
    probes=json.loads((work/'dependency-probe.json').read_text())
    assert len(probes)==10
    for p,v in zip(probes,diagnostics):
        assert (p['scenario'],p['level'])==(v['scenario'],v['level'])
        assert p['exact_endpoint_errors'][0]==p['exact_endpoint_errors'][1]
        assert Q(p['endpoint_error_interval'][0])<Q(p['endpoint_error_interval'][1])
        assert Q(p['endpoint_error_interval'][0]) <= Q(p['exact_endpoint_errors'][0]) <= Q(p['endpoint_error_interval'][1])
        assert p['candidate_relative_raw']==p['exact_relative_raw']=='0'
        assert p['independent_relative_interval_si']==v['relative_si_interval']
        assert p['exact_error_equality_is_not_used_by_generator'] is True
    return dict(schema='mls.defect-tail.result.v1',parent_source=PARENT,
        decision=DECISION,subclass='VERIFIED_PARENT_SHORT_CONTROL_FORCE_CELL_INCONCLUSIVE',
        parent_identity_verified=True,parent_affine_blocks=90,parent_affine_checks=1890,
        new_blocks_passed=60,new_blocks_total=90,new_withheld_stage_checks=1320,
        exact_target_escape_events=0,failed_time_zero_blocks=30,
        full_tails_launched=0,resource_exhaustion_events=0,historical_noise_symbols=0,
        active_error_intervals=24,active_error_endpoints=48,matrix_slots=576,
        raw_scientific_twins_byte_identical=True,authenticated_candidate_stage_wires=1930,
        force_cell_diagnostics=diagnostics,full_tail_budgets_certified=False,
        selected_precision=None,promotion='NO_PROMOTION',
        interpretation='Component error intervals lose cross-coordinate cancellation; no B96 defect or budget violation established.')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('work',type=Path);p.add_argument('parent',type=Path)
    a=p.parse_args();print(json.dumps(audit(a.work,a.parent),sort_keys=True,indent=2))
