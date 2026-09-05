# Publishing this repository

The agent is MIT-licensed. This guide prepares a GitHub source repository;
it does not assume a PyPI account or publish anything automatically.

## Push the prepared local repository

The prepared working folder has a local `main` branch and an initial commit.
Create an **empty** repository in your GitHub account, without initializing a
second README, license or gitignore. Copy its SSH or HTTPS URL.

From this folder, replace `YOUR_REPOSITORY_URL` before running:

```bash
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

No remote URL is baked into this project. No credentials are needed by the
agent; GitHub authentication is only for your normal Git push. If an origin
already exists, inspect `git remote -v` before changing anything.

A downloaded source ZIP does not contain Git history. If starting from that
instead of the prepared working folder, first run:

```bash
git init -b main
git add .
git commit -m "Initial Crafter Symbolic release"
```

The CI workflow will run when pushed. It is configured, not represented as
already passing on GitHub.

## What belongs in Git

Track source, README/docs, tests, examples, license, package metadata, CI and
portable evidence. The bundled benchmark summaries are small enough for
ordinary Git; there is no need for Git LFS.

`.gitignore` excludes `dist/`, `runs/`, virtual environments, build caches and
local environment files. Do not force-add old wheels, model weights, credentials,
raw training data or a large collection of GIFs. Earlier release archives
remain on disk for provenance; they are not part of the Git history.

## Release checks

Use a clean virtual environment and run:

```bash
python -m pip install -r requirements.lock ".[viewer]"
python -m unittest discover -s tests -v
python scripts/verify_evidence.py
python scripts/verify_repository.py
python -m pip check
crafter-symbolic --episodes 2 --workers 2 --length 20 --output runs/release-smoke.json
```

Choose a fresh smoke filename on repeated checks. A short smoke does not
establish a new benchmark result. Preserve policy/source provenance and label
new measurements separately.

To make ordinary distributable packages:

```bash
python -m pip install build
python -m build
```

This writes the wheel and source distribution under `dist/`. Review their
contents, install the wheel in a separate environment, and run tests before
attaching them to a GitHub Release. No PyPI upload is necessary for repository
users to install with `pip install .`.

## Version and provenance discipline

Update the version in `pyproject.toml`, `src/crafter_symbolic/__init__.py`
and `src/crafter_symbolic/release.json` together. The repository verifier
checks agreement. Add a changelog entry; distinguish packaging/documentation
changes from new policy behavior.

`SOURCE_SHA256SUMS` describes a frozen source snapshot, excluding Git metadata,
itself and ignored build/run output. It is not a live-working-tree lock.
After an intentional change, generate a new snapshot at the next release;
do not claim old snapshot checksums describe new files.

Policy hashes in `evidence/policy_provenance.json` have a different role:
they identify the measured controller. Changing them requires explicit new
policy provenance, not just refreshing a documentation checksum.
