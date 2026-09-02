# Phase 3 API

The local API is served at `http://127.0.0.1:8217`. Interactive documentation is available at `/docs` while the API is running.

## Workflow endpoints

- `GET /api/applications` lists priority-ranked workflows.
- `POST /api/applications` creates or returns the single workflow for a scholarship.
- `GET /api/applications/{id}` returns safety evidence, tasks, and state history.
- `POST /api/applications/{id}/transition` applies a valid transition with an expected version.
- `POST /api/applications/{id}/reassess-safety` creates a new assessment after a policy decision.
- `GET /api/tasks` returns the manual action queue.
- `PATCH /api/tasks/{id}` resolves or dismisses a task.

## Safety endpoints

- `GET /api/safety/domains` lists local exact-hostname decisions.
- `PUT /api/safety/domains` creates or updates an approved/blocked decision with notes.
- `GET /api/safety/scholarships/{id}` returns the current assessment.
- `POST /api/safety/scholarships/{id}/assess` records a fresh assessment.

## Priority endpoints

- `GET /api/priority/settings` returns the explicit weights.
- `PUT /api/priority/settings` saves weights and recalculates priorities.
- `POST /api/priority/recalculate` recalculates without changing settings.

Application preparation and submission states return `409 Conflict` in Phase 3, even when safety is approved.
