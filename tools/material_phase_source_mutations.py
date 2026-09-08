"""Compiled ownership mutants; compilation failures never count as rejection."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True

def run(repo,build,boost,parent,out):
    out.mkdir(parents=True,exist_ok=False);source=(repo/'src/world_material_phase_lab.cpp').read_text()
    anchor='  staged.material_phase_ = std::move(c);'
    mutations={
        'swapped_identity':(anchor,anchor+'\n  std::swap(staged.material_phase_->binding[0].material, staged.material_phase_->binding[1].material);'),
        'stale_binding':(anchor,anchor+'\n  ++staged.material_phase_->binding[0].material.generation;'),
        'incorrect_mass':('    p.mass = mass_of(p.composition, compounds_, elements_);','    p.mass = mass_of(p.composition, compounds_, elements_) + Mass::from_raw(1);'),
        'duplicate_phase_authority':('  c.schedule.wire.clear();','  c.schedule.wire = input.wire;'),
        'legacy_coordinate_feedback':('      material.phase = packets[j].phase;','      material.phase = packets[j].phase;\n      for (std::size_t axis=0;axis<3;++axis) { std::fill_n(material.phase.begin()+static_cast<std::ptrdiff_t>(17*axis),17,0); material.phase[17*axis+1]=96; }'),
        'omitted_phase_state':("    records << hex(p.phase) << '\\n';","    records << \"00\" << '\\n';"),
        'observer_feedback':('ResearchMechanicsSnapshot World::material_phase_mechanics() const {','ResearchMechanicsSnapshot World::material_phase_mechanics() const {\n  const_cast<World*>(this)->packets_.material_phase_.begin()->second.phase[16] ^= 1;'),
        'corrupted_binding':(anchor,anchor+'\n  staged.material_phase_->binding[1].mechanics_id=staged.material_phase_->binding[0].mechanics_id;'),
    }
    rows=[]
    for name,(old,new) in mutations.items():
        assert source.count(old)==1,(name,'mutation target drift')
        directory=out/name;directory.mkdir();mutant=directory/'mutant.cpp';mutant.write_text(source.replace(old,new));obj=directory/'mutant.o';exe=directory/'mutant'
        commands=[['c++','-std=c++20','-O2','-DMLS_RESEARCH_WORLD_MECHANICS=1','-DMLS_RESEARCH_MATERIAL_PHASE=1','-I'+str(repo/'include'),'-I'+str(boost),'-c',str(mutant),'-o',str(obj)],
            ['c++',str(build/'CMakeFiles/mls_material_phase_lab.dir/apps/world_material_phase_lab.cpp.o'),str(obj),str(build/'libmls_material_phase_core.a'),str(build/'libmls_kernel_parity.a'),'-o',str(exe)]]
        with (directory/'compile.log').open('w') as log:
            for cmd in commands:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
        inp=parent/'parent/evidence/gcc/full/short-k4_internal-L0-bounded_binary_kick_drift_kick.input'
        with (directory/'test.log').open('w') as log:r=subprocess.run([str(exe),'--research-material-phase','contracts',str(inp),str(directory/'output.json')],stdout=log,stderr=subprocess.STDOUT)
        assert r.returncode!=0,('compiled material mutant escaped',name)
        rows.append(dict(name=name,rejected=True,exit_code=r.returncode,source_sha256=hashlib.sha256(mutant.read_bytes()).hexdigest()));print('REJECTED',name,flush=True)
    (out/'result.json').write_text(json.dumps(dict(status='PASS',mutations=rows),sort_keys=True)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('repo','build','boost','parent','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.repo.resolve(),a.build.resolve(),a.boost.resolve(),a.parent.resolve(),a.output.resolve())
