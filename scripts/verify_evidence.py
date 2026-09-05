"""Recompute all shipped achievement/diamond statistics without the lab."""
import ast
import hashlib
import json
import math
from pathlib import Path

from crafter_symbolic.metrics import summarize

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT/'evidence/benchmarks.json').read_text())
    total = 0
    for court in data['courts'].values():
        for group in court['variants'].values():
            got = summarize(group['episodes'])
            expected = group['summary']
            assert got == expected
            total += len(group['episodes'])
    for variant, expected in data['pooled'].items():
        rows = [r for name in expected['included_courts']
                for r in data['courts'][name]['variants'][variant]['episodes']]
        assert len({r['seed'] for r in rows}) == len(rows)
        got = summarize(rows)
        assert all(got[k] == expected[k] for k in got)
    provenance = json.loads((ROOT/'evidence/policy_provenance.json').read_text())
    core = ROOT/'src/crafter_symbolic/_policy'
    for name, evidence in provenance['modules'].items():
        assert hashlib.sha256((core/name).read_bytes()).hexdigest() == evidence['packaged_sha256'], name
    assert hashlib.sha256((core/'config.py').read_bytes()).hexdigest() == provenance['config']['packaged_sha256']
    print(f'PASS: {total} portable episode rows, both pooled profiles, and all transplanted source hashes')


if __name__ == '__main__':
    main()
