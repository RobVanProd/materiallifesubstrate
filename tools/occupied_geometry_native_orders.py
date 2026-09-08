"""Independent native audit of every decoded order/ID stream, including I1 views."""
import argparse
import json
from pathlib import Path
import resource
import subprocess
import time

from occupied_geometry_input_check import Reader


NAMES=('vertices','tetrahedra','facets','incidence','samples','resolution')


def run(root,exe,group,out):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));assert not out.exists();results=[]
    fixtures=(1,2) if group=='cartesian' else (3,4,5,6,7)
    for f in fixtures:
        for k in range(5):
            start=time.monotonic()
            name={1:f'cube-k{k}',2:f'slab-k{k}',3:f'sphere-d{k+1}',4:f'pair-d{k+1}',5:f'pair-d{k+1}',6:f'sphere-d{k+1}',7:f'u-k{k}'}[f]
            paths={i+1:root/name/'candidate'/f'{n}.bin' for i,n in enumerate(NAMES)}
            if f==6:
                for kind in (1,5):paths[kind]=root/f'plane-d{k+1}/candidate'/f'{NAMES[kind-1]}.bin'
            motion={5:f'motion-pair-d{k+1}',6:f'motion-plane-d{k+1}',7:f'motion-u-k{k}'}
            if f in motion:paths[7]=root/motion[f]/'motion.bin'
            paths[8]=root/f'queries-f{f}/candidate/queries-30.bin'
            assert paths[8].read_bytes()==(root/f'queries-f{f}/candidate/queries-31.bin').read_bytes()==(root/f'queries-f{f}/candidate/queries-32.bin').read_bytes()
            counts={}
            for kind,path in paths.items():
                r=Reader(path,kind);counts[kind]=r.count;r.f.close()
            expected=json.loads((root/f'orders-f{f}-k{k}.json').read_text())
            streams=[]
            for kind,path in paths.items():
                seed=260908^(kind<<32)^(f<<16)^(k<<8)
                command=[str(exe.resolve()),str(path),str(seed)]+[str(counts[n]) for n in (1,2,3,5)]
                p=subprocess.run(command,text=True,capture_output=True,check=True,timeout=1800)
                lines=p.stdout.splitlines();assert len(lines)==3
                for index,line in enumerate(lines):
                    variant,actual_kind,n,size,sha=line.split()
                    assert int(variant)==30+index and int(actual_kind)==kind and int(n)==counts[kind]
                    value=dict(records=int(n),size=int(size),sha256=sha)
                    wanted=expected['variants'][index]['files'][str(kind)]
                    assert value=={key:wanted[key] for key in value},('independent order mismatch',f,k,variant,kind)
                    streams.append(dict(variant=int(variant),kind=kind,**value))
                print('independent order table',f,k,kind,flush=True)
                assert time.monotonic()-start<=1800,('native order input row ceiling',f,k)
            if f in motion:
                i1=root/f'i1-{motion[f]}'/'motion.bin';r=Reader(i1,7);n=r.count;r.f.close()
                seed=260908^(7<<32)^(f<<16)^(k<<8)
                command=[str(exe.resolve()),str(i1),str(seed),'0','0','0',str(n)]
                p=subprocess.run(command,text=True,capture_output=True,check=True,timeout=1800)
                all_expected=json.loads((root/'i1-motion-orders-v1.json').read_text())['streams']
                for line in p.stdout.splitlines():
                    variant,kind,count,size,sha=line.split();assert kind=='7' and int(count)==n
                    wanted=next(x['stream'] for x in all_expected if (x['fixture'],x['level'],x['variant'])==(f,k,int(variant)))
                    value=dict(records=n,size=int(size),sha256=sha)
                    assert value=={key:wanted[key] for key in value}
                    streams.append(dict(variant=int(variant),kind=7,tier='I1',**value))
            results.append(dict(fixture=f,level=k,streams=streams))
    payload=dict(status='PASS',schema='mls.occupied-geometry.native-order-audit.v1',
        rows=results,candidate_evaluations=0,complete_input_seal=False)
    out.write_text(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status='PASS',rows=len(results),candidate_evaluations=0,complete_input_seal=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('executable',type=Path)
    p.add_argument('--group',choices=('cartesian','other'),required=True);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.root,a.executable,a.group,a.output)
