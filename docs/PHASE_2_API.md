# Phase 2 opportunity intelligence API

The interactive API reference is available at <http://127.0.0.1:8217/docs> while the app is running.

## Ingest a structured scholarship

`POST /api/scholarships/ingest` accepts normalized source facts and typed rules. Monetary values are integer cents. A normalized deadline must include its original text and a timezone offset. The service stores the normalized instant in UTC and retains the source offset separately.

```json
{
  "name": "Example Engineering Scholarship",
  "provider": "Example Foundation",
  "source_url": "https://example.org/scholarship",
  "application_url": "https://example.org/apply",
  "award_max_cents": 500000,
  "raw_deadline_text": "March 4, 2027 at 5:00 PM ET",
  "deadline": "2027-03-04T17:00:00-05:00",
  "deadline_type": "fixed",
  "requirements": { "essay": false, "transcript": true },
  "source_text": "Applicants must have a cumulative GPA of 3.0 or higher.",
  "source_adapter": "manual",
  "rules": [
    {
      "requirement": "Cumulative GPA must be at least 3.0",
      "field_key": "education.gpa",
      "operator": "gte",
      "expected_value": 3.0,
      "confidence": 0.99,
      "needs_review": false,
      "source_quote": "Applicants must have a cumulative GPA of 3.0 or higher."
    }
  ]
}
```

The source quote must appear in `source_text`. This prevents an extracted rule from being stored without evidence.

Source URLs are canonicalized for matching: tracking parameters and fragments are removed. Application URLs use the same cleanup but retain meaningful route fragments because some application portals encode the exact competition in the fragment.

When a verified repeat source matches an existing scholarship, ingestion may add a previously missing application destination or enrich the same portal URL with its route fragment. It does not replace a different stored destination; conflicts are retained for review and recorded in the event trail. Any still-open local workflow task that pointed to the source or fragmentless portal is synchronized to the enriched route.

## Read and reevaluate

- `GET /api/scholarships` — paginated search and status filters
- `GET /api/scholarships/{id}` — scholarship, rules, source quotes, and checks
- `POST /api/scholarships/{id}/evaluate` — reevaluate one record after a profile change
- `POST /api/scholarships/evaluate-all` — reevaluate a bounded batch
- `GET /api/scholarships/{id}/eligibility-history` — inspect every decision snapshot

## Supported rule operators

- `equals`, `not_equals`
- `gte`, `lte`
- `in`
- `contains_any`, `contains_all`
- `is_true`, `exists`

Every evaluation stores a snapshot of the profile value used. Missing values produce `unknown`; low-confidence or unmapped rules produce `needs_verification`.
