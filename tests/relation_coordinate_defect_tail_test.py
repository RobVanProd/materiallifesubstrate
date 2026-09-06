import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import unittest
from types import SimpleNamespace as NS
from fractions import Fraction as Q
import relation_coordinate_defect_tail as v
import relation_coordinate_defect_full as full
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import relation_coordinate_defect_tail_suite as suite


def image(a,x):
    return [sum((c*t for c,t in zip(row,x)),Q()) for row in a]


class RelationTests(unittest.TestCase):
    def setUp(self):
        self.ids=[1,2,3];self.masses=[2,3,5]
        self.model=NS(relations=[NS(index=0,first_id=1,second_id=2,rest_length=1.),
                                 NS(index=1,first_id=2,second_id=3,rest_length=1.)],
            reference={1:[Q(0)]*3,2:[1/v.frozen.LQ,Q(0),Q(0)],
                       3:[2/v.frozen.LQ,Q(0),Q(0)]},h=[[1.,0.],[0.,1.]])
        self.c=list(map(Q,[0,0,0,1,2,3,2,0,0,4,5,6,4,0,0,7,8,9]))
        # Reference model has nonzero extension without tiny physical geometry.
        for i in range(3): self.c[6*i] /= v.frozen.LQ
        self.rc=v.observe(self.model,self.ids,self.masses,self.c)
        self.e=[v.base.Interval(Q(),Q()) for _ in self.rc]

    def matrices(self,stage):
        return v.operators(self.model,self.ids,self.masses,self.rc,self.e,stage,2)[:2]

    def test_incidence_closure_all_basis_vectors(self):
        for stage in ['first_kick','drift','second_kick']:
            pm,rm=self.matrices(stage)
            for k in range(18):
                x=[Q(int(j==k)) for j in range(18)]
                self.assertEqual(v.observe(self.model,self.ids,self.masses,image(pm,x)),
                    image(rm,v.observe(self.model,self.ids,self.masses,x)))

    def test_translation_and_common_velocity_boost(self):
        translated=self.c.copy()
        for i,m in enumerate(self.masses):
            for a in range(3):
                translated[6*i+a]+=Q(a+1,7)
                translated[6*i+3+a]+=m*Q(a+1,11)
        self.assertEqual(self.rc,v.observe(self.model,self.ids,self.masses,translated))

    def test_arbitrary_center_and_exact_defects(self):
        _,rm=self.matrices('first_kick')
        nc=[q+Q(i+1,201) for i,q in enumerate(self.rc)]
        out,d=v.base.propagate(rm,self.rc,nc,self.e)
        v.base.affine_image(rm,self.rc,nc,self.e,out,d)
        with self.assertRaises(AssertionError):
            v.base.affine_image(rm,self.rc,nc,self.e,out,[Q()]*len(d))

    def test_direct_zero_not_independent_endpoint_subtraction(self):
        c=[Q()]*12
        pe=[v.base.Interval(Q(1,7),Q(2,7))]*12
        cart=v.base.relative(c,pe,0,1)[0]
        direct=v.target_relations([Q()]*6,[v.base.Interval(Q(),Q())]*6)[0][0]
        self.assertLess(cart.lo,0);self.assertGreater(cart.hi,0)
        self.assertEqual(v.base.certify_cell(direct,0,0),0.)
        with self.assertRaises(v.base.Inconclusive): v.base.certify_cell(cart,0,0)

    def test_wrong_orientation_or_mass_breaks_closure(self):
        pm,rm=self.matrices('first_kick')
        correct=v.observe(self.model,self.ids,self.masses,image(pm,self.c))
        rm[3][0]=-rm[3][0]
        self.assertNotEqual(correct,image(rm,self.rc))
        self.assertNotEqual(self.rc,v.observe(self.model,self.ids,[1,1,1],self.c))

    def test_inward_and_omitted_relation_error_rejected(self):
        rm=v.base.identity(12)
        e=[v.base.Interval(Q(-1),Q(1))]*12
        out,d=v.base.propagate(rm,self.rc,self.rc,e)
        out[0]=v.base.Interval(Q(),Q())
        with self.assertRaises(AssertionError):v.base.affine_image(rm,self.rc,self.rc,e,out,d)

    def test_signed_stream(self):
        z=v.base.Interval(Q(),Q())
        a=v.base.signed_add(z,Q(-2),v.base.Interval(Q(3),Q(3)))
        a=v.base.signed_add(a,Q(3),v.base.Interval(Q(2),Q(2)))
        self.assertEqual(a,z)

    def test_domain_fail_closed(self):
        rr=[v.base.Interval(Q(),Q())]*3
        with self.assertRaises(v.base.Inconclusive):v.base.safe(self.model,self.model.relations[0],rr)

    def test_frame_box_matches_independent_com(self):
        self.model.relations.append(NS(index=2,first_id=1,second_id=3,rest_length=2.))
        rc=v.observe(self.model,self.ids,self.masses,self.c)
        target=[c+Q(k+1,201) for k,c in enumerate(self.c)]
        rt=v.observe(self.model,self.ids,self.masses,target)
        re=[v.base.enclose(t-c,t-c) for t,c in zip(rt,rc)]
        boxes=full.frame_box(self.model,self.ids,self.masses,self.c,rc,re)
        total=sum(self.masses)
        for i,m in enumerate(self.masses):
            for a in range(6):
                unit=v.frozen.LQ if a<3 else v.frozen.PQ
                if a<3:
                    c=self.c[6*i+a]-sum(self.masses[j]*self.c[6*j+a] for j in range(3))/total
                    t=target[6*i+a]-sum(self.masses[j]*target[6*j+a] for j in range(3))/total
                else:
                    c=self.c[6*i+a]-Q(m,total)*sum(self.c[6*j+a] for j in range(3))
                    t=target[6*i+a]-Q(m,total)*sum(target[6*j+a] for j in range(3))
                box=boxes[6*i+a]
                self.assertEqual(Q(box['candidate']),c*unit)
                self.assertLessEqual(Q(box['error'][0]),(t-c)*unit)
                self.assertGreaterEqual(Q(box['error'][1]),(t-c)*unit)

    def test_energy_box_against_exact_rational_kinetic_observer(self):
        packets=[v.frozen.PacketState(pid,m,self.c[6*i:6*i+3],self.c[6*i+3:6*i+6])
                 for i,(pid,m) in enumerate(zip(self.ids,self.masses))]
        candidate=v.frozen.PhaseState(96,0,packets)
        target=v.frozen.RationalState(0,[v.frozen.PacketState(p.identifier,p.mass_raw,p.x.copy(),
            [q+Q(a+1,201) for a,q in enumerate(p.p)]) for p in packets])
        error=[v.base.enclose(t-c,t-c) for t,c in zip(v.base.flat(target),self.c)]
        interval=full.energy_error(self.model,candidate,self.c,error,self.rc,self.e)
        exact=v.frozen.rational_energy(self.model,target)-v.frozen.mechanical_energy(self.model,candidate)[2]
        self.assertTrue(interval.contains(exact))


