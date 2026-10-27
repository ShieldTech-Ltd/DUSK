# DUSK Project Rules

## Commit Authorship

NEVER add any of the following to any git commit message, PR description, or code comment:

- `Co-Authored-By: Claude`
- `Co-Authored-By: claude`
- `Co-Authored-By: Anthropic`
- `Claude-Session:`
- Any trailer or line that identifies Claude, an AI model, or Anthropic as a contributor

Every commit must show only the human author (Tanvir Farhad). No AI attribution, co-author trailers, or session links.

When creating commits, use only:
```
git commit --signoff -m "message"
```

## Merge and Branch Rules

- Never merge to main or dev directly. All changes go through PRs.
- Never force-push, reset --hard, or rewrite published history.
- Never trigger `real-agent-sandbox.yml` without explicit user instruction.
- Never modify AWS resources or GitHub environment configuration without explicit user instruction.

## Writing Style

Never use em dashes (U+2014) in any text. Rewrite with commas, parentheses, colons, or split sentences.
