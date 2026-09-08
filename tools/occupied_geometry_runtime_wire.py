"""Candidate-only canonical wire reader: no fixtures, oracle or generator."""
import gmpy2 as g


class WireError(ValueError):pass


class Reader:
    def __init__(self,path,kind):
        self.f=open(path,'rb')
        if self.take(8)!=b'MLSOMG01' or self.uint(4)!=1 or self.uint(4)!=kind:
            raise WireError('wrong wire schema/kind')
        self.count=self.uint(8)
    def take(self,n):
        raw=self.f.read(n)
        if len(raw)!=n:raise WireError('truncated wire')
        return raw
    def uint(self,n):return int.from_bytes(self.take(n),'little')
    def q(self):
        sign=self.uint(1);n=self.uint(4)
        if sign>1 or n>1024:raise WireError('invalid numerator')
        raw=self.take(n)
        if n and raw[-1]==0:raise WireError('redundant numerator')
        numerator=int.from_bytes(raw,'little');d=self.uint(4)
        if not 1<=d<=1024 or (not numerator and sign):raise WireError('invalid rational')
        raw=self.take(d)
        if raw[-1]==0:raise WireError('redundant denominator')
        denominator=int.from_bytes(raw,'little')
        if g.gcd(numerator,denominator)!=1:raise WireError('unreduced rational')
        return g.mpq(-numerator if sign else numerator,denominator)
    def end(self):
        if self.f.read(1):raise WireError('trailing bytes')
        self.f.close()


class WorkLimit(Exception):pass


class Work:
    def __init__(self):self.used=0;self.pending=None
    def charge(self,operation,n=1):
        if type(n) is not int or n<0:raise ValueError('invalid work charge')
        if self.used+n>4194304:
            self.pending=dict(operation=operation,requested=n,used=self.used,cap=4194304)
            raise WorkLimit(operation)
        self.used+=n
