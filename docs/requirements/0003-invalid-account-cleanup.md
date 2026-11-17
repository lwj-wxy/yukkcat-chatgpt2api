# 0003: Manual cleanup of invalid accounts

Status: pending-verification

- Owner: AccountService and the Accounts page
- Created: 2026-11-17
- Updated: 2026-11-17
- Related ADRs: 0001, 0004

## Problem and scope

Administrators need to identify and clear invalid Upstream Accounts across pages. The Accounts list displays abnormal accounts and accounts with unknown image quota, including unsynchronized imports, as invalid. The status filter and the button beside the batch menu cover the same accounts. Accounts with unlimited image quota qualify only if their status is abnormal.

## Behavior and ownership

- The account projection owns quota and status classification. `AccountService` applies those classifications to preview and deletion. The Account Repository stores the same account records as before.
- An administrator previews the deletion count, then confirms the previewed management IDs once. The service rechecks eligibility before a single batch mutation. A concurrent storage change that conflicts with the mutation requires a fresh preview.
- The Accounts page owns the confirmation dialog, disabled state during the operation, and list refresh. It displays a zero-result message when no accounts qualify.
- The management projection leaves stored account status, scheduling, automatic cleanup, and import cleanup rules intact. No schema migration or new ADR is required.

## Acceptance and verification

| Acceptance criterion | Verification |
| --- | --- |
| Unknown and abnormal accounts qualify across pages. Known quota, rate-limited and unlimited accounts are excluded unless abnormal. | API contract tests with isolated accounts |
| Unknown quota rows display the invalid label in both status and quota columns and appear under the invalid filter. | API contract and browser checks with isolated accounts |
| Confirmation deletes the previewed accounts that still qualify. Storage conflicts cannot delete a concurrently recovered account. | API and storage integration tests |
| The toolbar button shows the count, supports cancellation and refreshes the list on success. | Browser test with isolated data and desktop and mobile viewports |

The Python suite passed 14 tests, including the cleanup API, repository conflicts and the invalid status filter. The frontend build passed. Browser checks at 1440 × 900 and 390 × 844 verified the cross-page preview, cancellation, deletion and refreshed list, plus the invalid row labels, filter and merged preview count. User acceptance is pending.

Rollback restores the prior application code. Account deletion uses the existing permanent deletion behavior.
