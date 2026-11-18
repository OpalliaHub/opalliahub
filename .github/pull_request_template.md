<!-- Describe the final change, not the conversation that produced it. -->
## Problem and behavior

What user action or research requirement motivated this change? Give one before/after example.

## Validation

- [ ] A regression test fails for the original defect and passes with this change, or explain why it is unnecessary.
- [ ] `python scripts/quality_gate.py --mutations` passes; attach its actual report.
- [ ] Changed AI behavior is tested with mocked responses and invalid plans.
- [ ] Data source, denominator, time window and deduplication rules remain explicit.
- [ ] Package contains source and approved benchmark fixture; no `.env`, personal resume, local database or raw private collection.
- [ ] Document and presentation claims match the current code and recorded measurements.

## Review

Reviewer: <!-- actual person; leave blank until review happens -->

- [ ] Logic, boundary cases, exception handling and input/output validation reviewed.
- [ ] Naming, functions/classes, duplication and technical-debt impact reviewed.
- [ ] Reviewer reproduced the relevant checks and recorded unresolved concerns.

## Limitations and follow-up

State meaningful limitations, debt item IDs, and manual checks still pending. AI-generated implementation or review must be disclosed; it is not a substitute for a named student's independent review.
