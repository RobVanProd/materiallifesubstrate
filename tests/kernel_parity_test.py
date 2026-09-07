"""Independent executable boundary controls and semantic evidence mutations."""
import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import run_authoritative_mechanics_kernel_parity as p
f=p.f

def run(exe,parent,out):
    out.mkdir(parents=True,exist_ok=False);models,mids,states=p.initial_models(parent/'parent');model=models['k4'];state=states['k4_internal']
    p.primitives(exe,out);checks=[]
    rng=random.Random(260907)
    # Initial/final/interior, exact coincidence, threshold ties and random chords.
    cases=[([1,0,0],[1,0,0],[1,0,0]),([1,0,0],[-1,0,0],[1,0,0]),([2,0,0],[1,0,0],[1,0,0]),([0,0,0],[1,0,0],[1,0,0])]
    for d in (-1,0,1):cases.append(([f.Fraction(1,2**24)+f.Fraction(d,2**96),0,0],[1,0,0],[1,0,0]))
    for _ in range(100):cases.append(tuple([f.Fraction(rng.randrange(-100,101),2**rng.randrange(0,30)) for _ in range(3)] for _ in range(3)))
    for i,(a,b,r) in enumerate(cases):
        a,b,r=[[f.Fraction(x) for x in v] for v in (a,b,r)];c=f.bounded_chord_certificate(a,b,r,96)
        inp=out/f'chord-{i}.input';dst=out/f'chord-{i}.output'
        inp.write_text('chord\n'+' '.join(f'{q.numerator} {q.denominator}' for q in [*a,*b,*r]))
        subprocess.run([str(exe),str(inp),str(dst)],check=True)
        expected=f'{int(c.safe)} {c.minimum_case} {c.lhs.numerator} {c.lhs.denominator} {c.rhs.numerator} {c.rhs.denominator} {c.scratch_observed_bits} {c.scratch_limit_bits}'
        assert dst.read_text().strip()==expected,('chord',i,dst.read_text(),expected)
    checks.append(dict(kind='exact_chord_predicate',cases=len(cases)))
    wire=f.encode_state(state);magic=len(f.MAGIC);bad=[]
    bad.extend([wire[:-1],wire+b'\0',b'BAD'+wire[3:]])
    for pos,val in [(magic+2,64),(magic+24+16,2),(magic+24+16+1,128)]:
        z=bytearray(wire);z[pos]=val;bad.append(bytes(z))
    # Noncanonical negative zero and duplicate/out-of-order packet identity.
    z=bytearray(wire);base=magic+24+16;z[base:base+17]=bytes([1,96,0,0,0])+bytes(12);bad.append(bytes(z))
    z=bytearray(wire);z[magic+24+118:magic+24+126]=z[magic+24:magic+32];bad.append(bytes(z))
    for i,z in enumerate(bad):
        inp=out/f'bad-wire-{i}.input';dst=out/f'bad-wire-{i}.output'
        inp.write_text('run test 0 62500000 0 0 KDK\n'+z.hex()+'\n'+p.model_text(model))
        status=subprocess.run([str(exe),str(inp),str(dst)]).returncode
        assert status!=0 and dst.read_text().startswith('ERROR'),('invalid wire admitted',i)
    checks.append(dict(kind='noncanonical_wire_rejection',cases=len(bad)))
    domain=states['domain_crossing'];domain_model=models[mids['domain_crossing']]
    failures=[];status,prior=f.one_step(domain_model,domain,1000000000,f.KDK,f.profile_for(96),failure_details=failures)
    result=p.invoke(exe,out,'atomic-domain',domain_model,f.encode_state(domain).hex(),'test',0,1000000000,1)
    lines=result.read_text().splitlines()
    assert status=='chord_domain_failure' and len(lines)==3 and lines[1].startswith('D ')
    assert lines[-1]==f'REJECT 1 {status} {f.encode_state(prior).hex()}',('atomic_domain',lines)
    assert not any(line.startswith(('E ','T ','G ')) for line in lines)
    checks.append(dict(kind='atomic_domain_no_partial_events',passed=True))
    collapsed=state.clone();r=model.relations[0];lookup=f.packet_lookup(collapsed);lookup[r.second_id].x=list(lookup[r.first_id].x)
    status,prior=f.one_step(model,collapsed,62500000,f.KDK,f.profile_for(96))
    result=p.invoke(exe,out,'coincidence',model,f.encode_state(collapsed).hex(),'test',0,62500000,1)
    assert status=='force_domain_failure' and result.read_text().splitlines()[-1]==f'REJECT 1 {status} {f.encode_state(prior).hex()}'
    checks.append(dict(kind='initial_coincidence_fail_closed',passed=True))
    # One authenticated first step: mutations must fail the actual comparison.
    reference=parent/'evidence/short'/f'k4_internal-L0-{f.KDK}.json'
    wires=json.loads(reference.read_text())['wires'][:2]
    result=p.invoke(exe,out,'positive',model,wires[0],'bakeoff-A',0,f.TIMESTEPS_RAW[0],1)
    p.compare(result,model,wires,'bakeoff-A',0,f.TIMESTEPS_RAW[0],0,f.KDK)
    lines=result.read_text().splitlines()
    for kind in ('state','stage','event','force','omission','false_pass'):
        changed=list(lines)
        if kind=='false_pass':changed=['S 0 '+wires[0]+' -','REJECT 1 force_domain_failure '+wires[0]]
        else:
            prefix={'state':'S 1 ','stage':'T ','event':'E ','force':'G ','omission':'E '}[kind]
            i=next(i for i,s in enumerate(changed) if s.startswith(prefix))
            if kind=='omission':changed.pop(i)
            else:
                cols=changed[i].split();j=2 if kind=='event' else 2 if kind=='state' else 3 if kind=='stage' else 4
                cols[j]=('1' if cols[j][0]!='1' else '2')+cols[j][1:];changed[i]=' '.join(cols)
        dst=out/('mutant-'+kind+'.output');dst.write_text('\n'.join(changed)+'\n')
        try:p.compare(dst,model,wires,'bakeoff-A',0,f.TIMESTEPS_RAW[0],0,f.KDK)
        except (AssertionError,ValueError,KeyError):pass
        else:raise AssertionError(('mutation accepted',kind))
        checks.append(dict(kind='mutation_'+kind,rejected=True))
    for kind in ('H','reference','endpoint_order'):
        changed=copy.deepcopy(model)
        if kind=='H':changed.h[0][0]*=1.01
        elif kind=='reference':changed.reference[next(iter(changed.reference))][0]+=1
        else:
            r=changed.relations[0];changed.relations[0]=f.exact_lab.Relation(r.index,r.second_id,r.first_id,r.rest_length)
        dst=p.invoke(exe,out,'mutant-'+kind,changed,wires[0],'bakeoff-A',0,f.TIMESTEPS_RAW[0],1)
        try:p.compare(dst,model,wires,'bakeoff-A',0,f.TIMESTEPS_RAW[0],0,f.KDK)
        except (AssertionError,ValueError,KeyError):pass
        else:raise AssertionError(('input mutation accepted',kind))
        checks.append(dict(kind='mutation_'+kind,rejected=True))
    p.save(out/'tests.json',dict(status='PASS',checks=checks,promotion='NO_PROMOTION'))
    print('BOUNDARY AND MUTATION CONTROLS PASS',flush=True)

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve())
