"""Close oracle-only query joins after the registered query-ID permutation.

This reads only preserved input artifacts; it never evaluates a geometry
candidate. The oracle join remains a controller artifact, not candidate input.
"""
import argparse
import hashlib
import json
from pathlib import Path


def run(root, output):
    assert not output.exists()
    streams = []
    for fixture in range(1, 8):
        receipts = json.loads((root / f'query-factoring-f{fixture}.json').read_text())
        for variant in range(33):
            source = root / f'queries-f{fixture}/oracle/queries-{variant:02}.jsonl'
            raw = source.read_bytes()
            rows = [json.loads(line) for line in raw.splitlines()]
            expected = receipts['streams'][variant]
            assert len(rows) == expected['records']
            assert hashlib.sha256(raw).hexdigest() == expected['oracle_join']['sha256']
            assert len(raw) == expected['oracle_join']['size']
            assert [r['query'] for r in rows] == list(range(1, len(rows) + 1))
            if variant == 32:
                # Reverse IDs, then canonicalize the oracle lookup by new ID.
                transformed = [dict(query=len(rows) + 1 - r['query'],
                                    obligations=r['obligations']) for r in rows]
                transformed.sort(key=lambda r: r['query'])
                encoded = b''.join((json.dumps(r, sort_keys=True) + '\n').encode('ascii')
                                   for r in transformed)
                # Independent inverse-ID lookup, without transformed-row sorting.
                inverse = {r['query']: r['obligations'] for r in rows}
                for new, line in enumerate(encoded.splitlines(), 1):
                    decoded = json.loads(line)
                    assert decoded == dict(query=new,
                        obligations=inverse[len(rows) + 1 - new])
            else:
                encoded = raw
            streams.append(dict(fixture=fixture, variant=variant,
                records=len(rows), size=len(encoded),
                sha256=hashlib.sha256(encoded).hexdigest(),
                rule='reverse_query_ids_then_sort' if variant == 32 else 'identity'))
    result = dict(schema='mls.occupied-geometry.final-query-joins.v1', status='PASS',
                  streams=streams, candidate_evaluations=0, complete_input_seal=False)
    output.write_text(json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n')
    print(json.dumps(dict(status='PASS', streams=len(streams), candidate_evaluations=0)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    run(args.root, args.output)
