"""Pinned public parent/dependency preparation for the research World target."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile
sys.dont_write_bytecode=True
import kernel_parity_ci as k
import world_mechanics_parity as w

def prepare(root):
    root.mkdir(parents=True,exist_ok=True)
    archive=root/'parent.tar.gz'
    k.fetch('https://github.com/RobVanProd/materiallifesubstrate/releases/download/authoritative-mechanics-kernel-parity-lab-evidence-v1/authoritative-mechanics-kernel-parity-evidence-v1.tar.gz',archive,w.ARCHIVE,817038443)
    parent=root/'authoritative-mechanics-kernel-parity-evidence-v1'
    if not parent.exists():
        with tarfile.open(archive) as t:t.extractall(root,filter='data')
    boost=parent/'dependencies/boost_1_83_0.tar.bz2'
    assert w.digest(boost)==k.BOOST_HASH
    if not (root/'boost_1_83_0').exists():
        with tarfile.open(boost) as t:t.extractall(root,filter='data')
    (root/'dependencies.json').write_text(json.dumps(dict(parent=w.ARCHIVE,boost=k.BOOST_HASH),sort_keys=True)+'\n')
def run(exe,root,out):
    parent=root/'authoritative-mechanics-kernel-parity-evidence-v1'
    w.run(exe,parent,out,Path(__file__).resolve().parents[1])
    w.report_check(json.loads((out/'result.json').read_text()))
    with (out/'inventory-mutations.log').open('w') as log:
        subprocess.run([sys.executable,'tests/world_mechanics_inventory_test.py',str(out/'result.json')],stdout=log,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);p.add_argument('root',type=Path);p.add_argument('--executable',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.mode=='prepare':prepare(a.root.resolve())
    else:run(a.executable.resolve(),a.root.resolve(),a.output.resolve())
