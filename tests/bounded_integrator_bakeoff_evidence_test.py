import copy
from fractions import Fraction as Q
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'reference'),str(ROOT/'tools')]
import bakeoff_final_audit as a
import bounded_integrator_bakeoff_bundle as b


def result():
    return dict(decision=a.DECISION,promotion='NO_PROMOTION',selected_precision=96,pareto_set=['A'],
        A=dict(tails=10,short_KDK=15,first_order_controls=15,steps=15872,stages=47616),
        B=dict(eligible=False,tails_run=0,disposition='reject_integrator_solver',root_certified_controls=5,output_mismatches=5,cell_inconclusive=5),
        C=dict(eligible=False,tails_run=0,disposition='candidate_c_incompatible_with_frozen_path_b',solver_implemented=False,tested_endpoint_pairs=1),
        exact_conservation_claimed=False,production_integrator_selected=False)


class Evidence(unittest.TestCase):
    def test_positive_closed_disposition(self):self.assertTrue(a.check_result(result()))

    def test_disposition_mutations(self):
        mutations=[('promotion','PROMOTION'),('selected_precision',128),('pareto_set',['A','B']),
            ('exact_conservation_claimed',True),('production_integrator_selected',True),('decision','all_methods_pass')]
        for key,value in mutations:
            with self.subTest(key=key):
                r=result();r[key]=value
                with self.assertRaises(AssertionError):a.check_result(r)

    def test_inventory_and_rejection_mutations(self):
        mutations=[('A','tails',9),('A','short_KDK',14),('A','steps',15871),('A','stages',47615),
            ('B','eligible',True),('B','tails_run',1),('B','output_mismatches',0),('B','cell_inconclusive',0),
            ('B','disposition','resource_limit_pass'),('C','solver_implemented',True),('C','tested_endpoint_pairs',15),
            ('C','disposition','compatible')]
        for candidate,key,value in mutations:
            with self.subTest(candidate=candidate,key=key):
                r=result();r[candidate][key]=value
                with self.assertRaises(AssertionError):a.check_result(r)

    def test_ci_scope_and_failures(self):
        ci=dict(headSha='sealed-source',status='completed',conclusion='success',
            jobs=[dict(name=n,status='completed',conclusion='success') for n in sorted(b.REQUIRED_JOBS)])
        b.ci_check(ci,'sealed-source')
        for kind in ('sha','pending','missing','failed'):
            changed=copy.deepcopy(ci)
            if kind=='sha':changed['headSha']='other-source'
            elif kind=='pending':changed['status']='in_progress'
            elif kind=='missing':changed['jobs'].pop()
            else:changed['jobs'][0]['conclusion']='failure'
            with self.assertRaises(AssertionError):b.ci_check(changed,'sealed-source')

    def test_exact_frame_budget(self):
        a.require_budget(a.f.POSITION_BUDGET,a.f.MOMENTUM_BUDGET)
        with self.assertRaises(AssertionError):a.require_budget(a.f.POSITION_BUDGET+Q(1,2**200),Q())
        with self.assertRaises(AssertionError):a.require_budget(Q(),a.f.MOMENTUM_BUDGET+Q(1,2**200))


if __name__=='__main__':unittest.main()
