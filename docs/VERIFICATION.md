# Release verification

## README wording update: 2.0.5

The README uses plainer language. Commands, scores and comparison caveats are
unchanged, as are the agent and benchmark data. All 20 installed-wheel tests
passed outside the source tree. The 2,192 evidence rows, frozen policy hashes
and 57 local documentation links verify. No new benchmark runs were needed.

## Comparison framing update: 2.0.4

Documentation and version metadata only. README and the supporting guides now
explicitly present the literature as context, not a leaderboard or a SOTA claim.
Runtime files and benchmark rows remain unchanged from the frozen release.
All **20 installed-wheel tests passed** outside the source tree; all 2,192
evidence rows, frozen policy hashes and 57 local documentation links verify.
No optimization or external-agent reproduction was run.

## Motivation and literature update: 2.0.3

Documentation and version metadata only; no controller behavior or benchmark
rows changed. All **20 tests passed** both against the source checkout and the
installed 2.0.3 wheel, with the installed run launched outside the source tree.
Dependency consistency, all 2,192 evidence rows, frozen policy hashes and local
documentation links/anchors verify.

README is a short landing page; docs/USAGE.md preserves the full guide. The
repository checker now verifies CLI-option coverage across both documents.

Key paper tables and the C-VPT achievement plot were visually checked against
their PDFs. Primary-source environment configuration checks are documented in
[the literature comparison](LITERATURE_COMPARISON.md). These are literature
checks, not reproduced external-agent results or a new optimization run.

## Public repository update: 2.0.2

The owner approved MIT licensing. The wheel includes LICENSE and SPDX MIT
metadata. The public README documents all ten CLI options; repository checks
verify local documentation links/anchors, version agreement and privacy markers.

All **20 installed-wheel tests passed** on Python 3.11/macOS arm64. The
two-worker CLI smoke passed outside the source folder. All 2,192 portable
benchmark rows and frozen policy hashes still verify. No policy or benchmark
change was made, and no GitHub upload or remote CI pass is claimed.

## Viewer update: 2.0.1

The policy source hashes still match 2.0.0. The new live viewer is opt-in through
`--show`, and `--record-dir` remains opt-in for GIFs. The release suite now
has **20 passing tests** when the optional Pygame dependency is installed
(otherwise one display test is skipped).

Additional checks cover headless operation without display initialization,
exact returned-frame handoff, pixel orientation and nearest-neighbor scaling,
pause/Escape behavior, cleanup on interruption, one-worker enforcement, and
GIF dimensions/playback duration. An integrated show-and-record smoke passed
using SDL's offscreen driver. A physical desktop window has not been visually
inspected in this automated verification; the offscreen path tests drawing and
event handling without opening unsolicited windows.

Install `python -m pip install ".[viewer]"` to include the pinned Pygame extra.
The 2.0.0 distributions and their verification record remain preserved.

## Original frozen-policy release: 2.0.0

Verified locally on 2026-09-05 with Python 3.11, macOS arm64.
This is integration verification of a frozen controller, not a new score run.

## Checks completed

- Original lab regression suite: **136 tests passed**.
- Standalone release suite: **15 tests passed**, including integer actions,
  per-episode reset, invalid-input rejection, stock action order, source-channel
  checks, day material decoding, all HUD digits, night abstention, explicit
  unknown versus absence, pre-diamond equivalence, metric denominators,
  output protection and exact-frame GIF recording.
- Fresh isolated virtual environment installed this package and its dependencies
  from package distributions, without the research environment or PYTHONPATH.
- All **67** checked Crafter Python/YAML/PNG files matched between the research
  installation and the fresh PyPI 1.8.3 installation.
- Six complete stock episodes compared the installed package to the frozen
  lab source on the same exact RGB/reward stream. All **3,870 actions** and
  relative positions agreed, including successful-diamond continuations.
- A two-worker CLI smoke ran from outside both the repo and lab. It used
  20-action episodes and is explicitly not a 10,000-action benchmark.
- Portable evidence verification recomputed all **2,192** included episode
  rows, both pooled profiles and transplanted policy source hashes.
- Frozen source normalization matched all eight policy modules. The old oracle
  adapter was not copied; only its frozen action/configuration constants were
  extracted. The public action-name-to-integer conversion is separately tested.

The exact checked package/runtime dependencies are in
[requirements.lock](../requirements.lock). Standard installation resolves
compatible versions; the lock reproduces the tested dependency set.
No torch, Gym, GPU or live service is needed.

## Recheck a checkout

```bash
python -m pip install -r requirements.lock .
python -m unittest discover -s tests -v
python scripts/verify_evidence.py
python -m pip check
crafter-symbolic --episodes 2 --workers 2 --length 20 --output smoke.json
```

Choose a fresh output name on each invocation; existing JSON/JSONL files are
deliberately protected. Tests inspect simulator truth only as a test oracle;
that channel is never passed into the agent.

The repository includes a Linux/Python-3.11 CI workflow. It has not yet run on a
remote host. Windows and other Python/platform combinations are not locally
verified, even though the source and multiprocessing entry point are portable.

## What these checks do not establish

They do not prove population superiority, error-free nighttime decoding,
invulnerability, arbitrary-renderer compatibility, bitwise replay across stock
processes, or neural imitation parity. The full benchmark evidence belongs to
the frozen original policy; namespacing plus complete-episode checks support
transferring that evidence to this package, without pretending six packaging
episodes are another large benchmark.

The agent assumes reset at the start of each episode and execution of every
proposed action. A future learner-action override/DAgger interface requires
additional executed-action reconciliation. The current API intentionally does
not imply support for that training workflow.
