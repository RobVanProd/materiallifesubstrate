"""Pre-data exact encoding/template regressions, not candidate measurements."""
from fractions import Fraction as Q
import io
import itertools
from math import comb
import unittest

import occupied_geometry_input as gen
import occupied_geometry_input_check as independent
import occupied_geometry_weights as weights
import occupied_geometry_weight_inventory as inventory
import occupied_geometry_weight_replay as weight_replay
from occupied_geometry_incidence_check import facet_components


def decode(data):
    reader=independent.Reader.__new__(independent.Reader)
    reader.f=io.BytesIO(data)
    value=reader.q();reader.end();return value


class InputContract(unittest.TestCase):
    def test_full_facet_connectivity_not_vertex_or_edge_connectivity(self):
        self.assertEqual(facet_components({1:(1,2,3,4),2:(1,2,3,5)}),((1,2),))
        self.assertEqual(facet_components({1:(1,2,3,4),2:(1,2,5,6)}),((1,),(2,)))
        self.assertEqual(facet_components({1:(1,2,3,4),2:(1,5,6,7)}),((1,),(2,)))
        self.assertEqual(facet_components({1:(1,2,3,4),2:(1,2,3,5),3:(1,2,5,6)}),((1,2,3),))

    def test_invalid_facet_incidence(self):
        for cells in ({1:(1,2,3,4),2:(4,3,2,1)},
                      {1:(1,2,3,4),2:(1,2,3,5),3:(1,2,3,6)}):
            with self.assertRaises(ValueError):facet_components(cells)

    def test_wire_roundtrip(self):
        self.assertEqual(gen.rational(Q(0)).hex(),'00000000000100000001')
        for q in (Q(0),Q(1),Q(-1),Q(1,201),Q(-13,17),Q(1,1<<896),Q(1<<700,3)):
            self.assertEqual(decode(gen.rational(q)),q)

    def test_wire_mutations(self):
        zero=gen.rational(Q(0));half=gen.rational(Q(1,2))
        variants=(b'\x01'+zero[1:],b'\x02'+half[1:],zero[:-1],
                  zero+b'\x00',zero[:5]+b'\x00'*4,
                  gen.sint(2)+gen.uint(4),gen.sint(0)+gen.uint(2),
                  b'\x00\x01\x00\x00\x00\x00'+gen.uint(1))
        for data in variants:
            with self.subTest(data=data.hex()),self.assertRaises(AssertionError):decode(data)

    def test_child_partition_and_shared_faces(self):
        root=((0,0,0),(1,0,0),(0,1,0),(0,0,1));children=gen.refine(root)
        faces={}
        for child in children:
            determinant=gen.determinant(child)
            self.assertEqual(abs(determinant),1)
            oriented=list(child)
            if determinant<0:oriented[-1],oriented[-2]=oriented[-2],oriented[-1]
            for i in range(4):
                face=[p for j,p in enumerate(oriented) if j!=i]
                inv=sum(face[j]>face[k] for j in range(3) for k in range(j+1,3))
                faces.setdefault(tuple(sorted(face)),[]).append((-1)**(i+inv))
        boundary=0
        for face,signs in faces.items():
            if len(signs)==2:self.assertEqual(sum(signs),0)
            else:
                self.assertEqual(len(signs),1);boundary+=1
                self.assertTrue(any(all(p[j]==0 for p in face) for j in range(3))
                                or all(sum(p)==2 for p in face))
        self.assertEqual(boundary,16)

    def test_gram_closure(self):
        root=((0,0,0),(1,0,0),(0,1,0),(0,0,1))
        operators=[]
        for child in gen.refine(root):
            operators.append(tuple(tuple(child[j+1][i]-child[0][i] for j in range(3)) for i in range(3)))
        identity=((1,0,0),(0,1,0),(0,0,1));seen={identity};pending=[identity]
        while pending:
            gram=pending.pop()
            for matrix in operators:
                next_gram=tuple(tuple(sum(matrix[a][i]*gram[a][b]*matrix[b][j]
                    for a in range(3) for b in range(3)) for j in range(3)) for i in range(3))
                if next_gram not in seen:seen.add(next_gram);pending.append(next_gram)
                self.assertLessEqual(len(seen),6)
        self.assertEqual(len(seen),6)
        for gram in seen:
            self.assertLessEqual(max([gram[i][i] for i in range(3)]+
                [gram[i][i]+gram[j][j]-2*gram[i][j] for i in range(3) for j in range(i)]),3)

    def test_exact_taylor_recurrence(self):
        for c in ((Q(1),Q(2),Q(3)),(Q(2,3),Q(1,7),Q(3,5))):
            for u in ((Q(1,20),Q(-1,17),Q(1,9)),(Q(0),Q(0),Q(0))):
                a=sum(x*x for x in c);b=2*sum(x*y for x,y in zip(c,u))/a
                v=sum(x*x for x in u)/a;s0=sum(c);s1=sum(u)
                ns=(s0**3,3*s0*s0*s1,3*s0*s1*s1,s1**3)
                old=sum(weights.BETA[m]*comb(m,j)*b**(m-j)*v**j*ns[l]
                    for m in range(13) for j in range(m+1)
                    for l in range(min(3,12-m-j)+1))
                self.assertEqual(weights.polynomial_at(c,u),old)
                self.assertEqual(weight_replay.polynomial_at(c,u),old)

    def test_exact_monomial_rule(self):
        self.assertEqual(weights.rule_check(),560)

    def test_weight_carries(self):
        value=weights.Q(13,29)
        ranges=[(weights.Q(i+1),weights.Q(i+1)+weights.Q(1,100)) for i in range(8)]
        children=inventory.allocate(value,ranges)
        self.assertEqual(sum(children),value)
        self.assertTrue(all(c>0 for c in children))
        self.assertEqual(inventory.allocate(value,[(weights.Q(1),weights.Q(1))]*8),[value/8]*8)


if __name__=='__main__':unittest.main()
