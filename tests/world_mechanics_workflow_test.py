"""Fail before jobs: reject duplicate YAML and preserve inherited CI gates."""
from pathlib import Path
import subprocess
import sys
import yaml

class UniqueLoader(yaml.SafeLoader):
    pass
def mapping(loader,node,deep=False):
    result={}
    for key_node,value_node in node.value:
        key=loader.construct_object(key_node,deep=deep)
        if key in result:raise ValueError(('duplicate workflow key',key))
        result[key]=loader.construct_object(value_node,deep=deep)
    return result
UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)

root=Path(__file__).resolve().parents[1]
text=(root/'.github/workflows/authoritative-world-mechanics-integration-lab.yml').read_text()
new=yaml.load(text,Loader=UniqueLoader)
old=yaml.load((root/'.github/workflows/authoritative-mechanics-kernel-parity-lab.yml').read_text(),Loader=UniqueLoader)
assert set(new['jobs'])=={'cpp','exact-oracle','lean'}
assert new['jobs']['exact-oracle']==old['jobs']['exact-oracle']
assert new['jobs']['lean']==old['jobs']['lean']
assert len(new['jobs']['cpp']['strategy']['matrix']['include'])==3
for step in new['jobs']['cpp']['steps']:
    # Binary stdin preserves LF on Windows; text-mode pipes may insert CRLF.
    if step.get('shell')=='bash' and 'run' in step:subprocess.run([sys.argv[1] if len(sys.argv)>1 else 'bash','-n'],input=step['run'].encode('utf-8'),check=True)
prepare=next(s for s in new['jobs']['cpp']['steps'] if s.get('name')=='Pinned inputs')
assert prepare['shell']=='bash' and prepare['run'].startswith('set -euo pipefail')
assert '"$BASH"' in prepare['run']
try:yaml.load(text+'\njobs: {}\n',Loader=UniqueLoader)
except ValueError:pass
else:raise AssertionError('duplicate job map accepted')
print('World workflow strict YAML, inherited gates and shell syntax: PASS')
