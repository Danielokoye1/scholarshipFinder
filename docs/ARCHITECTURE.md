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

All dashboard values originate from database queries. Empty tables produce zero counts and empty lists—not fixtures.

