# Architecture

`scholarshipFinder` is a single-user local application. The browser UI talks to a localhost FastAPI service. The service is the only layer allowed to access the SQLite database and document vault.

```text
Next.js UI (localhost:3217)
          |
          v
FastAPI (127.0.0.1:8217)
     |               |
     v               v
SQLite database   Local document vault
```

## Trust boundary

Profile values are stored with a status, source, and verification timestamp. Missing values are represented by their absence or `unknown` status. Document content is not sent to any external service. Uploaded files receive a SHA-256 checksum and require explicit approval before future automation may use them.

The API currently enables credentials for the configured local web origin only. It is not designed for public network exposure.

## Phase 1 modules

- `apps/api/app/models.py`: persistent source of truth
- `apps/api/app/routes`: HTTP boundary and input validation
- `apps/api/alembic`: schema migrations
- `apps/web`: operational interface
- `storage`: ignored local database, documents, and screenshots

## Phase 2 intelligence flow

```text
Structured source record
  -> canonical text and URLs
  -> exact/fingerprint/provider-title deduplication
  -> immutable source evidence
  -> deterministic legitimacy signals
  -> typed eligibility rules
  -> canonical profile comparison
  -> persisted eligibility checks and overall status
```

The ingestion boundary requires each rule to carry a quote that actually occurs in the captured source text. Low-confidence rules, unmapped fields, unsupported values, and missing profile information stop at `needs_verification` or `unknown`. They cannot become eligibility passes.

Trusted discovery sources are deny-by-default. An exact domain or its subdomains may be added to `SCHOLARSHIP_FINDER_TRUSTED_SOURCE_DOMAINS` after review; detecting no scam phrases by itself produces only `likely_legitimate`, never `verified`.

## Phase 3 guarded workflow

An application workflow begins only after the stored eligibility result and a fresh destination safety assessment are read. Application destinations use a separate exact-hostname policy from discovery sources. A source-page hostname is never used as an application destination when the application URL is absent.

```text
Opportunity
  -> deterministic eligibility result
  -> fresh application destination assessment
  -> ineligible | needs user input | needs safety review | ready to apply
  -> explicit state transitions + append-only events
  -> priority-ranked manual task queue
```

## Phase 4 read-only browser boundary

Phase 4 may inspect an approved application URL only after a fresh safety assessment and verified eligibility result. Each run uses a new non-persistent Chrome context with service workers, downloads, WebSockets, non-read-only methods, cross-host requests, private/reserved addresses, unusual ports, and excessive requests blocked. The approved hostname is pinned to the public address resolved before launch to reduce DNS-rebinding exposure.

The browser collects form labels, element kinds, required status, autocomplete hints, challenge categories, a page hash, redacted destinations, and response status. It does not collect input values, option values, raw HTML, cookies, browser profiles, screenshots, or profile values.

```text
Fresh safety assessment
  -> public HTTPS target validation
  -> isolated read-only browser context
  -> redacted field structure
  -> deterministic profile-key mapping (references only)
  -> manual checkpoint tasks
  -> persisted BrowserRun + FormFieldPlan evidence
```

The `application_started`, `filling`, `ready_to_submit`, `submitting`, and `submitted` states remain locked in Phase 4. This is an API constraint, not merely a disabled UI control.

See `SAFETY_MODEL.md` for the threat model and `ISOLATION.md` for project boundaries.

All dashboard values originate from database queries. Empty tables produce zero counts and empty lists—not fixtures.
