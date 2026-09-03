# Local profile intelligence

The profile workspace combines related fields, deterministic checks, and local document corroboration without turning unreviewed guesses into personal facts.

## Trust order

1. Verified profile fields with a named source
2. Deterministic values derived from verified fields, such as a full name or graduation year
3. User-entered values awaiting corroboration
4. Suggestions that require explicit review
5. Unknown when the available evidence is missing or contradictory

Changing a verified field in the interface changes its status to `user_entered`. A suggestion is never committed merely because it appeared in a document.

## Multi-input checks

- Verified first, middle, and last name components may produce a derived full name.
- A verified expected-graduation term may produce a derived graduation year.
- Class standing is compared with graduation year and the current academic cycle, but a nontraditional schedule is never treated as an error by itself.
- GPA can be corroborated against a readable document, and a missing GPA scale can be suggested for confirmation.
- Institution, major, name, and graduation timing can be compared with readable local documents.
- Email, US phone, state, ZIP code, GPA, class standing, and enrollment status use deterministic format validation.
- Optional race/ethnicity and national-origin/heritage facts remain separate from citizenship and residency. They are stored only when the user self-identifies, marked sensitive, and may be used for local eligibility matching.
- Scholarship-specific affiliation facts, such as paid NSBE membership and NSBE region, have explicit profile fields instead of being inferred from demographic identity or school location.

## Document privacy

PDF text is read in memory and discarded after each review. Extracted text is not written to the database, event log, or API response. The reader is limited by the document-vault size cap and a 50-page/300,000-character ceiling. Encrypted PDFs are reported as locked and are never decrypted or bypassed.

When multiple resumes exist, only the newest stored version is used for profile corroboration. Older copies remain visible as history. Adding a new document version revokes automatic-upload approval from older documents of the same type, and the new version also starts unapproved.

## Address boundary

The local checker can validate only structure: required components, state names, ZIP format, and basic field normalization. It cannot prove that a residence is real or deliverable. USPS, Google, Census, or another external address-verification service would require sending private address data outside the device and therefore is not connected. Such a feature must require a separate, explicit user decision.

## Submission boundary

Profile review changes local profile data only. It does not authorize browser filling, document upload, account creation, or submission. Phase 7 remains locked.
