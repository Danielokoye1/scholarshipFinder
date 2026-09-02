# Phase 4 API

Phase 4 adds read-only browser inspection. It does not fill or submit forms.

## Endpoints

- `POST /api/applications/{id}/inspect` starts a synchronous, user-requested inspection and returns its redacted plan.
- `GET /api/applications/{id}/inspections` returns inspection history, newest first.
- `GET /api/applications/{id}` includes `latest_inspection`.

Inspection requires:

- application status `ready_to_apply`
- deterministic eligibility status `eligible`
- a distinct application URL
- a fresh safety result of `approved`
- emergency stop disabled
- the per-application inspection cooldown to have elapsed

## Stored evidence

`BrowserRun` stores redacted start/final URLs, exact hostname, redirect/request safety results, page title, HTTP status, page-content hash, counts, barriers, generic errors, and timestamps. URL credentials, query strings, fragments, and token-like path segments are removed, and at most 50 blocked-request records are retained per run.

`FormFieldPlan` stores form order, label, control type, required/disabled state, autocomplete hint, mapped canonical profile key, confidence, profile verification status, disposition, and explanation.

It intentionally does **not** store form values, profile values, option values, hidden values, raw page HTML, cookies, credentials, browser storage, or submitted data.

## Browser prerequisite

The current computer is on macOS 13, which is below the supported OS for current downloaded Playwright Chromium builds. The system therefore launches the already-installed Google Chrome using Playwright's supported `chrome` channel. `npm run browser:check` verifies this prerequisite without installing or replacing Chrome.
