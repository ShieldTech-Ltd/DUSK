# Publish DUSK to PyPI

Distribution: `dusk-security`. Executable: `dusk`. Candidate: `0.3.0rc1`.
The PyPI project `dusk` is owned by another publisher; do not upload under it.

The release workflow contains an opt-in PyPI publishing job that only consumes
distributions verified by the existing release gate. It checks artifact hashes,
selects the wheel and source distribution, then uses PyPI Trusted Publishing.
No password or long-lived API token is needed in the repository.

## One-time account setup

Sign into your own PyPI account with two-factor authentication. In Publishing,
add a pending publisher with these exact values:

| Field | Value |
| --- | --- |
| PyPI project | `dusk-security` |
| GitHub owner | `ShieldTech-Ltd` |
| Repository | `DUSK` |
| Workflow | `release.yml` |
| Environment | `pypi` |

Create and protect the GitHub environment `pypi` with a required reviewer and
appropriate release branch/tag rules. Publisher account setup requires access
to the user's PyPI account. Never paste a password or API token into chat.

## Release

1. Merge the reviewed candidate after required CI and release evidence pass.
2. Create a verified annotated release tag on the approved main commit.
3. Dispatch `release.yml` with `release_ref` set to that tag and `publish_pypi`
   enabled. Leave `publish` disabled if the tag push already created the GitHub
   release. Approve the protected environment after reviewing the exact tag
   and artifacts. The existing workflow requires main ancestry.
4. Verify installation in a fresh environment using the public index:
   `python -m pip install --pre dusk-security==0.3.0rc1` and `dusk`.

The `publish` switch controls GitHub release creation independently. Leave it
disabled when an existing GitHub release should be retained.

For the later stable version, synchronize all package/runtime versions first.
Only after stable publication should the public quickstart say simply
`pip install dusk-security`.

Reference: [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/).
