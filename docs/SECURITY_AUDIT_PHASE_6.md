# Phase 6 security audit

Date: 2026-09-02

Scope: the local application through immutable dry-run validation. This is not approval for live submission.

## Verified controls

- Both services listen only on `127.0.0.1` using project-specific ports.
- The API accepts only trusted localhost Host headers and rejects cross-origin browser writes.
- External browser inspection uses a fresh context and blocks private networks, cross-host traffic, non-read-only methods, WebSockets, downloads, excessive requests, and unsafe redirects.
- Profile values enter only a script-free synthetic page with every network request blocked.
- Fill and validation evidence contains provenance and SHA-256 hashes, not copied answer values.
- SQLite files are `0600`; database, document, and screenshot directories are `0700`.
- `.env`, the database, documents, screenshots, virtual environments, test documents, and build artifacts are ignored by Git.
- A tracked-file scan found no credential-shaped API keys or private keys.
- `npm audit --omit=dev` reported zero production vulnerabilities.
- `pip check` reported no broken Python requirements.
- The emergency stop, Origin guard, Host guard, live-state lock, manual barriers, changed page, expired deadline, changed profile, and ambiguous-document behavior have regression coverage.

## Required before Phase 7

- explicit user authorization to design and enable controlled live submission
- a transactional per-application submission lock and idempotency key
- OS-keychain-backed credential/session handling
- form-action and final-submit-control verification on each supported adapter
- user-reviewed no-submit trials on real destinations with non-sensitive test data where permitted
- screenshot redaction and retention controls
- crash/restart recovery checkpoints and preserved-session controls
- site automation-policy review and a domain-specific allowlist
- a final human review screen showing the exact intended answers and documents
- confirmation-evidence parsing that cannot infer success from a click alone
- an explicit live-mode activation flow that defaults back to locked after material configuration changes

Until all items above are implemented and reviewed, Phase 7 must remain unavailable.
