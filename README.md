# scholarshipFinder

A private, local-first scholarship workflow system. The project is intentionally being built in guarded vertical phases; the current implementation includes **Phases 1–6**.

## What works now

- A canonical profile whose values carry verification status and provenance
- A grouped profile-intelligence workspace with multi-field validation and explicit review
- Local resume corroboration with no extracted document text stored in the database
- Deterministic email, phone, state, ZIP, GPA, graduation, class-standing, and enrollment checks
- Sensitive self-identification fields kept distinct from citizenship and used only for local matching
- Derived full-name and graduation-year facts only when their source fields are verified
- A local document vault with checksums and explicit auto-upload approval
- Safe document versioning that uses the newest profile source and revokes stale upload approvals
- A database-driven dashboard (no fabricated production metrics)
- Persistent automation controls, including pause and emergency stop
- A durable activity log
- SQLite migrations and API regression tests
- Localhost-only API defaults
- Structured scholarship ingestion with source evidence
- Deterministic URL normalization and duplicate detection
- Conservative duplicate-source enrichment that adds missing routed destinations without overwriting conflicts
- Rule-based eligibility evaluation with profile-value snapshots
- Conservative scholarship legitimacy screening
- A default-deny application destination safety gate
- Local application-domain approvals and blocks with review notes
- A durable application state machine and append-only event history
- A priority-ranked action queue and transparent ranking weights
- Requirement-specific action items that identify exactly which eligibility facts remain unresolved
- Opportunities, applications, safety review, and action queue interfaces
- Playwright inspection through a fresh, non-persistent Chrome context
- SSRF, same-origin, HTTPS, request-method, WebSocket, download, timeout, and size guards
- Redacted form plans that store field labels and provenance references but never profile values
- Deterministic detection of essays, CAPTCHA, 2FA, signatures, attestations, recommendations, uploads, and unmapped fields
- Offline synthetic form filling using only verified canonical profile fields
- Per-field provenance, freshness timestamps, and value hashes without duplicating raw answers
- Idempotent dry-run evidence tied to the exact inspected page hash
- Immutable pre-submission validation snapshots with explicit pass/block evidence
- A readiness gate that blocks on cross-field profile or current-resume conflicts
- Fresh deadline, legitimacy, eligibility, safety, page, profile, task, and document checks
- Regression gates for changed pages, expired deadlines, ambiguous documents, and manual checkpoints

No real scholarship application can be filled or submitted by this version. The operating mode defaults to `DISCOVERY_ONLY`; Phase 6 can inspect an approved page, test verified mappings in an offline synthetic form, and validate a hashed dry-run snapshot. Live-site filling and submission transitions remain hard-locked in the API.

## Requirements

- Node.js 20+
- Python 3.11+
- Google Chrome installed locally (the current Mac uses its existing Chrome channel)

## Start locally

```bash
cp .env.example .env
npm run setup
npm run dev
```

Open <http://127.0.0.1:3217>. The API documentation is available locally at <http://127.0.0.1:8217/docs>.

## Useful commands

```bash
npm test
npm run lint
npm run build
npm run migrate
```

## Safety boundaries

- Unknown profile data remains unknown; it is never inferred.
- Conflicting document and profile values become review items; neither side silently overwrites the other.
- Encrypted PDFs are never decrypted or bypassed for profile analysis.
- Address checks remain structural and local; no private address is sent to an external verification service.
- Only `verified` or `user_entered` profile values may eventually be considered for form filling.
- Documents cannot be auto-uploaded unless explicitly approved.
- Secrets and document contents are excluded from Git.
- The API binds to loopback by default.
- External browser use remains read-only: no profile values, cookies, login state, uploads, clicks, form writes, or submissions.
- Phase 5 fill tests occur only in locally generated, script-free pages with all network requests blocked.
- A passing Phase 6 validation is evidence only; it does not authorize, unlock, or attempt submission.
- Every distinct application domain starts unapproved; listing-page trust never substitutes for a verified application destination.
- HTTPS, direct-IP, unusual-port, payment, banking, identity, and signature rules are checked before a workflow can become ready.
- Security-clearance, background-check, employment, and service commitments always remain explicit review gates.
- Supabase and other cloud services are intentionally not connected. Data remains in this repository's ignored `storage/` tree.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/SAFETY_MODEL.md](docs/SAFETY_MODEL.md), [docs/PROFILE_INTELLIGENCE.md](docs/PROFILE_INTELLIGENCE.md), [docs/ISOLATION.md](docs/ISOLATION.md), [docs/PHASE_2_API.md](docs/PHASE_2_API.md), [docs/PHASE_3_API.md](docs/PHASE_3_API.md), [docs/PHASE_4_API.md](docs/PHASE_4_API.md), [docs/PHASE_5_API.md](docs/PHASE_5_API.md), [docs/PHASE_6_API.md](docs/PHASE_6_API.md), [docs/SECURITY_AUDIT_PHASE_6.md](docs/SECURITY_AUDIT_PHASE_6.md), and [docs/ROADMAP.md](docs/ROADMAP.md).
