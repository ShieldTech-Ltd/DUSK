# OWASP Demo Recording Guide

The v0.2.0 application recording demonstrates real local behavior without
claiming production readiness. Record a single continuous run from a clean
checkout of tag `v0.2.0`.

## Safety boundary

- Use only the keyless mock agent included in the repository.
- Keep all published ports on localhost.
- Do not configure AWS, SIE, webhook, or production credentials.
- Close unrelated terminals and notifications before recording.
- Review the final frames for usernames, tokens, paths, or private data.

## Recording sequence

Target duration: 90 seconds.

1. Show the repository URL and architecture diagram.
2. State that DUSK is applying at Incubator level and is not production-ready.
3. Run `./scripts/run_owasp_demo.sh watch`.
4. Highlight clean `ALLOW`, poisoned `WOULD-BLOCK`, and two applied actions.
5. Run `./scripts/run_owasp_demo.sh enforce`.
6. Highlight clean `ALLOW`, poisoned `BLOCK`, and one applied action.
7. Show the automatic cleanup and the commands needed to reproduce the run.

Do not edit the terminal output or splice in a successful result from another
commit. If either verifier fails, fix the failure and record the complete run
again.

## Publication

Export the recording as `dusk-owasp-demo-v0.2.0.mp4`. Attach it to the v0.2.0
GitHub release and link that release from the README and private OWASP request.
The release tag, recording checkout, and displayed version must all be
`v0.2.0`.
