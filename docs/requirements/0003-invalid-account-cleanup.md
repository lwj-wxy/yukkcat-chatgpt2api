# 0003: Manual cleanup of invalid accounts

Status: pending-verification

- Owner: AccountService and the Accounts page
- Created: 2026-11-17
- Updated: 2026-11-17
- Related ADRs: 0001, 0004

## Problem and scope

Administrators currently select accounts manually to delete them. Add a button beside the batch menu that previews all abnormal Upstream Accounts and all accounts whose projected image quota is unknown, including unsynchronized imports. Preview spans the entire account pool. Accounts with unlimited image quota qualify only if their status is abnormal.

## Behavior and ownership

- The account projection owns quota and status classification. `AccountService` applies those classifications to preview and deletion. The Account Repository stores the same account records as before.
- An administrator previews the deletion count, then confirms the previewed management IDs once. The service rechecks eligibility before a single batch mutation. A concurrent storage change that conflicts with the mutation requires a fresh preview.
- The Accounts page owns the confirmation dialog, disabled state during the operation, and list refresh. It displays a zero-result message when no accounts qualify.
- Scheduling, automatic cleanup, account status labels, and import cleanup retain their existing rules. No schema migration or new ADR is required.

## Acceptance and verification

| Acceptance criterion | Verification |
| --- | --- |
| Unknown and abnormal accounts qualify across pages. Known quota, rate-limited and unlimited accounts are excluded unless abnormal. | API contract tests with isolated accounts |
| Confirmation deletes the previewed accounts that still qualify. Storage conflicts cannot delete a concurrently recovered account. | API and storage integration tests |
| The toolbar button shows the count, supports cancellation and refreshes the list on success. | Browser test with isolated data and desktop and mobile viewports |

The Python suite passed 13 tests, including the cleanup API and repository conflict checks. The frontend build passed. Browser checks at 1440 × 900 and 390 × 844 verified the two-page preview, cancellation, confirmation, the refreshed list and the empty preview. User acceptance is pending.

Rollback restores the prior application code. Account deletion uses the existing permanent deletion behavior.
