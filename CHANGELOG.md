# Changelog

## Unreleased

- Credit GPT 5.6 Sol and GPT 6 Astra (xhigh), used in Codex during development
  and iteration. Neither model is used during gameplay.
- README-only change; the 2.0.5 archives and source snapshot are unchanged.

## 2.0.5 — 2026-09-05

- Rewrite README in plain language, with less emphasis and repetition.
- Keep commands, code links, reported scores and comparison caveats.
- No changes to agent behavior or benchmark data.

## 2.0.4 — 2026-09-05

- Frame literature figures as context, not a leaderboard or SOTA claim.
- Explain symbolic inputs versus RGB-derived symbols and Craftax-Classic
  versus stock Crafter; correct shorthand to 10,000 steps per episode.
- Keep higher related results visible without attributing the performance
  difference to inputs, worlds or policy quality without a matched test.
- Documentation/metadata only; runtime and benchmark evidence unchanged.

## 2.0.3 — 2026-09-05

- Explain the original aim: push whole-episode Score and diamond probability
  within 10,000 actions through an iteratively improved symbolic solver.
- Add a compact human/literature comparison and detailed primary-source notes.
- Keep README brief; move the complete command/API/troubleshooting reference
  to docs/USAGE.md and link directly to runtime code and supporting reports.
- Distinguish training budgets, episode horizons, pixel resolution, symbolic
  input and Craftax variants; label the C-VPT diamond figure estimate.
- Documentation/metadata only; frozen policy and benchmark evidence unchanged.

## 2.0.2 — 2026-09-05

- Substantial public README with installation, viewing, GIFs, API, CLI options,
  batch output, benchmark interpretation and troubleshooting.
- Owner-approved MIT license and package license metadata.
- Repository checks, contributor/publishing guides and GitHub issue/PR templates.
- Repository-ready source distribution; frozen policy and measured scores unchanged.

## 2.0.1 — 2026-09-05

- Optional Pygame live viewer with pause, stop and pixel enlargement.
- Live/GIF playback-speed control; viewing and recording remain opt-in.
- Twenty release tests passed, including offscreen drawing and event handling.
- No policy changes; 2.0.0 distribution artifacts preserved locally.

## 2.0.0 — 2026-09-05

- Standalone RGB-only package with default pocket and optional combined controller.
- Integer-action Python API, stock-Crafter runner, GIF export and multiprocessing.
- Portable benchmark evidence, observation-contract audit and frozen-source hashes.
- Fifteen initial package tests and six complete episode-equivalence checks passed.

Historical 1.0 used privileged local simulator labels through nighttime
corruption. It is not the RGB-only release, and its scores are not included
in the current benchmark pools. See [the audit](docs/AUDIT.md).
