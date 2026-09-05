"""Deterministic withheld-answer and full-horizon pilot inventory."""
import argparse
import json
from pathlib import Path
import bounded_phase_tail_interval as v

def run(bundle):
    raw=bundle/'raw-a'
    parent=bundle/'parent-explicit-fractional/raw-a'
    cases=[('k4_internal',i) for i in (1,2,3,4,0)]+[('k4_boosted',i) for i in range(5)]
    full=[v.run(raw,parent,scenario,level) for scenario,level in cases]
    blocks=[v.run(raw,parent,scenario,level,start,length)
            for scenario,level in cases for start in (0,8,32) for length in (1,4,16)]
    return dict(schema='mls.bounded-phase-tail.pilot-suite.v1',
        full_horizons=full,withheld_blocks=blocks,
        whole_trajectory_certified=False,
        limitations=['Exact-checkpoint blocks do not reset or repair the failed full-trajectory enclosure.',
                     'Successful blocks certify reference state inclusion only, not energy or physical budgets.'],
        promotion='NO_PROMOTION')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path)
    a=p.parse_args();print(json.dumps(run(a.bundle),sort_keys=True,indent=2))
