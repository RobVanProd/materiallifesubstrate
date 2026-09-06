"""Independent exact audit of an affine interval image and launch eligibility."""
from fractions import Fraction as Q


def affine_image(matrix,center,following,before,after,defects):
    n=len(center)
    assert len(matrix)==len(following)==len(before)==len(after)==len(defects)==n
    for i,row in enumerate(matrix):
        assert len(row)==n
        exact_defect=sum((row[j]*center[j] for j in range(n)),Q())-following[i]
        assert exact_defect==defects[i], 'wrong or omitted exact stage defect'
        # Explicit extremizing points of the Cartesian domain, independent of
        # the generator's incremental endpoint propagation and dyadic rounder.
        minimizer=[before[j].lo if row[j]>=0 else before[j].hi for j in range(n)]
        maximizer=[before[j].hi if row[j]>=0 else before[j].lo for j in range(n)]
        minimum=exact_defect+sum((row[j]*minimizer[j] for j in range(n)),Q())
        maximum=exact_defect+sum((row[j]*maximizer[j] for j in range(n)),Q())
        assert after[i].lo <= minimum <= maximum <= after[i].hi, 'inward image enclosure'


def full_tail_eligible(reports):
    expected={(s,l,start,length) for s in ('k4_internal','k4_boosted')
              for l in range(5) for start in (0,8,32) for length in (1,4,16)}
    assert len(reports)==90
    assert {(r['scenario'],r['level'],r['start_step'],r['block_steps']) for r in reports}==expected
    passed=0
    for r in reports:
        assert r['precision']==96 and r['verifier_bits']==512
        assert not r['physical_budgets_certified'] and r['selected_precision'] is None
        assert r['promotion']=='NO_PROMOTION' and r['historical_noise_symbols']==0
        assert r['active_error_intervals']==24 and r['active_error_endpoints']==48 and r['matrix_slots']==576
        if r['status']=='withheld_block_contained':
            assert r['reason'] is None
            assert r['complete_steps']==r['block_steps'] and r['withheld_checks']==3*r['block_steps']
            passed+=1
        else:
            assert r['status']=='certificate_inconclusive' and r['reason'] in (
                'force_cell','domain_enclosure','verifier_exponent_limit','verifier_resource_limit')
    return dict(eligible=passed==90,blocks_passed=passed,blocks_total=90,
                stage_checks=sum(r['withheld_checks'] for r in reports),promotion='NO_PROMOTION')
