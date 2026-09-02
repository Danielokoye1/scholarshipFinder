# Phase 5 API

Phase 5 verifies deterministic form filling without placing personal data on an external website.

## Endpoints

- `POST /api/applications/{id}/dry-run-fill` creates or returns idempotent offline fill evidence for the latest completed inspection.
- `GET /api/applications/{id}/dry-run-fills` returns local dry-run history, newest first.
- `GET /api/applications/{id}` includes `latest_fill`.

## Required gates

- emergency stop is clear
- operating mode is `dry_run`
- application preparation is enabled
- application is `ready_to_apply`
- eligibility is exactly `eligible`
- destination safety is `approved`
- the latest inspection completed without a manual barrier
- every active required field has a supported deterministic mapping
- every selected canonical profile value is currently `verified`

## Execution boundary

The engine generates a script-free HTML form from the redacted field plan, creates a fresh non-persistent Chrome context, disables JavaScript, blocks all network requests, fills only supported scalar controls, verifies their in-memory values, and destroys the context. It never navigates to the scholarship destination during filling.

Supported Phase 5 control types are text, email, telephone, number, date, URL, and search. Dropdowns, checkboxes, radio buttons, files, passwords, essays, signatures, attestations, recommendations, and unknown controls remain manual until their semantics can be validated deterministically.

## Stored evidence

Each completed field records its label, canonical profile key, profile record reference, verification status, source reference, profile timestamp, value type, and SHA-256 value hash. Raw answer values are not copied into fill evidence, API responses, events, or logs.
