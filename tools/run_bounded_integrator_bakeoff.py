"""Closed-inventory bakeoff controls; preserves every stopping witness."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import run_bounded_fractional_phase_state_lab as f
import bakeoff_midpoint as midpoint
import bounded_integrator_bakeoff_check as check

PARENT='a5f83d13c276bd1f41f6121e4d3bc50dc7287983'
MANIFEST='6f33d5586dc75250ca4356aedb6cc58da62f8b153e62bf6b4d55e620ea12e818'
BASELINE='c4ac14cdcd46f948c1640535164c5bee400b4811868a572fe3873646cbed06de'


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,value):
    with path.open('x') as stream:json.dump(value,stream,sort_keys=True,separators=(',',':'));stream.write('\n')


def authenticate(parent):
    assert digest(parent/'manifest.json')==MANIFEST
    manifest=json.loads((parent/'manifest.json').read_text())
    assert manifest['source_sha']==PARENT and manifest['selected_precision']==96
    assert manifest['promotion']=='NO_PROMOTION'
    for name,entry in manifest['files'].items():
        p=parent/name
        assert p.stat().st_size==entry['size'] and digest(p)==entry['sha256'],name
    assert digest(Path(f.__file__))==BASELINE,'frozen A implementation altered'
    return dict(parent=PARENT,manifest_sha256=MANIFEST,payload_files=len(manifest['files']),status='PASS')


def inputs(parent):return parent/'parent/parent/parent/inputs'


def initial_models(parent):
    inp=inputs(parent)
    models=f.exact_lab.load_models(inp/'raw-a')
    model_ids,states=f.load_exact_states(inp/'parent-explicit-fractional/raw-a')
    return models,model_ids,{s:f.bounded_state(v,f.profile_for(96)) for s,v in states.items()}


def expected_states(parent):
    result={}
    for row in f.read_rows(inputs(parent)/'raw-a/representation_error.csv'):
        if row['scope']=='short' and int(row['precision'])==96:
            result[(row['scenario_id'],row['path'],int(row['level']),int(row['sample']))]=row['candidate_state_hash']
    return result


def control_run(parent,out):
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic()
    auth=authenticate(parent);save(out/'parent-authentication.json',auth)
    models,model_ids,states=initial_models(parent)
    oracle_models=check.f.load_models(inputs(parent)/'raw-a')
    expected=expected_states(parent)
    a_controls=[];first_pairs={}
    for scenario in f.SCENARIOS:
        for level,n in enumerate(f.TIMESTEPS_RAW):
            old=states[scenario]
            assert f.state_hash(old)==expected[(scenario,f.KDK,level,0)]
            status,new=f.one_step(models[model_ids[scenario]],old,n,f.KDK,f.profile_for(96))
            assert status=='accepted' and f.state_hash(new)==expected[(scenario,f.KDK,level,1)]
            # Independent integer-rounder KDK reconstruction of this same step.
            wire=f.encode_state(old)
            oracle=check.f.phase_from_rows([r for r in check.f.rows(inputs(parent)/'raw-a/initial_states.csv')
                if r['scenario_id']==scenario and int(r['precision'])==96])
            os,on,*_=check.f.one_step(oracle_models[model_ids[scenario]],oracle,n,check.f.KDK)
            assert os=='accepted' and check.f.encode_phase_state(on)==f.encode_state(new)
            a_controls.append(dict(scenario=scenario,level=level,status='PASS',old_wire=wire.hex(),new_wire=f.encode_state(new).hex()))
            first_pairs[(scenario,level)]=(wire,f.encode_state(new))
    save(out/'a-parent-first-step-controls.json',a_controls)

    c=[]
    for scenario in f.SCENARIOS:
        for level in range(5):
            old,new=first_pairs[(scenario,level)]
            model=oracle_models[model_ids[scenario]]
            same=check.compatibility(model,old,old)
            assert same['status']=='compatible'
            row=check.compatibility(model,old,new)
            row.update(scenario=scenario,level=level,old_wire=old.hex(),new_wire=new.hex(),identical_endpoint=same)
            c.append(row)
            if row['status']!='compatible':break
        if c[-1]['status']!='compatible':break
    save(out/'c-compatibility.json',c)
    print(json.dumps(dict(candidate='C',status=c[-1]['status'],scenario=c[-1]['scenario'],level=c[-1]['level']),sort_keys=True),flush=True)

    b=[]
    for scenario in f.SCENARIOS:
        for level,n in enumerate(f.TIMESTEPS_RAW):
            label=scenario+'-L'+str(level);old=states[scenario];wire=f.encode_state(old)
            row=dict(scenario=scenario,level=level,prior_wire=wire.hex(),completed_steps=0)
            try:
                values,causal=midpoint.solve(models[model_ids[scenario]],old,n,256)
                values384,verifier=midpoint.solve(models[model_ids[scenario]],old,n,384)
                causal['n']=n;verifier['n']=n
                save(out/(label+'-solver256.json'),causal)
                save(out/(label+'-verifier384.json'),verifier)
                counts=[check.audit_operations(v) for v in (causal,verifier)]
                for v in (causal,verifier):check.audit_counts(v,len(old.packets),len(models[model_ids[scenario]].relations))
                _,_,_,exact_old=check.decode_wire(wire)
                norms=[check.audit_norms(v,exact_old) for v in (causal,verifier)]
                proposed=midpoint.proposal96(old,values,n)
                checked=midpoint.proposal96(old,values384,n)
                row.update(operations=counts,norms=norms,
                    sweeps=[causal['sweeps'],verifier['sweeps']],
                    proposed_wire=f.encode_state(proposed).hex(),
                    verifier_proposed_wire=f.encode_state(checked).hex())
                if f.encode_state(proposed)!=f.encode_state(checked):
                    row['output_agreement']=False
                    raise midpoint.Rejected('256_384_output_mismatch')
                midpoint.check_chord(models[model_ids[scenario]],old,midpoint.packet_values(proposed),96)
                certificate=check.fixed_cell_root(oracle_models[model_ids[scenario]],wire,f.encode_state(proposed),verifier)
                row.update(status=certificate['status'],certificate=certificate,norms=norms,
                    operations=counts,sweeps=[causal['sweeps'],verifier['sweeps']],
                    proposed_wire=f.encode_state(proposed).hex(),output_agreement=True)
                if certificate['status']=='root_certified':
                    # This entry point is a first-step control inventory only.
                    row['next_gate']='short_trajectory_required'
            except midpoint.Rejected as error:
                row.update(status='reject_integrator_solver',reason=str(error))
            assert f.encode_state(old)==wire,'rejection mutated prior state'
            row['returned_prior_wire']=wire.hex();row['atomic_prior_unchanged']=True
            b.append(row);save(out/(label+'-control.json'),row)
            print(json.dumps(dict(candidate='B',case=label,status=row['status'],reason=row.get('certificate',{}).get('reason',row.get('reason'))),sort_keys=True),flush=True)
    save(out/'b-short-control-inventory.json',b)
    save(out/'control-summary.json',dict(parent=auth,A_controls=len(a_controls),
        C=c[-1]['status'],C_attempted=len(c),C_remaining_not_run=15-len(c),
        B_controls=len(b),B_certified=sum(r['status']=='root_certified' for r in b),
        B_full_tails_run=0,promotion='NO_PROMOTION',scope='first-step controls, not completed bakeoff'))
    save(out/'external-resources.json',dict(seconds=time.monotonic()-start,maxrss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('parent',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args();control_run(args.parent,args.output)
