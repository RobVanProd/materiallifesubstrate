import copy
from fractions import Fraction as Q
from itertools import product
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import defect_recurrence_tail as d
import defect_recurrence_tail_check as check
import bounded_fractional_phase_state_oracle as f


class DefectTests(unittest.TestCase):
    def fixture(self):
        return ([[Q(1,3),Q(-2)],[Q(4),Q(1,7)]], [Q(9),Q(11)],
                [Q(13),Q(-7)], [d.enclose(Q(1,11),Q(2,11)),d.enclose(Q(-3,13),Q(5,13))])

    def test_arbitrary_candidate_identity_and_corners(self):
        a,c,n,e=self.fixture(); out,defects=d.propagate(a,c,n,e)
        check.affine_image(a,c,n,e,out,defects)
        for corner in product(*[(v.lo,v.hi) for v in e]):
            target=[c[i]+corner[i] for i in range(2)]
            true=[sum((v*x for v,x in zip(row,target)),Q())-after for row,after in zip(a,n)]
            self.assertTrue(all(b.contains(x) for b,x in zip(out,true)))

    def test_zero_defect_mutation(self):
        a,c,n,e=self.fixture(); out,defects=d.propagate(a,c,n,e)
        with self.assertRaises(AssertionError): check.affine_image(a,c,n,e,out,[Q(),Q()])

    def test_one_omitted_defect_mutation(self):
        a,c,n,e=self.fixture(); out,defects=d.propagate(a,c,n,e)
        defects[1]=Q()
        with self.assertRaises(AssertionError): check.affine_image(a,c,n,e,out,defects)

    def test_omitted_kick_and_drift_stage_defects(self):
        for a in ([[Q(1),Q()],[Q(1,3),Q(1)]],[[Q(1),Q(1,5)],[Q(),Q(1)]]):
            c,n=[Q(2),Q(3)],[Q(7),Q(11)]
            e=[d.Interval(Q(),Q())]*2
            out,defects=d.propagate(a,c,n,e)
            check.affine_image(a,c,n,e,out,defects)
            with self.assertRaises(AssertionError): check.affine_image(a,c,n,e,out,[Q(),Q()])

    def test_candidate_recenter_is_not_truth(self):
        a,c,n,e=self.fixture()
        out,_=d.propagate(a,c,n,e)
        translated=[d.Interval(b.lo+x,b.hi+x) for b,x in zip(e,c)]
        recentered,_=d.propagate(a,[Q(),Q()],n,translated)
        self.assertEqual(out,recentered)

    def test_candidate_as_truth_mutation(self):
        a,c,n,e=self.fixture(); out,defects=d.propagate(a,c,n,e)
        with self.assertRaises(AssertionError): check.affine_image(a,c,n,e,[d.Interval(Q(),Q())]*2,defects)

    def test_inward_endpoint_mutation(self):
        a,c,n,e=self.fixture(); out,defects=d.propagate(a,c,n,e)
        out[0]=d.Interval(out[0].hi,out[0].hi)
        with self.assertRaises(AssertionError): check.affine_image(a,c,n,e,out,defects)

    def test_signed_stream(self):
        acc=d.Interval(Q(),Q())
        for w,s in [(Q(-3),Q(5)),(Q(2),Q(7)),(Q(1),Q(1))]:
            acc=d.signed_add(acc,w,d.Interval(s,s))
        self.assertEqual((acc.lo,acc.hi),(Q(),Q()))
        self.assertNotEqual(sum(abs(w*s) for w,s in [(-3,5),(2,7),(1,1)]),0)

    def test_dropped_relative_error_mutation(self):
        c=[Q()]*12;e=[d.Interval(Q(),Q())]*12
        e[0]=d.Interval(Q(1),Q(2));e[6]=d.Interval(Q(4),Q(5))
        self.assertEqual(d.relative(c,e,0,1)[0],d.Interval(Q(2),Q(4)))
        self.assertFalse(d.relative(c,[d.Interval(Q(),Q())]*12,0,1)[0].contains(Q(3)))

    def test_rounding_cell_not_nominal_truth(self):
        with self.assertRaises(d.Inconclusive):
            d.certify_cell(d.Interval(Q(-1,2**600),Q(1,2**600)),5,0)
        self.assertEqual(d.certify_cell(d.Interval(Q(),Q()),5,0),0.0)
        self.assertFalse(d.cells.contains(Q(1),Q(1),struct.unpack('>Q',struct.pack('>d',2.0))[0]))

    def test_wire_decode_and_no_b256(self):
        state=f.PhaseState(96,0,[f.PacketState(1,2,[Q(1),Q(-2),Q()],[Q(3),Q(4),Q(5)])])
        wire=f.encode_phase_state(state)
        self.assertEqual(d.decode_wire(wire)[3],d.flat(state))
        for bad in (wire+b'0',wire[:-1]):
            with self.assertRaises(AssertionError): d.decode_wire(bad)
        state.precision=256
        with self.assertRaises(AssertionError): d.decode_wire(f.encode_phase_state(state))

    def test_checkpoint_error_not_zero(self):
        state=f.RationalState(0,[f.PacketState(1,2,[Q(1,3)]*3,[Q()]*3)])
        c=[Q()]*6
        e=[d.enclose(q,q) for q in d.flat(state)]
        self.assertTrue(d.withheld_check(e,c,state))
        self.assertFalse(d.withheld_check([d.Interval(Q(),Q())]*6,c,state))

    def test_fixed_precision_range(self):
        b=d.enclose(Q(1,3),Q(1,3))
        self.assertLess(b.lo,Q(1,3));self.assertGreater(b.hi,Q(1,3))
        with self.assertRaises(d.Inconclusive): d.enclose(Q(2)**17000,Q(2)**17000)

    def reports(self):
        return [dict(scenario=s,level=l,start_step=t,block_steps=n,precision=96,verifier_bits=512,
                     physical_budgets_certified=False,selected_precision=None,promotion='NO_PROMOTION',
                     historical_noise_symbols=0,active_error_intervals=24,active_error_endpoints=48,
                     matrix_slots=576,status='withheld_block_contained',reason=None,
                     complete_steps=n,withheld_checks=3*n)
                for s in ('k4_internal','k4_boosted') for l in range(5)
                for t in (0,8,32) for n in (1,4,16)]

    def test_full_launch_guard(self):
        r=self.reports();self.assertTrue(check.full_tail_eligible(r)['eligible'])
        r[0].update(status='certificate_inconclusive',reason='force_cell',complete_steps=0,withheld_checks=0)
        self.assertFalse(check.full_tail_eligible(r)['eligible'])

    def test_cell_and_resource_relabel_mutations(self):
        for reason in ('force_cell','verifier_resource_limit'):
            r=self.reports();r[0]['reason']=reason
            with self.assertRaises(AssertionError): check.full_tail_eligible(r)


if __name__=='__main__': unittest.main()
