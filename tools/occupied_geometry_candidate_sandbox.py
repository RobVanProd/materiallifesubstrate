"""Controller-only isolated Candidate C pilot launcher; no full-row claim."""
import argparse
import hashlib
import importlib.util
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys


def run(view,output):
    assert not output.exists();output.mkdir(parents=True)
    base=Path(sys.base_prefix).resolve()
    site=Path(importlib.util.find_spec('gmpy2').origin).parent.parent
    version=importlib.metadata.version('gmpy2');assert version=='2.3.1'
    code=Path(__file__).resolve().parent
    sources=('occupied_geometry_candidate_c_pilot.py','occupied_geometry_runtime_wire.py')
    command=['bwrap','--unshare-all','--die-with-parent','--clearenv',
        '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin',
        '--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64',
        '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
        '--ro-bind',str(base),'/py',
        '--ro-bind',str(site/'gmpy2'),'/deps/gmpy2',
        '--ro-bind',str(site/'gmpy2.libs'),'/deps/gmpy2.libs',
        '--ro-bind',str(site/f'gmpy2-{version}.dist-info'),f'/deps/gmpy2-{version}.dist-info',
        '--ro-bind',str(view.resolve()),'/input',
        '--setenv','PYTHONPATH','/code:/deps',
        '--setenv','PYTHONDONTWRITEBYTECODE','1','--chdir','/input']
    for name in sources:command+=['--ro-bind',str(code/name),'/code/'+name]
    probe="import os; assert not os.path.exists('/oracle'); assert not os.path.exists('/control'); assert not os.path.exists('/home/lsd/Documents/ChatGPT/MLS'); print('oracle/control/repository unavailable')"
    checked=subprocess.run(command+['/py/bin/python3.13','-c',probe],capture_output=True,timeout=30)
    (output/'isolation-probe.stdout').write_bytes(checked.stdout)
    (output/'isolation-probe.stderr').write_bytes(checked.stderr)
    assert checked.returncode==0,checked.stderr.decode()
    streams=[]
    for index in range(2):
        result=subprocess.run(command+['/py/bin/python3.13','/code/'+sources[0],'/input'],
                              capture_output=True,timeout=1800)
        (output/f'twin-{index}.json').write_bytes(result.stdout)
        (output/f'twin-{index}.stderr').write_bytes(result.stderr)
        assert result.returncode==0,result.stderr.decode()
        assert json.loads(result.stdout)['complete_row'] is False
        streams.append(result.stdout)
    assert streams[0]==streams[1]
    receipt=dict(status='PASS_ISOLATED_PILOT_TWINS',candidate_evaluations=2,
        complete_row=False,complete_lab=False,
        candidate_result_sha256=hashlib.sha256(streams[0]).hexdigest(),
        runtime_sources={name:hashlib.sha256((code/name).read_bytes()).hexdigest() for name in sources},
        namespace='no repository/oracle/control mounts; network namespace isolated',
        promotion='NO_PROMOTION')
    (output/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('view',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.view,a.output)
