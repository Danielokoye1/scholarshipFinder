# Architecture

`scholarshipFinder` is a single-user local application. The browser UI talks to a localhost FastAPI service. The service is the only layer allowed to access the SQLite database and document vault.

```text
Next.js UI (localhost:3000)
          |
          v
FastAPI (127.0.0.1:8000)
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

Trusted domains are deny-by-default. An exact domain or its subdomains may be added to `TRUSTED_SOURCE_DOMAINS` after review; detecting no scam phrases by itself produces only `likely_legitimate`, never `verified`.

All dashboard values originate from database queries. Empty tables produce zero counts and empty lists—not fixtures.
