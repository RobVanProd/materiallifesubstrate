"""Fresh replay of all new short AND complete tails. No B256 truth."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.dont_write_bytecode=True
import relation_coordinate_defect_tail_bundle as bundle
import defect_recurrence_tail_verify as parent_verify
from relation_coordinate_defect_tail_audit import identical


def verify(root,records_only=False):
    identity=bundle.check(root)
    source=root/'source';work=root/'evidence';parent=root/'parent'
    inherited=parent_verify.verify(parent,records_only=True)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    for test in ('relation_coordinate_defect_tail_test.py','defect_recurrence_tail_test.py'):
        subprocess.run([sys.executable,str(source/'tests'/test)],cwd=source,env=env,check=True)
    replay_directory=None
    if not records_only:
        temp=Path(tempfile.mkdtemp(prefix='mls-relation-public-replay-'))
        replay_directory=str(temp)
        inputs=parent/'parent/parent/inputs'
        invariants=parent/'evidence/candidate-auth/invariants.csv'
        with (temp/'short.log').open('w') as log:
            subprocess.run([sys.executable,str(source/'tools/relation_coordinate_defect_tail_suite.py'),
                str(inputs),str(temp/'short')],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        identical(temp/'short',work/'withheld')
        with (temp/'full.log').open('w') as log:
            subprocess.run([sys.executable,str(source/'tools/relation_coordinate_defect_full_suite.py'),
                str(inputs),str(invariants),str(temp/'short'),str(temp/'full')],cwd=source,env=env,
                stdout=log,stderr=subprocess.STDOUT,check=True)
        identical(temp/'full',work/'full')
    bundle.check(root)
    return dict(identity=identity,parent_verification=inherited,records_only=records_only,
        new_short_blocks_replayed=0 if records_only else 90,
        new_full_tails_replayed=0 if records_only else 10,replay_directory=replay_directory,
        prior_full_exact_prefix_replayed=False,selected_precision=96,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--records-only',action='store_true')
    a=p.parse_args();print(json.dumps(verify(a.root.resolve(),a.records_only),sort_keys=True))
