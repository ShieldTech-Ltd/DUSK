# Live Sandbox Evidence Runner

The restricted proxy is the only path from a DUSK decision to a downstream tool. A live demonstration should run with a real provider in an isolated sandbox and capture the following fields for every scenario:

- model identifier and provider
- action type and protected target
- DUSK decision and reason
- execution status, either `allowed and executed` or `blocked before execution`
- trace identifier

The evidence formatter in `dusk.proxy_evidence.format_decision` intentionally records only safe summary fields. It does not include credentials, prompts containing secrets, raw tokens, or private customer data.

## Demonstration sequence

1. Show the provider and enforce mode, with credentials hidden.
2. Run one benign action and show the proxy allowing execution.
3. Run a high-risk action and show the proxy blocking it before the executor is called.
4. Activate the emergency kill switch and show that even a valid permit cannot execute.
5. Show the redacted per-scenario records and final counts.

This is sandbox evidence of pre-execution control. It is not a production certification, penetration test, or claim of universal protection.
