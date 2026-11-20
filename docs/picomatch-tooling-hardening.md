# Picomatch tooling guard

GHSA-fc5q-39xc-vjpf (CVE-2026-112366) affects picomatch through 4.0.7. On 2026-11-17 the official advisory and npm registry list no patched release. This repository retains that version and applies an explicit local source guard, rather than claiming a nonexistent upstream release or downgrading the test stack.

## Intentional matching restriction

The guard uses picomatch's existing risky-extglob fallback. Repeated `+()` and `*()` extglobs retain regex repetition only for fixed-width literal bodies, including double-quoted literal metacharacters. Bodies containing unquoted wildcard/regex/glob operators, any backslash, brackets or slash are treated as literal pattern text. The mandatory guard runs before the optional recursion safeguard, including when `maxExtglobRecursion:false` is supplied.

This intentionally restricts repeated-extglob syntax. It is **not** a fully compatible general-purpose picomatch replacement. Ordinary globstars, brace extensions and non-repeating extglobs used by Vite/Vitest remain supported. Quoted literal stars and captures of accepted literal repetition are regression-tested. The source change is confined to development/build tooling; it does not change DUSK's action contract or customer execution policy.

Unchanged upstream PR #237 was rejected: it still allowed nested/braced and adjacent-star denial-of-service patterns and changed quoted-star matching. The local guard therefore does not use its incomplete repetition-flattening algorithm. It does not claim to eliminate every possible expensive regular expression or arbitrary user-supplied glob expression.

## Source admission and audit evidence

`scripts/ci/picomatch-backport.cjs` enumerates all picomatch copies in each project's lock file. It accepts only actual package version 4.0.7 and the known parser SHA-256. Only that source can be changed, and the result must have the exact reviewed patched SHA-256. Package names, versions, lock integrity fields and registry data are not rewritten. Unknown versions, modified sources, missing installations and paths outside the project's installation fail closed.

The audit command executes the ordinary `npm audit --json` and retains its complete raw report. Audit execution/network/JSON/summary errors fail. The existing moderate threshold remains for Worker/console tooling; the existing low threshold remains for the isolated Cloudflare demo. A finding is dispositioned only when its complete dependency chain leads exclusively to this exact advisory on verified patched picomatch paths. Other advisories, mixed chains, unverified paths and unknown severities fail. The original audit still reports the affected registry version, and that raw finding remains in the CI artifact beside the exact source hashes and disposition.

The local disposition expires 2026-12-01. It requires explicit maintainer review and must be replaced with a verified upstream release when available. No upstream approval or registry fix is implied. Raw reports and dispositions are retained in `worker-dependency-evidence` and `console-dependency-evidence` artifacts.

## Verification

The bounded regressions run payloads in child processes with a two-second deadline. They cover simple, adjacent-star, nested, braced, multi-branch, escaped and class patterns, including `unescape`, capture and recursion-opt-out options. Separate tests cover accepted match/capture compatibility and audit rejection for missing or changed source/advisory evidence. Actual Worker, console and demo suites plus build/lint/type checks remain required on the candidate commit. Passing isolated regressions alone does not establish complete consumer compatibility.

Apply explicitly after `npm ci --ignore-scripts`, then run the audit after tests:

```sh
node scripts/ci/picomatch-backport.cjs apply .
node --test scripts/ci/picomatch-backport.test.cjs
node scripts/ci/picomatch-backport.cjs audit . moderate
```

The console Docker builder applies the same source guard before running build tools. The final nginx image contains the compiled site, not this JavaScript development toolchain.
