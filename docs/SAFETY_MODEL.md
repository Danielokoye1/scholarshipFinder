# Application safety model

The safety system reduces risk; it cannot guarantee that a scholarship or website is harmless. Its primary rule is simple: **do not enter personal information until the exact application destination has passed local review**.

## Default-deny destination gate

Every new application hostname begins at `review_required`. Approval requires all of the following:

- A distinct application URL has been captured. A listing/source URL is never substituted.
- The application URL uses HTTPS.
- The hostname is not a direct IP address and is not locally blocked.
- The exact hostname has a local `approved` decision with review notes.
- Scholarship legitimacy screening is not blocked or awaiting review.
- No sensitive requirement requires separate review or blocking.

Punycode hostnames and unusual ports require review. Any application fee, bank login, bank credentials, payment requirement, gift card, or cryptocurrency request blocks the destination. SSNs, government IDs, passports, household income, financial information, bank account details, signatures, attestations, security-clearance or background-check requirements, and employment or service commitments require individual review even when the domain is approved.

## Layered statuses

Legitimacy, eligibility, and destination safety are intentionally separate:

- Legitimacy asks whether the scholarship record shows known suspicious signals.
- Eligibility asks whether verified local profile data satisfies recorded rules.
- Destination safety asks whether this exact external endpoint is acceptable for application activity.

One passing status never implies another. An approval is a recorded user judgment, not a guarantee or a wildcard for subdomains.

The local API also rejects untrusted Host headers to reduce DNS-rebinding risk and rejects state-changing browser requests whose `Origin` is not the configured local UI. SQLite, document, and screenshot storage use owner-only filesystem permissions.

## Phase 6 hard boundary

Phase 6 can create and organize a workflow, calculate priority, request a manual review, inspect the structure of an approved application form in a fresh browser context, test deterministic mappings inside a synthetic offline form, and create an immutable pre-submission validation snapshot. It cannot type into an external site, select external options, click external controls, upload, authenticate, preserve sessions, or submit. A passing snapshot is not submission authorization. Both the user interface and the API state machine enforce this boundary.

Before controlled submission, the system still must add transactional duplicate-submission locks, secure session and credential handling, form-action verification, real-site dry-run review, screenshot retention controls, recovery checkpoints, a full dependency/local-storage audit, and an explicit live-mode activation ceremony. CAPTCHA, 2FA, recommendations, signatures, attestations, and submission confirmation remain manual gates.

## Safe review practice

When reviewing a destination, independently navigate from the provider's official site or contact the provider through independently sourced information. Do not trust contact details supplied only by a suspicious listing. Never pay to receive a scholarship, share online-banking credentials, buy gift cards, send cryptocurrency, or disable device protections.
