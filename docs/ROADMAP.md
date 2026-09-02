# Delivery roadmap

## Phase 1 — foundation (implemented)

- Local profile, document metadata/vault, dashboard shell, persistent safety controls

## Phase 2 — opportunity intelligence (implemented)

- Scholarship ingestion, normalized sources, deterministic deduplication, eligibility rules and evidence
- Canonical URL cleanup, source hashes, legitimacy screening, and repeatable reevaluation

## Phase 3 — safe workflow (implemented)

- Opportunity table and detail review with safety evidence
- Default-deny destination policy and sensitive-information checks
- Application state machine, event trail, action queue, and transparent prioritization
- API-level lock preventing browser preparation or submission states

## Phase 4 — guarded form inspection (implemented)

- Fresh non-persistent Chrome context with no login state or personal data
- HTTPS, same-origin, public-network, request-method, request-count, timeout, and content-size guards
- Redacted field plans with deterministic profile-key mappings and manual barrier detection
- Fake local application fixture proving that hidden values and blocked requests are not used

## Phase 5–6 — guarded browser preparation

- Verified-field dry-run filling and pre-submission validation

## Phase 7+ — controlled operation

- Explicitly enabled submission, durable workers, response tracking, additional source adapters

Live submission must remain unavailable until the safety regression suite, dry runs, recovery behavior, audit evidence, and emergency stop have all been validated.
