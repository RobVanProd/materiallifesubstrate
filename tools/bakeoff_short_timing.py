"""Registered serial warmup + five timings for each eligible short KDK case."""
import argparse
from pathlib import Path
import resource
from bakeoff_baseline_tails import one
from run_bounded_integrator_bakeoff import initial_models,expected_states,save
import run_bounded_fractional_phase_state_lab as f


def run(parent,out):
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    models,mids,states=initial_models(parent);expected=expected_states(parent);rows=[]
    for scenario in f.SCENARIOS:
        for level,n in enumerate(f.TIMESTEPS_RAW):
            count=f.STEP_COUNTS[level]
            auth={k:expected[(scenario,f.KDK,level,k)] for k in range(count+1)}
            warm,_=one(models[mids[scenario]],states[scenario],n,count,auth,False)
            seconds=[]
            for _ in range(5):
                row,elapsed=one(models[mids[scenario]],states[scenario],n,count,auth,False)
                assert row['wire_stream']==warm['wire_stream'],'short timing repeat differs'
                seconds.append(elapsed)
            rows.append(dict(scenario=scenario,level=level,seconds=seconds,warmups=1,
                median=sorted(seconds)[2],range=[min(seconds),max(seconds)],wire_stream=warm['wire_stream'],
                note='single-thread candidate one_step only; observers outside timed interval'))
    save(out,rows)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('parent',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.parent,a.output)
