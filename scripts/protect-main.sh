#!/usr/bin/env bash
#
# Apply DUSK's branch-protection posture to `main` and harden repo merge
# settings. Idempotent — safe to re-run. Requires the GitHub CLI (`gh`)
# authenticated as a repo admin.
#
#   gh auth login          # once, as a repo admin
#   ./scripts/protect-main.sh
#
# What it enforces on `main`:
#   * changes land only through pull requests (no direct pushes for non-admins)
#   * the four CI jobs must pass and be up to date: lint, typecheck, security, test
#   * at least one approving review, including Code Owners (see .github/CODEOWNERS)
#   * stale approvals dismissed on new pushes; all conversations resolved
#   * commits must be signed (Verified) — keeps main's history fully verified
#   * linear history; force-pushes and branch deletion blocked
#
# Repo-level: squash-only merges (so the merge commit is GitHub-signed and
# Verified) and auto-delete of merged branches.

set -euo pipefail

OWNER="${OWNER:-TFT444}"
REPO="${REPO:-DUSK}"
BRANCH="${BRANCH:-main}"

echo "==> Hardening repository merge settings for ${OWNER}/${REPO}"
gh api -X PATCH "repos/${OWNER}/${REPO}" \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true \
  -F allow_auto_merge=true >/dev/null

echo "==> Applying branch protection to '${BRANCH}'"
gh api -X PUT "repos/${OWNER}/${REPO}/branches/${BRANCH}/protection" \
  --input - >/dev/null <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "typecheck", "security", "test"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

echo "==> Requiring signed commits on '${BRANCH}'"
gh api -X POST "repos/${OWNER}/${REPO}/branches/${BRANCH}/protection/required_signatures" \
  -H "Accept: application/vnd.github+json" >/dev/null

echo "✅ Done. '${BRANCH}' now requires PRs, green CI, code-owner review, and signed commits."
echo "   Note: enforce_admins is false so you (admin) can still administer the repo."
echo "   For maximum strictness (applies rules to admins too), set enforce_admins=true."
