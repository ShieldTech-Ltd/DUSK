# Contributing to DUSK

Thanks for your interest in DUSK. This document describes how we work so that
contributions land cleanly and the published history stays professional.

## Branch model

- `main` is the published, production branch. It is protected: changes reach it
  only through reviewed, CI-green, signed pull requests. See
  [docs/branch-protection.md](docs/branch-protection.md).
- `dev` is the integration branch for in-progress work.
- Feature work happens on a short-lived branch named for its purpose, for
  example `feature/lateral-detection`, `fix/pcap-empty-file`, or
  `docs/readme-polish`.

Open a pull request from your branch into `dev`. Maintainers promote tested
changes from `dev` to `main` through a separate release pull request. Pull
requests are squash merged, which keeps a linear history and produces a single
signed, verified commit on `main`.

## Issue first

Open an issue before you open a pull request. The issue states the problem, the
proposed solution, and the acceptance criteria. The pull request then references
and closes that issue.

The only exception is a genuinely trivial change, such as a typo fix or a
one-line revert. Call it out explicitly in the pull request when you skip the
issue.

Use the issue forms under [.github/ISSUE_TEMPLATE](.github/ISSUE_TEMPLATE) for
routine bug reports and feature requests. The blank-issue route is reserved for
important or urgent items that do not fit a form. Do not file security
vulnerabilities as public issues; use the private advisory link in
[SECURITY.md](SECURITY.md).

## Developer Certificate of Origin

DUSK uses the [Developer Certificate of Origin 1.1](https://developercertificate.org/).
Every commit in a pull request must include a `Signed-off-by` trailer that
certifies you have the right to submit the contribution under this project's
licenses.

Create signed-off commits with:

```bash
git commit --signoff -m "type: concise description"
```

If a commit is missing the trailer, amend it with `git commit --amend --signoff`
and update the branch. The DCO CI job rejects pull requests containing unsigned
commits.

## Local checks

Install the project with its development extras, then run the same gates CI runs:

```bash
pip install -e ".[dev]"

ruff check src/ tests/
ruff format --check src/ tests/
mypy src/dusk/
bandit -r src/ -ll
pip-audit -r requirements.txt
pytest --cov=src/dusk --cov-fail-under=70
```

Install the pre-commit hooks so formatting and basic checks run automatically:

```bash
pre-commit install
```

## Code standards

- Every function and class in `src/` has type annotations and a docstring.
  `mypy --strict` must pass.
- No bare `except` clauses. Catch specific exception types.
- No magic numbers in detection logic. Thresholds come from `Config`.
- No `print()` in `src/`. Use the module logger,
  `logging.getLogger("dusk.<module>")`.
- Tests cover normal input, attack input, and edge cases. Coverage stays at or
  above 70 percent.
- Plain-text house style in docs and user-facing strings: no emojis and no em or
  en dashes.

## Adding a detection

A new detection is a class in `src/dusk/detections/` that extends `Detection`,
sets `name`, `mitre_technique`, and `kill_chain_stage`, reads its thresholds from
`Config`, and returns a `DetectionResult`. Register it in
`src/dusk/detections/__init__.py` and add it to `default_detections` in
`src/dusk/core/engine.py`. Add a lab scenario that generates a fixture and tests
that cover both the attack and benign cases. Document it in
[docs/threat-model.md](docs/threat-model.md).

## Pull request checklist

The pull request template captures the full checklist. In short: link the issue,
state how you tested, confirm the gates pass, and update `CHANGELOG.md` under
`[Unreleased]`.

By participating, contributors agree to follow
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Project decisions and maintainer
responsibilities are documented in [GOVERNANCE.md](GOVERNANCE.md).

## Verified commits

Commits made with plain `git` in an ephemeral environment are unsigned and show
as Unverified. This does not affect the code, and squash merges into `main` are
signed by GitHub, so the published branch stays fully verified. To sign your
local commits as well, configure SSH or GPG signing and add the public key to
your GitHub account, then enable `git config --global commit.gpgsign true`.
