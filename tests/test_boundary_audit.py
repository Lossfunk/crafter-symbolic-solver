"""Regression checks for the audit tools and retained evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BoundaryAuditTests(unittest.TestCase):
    def test_source_checks_include_from_imports(self):
        spec = importlib.util.spec_from_file_location('audit_boundary', ROOT/'scripts/audit_boundary.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        checked = module.source_checks()
        self.assertEqual(len(checked), 11)

    def test_recorded_boundary_evidence_matches_current_policy(self):
        import crafter_symbolic
        package = Path(crafter_symbolic.__file__).parent
        data = json.loads((ROOT/'evidence/input_boundary_audit.json').read_text())
        for source in data['sources']:
            path = package/'agent.py' if source['file'] == 'agent.py' else package/'_policy'/source['file']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source['sha256'])
        rows = data['records']
        self.assertEqual(sum(r['actions'] for r in rows), 6634)
        self.assertEqual(sum(r['reset_action_matches'] for r in rows), 6634)
        self.assertEqual(sum(r['combined_prefix_matches'] for r in rows), 4444)
        self.assertTrue(all(r['action_matches'] == r['actions'] and not r['crafter_imported'] for r in rows))

    def test_documented_cooldown_counterexample(self):
        result = subprocess.run([sys.executable, str(ROOT/'scripts/audit_assumptions.py')],
                                check=True, capture_output=True, text=True)
        data = json.loads(result.stdout)
        self.assertEqual(data['surviving_zombie_true_cooldown'], 1)
        self.assertEqual(data['surviving_zombie_inferred_cooldown'], 5)
        self.assertFalse(data['policy_modified'])


if __name__ == '__main__':
    unittest.main()
