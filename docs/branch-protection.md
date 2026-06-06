# Branch protection & verified commits

This repo treats `main` as the published, production branch. It is protected so
that only reviewed, CI-green, **signed** changes reach it.

## Why your commits showed "Unverified"

GitHub's **Verified** badge means a commit is cryptographically signed by a key
tied to the author's account. Commits created with plain `git` in an ephemeral
environment are unsigned, so they show **Unverified** — this is cosmetic and
does not affect the code, but a maintained security project should keep a clean,
verified history on its published branch.

We solve this without rewriting history:

1. **`main` only receives verified commits.** All changes merge via a
   **squash** PR; GitHub signs the squash commit with its web-flow key, so every
   commit that lands on `main` is **Verified**. Required-signed-commits
   protection enforces this.
2. **Governance changes are made via the GitHub API**, which GitHub signs
   automatically — so they are Verified on `dev` too.
3. Unsigned working commits live only on feature branches and are squashed away
   on merge; they never reach `main`.

> To sign your *local* commits as well, configure SSH or GPG signing and add the
> public key to your GitHub account under **Settings → SSH and GPG keys →
> New signing key**, then `git config --global commit.gpgsign true`.

## Applying protection

Run once, as a repo admin with the GitHub CLI:

```bash
./scripts/protect-main.sh
```

This is the source of truth for our protection posture. To apply it by hand
instead, in **Settings → Branches → Add branch protection rule** for `main`:

- Require a pull request before merging — **1 approval**, **Require review from
  Code Owners**, **Dismiss stale approvals**
- Require status checks to pass — **lint**, **typecheck**, **security**, **test**
  (and "Require branches to be up to date")
- **Require signed commits**
- **Require linear history**
- **Require conversation resolution before merging**
- Do **not** allow force pushes or deletions

And in **Settings → General → Pull Requests**: allow **squash merging** only,
and **automatically delete head branches**.

`enforce_admins` is left off so a solo maintainer can still administer the repo;
flip it on (or set `enforce_admins=true` in the script) to apply the rules to
admins too.
