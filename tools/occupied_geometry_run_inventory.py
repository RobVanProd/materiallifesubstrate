"""Controller-only exact run/view inventory. Does not seal or evaluate inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


NAMES = ('vertices', 'tetrahedra', 'facets', 'incidence', 'samples', 'resolution')


def run(root, preflight, output):
    assert not output.exists()
    storage = json.loads(preflight.read_text())
    blobs = {v['source']: key for key, v in storage['files'].items()}
    # Source aliases with identical content are legitimate input deduplication.
    def blob(path):
        rel = path.relative_to(root).as_posix()
        if rel in blobs:
            return blobs[rel]
        with path.open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        key = 'candidate/' + digest
        assert key in storage['files'] and storage['files'][key]['size'] == path.stat().st_size
        blobs[rel] = key
        return key

    def read(name):
        return json.loads((root / name).read_text())

    def identity(value):
        return {key: value[key] for key in ('records', 'size', 'sha256')}

    empty = b'MLSOMG01' + struct.pack('<IIQ', 1, 7, 0)
    empty_identity = dict(records=0, size=len(empty), sha256=hashlib.sha256(empty).hexdigest())
    joins = {(r['fixture'], r['variant']): r for r in read('final-query-joins-v1.json')['streams']}
    i1orders = {(r['fixture'], r['level'], r['variant']): r['stream']
                for r in read('i1-motion-orders-v1.json')['streams']}
    rows = []
    for f in range(1, 8):
        queries = read(f'query-factoring-f{f}.json')['streams']
        for k in range(5):
            name = {1: f'cube-k{k}', 2: f'slab-k{k}', 3: f'sphere-d{k+1}',
                    4: f'pair-d{k+1}', 5: f'pair-d{k+1}',
                    6: f'sphere-d{k+1}', 7: f'u-k{k}'}[f]
            decoded_name = f'plane-d{k+1}' if f == 6 else name
            globals_ = read(f'decoded-{decoded_name}.json')['variants']
            orders = read(f'orders-f{f}-k{k}.json')['variants']
            motion = {5: f'motion-pair-d{k+1}', 6: f'motion-plane-d{k+1}',
                      7: f'motion-u-k{k}'}.get(f)
            mg = read(f'decoded-{motion}.json')['variants'] if motion else None
            mi = read(f'decoded-i1-{motion}.json')['variants'] if motion else None
            source = {str(i+1): blob(root/name/'candidate'/f'{n}.bin')
                      for i, n in enumerate(NAMES)}
            if motion:
                source['7'] = blob(root/motion/'motion.bin')
            source['8'] = blob(root/f'queries-f{f}/candidate/queries-00.bin')
            for v in range(33):
                files = globals_[v]['files'] if v < 30 else orders[v-30]['files']
                b = {str(kind): identity(files[str(kind)]) for kind in range(1, 7)}
                if motion:
                    b['7'] = identity(mg[v]['files']['7'] if v < 30 else files['7'])
                    i1motion = identity(mi[v]['files']['7'] if v < 30 else i1orders[f, k, v])
                else:
                    b['7'] = dict(empty_identity)
                    i1motion = dict(empty_identity)
                b['8'] = (dict(records=queries[v]['records'], **queries[v]['query'])
                          if v < 30 else identity(files['8']))
                a = {key: b[key] for key in ('5', '6', '8')}
                a['7'] = i1motion
                assert a['5']['records'] == b['2']['records']
                recipe = dict(fixture=f, level=k, variant=v, source_blobs=source,
                    transform=blob(root/f'queries-f{f}/candidate/transform-{v:02}.bin'),
                    base_pose=(blob(root/f'plane-d{k+1}/base-pose.bin') if f == 6 else None),
                    order=('canonical' if v < 30 else ('reverse', 'shuffle', 'relabel')[v-30]),
                    seed_rule='260908 XOR (kind << 32) XOR (fixture << 16) XOR (level << 8)',
                    I1_motion_projection='target_kind_5_only_then_renumber_before_transform_and_order',
                    static_motion='empty_kind_7_no_time_advance' if not motion else None,
                    views={'I1': a, 'I2': b}, oracle_join=identity(joins[f, v]))
                rows.append(recipe)
    assert len(rows) == 1155
    result = dict(schema='mls.occupied-geometry.controller-run-inventory.v1',
        candidate_evaluations=0, complete_input_seal=False,
        candidate_access='decoded_view_only_no_recipe_no_oracle_no_generator',
        empty_motion_wire_hex=empty.hex(), runs=rows)
    output.write_text(json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n')
    print(json.dumps(dict(runs=len(rows), views=2*len(rows), candidate_evaluations=0,
                         complete_input_seal=False, size=output.stat().st_size)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('preflight', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    run(args.root, args.preflight, args.output)
