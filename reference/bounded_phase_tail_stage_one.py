"""Read-only exact extraction from the immutable parent oracle summary.

This diagnoses the frozen gate, not the sign/cause of unexported maxima.
"""
import argparse
import hashlib
import json
import sys
from fractions import Fraction as Q
from pathlib import Path

sys.set_int_max_str_digits(0)
PARENT = "17532284c2f0878e908f6a613f4c2e3baa47cbcd"
SUMMARY_HASH = "24d5d2fadd30b49cc2aab49506510d6e6c423fe312b01fbba3b561668a112554"

def nearest(q, bits):
    if q == 0:
        return Q(0), Q(0)
    sign = 1 if q > 0 else -1
    q = abs(q)
    exponent = q.numerator.bit_length() - q.denominator.bit_length()
    if q < Q(2) ** exponent:
        exponent -= 1
    ulp = Q(2) ** (exponent - bits + 1)
    scaled = q / ulp
    whole, rem = divmod(scaled.numerator, scaled.denominator)
    whole += 2 * rem > scaled.denominator or (
        2 * rem == scaled.denominator and whole % 2 == 1)
    return sign * whole * ulp, ulp / 2

def controls():
    rows = []
    for q, lo, hi in [(Q(1, 201), 192, 256),
                      (1 + Q(1, 1024), 4, 8),
                      (Q(1, 3), 4, 8), (Q(-1, 201), 192, 256),
                      (Q(17, 16), 4, 8)]:
        a, ba = nearest(q, lo)
        b, bb = nearest(q, hi)
        ea, eb = a-q, b-q
        assert abs(ea) <= ba and abs(eb) <= bb
        allowed = 4 * Q(2) ** (lo-hi) * abs(ea)
        rows.append(dict(input=str(q), lower_bits=lo, higher_bits=hi,
                         signed_lower_error=str(ea), signed_higher_error=str(eb),
                         lower_upper_bound=str(ba), higher_upper_bound=str(bb),
                         permitted_higher_error=str(allowed),
                         ratio_gate_pass=abs(eb) <= allowed,
                         excess=str(abs(eb)/allowed) if allowed else None))
    assert rows[0]["excess"] == "25/2"
    assert rows[1]["excess"] == "4"
    return rows

def signed_sum_controls():
    rows=[]
    for values in ((Q(1),Q(1,201),Q(-1)),
                   (Q(1),Q(1,1024),Q(-1)),
                   (Q(1,3),Q(-1,3),Q(1,201))):
        for bits in (192,256):
            value,bound=Q(0),Q(0)
            local=[]
            for term in values:
                exact=value+term
                value,slack=nearest(exact,bits)
                local.append(value-exact)
                bound+=slack
            error=value-sum(values)
            assert error==sum(local) and abs(error)<=bound
            rows.append(dict(terms=list(map(str,values)),bits=bits,
                signed_error=str(error),local_signed_errors=list(map(str,local)),
                independently_summed_upper_bound=str(bound),
                eta=str(abs(error)/bound) if bound else None))
    return rows

def extract(path):
    content = path.read_bytes()
    assert hashlib.sha256(content).hexdigest() == SUMMARY_HASH
    source = json.loads(content)
    assert source["source_sha"] == PARENT
    rows, failures = [], []
    for level, group in source["long_run"]["long_exact_prefix_anchor"].items():
        for scenario, report in group["scenarios"].items():
            for metric, values in report["metric_envelopes"].items():
                a, b = Q(values["192"]), Q(values["256"])
                bound = 4 * Q(1, 2**64) * a
                passed = (b == 0 if a == 0 else b < a and b <= bound)
                assert passed == report["b192_b256_unit_roundoff_scaling"][metric]
                row = dict(level=int(level), scenario=scenario, metric=metric,
                           anchor_required=report["anchor_required"],
                           lower_error=str(a), higher_error=str(b),
                           permitted_higher_error=str(bound),
                           ratio=str(b/a) if a else None,
                           excess=str(b/bound) if bound else None,
                           units="J/s" if metric == "energy_slope" else
                           "J" if metric.startswith("energy") else
                           "m" if metric.startswith("position") else "kg*m/s",
                           ratio_units="dimensionless", ratio_gate_pass=passed,
                           physical_budget=report["physical_budgets"][metric],
                           sign_and_argmax_status="not exported by parent summary",
                           cause="unresolved")
                if scenario == "k4_internal" and metric in ("energy_final", "energy_slope"):
                    field = ("final_energy_representation_error" if metric == "energy_final"
                             else "energy_representation_least_squares_slope")
                    signed = [source["long_run"]["runs"][f"B{p}:L{level}"][field]
                              for p in (192, 256)]
                    assert [abs(Q(x)) for x in signed] == [a, b]
                    row.update(signed_lower_error=signed[0], signed_higher_error=signed[1],
                               sign_and_argmax_status="signed scalar exported; sample contributions need targeted replay")
                if report["anchor_required"] and not passed:
                    failures.append((int(level), scenario, metric))
                rows.append(row)
    assert sorted(failures) == [(1, "k4_internal", "position_final"),
                               (2, "k4_internal", "energy_final"),
                               (3, "k4_internal", "energy_slope")]
    structure=source['composition_contracts']['structure_residuals']
    reversal=structure['envelopes']['reversal_position']
    reversal_ratio=Q(reversal['256'])/Q(reversal['192'])
    assert reversal_ratio/(4*Q(1,2**64))==Q(1024,9)
    assert structure['scaling_until_budget']['reversal_position']
    return dict(schema="mls.bounded-phase-tail.stage-one.v1", parent=PARENT,
                parent_summary_sha256=SUMMARY_HASH, promotion="NO_PROMOTION",
                stage_one_complete=False, comparisons=rows, exact_controls=controls(),
                signed_sum_controls=signed_sum_controls(),
                parent_prefix_energy_certificates=source['long_run']['exact_prefix_energy_componentwise_certificates'],
                nongating_reversal=dict(envelopes=reversal,ratio=str(reversal_ratio),
                    excess='1024/9',gating=False,ordinary_registered_gate_pass=True,
                    bit_exact_reversal=False),
                limitations=["Signed position argmax and per-sample slope contributions require targeted prefix replay.",
                             "Parent inward witnesses are retrospective, not unconditional tail enclosures.",
                             "No cancellation diagnosis or full-tail certification follows from this extraction."])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.summary), sort_keys=True, indent=2))
