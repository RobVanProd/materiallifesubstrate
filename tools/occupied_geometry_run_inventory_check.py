"""Independent controller inventory audit against native stream receipts.

Does not import the inventory constructor or grant the candidate data gate.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def check(root, value, storage):
    def read(path):
        return json.loads((root/path).read_text())
    native = {}
    for group in ('cartesian', 'other'):
        receipt = read(f'native-{group}-v1.json')
        assert receipt['status'] == 'PASS' and not receipt['pending']
        for row in receipt['datasets']:
            assert row['dataset'] not in native
            native[row['dataset']] = row['variants']
    assert len(native) == 60
    order = {}
    for group in ('cartesian', 'other'):
        receipt = read(f'native-orders-{group}-v1.json')
        assert receipt['status'] == 'PASS'
        for row in receipt['rows']:
            for s in row['streams']:
                key = (row['fixture'], row['level'], s['variant'], s['kind'], s.get('tier', 'I2'))
                assert key not in order
                order[key] = {k: s[k] for k in ('records', 'size', 'sha256')}
    def bytes_identity(path):
        raw = path.read_bytes()
        return dict(records=int.from_bytes(raw[16:24], 'little'), size=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest())
    assert value['candidate_access'] == 'decoded_view_only_no_recipe_no_oracle_no_generator'
    assert value['candidate_evaluations'] == 0 and value['complete_input_seal'] is False
    runs = value['runs']
    assert len(runs) == 7*5*33
    keys = [(r['fixture'], r['level'], r['variant']) for r in runs]
    assert keys == [(f,k,v) for f in range(1,8) for k in range(5) for v in range(33)]
    empty = b'MLSOMG01\x01\x00\x00\x00\x07\x00\x00\x00' + bytes(8)
    assert value['empty_motion_wire_hex'] == empty.hex()
    empty_id = dict(records=0, size=24, sha256=hashlib.sha256(empty).hexdigest())
    comparisons = 0
    for r in runs:
        f,k,v = r['fixture'],r['level'],r['variant']
        dataset = (f'cube-k{k}', f'slab-k{k}', f'sphere-d{k+1}',
                   f'pair-d{k+1}', f'pair-d{k+1}', f'plane-d{k+1}', f'u-k{k}')[f-1]
        base = f'sphere-d{k+1}' if f == 6 else dataset
        motion = None if f < 5 else (f'motion-pair-d{k+1}', f'motion-plane-d{k+1}', f'motion-u-k{k}')[f-5]
        for key in list(r['source_blobs'].values()) + [r['transform']] + ([r['base_pose']] if r['base_pose'] else []):
            assert key.startswith('candidate/') and key in storage['files']
        for kind, name in enumerate(('vertices','tetrahedra','facets','incidence','samples','resolution'),1):
            # Check sources independently against their raw base file identity.
            source=root/base/'candidate'/f'{name}.bin'
            # Avoid repeatedly reading the large base tables: globals receipts
            # contain their independently authenticated base identities.
            source_identity=read(f'decoded-{base}.json')['source_files'][str(kind)]
            assert r['source_blobs'][str(kind)] == 'candidate/'+source_identity['sha256']
            assert storage['files'][r['source_blobs'][str(kind)]]['size']==source_identity['size']
            if v >= 30:
                expected=order[f,k,v,kind,'I2']
            elif kind in (2,3,4):
                expected=source_identity
            else:
                expected=native[dataset][v]['files'][str(kind)]
            assert r['views']['I2'][str(kind)]==expected,(f,k,v,kind)
            comparisons+=1
        for tier in ('I1','I2'):
            view=r['views'][tier]
            assert set(view)==(set(('5','6','7','8')) if tier=='I1' else set(map(str,range(1,9))))
            if motion:
                if v<30:
                    expected=native[('i1-' if tier=='I1' else '')+motion][v]['files']['7']
                else:
                    expected=order[f,k,v,7,tier]
            else:
                expected=empty_id
            assert view['7']==expected,(f,k,v,tier,'motion')
            if v>=30:
                expected=order[f,k,v,8,'I2']
            else:
                expected=bytes_identity(root/f'queries-f{f}/candidate/queries-{v:02}.bin')
            assert view['8']==expected
            comparisons+=2
        assert r['views']['I1']['5']==r['views']['I2']['5']
        assert r['views']['I1']['6']==r['views']['I2']['6']
        assert r['I1_motion_projection']=='target_kind_5_only_then_renumber_before_transform_and_order'
        assert r['seed_rule']=='260908 XOR (kind << 32) XOR (fixture << 16) XOR (level << 8)'
        assert r['order']==('canonical' if v<30 else ('reverse','shuffle','relabel')[v-30])
        descriptor=bytes_identity(root/f'queries-f{f}/candidate/transform-{v:02}.bin')
        assert r['transform']=='candidate/'+descriptor['sha256']
        if f==6:
            assert r['base_pose']=='candidate/'+bytes_identity(root/f'plane-d{k+1}/base-pose.bin')['sha256']
        else:
            assert r['base_pose'] is None
        oracle=[json.loads(line) for line in (root/f'queries-f{f}/oracle/queries-{v:02}.jsonl').read_text().splitlines()]
        if v==32:
            oracle=[dict(query=i+1,obligations=row['obligations']) for i,row in enumerate(reversed(oracle))]
        encoded=b''.join((json.dumps(row,sort_keys=True)+'\n').encode('ascii') for row in oracle)
        assert r['oracle_join']==dict(records=len(oracle),size=len(encoded),sha256=hashlib.sha256(encoded).hexdigest())
    return comparisons


def run(root, inventory, preflight, output):
    assert not output.exists()
    value=json.loads(inventory.read_text());storage=json.loads(preflight.read_text())
    comparisons=check(root,value,storage)
    # Mutate distinct closure surfaces; a parser/compile failure is not involved.
    mutations=[]
    for name in ('missing_run','I1_vertex_leak','changed_digest','wrong_seed','wrong_pose','wrong_join'):
        bad=copy.deepcopy(value)
        if name=='missing_run':bad['runs'].pop()
        elif name=='I1_vertex_leak':bad['runs'][0]['views']['I1']['1']=bad['runs'][0]['views']['I2']['1']
        elif name=='changed_digest':bad['runs'][0]['views']['I2']['1']['sha256']='0'*64
        elif name=='wrong_seed':bad['runs'][0]['seed_rule']='260909'
        elif name=='wrong_pose':bad['runs'][0]['base_pose']=bad['runs'][0]['transform']
        else:bad['runs'][0]['oracle_join']['sha256']='0'*64
        try:check(root,bad,storage)
        except AssertionError:mutations.append(name)
        else:raise AssertionError(('mutation survived',name))
    result=dict(status='PASS',runs=1155,views=2310,stream_comparisons=comparisons,
                rejected_mutations=mutations,candidate_evaluations=0,complete_input_seal=False)
    output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('root','inventory','preflight','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.root,a.inventory,a.preflight,a.output)
