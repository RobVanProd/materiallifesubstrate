"""Compile incorrect World adapters and require ownership/parity rejection."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True

def run(repo,build,parent,out):
    out.mkdir(parents=True,exist_ok=False)
    source=(repo/'src/world_mechanics_integration_lab.cpp').read_text()
    mutations={
      'omitted_transition':('research_kernel_request(r, 1)','research_kernel_request(r, 0)'),
      'double_transition':('research_kernel_request(r, 1)','research_kernel_request(r, 2)'),
      'legacy_double_drift':('    r.wire = wire;','    staged.packets_.advance_positions_one_timestep(staged.config_.physical_timestep, staged.config_.momentum_mass_to_velocity_scale, staged.tick_+1);\n    r.wire = wire;'),
      'premature_clock':('  auto staged = *this;\n  std::string committed;','  ++tick_;\n  auto staged = *this;\n  std::string committed;'),
      'failed_step_commit':('      throw ResearchMechanicsRejection(body);','      { *this=staged; ++tick_; throw ResearchMechanicsRejection(body); }'),
      'checkpoint_omission':('field(out, research_kernel_request(r, 0));','field(out, std::string());'),
      'changed_packet_id':('    r.wire = wire;','    r.wire = wire; r.wire[104] = \'2\';'),
      'changed_phase_payload':('    r.wire = wire;','    r.wire = wire; r.wire[169] = r.wire[169] == \'1\' ? \'0\' : \'1\';'),
      'observer_feedback':('  return s; // A copy;','  const_cast<World*>(this)->research_mechanics_->request.wire[104] = \'2\';\n  return s; // A copy;'),
    }
    rows=[]
    for name,(old,new) in mutations.items():
        assert source.count(old)==1,(name,'mutation target drift')
        directory=out/name;directory.mkdir();mutant=directory/'mutant.cpp';mutant.write_text(source.replace(old,new))
        obj=directory/'mutant.o';exe=directory/'mutant'
        commands=[['c++','-std=c++20','-O2','-DMLS_RESEARCH_WORLD_MECHANICS=1','-I'+str(repo/'include'),'-c',str(mutant),'-o',str(obj)],
                  ['c++',str(build/'CMakeFiles/mls_world_mechanics_lab.dir/apps/world_mechanics_integration_lab.cpp.o'),str(obj),str(build/'libmls_world_research_core.a'),str(build/'libmls_kernel_parity.a'),'-o',str(exe)]]
        with (directory/'compile.log').open('w') as log:
            for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        inp=parent/'evidence/gcc/tests/atomic-domain.input' if name in ('premature_clock','failed_step_commit') else parent/'evidence/gcc/full/short-k4_internal-L0-bounded_binary_kick_drift_kick.input'
        with (directory/'test.log').open('w') as log:r=subprocess.run([str(exe),'--research-world-mechanics','contracts',str(inp),str(directory/'output.json')],stdout=log,stderr=subprocess.STDOUT)
        assert r.returncode!=0,('World source mutant escaped',name)
        rows.append(dict(name=name,rejected=True,exit_code=r.returncode,source_sha256=hashlib.sha256(mutant.read_bytes()).hexdigest()))
        print('REJECTED',name,flush=True)
    (out/'result.json').write_text(json.dumps(dict(status='PASS',mutations=rows),sort_keys=True)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('repo','build','parent','output'):p.add_argument(n,type=Path)
    a=p.parse_args();run(a.repo.resolve(),a.build.resolve(),a.parent.resolve(),a.output.resolve())
