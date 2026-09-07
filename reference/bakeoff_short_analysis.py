"""Exact energy pathology rules and independent smooth-oracle order analysis."""
import argparse
from decimal import Decimal, getcontext
from fractions import Fraction as Q
import json
from pathlib import Path
import bounded_integrator_bakeoff_check as c


def dec(q):return Decimal(q.numerator)/Decimal(q.denominator)


def energy_gate(values,uncertainties):
    boxes=[(max(Q(),v-u),v+u) for v,u in zip(values,uncertainties)]
    resolved=[v>64*u for v,u in zip(values,uncertainties)]
    worsening=[resolved[k] and resolved[k+1] and boxes[k+1][0]>boxes[k][1] for k in range(4)]
    if any(all(worsening[k:k+3]) for k in range(2)):return 'fail_three_worsening'
    if not resolved[4]:return 'pass_floor'
    if not resolved[0]:return 'inconclusive_initial_floor'
    if boxes[4][1]<boxes[0][0]:return 'pass_overall_contraction'
    if boxes[4][0]>=boxes[0][1]:return 'fail_overall_noncontraction'
    return 'inconclusive_overlap'


def analyse(baseline,exact,smooth):
    getcontext().prec=110
    oracle=json.loads(smooth.read_text());out=[]
    for scenario in c.f.SCENARIOS:
        paths={}
        for path in (c.f.KDK,c.f.CONTROL):
            errors=[];maxenergy=[];finalenergy=[];radii=[];uncertainties=[]
            for level in range(5):
                row=json.loads((baseline/f'{scenario}-L{level}-{path}.json').read_text())
                values=c.decode_wire(bytes.fromhex(row['wires'][-1]))[3];N=len(values)//6
                physical=[dec(values[6*i+a]*c.f.LQ) for i in range(N) for a in range(3)]
                physical += [dec(values[6*i+a+3]*c.f.PQ) for i in range(N) for a in range(3)]
                target=list(map(Decimal,oracle['endpoint'][scenario]))
                errors.append((sum(((a-b)**2 for a,b in zip(physical,target)),Decimal())/N).sqrt())
                energies=list(map(Q,row['energy']));d=[e-energies[0] for e in energies]
                maxenergy.append(max(abs(e) for e in d));finalenergy.append(abs(d[-1]))
                if path==c.f.KDK:
                    prefix=json.loads((exact/f'{scenario}-L{level}.json').read_text())
                    assert prefix['passed']
                    bound=(3*(dec(Q(prefix['x']))**2+dec(Q(prefix['p']))**2)).sqrt()
                    uncertainties.append(bound+Decimal(2)**-70)
                    radii.append(Q(prefix['energy']))
            orders=[(errors[k]/errors[k+1]).ln()/Decimal(2).ln() for k in range(4)]
            required=3 if path==c.f.KDK else 2
            lo,hi=(Decimal('1.6'),Decimal('2.4')) if path==c.f.KDK else (Decimal('.6'),Decimal('1.4'))
            window=any(all(lo<=x<=hi for x in orders[k:k+required]) for k in range(5-required))
            detail=dict(errors=list(map(str,errors)),orders=list(map(str,orders)),order_window=window,
                energy_maximum=list(map(str,maxenergy)),energy_final=list(map(str,finalenergy)))
            if path==c.f.KDK:
                detail.update(uncertainties=list(map(str,uncertainties)),
                    resolved=all(e>64*u and u<=e/10 for e,u in zip(errors,uncertainties)),
                    energy_max_gate=energy_gate(maxenergy,radii),energy_final_gate=energy_gate(finalenergy,radii))
            paths[path]=detail
        paths['first_order_separated']=max(map(Decimal,paths[c.f.KDK]['orders']))-max(map(Decimal,paths[c.f.CONTROL]['orders']))>=Decimal('.5')
        out.append(dict(scenario=scenario,paths=paths))
    passed=all(r['paths'][c.f.KDK]['order_window'] and r['paths'][c.f.CONTROL]['order_window']
        and r['paths']['first_order_separated'] and r['paths'][c.f.KDK]['resolved']
        and r['paths'][c.f.KDK]['energy_max_gate'].startswith('pass')
        and r['paths'][c.f.KDK]['energy_final_gate'].startswith('pass') for r in out)
    return dict(rows=out,passed=passed,oracle_agreement=oracle['refinement'],
        note='Smooth ODE refinement is inherited numerical verification, not a Lean or interval-ODE proof.')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('baseline','exact','smooth','output'):p.add_argument(name,type=Path)
    a=p.parse_args();result=analyse(a.baseline,a.exact,a.smooth)
    with a.output.open('x') as stream:json.dump(result,stream,sort_keys=True);stream.write('\n')
    print('PASS' if result['passed'] else 'NOT QUALIFIED')
