"""Authenticate all B96 stage wires used by short controls against sealed hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import bounded_fractional_phase_state_oracle as f
import defect_recurrence_tail as d
import seal_bounded_fractional_phase_state_evidence as old_seal

SOURCE='17532284c2f0878e908f6a613f4c2e3baa47cbcd'
PREHASH='cf18f208f5f25e0f6783a57fbf7c724b0c807eeb02ec9c4d11bf43ff3bcb8dff'
INVARIANT_HASH='0e0df2142b5abdaa8e90c642a5269599b666afcfd2792a98c23e5a88c30222b7'


def authenticate(inputs,invariants,seal_path):
    raw=seal_path.read_bytes();seal=json.loads(raw)
    assert raw==old_seal.canonical(seal)
    assert seal['source_sha']==SOURCE
    assert seal['outer_pre_hash']==old_seal.pre_hash(seal)==PREHASH
    payload=next(p for p in seal['payload'] if p['path']=='raw-a/invariants.csv')
    with invariants.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    assert digest==payload['sha256']==INVARIANT_HASH
    assert invariants.stat().st_size==payload['bytes']
    expected={}
    for row in f.iter_rows(invariants):
        if row['trajectory_id'].startswith('long:') and int(row['precision'])==96 and int(row['step'])<=48:
            key=(row['trajectory_id'],int(row['step']),row['stage'])
            assert key not in expected
            expected[key]=row['state_hash']
    model=f.load_models(inputs/'raw-a')['k4']
    initial=f.rows(inputs/'raw-a/initial_states.csv')
    checked=0;stream=hashlib.sha256()
    for scenario in ('k4_internal','k4_boosted'):
        for level in range(5):
            state=f.phase_from_rows([r for r in initial if r['scenario_id']==scenario and int(r['precision'])==96])
            tid=f'long:{scenario}:B96:L{level}'
            def audit(step,stage,state):
                nonlocal checked
                wire=f.encode_phase_state(state)
                assert d.decode_wire(wire)[3]==d.flat(state)
                digest=hashlib.sha256(wire).hexdigest()
                assert digest==expected[(tid,step,stage)], 'candidate stage differs from immutable corpus'
                stream.update(f'{tid}:{step}:{stage}:{digest}\n'.encode())
                checked+=1
            audit(0,'initial',state)
            for step in range(1,49):
                status,state,_,stages,_=f.one_step(model,state,f.TIMESTEPS_RAW[level],f.KDK)
                assert status=='accepted'
                for stage,snapshot,*_ in stages:
                    audit(step,stage,snapshot)
    assert checked==len(expected)==1930
    return dict(source_sha=SOURCE,invariants_sha256=INVARIANT_HASH,
                candidate_precision=96,steps_per_case=48,cases=10,
                authenticated_stage_wires=checked,stage_stream_sha256=stream.hexdigest(),
                used_by_certificate_to_choose_force_cells=False,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path)
    p.add_argument('invariants',type=Path);p.add_argument('seal',type=Path)
    a=p.parse_args();print(json.dumps(authenticate(a.inputs,a.invariants,a.seal),sort_keys=True,indent=2))
