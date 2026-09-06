"""Deterministic closed-inventory packaging; never overwrites an old seal."""
import argparse
import gzip
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

import bounded_phase_tail_bundle as parent_bundle
from correlation_aware_tail_audit import PARENT, PARENT_MANIFEST, DECISION, audit

digest, encode, files = parent_bundle.digest, parent_bundle.encode, parent_bundle.files


def build(repo, parent, work, output):
    assert not output.exists(), 'refusing to overwrite evidence'
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    parent_bundle.check(parent, repo)
    assert digest(parent/'manifest.json') == PARENT_MANIFEST
    result = audit(work)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=repo, text=True).strip()
    output.mkdir(parents=True)
    source = output/'source'
    source.mkdir()
    archive = subprocess.check_output(['git', 'archive', sha], cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(source, filter='data')
    shutil.copytree(parent, output/'parent')
    shutil.copytree(work, output/'evidence')
    (output/'evidence/result.json').write_bytes(encode(result))
    manifest = dict(schema='mls.correlation-aware.manifest.v1', source_sha=sha, source_tree=tree,
                    parent_sha=PARENT, decision=DECISION, selected_precision=None,
                    promotion='NO_PROMOTION', full_tail_budgets_certified=False,
                    files=files(output))
    (output/'manifest.json').write_bytes(encode(manifest))
    seal = dict(schema='mls.correlation-aware.outer.v1', source_sha=sha,
                manifest_sha256=digest(output/'manifest.json'), payload_files=len(manifest['files']),
                promotion='NO_PROMOTION')
    (output/'outer-seal.json').write_bytes(encode(seal))
    return check(output, repo)


def check(root, repo=None):
    seal = json.loads((root/'outer-seal.json').read_text())
    manifest = json.loads((root/'manifest.json').read_text())
    assert digest(root/'manifest.json') == seal['manifest_sha256']
    assert files(root) == manifest['files']
    assert seal['payload_files'] == len(manifest['files'])
    assert seal['source_sha'] == manifest['source_sha']
    assert manifest['parent_sha'] == PARENT and manifest['decision'] == DECISION
    assert manifest['selected_precision'] is None and manifest['promotion'] == 'NO_PROMOTION'
    assert manifest['full_tail_budgets_certified'] is False
    assert digest(root/'parent/manifest.json') == PARENT_MANIFEST
    parent_bundle.check(root/'parent')
    assert json.loads((root/'parent/manifest.json').read_text())['source_sha'] == PARENT
    assert json.loads((root/'evidence/result.json').read_text()) == audit(root/'evidence')
    # Every inherited source file is unchanged except the additive axiom report.
    for old in (root/'parent/source').rglob('*'):
        if not old.is_file():
            continue
        relative = old.relative_to(root/'parent/source')
        new = root/'source'/relative
        if str(relative) == 'formal/MLSFormal/AxiomReport.lean':
            retained = [line for line in new.read_text().splitlines() if line.strip()
                        and 'correlatedTail_' not in line
                        and line != 'import MLSFormal.CorrelationAwareTailCertification']
            assert retained == [line for line in old.read_text().splitlines() if line.strip()]
        else:
            assert digest(new) == digest(old), f'inherited source changed: {relative}'
    if repo:
        sha = manifest['source_sha']
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', sha], cwd=repo, text=True).splitlines()
        assert set(names) == {str(p.relative_to(root/'source')) for p in (root/'source').rglob('*') if p.is_file()}
        for name in names:
            expected = subprocess.check_output(['git', 'show', sha+':'+name], cwd=repo)
            assert digest(root/'source'/name) == __import__('hashlib').sha256(expected).hexdigest()
    return dict(status='PASS', source_sha=manifest['source_sha'], payload_files=len(manifest['files']),
                decision=DECISION, promotion='NO_PROMOTION')


def pack(root, archive):
    assert not archive.exists(), 'refusing to overwrite archive'
    check(root)
    with archive.open('xb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw,
                                                 mtime=0, compresslevel=9) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as tar:
            for path in sorted(root.rglob('*')):
                if path.is_file():
                    info = tar.gettarinfo(str(path), str(Path(root.name)/path.relative_to(root)))
                    info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    info.mtime = 0
                    info.mode = 0o644
                    with path.open('rb') as stream:
                        tar.addfile(info, stream)
    return dict(size=archive.stat().st_size, sha256=digest(archive))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build')
    for name in ('repo', 'parent', 'work', 'output'):
        b.add_argument(name, type=Path)
    c = sub.add_parser('check'); c.add_argument('root', type=Path); c.add_argument('--repo', type=Path)
    a = sub.add_parser('pack'); a.add_argument('root', type=Path); a.add_argument('archive', type=Path)
    args = p.parse_args()
    if args.command == 'build':
        result = build(args.repo, args.parent, args.work, args.output)
    elif args.command == 'check':
        result = check(args.root, args.repo)
    else:
        result = pack(args.root, args.archive)
    print(json.dumps(result, sort_keys=True))
