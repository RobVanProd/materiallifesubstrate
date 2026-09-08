"""Pinned public parent and offline dependency inputs for material unification."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile
sys.dont_write_bytecode=True
import kernel_parity_ci as k
import material_phase_parity as m
import world_mechanics_parity as w

def prepare(root):
    root.mkdir(parents=True,exist_ok=True);archive=root/'parent.tar.gz'
    k.fetch('https://github.com/RobVanProd/materiallifesubstrate/releases/download/authoritative-world-mechanics-integration-lab-evidence-v1/authoritative-world-mechanics-integration-evidence-v1.tar.gz',archive,m.ARCHIVE,m.SIZE)
    parent=root/'authoritative-world-mechanics-integration-evidence-v1'
    if not parent.exists():
        with tarfile.open(archive) as t:t.extractall(root,filter='data')
    boost=parent/'parent/dependencies/boost_1_83_0.tar.bz2';assert w.digest(boost)==k.BOOST_HASH
    if not (root/'boost_1_83_0').exists():
        with tarfile.open(boost) as t:t.extractall(root,filter='data')
    (root/'dependencies.json').write_text(json.dumps(dict(parent=m.ARCHIVE,boost=k.BOOST_HASH),sort_keys=True)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);p.add_argument('root',type=Path);p.add_argument('--executable',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.mode=='prepare':prepare(a.root.resolve())
    else:
        m.run(a.executable.resolve(),a.root.resolve()/'authoritative-world-mechanics-integration-evidence-v1',a.output.resolve(),Path(__file__).resolve().parents[1])
        subprocess.run([sys.executable,'tests/material_phase_inventory_test.py',str(a.output/'result.json')],check=True)
        subprocess.run([sys.executable,'tests/material_phase_checkpoint_test.py',str(a.output),str(a.root/'authoritative-world-mechanics-integration-evidence-v1')],check=True)
