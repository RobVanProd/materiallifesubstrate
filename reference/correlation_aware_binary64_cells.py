"""Exact integer decoding and rational RN-even preimages, verifier-only."""
import struct
from fractions import Fraction as Q

SIGN = 1 << 63
FRACTION = (1 << 52)-1


def decode(bits):
    exponent = (bits >> 52) & 2047
    significand = bits & FRACTION
    if exponent == 2047:
        raise ValueError('nonfinite binary64 value')
    if exponent:
        significand += 1 << 52
        power = exponent-1075
    else:
        power = -1074
    magnitude = Q(significand)*Q(2)**power
    return -magnitude if bits & SIGN else magnitude


def contains(lo, hi, bits):
    assert lo <= hi
    value = decode(bits)
    if value == 0:
        half_subnormal = Q(1, 2**1075)
        # Fraction has one exact zero, converted to positive zero by the
        # frozen map. A negative tiny nonzero value converts to negative zero.
        if bits & SIGN:
            return -half_subnormal <= lo <= hi < 0
        return 0 <= lo <= hi <= half_subnormal
    lower_bits, upper_bits = ((bits+1, bits-1) if bits & SIGN else (bits-1, bits+1))
    try:
        low_mid = (decode(lower_bits)+value)/2
        high_mid = (value+decode(upper_bits))/2
    except ValueError:
        return False  # No overflow-boundary shortcut in this certificate.
    even = bits & 1 == 0
    return ((lo >= low_mid if even else lo > low_mid) and
            (hi <= high_mid if even else hi < high_mid))


def verify(box, value):
    bits = struct.unpack('>Q', struct.pack('>d', value))[0]
    assert contains(box.lo, box.hi, bits), 'uncertified binary64 rounding outcome'
