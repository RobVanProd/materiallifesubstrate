import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import unittest
from types import SimpleNamespace as NS
from fractions import Fraction as Q
import relation_coordinate_defect_tail as v


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


if __name__=='__main__': unittest.main()
