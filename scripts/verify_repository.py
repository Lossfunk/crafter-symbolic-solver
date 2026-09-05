"""Check public docs, license, version agreement and documented CLI options."""
import ast
import json
from pathlib import Path
import re
import tomllib
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.venv', '__pycache__', '.pytest_cache', 'build', 'dist', 'runs',
            'htmlcov'}


def source_files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file()
        and not any(x in EXCLUDED or x.endswith('.egg-info') for x in p.relative_to(ROOT).parts)
        and p.name not in {'.DS_Store', '.coverage', 'SOURCE_SHA256SUMS'}
        and not p.name.startswith('.env'))


def headings(path):
    slugs, counts = set(), {}
    # The repository uses ordinary ASCII words in all linked heading anchors.
    for title in re.findall(r'^#{1,6} (.+)$', path.read_text(), re.M):
        base = re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-')
        count = counts.get(base, 0)
        slugs.add(base if not count else f'{base}-{count}')
        counts[base] = count+1
    return slugs


def main():
    metadata = tomllib.loads((ROOT/'pyproject.toml').read_text())
    package = ROOT/'src/crafter_symbolic'
    module = ast.parse((package/'__init__.py').read_text())
    version = next(ast.literal_eval(n.value) for n in module.body
                   if isinstance(n, ast.Assign) and any(
                       isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets))
    assert version == metadata['project']['version']
    assert version == json.loads((package/'release.json').read_text())['version']
    assert metadata['project']['license'] == 'MIT'
    license_text = (ROOT/'LICENSE').read_text()
    assert 'MIT License' in license_text and 'Permission is hereby granted' in license_text
    assert '## '+version+' ' in (ROOT/'CHANGELOG.md').read_text()
    readme = (ROOT/'README.md').read_text()
    usage = (ROOT/'docs/USAGE.md').read_text()
    cli = ast.parse((package/'cli.py').read_text())
    flags = {arg.value for n in ast.walk(cli) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == 'add_argument'
             for arg in n.args if isinstance(arg, ast.Constant)
             and isinstance(arg.value, str) and arg.value.startswith('--')}
    assert all(flag in readme + usage for flag in flags), flags
    checked, files = 0, source_files()
    # Construct markers so this check's source does not contain private paths.
    private_markers = ('/'+'Users/', '/'+'private/', 'Google'+'Drive', '@gmail'+'.com')
    for path in files:
        assert not path.is_symlink(), path
        if path.suffix not in {'.py', '.md', '.toml', '.json', '.yml', '.lock', ''}:
            continue
        text = path.read_text()
        assert not any(marker in text for marker in private_markers), path
        if path.suffix != '.md':
            continue
        for link in re.findall(r'\]\(([^)]+)\)', text):
            if '://' in link or link.startswith('mailto:'):
                continue
            target, _, anchor = unquote(link).partition('#')
            dest = (path.parent/target).resolve() if target else path
            assert dest.is_relative_to(ROOT), (path, link)
            assert dest.exists(), (path, link)
            if anchor:
                assert anchor in headings(dest), (path, link)
            checked += 1
    print(f'PASS: version {version}, MIT license, {len(flags)} CLI options, '
          f'{checked} local links/anchors, {len(files)} source files')


if __name__ == '__main__':
    main()
