"""Offline bundle verification with explicit, non-confusable replay scopes."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import bounded_integrator_bakeoff_bundle as bundle


def verify(root,records_only=False,replay_parent=False,replay_exact=False):
    identity=bundle.check(root,deep=not records_only)
    parent_result=exact_result=None
    if replay_parent:
        from relation_coordinate_defect_tail_verify import verify as parent_verify
        parent_result=parent_verify(root/'parent')
    if replay_exact:
        from bakeoff_exact_short_audit import run
        exact_result=run(root/'parent',root/'evidence/short',root/'evidence/exact')
        assert exact_result==json.loads((root/'evidence/exact-independent.json').read_text())
    return dict(identity=identity,records_only=records_only,
        new_implicit_graphs_and_short_stages_replayed=not records_only,
        accepted_parent_full_certificate_replay=parent_result,
        independent_exact_short_replayed=replay_exact,
        earlier_optional_historical_replays=False,promotion='NO_PROMOTION')


if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    p=argparse.ArgumentParser();p.add_argument('root',type=Path)
    p.add_argument('--records-only',action='store_true');p.add_argument('--replay-parent',action='store_true')
    p.add_argument('--replay-exact-short',action='store_true');a=p.parse_args()
    print(json.dumps(verify(a.root.resolve(),a.records_only,a.replay_parent,a.replay_exact_short),sort_keys=True))
