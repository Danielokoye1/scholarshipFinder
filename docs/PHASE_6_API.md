# Phase 6 API

Phase 6 creates immutable dry-run readiness evidence. It cannot fill or submit a live form.

## Endpoints

- `POST /api/applications/{id}/validate-submission` reruns every pre-submission check and stores an immutable snapshot.
- `GET /api/applications/{id}/validations` returns validation history, newest first.
- `GET /api/applications/{id}` includes `latest_validation`.

## Preconditions

- emergency stop is clear
- operating mode is `dry_run`
- application preparation is enabled
- application remains `ready_to_apply`
- a completed inspection and offline fill exist

## Checks

Each snapshot records explicit pass/block results for:

- live-submission lock and prior-submission history
- legitimacy screening
- normalized deadline and expiration
- freshly reevaluated deterministic eligibility
- freshly recomputed exact-destination safety
- latest inspection identity and page hash
- CAPTCHA, 2FA, essay, recommendation, signature, attestation, upload, or unknown barriers
- offline-fill completion and required-field coverage
- current profile verification status, source, timestamp, type, and value hash
- exactly one current auto-upload-approved document per recorded requirement
- unresolved action-queue items

Expired or ambiguous deadlines, changed pages, changed profile evidence, insufficient required-field evidence, suspicious legitimacy, destination changes, manual barriers, missing documents, ambiguous document selection, unresolved tasks, prior submissions, or any other failed check produce a `blocked` snapshot and a manual task.

## Immutability and privacy

Snapshots are insert-only. Their manifest hash covers the application, scholarship, browser run, fill run, safety assessment, page/fill hashes, eligibility run, deadline, checks, profile hash manifest, and selected document checksums. Raw profile answers and document contents are not copied into validation snapshots.

Even when every check passes, the application remains `ready_to_apply`. Phase 6 has no submission route, and the API state machine rejects live filling, ready-to-submit, submitting, and submitted transitions.

The local HTTP boundary rejects untrusted Host headers and cross-origin writes. Local database, document, and screenshot storage is initialized with owner-only permissions.
