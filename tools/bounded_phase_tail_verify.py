"""Independent record arithmetic and replay checks for the narrow tail audit.

This does not claim that any full tail has been certified. Use --replay-prefixes
to repeat the expensive signed phase-state replays as well as record validation.
"""
import argparse
import hashlib
import json
import sys
from fractions import Fraction as Q
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import bounded_phase_tail_stage_one as stage
import bounded_phase_tail_pilot_suite as pilot
import bounded_phase_tail_prefix as prefix
import bounded_fractional_phase_state_oracle as frozen

def verify(inputs, evidence, replay=False):
    source=json.loads((inputs/'oracle/oracle-summary.json').read_text())
    assert json.loads((evidence/'stage-one.json').read_text())==stage.extract(inputs/'oracle/oracle-summary.json')
    suite=json.loads((evidence/'pilot-suite.json').read_text())
    assert suite==pilot.run(inputs)
    assert len(suite['full_horizons'])==10
    assert all(r['status']=='certification_inconclusive' for r in suite['full_horizons'])
    assert sum(r['reason'] is None for r in suite['withheld_blocks'])==60
    assert sum(r['withheld_exact_stage_checks'] for r in suite['withheld_blocks'])==1320
    checked=0
    for name,scenario,level in [('internal-L'+str(i),'k4_internal',i) for i in (1,2,3,4)]+[('boosted-L4','k4_boosted',4)]:
        result=json.loads((evidence/f'prefix-{name}.json').read_text())
        assert (result['scenario'],result['level'])==(scenario,level)
        if replay:
            assert result==prefix.run(inputs,scenario,level)
        envelopes=source['long_run']['long_exact_prefix_anchor'][str(level)]['scenarios'][scenario]['metric_envelopes']
        dt=frozen.TIMESTEPS_RAW[level]*frozen.TQ
        for bits,report in result['profiles'].items():
            values=list(map(Q,report['signed_energy_samples']))
            assert len(values)==result['samples']==result['prefix_steps']+1
            # Pairwise centered times: independent of the generator's explicit mean.
            n=len(values)
            weights=[Q(2*i-(n-1),2)*dt for i in range(n)]
            signed=sum((w*e for w,e in zip(weights,values)),Q())
            unsigned=sum((abs(w*e) for w,e in zip(weights,values)),Q())
            denominator=sum((w*w for w in weights),Q())
            assert signed==Q(report['slope_numerator'])
            assert unsigned==Q(report['slope_sum_absolute_contributions'])
            assert denominator==Q(report['slope_denominator'])
            assert signed/denominator==Q(report['slope'])
            assert abs(signed)/unsigned==Q(report['cancellation_fraction'])
            assert values[-1]==Q(report['final_energy'])
            if scenario=='k4_internal':
                assert abs(values[-1])==Q(envelopes['energy_final'][bits])
                assert abs(signed/denominator)==Q(envelopes['energy_slope'][bits])
            else:
                # The sealed boosted anchor has position/momentum gates only.
                # Its signed energy trace is an added diagnostic, never a
                # fabricated parent gate or a reason to qualify a tail.
                assert 'energy_final' not in envelopes and 'energy_slope' not in envelopes
            position=report['final_position']
            assert Q(position['magnitude'])==Q(envelopes['position_final'][bits])
            assert position['sample']==n-1 and position['ties']
            assert all(abs(Q(t['signed_error']))==Q(position['magnitude']) for t in position['ties'])
            assert report['potential_binary64_matches']==n
            checked+=n
    return dict(record_samples_checked=checked,withheld_stage_checks=1320,
                parent_energy_anchor_profiles_checked=8,
                boosted_energy_profiles_diagnostic_only=2,
                full_prefix_replay=replay,full_tails_certified=False,promotion='NO_PROMOTION')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('evidence',type=Path)
    p.add_argument('--replay-prefixes',action='store_true')
    a=p.parse_args();print(json.dumps(verify(a.inputs,a.evidence,a.replay_prefixes),sort_keys=True))