class LaunchMutationTests(unittest.TestCase):
    def reports(self):
        return [dict(scenario=s,level=l,start_step=t,block_steps=n,precision=96,verifier_bits=512,
            packet_intervals=24,relation_intervals=36,matrix_slots=1872,historical_noise_symbols=0,
            promotion='NO_PROMOTION',selected_precision=None,physical_budgets_certified=False,
            status='withheld_block_contained',reason=None,complete_steps=n,withheld_checks=3*n)
            for s,l,t,n in suite.CASES]

    def test_complete_inventory_required(self):
        rows=self.reports();self.assertTrue(suite.gate(rows)['eligible'])
        rows[-1]=rows[0]
        with self.assertRaises(AssertionError):suite.gate(rows)

    def test_b256_substitution_rejected(self):
        rows=self.reports();rows[0]['precision']=256
        with self.assertRaises(AssertionError):suite.gate(rows)

    def test_packet_only_state_rejected(self):
        rows=self.reports();rows[0]['relation_intervals']=0
        with self.assertRaises(AssertionError):suite.gate(rows)

    def test_resource_or_cell_failure_cannot_be_pass(self):
        for reason in ('force_cell','verifier_resource_limit'):
            rows=self.reports();rows[0]['reason']=reason
            with self.assertRaises(AssertionError):suite.gate(rows)
            rows[0]['status']='certificate_inconclusive'
            self.assertFalse(suite.gate(rows)['eligible'])


if __name__=='__main__': unittest.main()
