"""Build altered executables in an isolated evidence directory, never edit kernel."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True

def run(compiler,boost,parent,out):
    out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    text=(repo/'src/authoritative_mechanics_kernel_parity_lab.cpp').read_text()
    mutations={
        'toward_zero':('if (2 * r > y.denominator() ||\n      (2 * r == y.denominator() && static_cast<bool>(n & 1)))','if (false)'),
        'wrong_precision':('Q z = rounded(x, 96);','Q z = rounded(x, 95);'),
        'wrong_endpoint_sign':('pj.p[a] = rn(oldj[a] - impulse[a]);','pj.p[a] = rn(oldj[a] + impulse[a]);'),
        'omitted_kick':('pi.p[a] = rn(oldi[a] + impulse[a]);','pi.p[a] = rn(oldi[a]);'),
        'ignored_chord':('if (!info.safe)','if (false)'),
        'partial_commit':('s = old;','/* mutation: retain the partial state */'),
        'incompatible_force_bits':('g.length = norm(g.si);','g.length = std::nextafter(norm(g.si), 1.0);'),
    }
    results=[]
    for name,(before,after) in mutations.items():
        assert before in text,name
        source=out/(name+'.cpp');source.write_text(text.replace(before,after,1))
        exe=out/name
        cmd=[compiler,'-std=c++20','-O2','-ffp-contract=off','-fno-fast-math','-I'+str(repo/'include'),'-I'+str(boost),str(source),str(repo/'apps/authoritative_mechanics_kernel_parity.cpp'),'-o',str(exe)]
        with (out/(name+'-build.log')).open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
        with (out/(name+'-test.log')).open('w') as log:
            result=subprocess.run([sys.executable,str(repo/'tests/kernel_parity_test.py'),str(exe),str(parent),str(out/(name+'-evidence'))],stdout=log,stderr=subprocess.STDOUT)
        assert result.returncode!=0,('mutant survived',name)
        results.append(dict(name=name,rejected=True,exit_code=result.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
        print(name+' MUTATION REJECTED',flush=True)
    (out/'result.json').write_text(json.dumps(dict(status='PASS',mutations=results),sort_keys=True)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('compiler');p.add_argument('boost',type=Path);p.add_argument('parent',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.compiler,a.boost.resolve(),a.parent.resolve(),a.output.resolve())
