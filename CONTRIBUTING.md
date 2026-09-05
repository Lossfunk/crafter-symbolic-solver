# Contributing

## Local setup

Use Python 3.11 in a virtual environment, then install from the repo root:

```bash
python -m pip install -r requirements.lock -e ".[viewer]"
python -m unittest discover -s tests -v
python scripts/verify_evidence.py
python scripts/verify_repository.py
```

The viewer extra is optional. Without it, one display test is skipped.
Automated display tests use SDL's offscreen driver.

## Reporting a problem

Include the package version/Git commit, Python and operating-system versions,
exact command, seed range, horizon and installed dependency versions.
Attach the smallest useful output or reproduction. Do not include credentials,
private machine paths or a large unrelated recording archive.

Distinguish an integration bug from a policy failure: failing to find diamond
is an expected possible outcome, not by itself proof that installation is broken.

## Changes to behavior

Keep the public observation contract intact: exact returned RGB, previous reward
and legal episode-local history. No simulator world/player/RNG fields, global
coordinates, perfect night labels, extra rendering or oracle routing may enter
the policy. Evaluator-only diagnostics must remain separate.

The files under `src/crafter_symbolic/_policy/` preserve measured source logic.
The evidence verifier intentionally detects edits to them. Do not update hashes
or old result rows simply to make a changed policy look like the measured one.
For a candidate policy, use a separate version/branch and new result artifacts,
and explicitly identify what changed.

Evaluate changes using full episodes and all 22 achievement rates, not just
successful diamond runs or a short development smoke. Freeze candidates before
fresh comparisons, retain failures and uncertainty, and keep the episode budget
and RGB boundary fixed. The historical audit explains why local improvements
and selected small-batch wins can regress on fresh worlds.

For packaging, API or display changes, add focused tests and verify that frozen
policy hashes remain unchanged. Keep optional GUI dependencies lazy so headless
users do not need a display.

## Pull requests

Explain the motivation, scope, contract impact and verification. Documentation,
test coverage and reproducible bug reports are welcome. Do not include
`runs/`, `dist/`, virtual environments, model weights or bulk gameplay data.
Avoid unrelated reformatting of the frozen controller.

Contributions are made under this repository's [MIT license](LICENSE).
See [Publishing](docs/PUBLISHING.md) for maintainer/release instructions.
