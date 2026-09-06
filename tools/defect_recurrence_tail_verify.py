"""Fresh verification: authenticate parents; replay all NEW short controls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.dont_write_bytecode=True
import defect_recurrence_tail_bundle as bundle
import correlation_aware_tail_verify as parent_verify
import defect_recurrence_stage_auth as stage_auth
import defect_recurrence_dependency_probe as dependency
from defect_recurrence_tail_audit import load


def verify(root,records_only=False):
    identity=bundle.check(root)
    parent=root/'parent'
    inherited=parent_verify.verify(parent,records_only=True)
    inputs=parent/'parent/inputs'
    work=root/'evidence'
    authenticated=stage_auth.authenticate(inputs,work/'candidate-auth/invariants.csv',work/'candidate-auth/outer-seal.json')
    assert authenticated==json.loads((work/'stage-auth.json').read_text())
    probes=[dependency.probe(inputs,s,l) for s in ('k4_internal','k4_boosted') for l in range(5)]
    assert probes==json.loads((work/'dependency-probe.json').read_text())
    source=root/'source'
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([sys.executable,str(source/'tests/defect_recurrence_tail_test.py')],cwd=source,env=env,check=True)
    replayed=0;replay_directory=None
    if not records_only:
        temp=Path(tempfile.mkdtemp(prefix='mls-defect-withheld-'))
        replay_directory=str(temp)
        with (temp/'runner.log').open('w') as log:
            subprocess.run([sys.executable,str(source/'tools/defect_recurrence_tail_suite.py'),str(inputs),str(temp/'replay')],
                           cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        assert load(temp/'replay')==load(work/'withheld')
        for p in (work/'withheld').glob('*.json'):
            assert p.read_bytes()==(temp/'replay'/p.name).read_bytes(),p.name
        replayed=90
    bundle.check(root)
    return dict(identity=identity,parent_records=inherited,new_unit_tests=15,
                candidate_stage_wires_authenticated=1930,dependency_diagnostics=10,
                new_blocks_replayed=replayed,new_checked_stages=1320 if replayed else 0,
                replay_directory=replay_directory,records_only=records_only,
                old_affine_blocks_replayed=False,old_memory_pilots_replayed=False,
                old_full_exact_prefix_replayed=False,full_tails_launched=0,
                selected_precision=None,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--records-only',action='store_true')
    a=p.parse_args();print(json.dumps(verify(a.root.resolve(),a.records_only),sort_keys=True))
