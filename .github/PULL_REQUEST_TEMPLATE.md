# Summary

<!-- What does this PR change, and why? -->

Closes #

## Type of change

- [ ] Bug fix
- [ ] New detection
- [ ] Feature (non-detection)
- [ ] Refactor / internal
- [ ] Docs / CI / tooling

## How it was tested

<!-- Paste the relevant output. All must pass before review. -->

- [ ] `ruff check src/ tests/` and `ruff format --check src/ tests/`
- [ ] `mypy src/dusk/`
- [ ] `bandit -r src/ -ll`
- [ ] `pip-audit -r requirements.txt`
- [ ] `pytest --cov=src/dusk --cov-fail-under=70`

## Checklist

- [ ] Every new function/class has type annotations and a docstring
- [ ] No `print()` in `src/`; logging only
- [ ] No magic numbers in detection logic — thresholds come from `Config`
- [ ] Tests cover normal, attack, and edge cases
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
