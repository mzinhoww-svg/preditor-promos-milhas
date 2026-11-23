# Loyalty Intelligence v2.1 — T0 execution
Date: 2026-11-23. Scope: isolated branch, no production changes.

## Verified starting point
- Existing predictor: Livelo → Smiles PoC, documented in STATUS.md (2026-10-14).
- No verified production deployment, current worker, or operational forecast accuracy.
- Loyalty News governance repo describes a conditional R0 gate; no automatic production deployment is authorized by that repo's current state.

## Independent implementation contracts
1. Live Sentinel: append-only source observations with observed_at and source timestamp distinct.
2. Temporal Evidence: announcement, effective start, publication and system discovery are separate intervals.
3. Forecast Preregistration: immutable predictions, hash, as_of timestamp and explicit experimental label until calibration.
4. 36-edge coverage: each pair ACTIVE, NO_ACTIVE_FOUND_AFTER_CHECK or NOT_CHECKED; absence of checking is not absence of offers.
5. Reaction analysis: sequence is not causation; placebo and red-team required before likely_response.
6. Economics: null if purchase cost cannot be substantiated; never manufacture CMI.
7. Operational safety: no secrets in repo, no paid API invocation, no production deployment from this branch.

## Next actions
- Connect approved runtime and mailbox, identify live operational repository and approved Supabase project.
- Validate baseline tests and migrations in isolated environment.
- Implement official/RSS/email collectors with robots and rate-limit checks.
- Publish first preregistration only when data and immutable timestamp evidence are available.

This is an engineering work branch, not a claim that workers or bots have been deployed.
