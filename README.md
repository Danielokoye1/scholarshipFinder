# scholarshipFinder

A private, local-first scholarship workflow system. The project is intentionally being built in guarded vertical phases; the current implementation includes **Phases 1–3**.

## What works now

- A canonical profile whose values carry verification status and provenance
- A local document vault with checksums and explicit auto-upload approval
- A database-driven dashboard (no fabricated production metrics)
- Persistent automation controls, including pause and emergency stop
- A durable activity log
- SQLite migrations and API regression tests
- Localhost-only API defaults
- Structured scholarship ingestion with source evidence
- Deterministic URL normalization and duplicate detection
- Rule-based eligibility evaluation with profile-value snapshots
- Conservative scholarship legitimacy screening
- A default-deny application destination safety gate
- Local application-domain approvals and blocks with review notes
- A durable application state machine and append-only event history
- A priority-ranked action queue and transparent ranking weights
- Opportunities, applications, safety review, and action queue interfaces

No real scholarship application can be filled or submitted by this version. The operating mode defaults to `DISCOVERY_ONLY`; browser preparation and submission transitions are hard-locked in the API.

## Requirements

- Node.js 20+
- Python 3.11+

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
- Only `verified` or `user_entered` profile values may eventually be considered for form filling.
- Documents cannot be auto-uploaded unless explicitly approved.
- Secrets and document contents are excluded from Git.
- The API binds to loopback by default.
- Browser automation and live submission are deliberately absent until later safety phases.
- Every distinct application domain starts unapproved; listing-page trust never substitutes for a verified application destination.
- HTTPS, direct-IP, unusual-port, payment, banking, identity, and signature rules are checked before a workflow can become ready.
- Supabase and other cloud services are intentionally not connected. Data remains in this repository's ignored `storage/` tree.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/SAFETY_MODEL.md](docs/SAFETY_MODEL.md), [docs/ISOLATION.md](docs/ISOLATION.md), [docs/PHASE_2_API.md](docs/PHASE_2_API.md), [docs/PHASE_3_API.md](docs/PHASE_3_API.md), and [docs/ROADMAP.md](docs/ROADMAP.md).
