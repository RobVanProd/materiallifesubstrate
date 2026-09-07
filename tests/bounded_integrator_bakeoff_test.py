import copy
from fractions import Fraction as Q
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'reference'),str(ROOT/'tools')]
import bounded_integrator_bakeoff_check as check
import bakeoff_midpoint as mid
import run_bounded_fractional_phase_state_lab as f
from bakeoff_short_analysis import energy_gate
from types import SimpleNamespace


class Arithmetic(unittest.TestCase):
    def test_ties(self):
        self.assertEqual(check.rn(Q(17,16),4),Q(1))
        self.assertEqual(check.rn(Q(19,16),4),Q(5,4))
        self.assertEqual(check.rn(Q(-19,16),4),Q(-5,4))

    def test_outward(self):
        for q in [Q(1,201),Q(-1,201),Q(),Q(2)**-1000]:
            self.assertLessEqual(check.outward(q,False),q)
            self.assertGreaterEqual(check.outward(q,True),q)

    def test_rounding_mutation(self):
        audit=dict(bits=256,sweeps=2,operations=[['add',['1','2'],'4',False]])
        with self.assertRaisesRegex(AssertionError,'primitive'):check.audit_operations(audit)

    def test_inexact_mutation(self):
        audit=dict(bits=256,sweeps=2,operations=[['add',['1','2'],'3',True]])
        with self.assertRaisesRegex(AssertionError,'flag'):check.audit_operations(audit)

    def test_iteration_mutation(self):
        with self.assertRaises(AssertionError):check.audit_operations(dict(bits=256,sweeps=130,operations=[]))

    def test_exact_units(self):
        self.assertEqual(check.norm([Q(1)]*6),check.f.PQ)
        self.assertEqual(check.norm([Q(1),Q(),Q(),Q(),Q(),Q()]),check.f.LQ)

    def test_cell_zero_dependency(self):
        self.assertTrue(check.contains(Q(),Q(),0))
        self.assertFalse(check.contains(-Q(2)**-160,Q(2)**-160,0))

    def test_energy_single_increase_allowed(self):
        self.assertEqual(energy_gate(list(map(Q,[10,11,6,3,1])),[Q()]*5),'pass_overall_contraction')

    def test_energy_three_worsenings_fail(self):
        self.assertEqual(energy_gate(list(map(Q,[10,11,12,13,1])),[Q()]*5),'fail_three_worsening')

    def test_energy_plateau_above_floor_fails(self):
        self.assertEqual(energy_gate([Q(10)]*5,[Q()]*5),'fail_overall_noncontraction')

    def test_energy_floor(self):
        self.assertEqual(energy_gate([Q()]*5,[Q(1,2**100)]*5),'pass_floor')

    def test_unscaled_norm_rejected(self):
        zero=['0']*6;huge=['1']+['0']*5
        audit=dict(bits=256,iterations=[dict(guess=zero,new=huge,residual_next=huge)])
        with self.assertRaisesRegex(AssertionError,'tolerance'):check.audit_norms(audit,[Q()]*6)

    def test_discrete_chain_known_answer_and_rounding_incompatibility(self):
        import gmpy2 as g
        with f.profile_for(96).activate():
            raw=g.mpfr(128000000000)
            initial=f.State(96,0,[f.Packet(1,524288,[g.mpfr(0)]*3,[g.mpfr(0)]*3),
                f.Packet(2,524288,[raw,g.mpfr(0),g.mpfr(0)],[g.mpfr(0)]*3)])
            final=initial.clone();final.packets[1].x[0]=raw*2
            tiny=initial.clone();tiny.packets[1].x[0]=raw+g.mpfr(g.mpq(1,2**40))
        model=check.f.Model('pair',{1:[Q(),Q(),Q()],2:[Q(128000000000),Q(),Q()]},
            {1:524288,2:524288},[check.f.Relation(0,1,2,1.0)],[[1.0]])
        old=f.encode_state(initial)
        self.assertEqual(check.compatibility(model,old,old)['status'],'compatible')
        self.assertEqual(check.compatibility(model,old,f.encode_state(final))['status'],'compatible')
        rejected=check.compatibility(model,old,f.encode_state(tiny))
        self.assertEqual(rejected['subcode'],'extension_chain')
        self.assertNotEqual(Q(rejected['extension_residuals'][0]),0)

    def test_ballistic_proposal_root_and_replay(self):
        with f.profile_for(96).activate():
            import gmpy2 as g
            state=f.State(96,0,[f.Packet(1,524288,[g.mpfr(0)]*3,[g.mpfr(1),g.mpfr(2),g.mpfr(3)])])
        model=SimpleNamespace(relations=[],h=[])
        prior=f.encode_state(state)
        values,audit=mid.solve(model,state,62500000,256)
        values384,audit384=mid.solve(model,state,62500000,384)
        out=mid.proposal96(state,values,62500000)
        out384=mid.proposal96(state,values384,62500000)
        self.assertEqual(f.encode_state(out),f.encode_state(out384))
        self.assertEqual(f.encode_state(state),prior)
        check.audit_operations(audit);check.audit_operations(audit384)
        check.audit_counts(audit,1,0);check.audit_counts(audit384,1,0)
        omitted=copy.deepcopy(audit);omitted['operations'].pop()
        with self.assertRaisesRegex(AssertionError,'inventory'):check.audit_counts(omitted,1,0)
        _,_,_,old=check.decode_wire(prior)
        check.audit_norms(audit,old);check.audit_norms(audit384,old)
        audit384['n']=62500000
        report=check.fixed_cell_root(model,prior,f.encode_state(out),audit384)
        self.assertEqual(report['status'],'root_certified')
        for a in range(3):
            self.assertEqual(Q(report['root'][a]),Q(62500000,524288)*(a+1))
        mutated=out.clone()
        with f.profile_for(96).activate():mutated.packets[0].x[0]+=1
        self.assertEqual(check.fixed_cell_root(model,prior,f.encode_state(mutated),audit384)['reason'],'exact_root_output_mismatch')
        values2,_=mid.solve(model,state,62500000,256)
        self.assertEqual(f.encode_state(mid.proposal96(state,values2,62500000)),f.encode_state(out))


if __name__=='__main__':unittest.main()
