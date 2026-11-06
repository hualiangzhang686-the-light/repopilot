# Security

## Threat model

Repository code, Issue text, model output, paths, patch contracts, and tool arguments are untrusted. RepoPilot assumes they may request path traversal, destructive actions, arbitrary commands, unsupported conclusions, or excessive output.

## Enforced controls

- Canonical repository-root resolution blocks relative, absolute, and symlink escapes.
- Delete and external capabilities are disabled by `PermissionGate`.
- Writes require an explicit path inside a disposable sandbox copy.
- Tests accept only the current Python executable with `-c` or `-m unittest`.
- Commands use `shell=False` and a wall-clock timeout.
- Consecutive failed tools, repeated calls, maximum steps, and total loop time stop execution.
- Research output is withheld when Evidence Ledger validation is missing or fails.
- Triage labels hypotheses `unverified` and blocks underspecified issues.
- Fix results require a non-empty diff and passing post-test.
- Large output is truncated inline and stored as a SHA-256-linked Artifact.

## Non-goals and remaining risks

- `SandboxWorkspace` is a filesystem copy, not an OS container. Only run trusted test code locally.
- Python `-c` can execute arbitrary Python inside the disposable directory; the allowlist prevents command substitution, not hostile Python behavior.
- Local Session and Artifact files are unencrypted. Never place secrets in them.
- Prompt injection is contained by narrow tools and evidence checks but not semantically solved.
- Remote Provider traffic and data retention follow the configured provider account and API settings.

Report security issues privately to the repository owner instead of publishing credentials or exploit details in a public issue.
