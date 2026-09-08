"""Independent exact parser: unified checkpoint versus sealed mechanics bytes.

Does not call C++, trust the candidate's material totals, or round phase values.
The fixed synthetic material law and units are the preregistered fixture.
"""
import struct

def fnv(b):
    h=14695981039346656037
    for x in b:h=((h^x)*1099511628211)&((1<<64)-1)
    return h

def check(data,wire_hex,step,dt,neutral=False):
    magic=b'MLS-MATERIAL-PHASE-v1\n';assert data.startswith(magic)
    assert len(data)<=16*1024*1024 and int.from_bytes(data[-8:],'little')==fnv(data[:-8])
    p=len(magic);fields=[]
    for _ in range(4):
        n=int.from_bytes(data[p:p+8],'little');p+=8;assert n<=16*1024*1024 and p+n<=len(data)-8
        fields.append(data[p:p+n]);p+=n
    assert p==len(data)-8
    base,records,model,events=fields;wire=bytes.fromhex(wire_hex)
    count=int.from_bytes(wire[44:52],'little');assert 0<count<=16 and len(wire)==52+118*count
    assert int.from_bytes(wire[36:44],'little',signed=True)==step*dt
    reference={}
    compound=fnv(struct.pack('<QHQ',1,1,0))
    for j in range(count):
        ident,mass=struct.unpack_from('<Qq',wire,52+118*j)
        reference[ident]=dict(material=10000+7*(count-j),mass=mass,phase=wire[68+118*j:170+118*j],index=j)
    assert base[:16]==b'MLSTTLAB'+struct.pack('<II',2,1)
    assert int.from_bytes(base[-8:],'little')==fnv(base[:-8])
    assert struct.unpack_from('<9q',base,16)==(1,1<<48,1,dt,1,1000000000,1,1,0)
    assert base[88]==1 and struct.unpack_from('<Qq',base,89)==(step,step*dt)
    pos=105
    def number(size=8):
        nonlocal pos
        assert pos+size<=len(base)-8
        n=int.from_bytes(base[pos:pos+size],'little');pos+=size;return n
    assert number()==1 and number(2)==1 and [number() for _ in range(3)]==[1,2,3]
    assert number()==0 # No bond-energy rule added to the synthetic catalog.
    assert number()==1 and number()==compound and number()==1 and number(2)==1 and number()==0
    assert number()==max(x['material'] for x in reference.values())+1
    assert number()==0 # No second/placeholder legacy material or phase record.
    assert not any(base[pos:-8]) # Legacy exact-mechanics ledger is empty, not double-counted.
    words=iter(records.decode().split())
    trajectory,path,level=next(words),next(words),int(next(words));assert trajectory and path in ('KDK','CONTROL') and 0<=level<5
    assert int(next(words))==dt and int(next(words))==step and int(next(words))==count
    observed={};prior=0;material_energy=0
    for _ in range(count):
        ident,generation,mechanics,mass,heat,structural,stored,thermal,mixtures=[int(next(words)) for _ in range(9)]
        assert ident>prior and generation==1 and mechanics in reference and mixtures==1;prior=ident
        ref=reference[mechanics];j=ref['index'];assert ident==ref['material'] and mass==ref['mass'] and heat==2*mass and structural==3*mass
        assert int(next(words))==compound and int(next(words))==mass
        phase=bytes.fromhex(next(words));assert phase==ref['phase'] and len(phase)==102
        odd=neutral and step%2==1
        assert stored==100+j-(1 if odd and j==0 else 0)
        assert thermal==200+j+(1 if odd and j==count-1 else 0)
        assert mechanics not in observed;observed[mechanics]=(ident,generation)
        material_energy+=structural+stored+thermal
    assert int(next(words))==count
    for mechanics in sorted(reference):
        assert (int(next(words)),int(next(words)),int(next(words)))==(mechanics,*observed[mechanics])
    mass_total=sum(x['mass'] for x in reference.values());index_sum=count*(count-1)//2
    assert [int(next(words)) for _ in range(7)]==[mass_total,3*mass_total,100*count+index_sum,200*count+index_sum,1,1,mass_total]
    assert material_energy==3*mass_total+300*count+2*index_sum
    assert next(words,None) is None
    assert model and events # Registered checkpoints are interior/final committed states.
    return dict(status='PASS',material_packets=count,phase_bytes=102*count,legacy_packets=0,neutral_change=bool(neutral and step%2))
