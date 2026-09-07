"""Portable CI entry: authenticate public parent and pinned header dependency."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
sys.dont_write_bytecode=True

PARENT_HASH='113daf203bfcbc93dbd54cfe013a942aa6f75ac658c288254afef9b0fbeabcc0'
BOOST_HASH='6478edfe2f3305127cffe8caf73ea0176c53769f4bf1585be237eb30798c3b8e'

def fetch(url,path,sha,size=None):
    if not path.exists():
        with urllib.request.urlopen(url) as inp,path.open('xb') as out:
            while block:=inp.read(1024*1024):out.write(block)
    with path.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==sha
    if size is not None:assert path.stat().st_size==size

def prepare(root):
    root.mkdir(parents=True,exist_ok=True)
    boost=root/'boost.tar.bz2';parent=root/'parent.tar.gz'
    fetch('https://archives.boost.io/release/1.83.0/source/boost_1_83_0.tar.bz2',boost,BOOST_HASH)
    fetch('https://github.com/RobVanProd/materiallifesubstrate/releases/download/bounded-integrator-bakeoff-lab-evidence-v1/bounded-integrator-bakeoff-evidence-v1.tar.gz',parent,PARENT_HASH,576118316)
    for archive,directory in ((boost,'boost_1_83_0'),(parent,'bounded-integrator-bakeoff-evidence-v1')):
        if not (root/directory).exists():
            with tarfile.open(archive) as tar:tar.extractall(root,filter='data')
    (root/'dependencies.json').write_text(json.dumps(dict(boost=BOOST_HASH,parent=PARENT_HASH),sort_keys=True)+'\n')

def run(exe,root,out):
    out.mkdir(parents=True,exist_ok=False);parent=root/'bounded-integrator-bakeoff-evidence-v1'
    commands=[['tests/kernel_parity_test.py',str(exe),str(parent),str(out/'tests')],
              ['tools/run_authoritative_mechanics_kernel_parity.py',str(exe),str(parent),str(out/'full')],
              ['tools/kernel_parity_controls.py','controls',str(exe),str(parent),str(out/'controls')],
              ['tools/kernel_parity_controls.py','replay',str(exe),str(parent),str(out/'replay'),'--full',str(out/'full')]]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    for i,cmd in enumerate(commands):
        with (out/f'command-{i}.log').open('w') as log:subprocess.run([sys.executable,*cmd],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    # Small complete comparison inventory for durable CI artifacts; full logs
    # and raw inputs/outputs remain available during each run.
    summary={}
    for name,path in [('tests','tests/tests.json'),('full','full/inventory.json'),('controls','controls/controls.json'),('replay','replay/replay.json')]:summary[name]=json.loads((out/path).read_text())
    summary['source_sha']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    summary['status']='PASS';summary['promotion']='NO_PROMOTION'
    (out/'result.json').write_text(json.dumps(summary,sort_keys=True)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);p.add_argument('root',type=Path);p.add_argument('--executable',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.mode=='prepare':prepare(a.root.resolve())
    else:run(a.executable.resolve(),a.root.resolve(),a.output.resolve())
