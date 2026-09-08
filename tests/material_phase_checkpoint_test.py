"""Exact independent checkpoint corruption controls with recomputed checksums."""
import json
from pathlib import Path
import struct
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import material_phase_checkpoint as c
evidence,parent=map(Path,sys.argv[1:3]);name='short-k4_internal-L0-bounded_binary_kick_drift_kick'
header=(parent/'parent/evidence/gcc/full'/(name+'.input')).read_text().splitlines()[0].split()
step=int(header[5])+max(1,int(header[4])//2-1);dt=int(header[3])
wire=next(line.split()[2] for line in (parent/'evidence/gcc'/(name+'.output')).read_text().splitlines() if line.startswith(f'S {step} '))
original=(evidence/(name+'.neutral-checkpoint')).read_bytes();c.check(original,wire,step,dt,True)
magic=b'MLS-MATERIAL-PHASE-v1\n';pos=len(magic);fields=[]
for _ in range(4):
    n=int.from_bytes(original[pos:pos+8],'little');pos+=8;fields.append(original[pos:pos+n]);pos+=n
def rebuild(values):
    b=magic+b''.join(struct.pack('<Q',len(v))+v for v in values);return b+struct.pack('<Q',c.fnv(b))
mutations={
 'mass':lambda t:t.__setitem__(9,str(int(t[9])+1)),
 'stale_generation':lambda t:t.__setitem__(7,'2'),
 'material_identity':lambda t:t.__setitem__(6,str(int(t[6])+1)),
 'phase_omitted':lambda t:t.__setitem__(17,'00'),
 'stored_energy':lambda t:t.__setitem__(12,str(int(t[12])+1)),
 'composition_count':lambda t:t.__setitem__(16,str(int(t[16])+1)),
 'structural_energy':lambda t:t.__setitem__(11,str(int(t[11])+1)),
 'binding':lambda t:t.__setitem__(8,str(int(t[8])+1)),
 'checkpoint_step':lambda t:t.__setitem__(4,str(int(t[4])+1)),
}
rejected=[]
for name,mutate in mutations.items():
    values=fields.copy();words=values[1].decode().split();mutate(words);values[1]=' '.join(words).encode()
    try:c.check(rebuild(values),wire,step,dt,True)
    except (AssertionError,ValueError,KeyError,StopIteration):rejected.append(name)
    else:raise AssertionError(('independent checkpoint mutation escaped',name))
values=fields.copy();base=bytearray(values[0]);base[-16]=1;base[-8:]=struct.pack('<Q',c.fnv(base[:-8]));values[0]=bytes(base)
try:c.check(rebuild(values),wire,step,dt,True)
except AssertionError:rejected.append('double_counted_legacy_ledger')
else:raise AssertionError('legacy ledger mutation escaped')
print(json.dumps(dict(status='PASS',rejected=rejected),sort_keys=True))
