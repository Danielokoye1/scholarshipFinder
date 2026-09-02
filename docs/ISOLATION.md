# Project isolation

`scholarshipFinder` is intentionally independent from the user's other personal projects.

## Current boundaries

- Database: repository-local SQLite at `storage/database/scholarship_finder.db`
- Documents: repository-local ignored files under `storage/documents/`
- Network: API binds to `127.0.0.1:8217`; UI binds to `127.0.0.1:3217`
- Request boundary: untrusted Host headers and cross-origin browser writes are rejected
- Configuration: API variables use the `SCHOLARSHIP_FINDER_` prefix
- Cloud services: no Supabase project, cloud database, cloud authentication, telemetry, or third-party storage is configured
- Git: `.env`, the SQLite database, documents, and screenshots are ignored
- Filesystem: database, document, and screenshot storage are owner-only (`0600` files / `0700` directories)

The uncommon ports and prefixed environment names prevent accidental inheritance from generic variables such as `DATABASE_URL` or collision with projects using the usual 3000/8000 development ports.

## Supabase decision

Supabase is not needed for this single-user local phase. Adding it now would create a cloud data boundary, credentials, remote row-level security configuration, and another potential point of project overlap without providing a requirement the local application currently has.

If encrypted multi-device sync is requested later, create a brand-new Supabase organization/project or other isolated backend specifically for `scholarshipFinder`. Do not reuse schemas, keys, buckets, auth tenants, or service roles from another project. That would be a separate, explicit migration—not an automatic setup step.

## Local setup responsibility

No account or dashboard setup is required. Copy `.env.example` to `.env`, run `npm run setup`, then `npm run dev`. The migration command creates and upgrades only the repository-local SQLite database.
