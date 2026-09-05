import sys
import struct
import unittest
from fractions import Fraction as Q
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'reference'))
import correlation_aware_binary64_cells as c


class CellTests(unittest.TestCase):
    def test_exact_decode_independent(self):
        for bits in (0, 1, 2, (1<<52)-1, 1<<52, 0x3ff0000000000000,
                     0x3ff0000000000001, 0x7fefffffffffffff):
            for sign in (0, 1<<63):
                raw = bits | sign
                reference = Q.from_float(struct.unpack('>d', struct.pack('>Q', raw))[0])
                self.assertEqual(c.decode(raw), reference)

    def test_tie_even_and_odd_cells(self):
        bits = 0x3ff0000000000000
        midpoint = Q(1)+Q(1, 2**53)
        self.assertTrue(c.contains(Q(1), midpoint, bits))
        self.assertFalse(c.contains(midpoint, midpoint, bits+1))
        self.assertTrue(c.contains(midpoint+Q(1, 2**100), Q(1)+Q(1, 2**52), bits+1))

    def test_signed_zero(self):
        half = Q(1, 2**1075)
        self.assertTrue(c.contains(-half, -half, 1<<63))
        self.assertFalse(c.contains(-half, Q(), 1<<63))
        self.assertTrue(c.contains(Q(), half, 0))
        self.assertFalse(c.contains(-half, half, 0))

    def test_non_nominal_bit_assumption_is_rejected(self):
        wanted = Q(1)+Q(1, 2**52)
        self.assertFalse(c.contains(wanted, wanted, 0x3ff0000000000000))


if __name__ == '__main__':
    unittest.main()
