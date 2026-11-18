# 0004: Recover image file groups from conversation results

Status: pending-verification

- Owner: image protocol services
- Created: 2026-11-17
- Updated: 2026-11-18
- Related ADRs: 0002, 0003

## Problem and user outcome

A reference-image edit asking for three separate images was executed three
times. Two conversations returned sandbox WebP links but were classified as
text-only results. Users should submit their existing prompt and reference;
they must not select a cropping mode or supply crop coordinates.

## Scope and non-goals

Recover terminal assistant PNG/JPEG/WebP/GIF files from the authenticated
current conversation. For multi-image Conversation edits, execute the first
attempt before allocating subsequent execution slots. Single images are held
as candidates; a later multi-file group supersedes them. A result group stays
within one conversation and never exceeds the requested count. A group with fewer
images remains partial; do not combine it with another execution's slices.

No local cropping, keyword intent classifier, new user controls, changes to
account eligibility/automatic cleanup, storage migration, or deployment.
Generation without references and Codex/SVG paths retain their scheduling.
Single-result edits execute successive variants serially and can take longer
than the previous parallel execution. One request-wide deadline bounds them.
The system cannot infer that a native single image is an unwanted collage.
If a multi-image edit has one stable native candidate and the active branch
still has an intermediate message, probe that conversation every two seconds
for up to eight additional seconds before accepting the candidate. A published
group wins immediately. The existing request and poll deadlines still apply.

## Unique owners and Interfaces

| Concern | Owner | Interface |
| --- | --- | --- |
| Current turn and failure semantics | image_failure | current_conversation_turn, ImageFailure |
| Artifact provenance, resolution, validation | OpenAIBackendAPI | resolve_conversation_image_urls, download_image_bytes |
| Request budget and scheduling | protocol/conversation | stream_image_outputs_with_pool |
| Public URL and DNS safety | utils/image_download_urls | validation and pinned curl options shared with input downloads |
| Publication and catalogue | ImageStorageService | existing formatting/storage path |

Public image request/response shapes and frontend interactions remain unchanged.
The log attempt contract adds `result_image_count` and `result_disposition`,
with defaults for attempts recorded before this change.
No persistent schema changes and no new dependencies are required.

## Failure and security behavior

Only the latest terminal assistant of the current turn may publish sandbox
images. Markdown links to `/mnt/data/` use the same conversation-bound resolver
as `sandbox:/mnt/data/` links. User attachments, other branches, previous turns, arbitrary text URLs,
and intermediate tool files do not qualify. Explicit policy failures remain
failures. File resolution is bound to conversation ID and message ID. Missing
files and invalid image bodies are delivery failures, not invalid accounts.
Temporarily missing URLs receive up to five same-conversation probes for a group (four for a single file), retaining
resolved URLs, within 30 seconds and the remaining request/poll deadline.
Authentication failures stop immediately. Log normalization preserves delivered
counts and superseded dispositions; retry sleep is counted only as polling wait.
Each file URL lookup records its candidate index, probe round, elapsed time,
result and available HTTP timings on the attempt's resolve event. Concurrent
lookups overlap. Their durations are diagnostic and are not added to the
group's wall time. Up to three sandbox lookups run concurrently, reusing the
polling thread's connection and keeping worker threads across readiness retries.
Public asset downloads use public DNS address pinning, no account credentials,
bounded redirects, timeouts and byte limits. Valid results survive another
variant's text-only failure. Existing account slot cleanup remains authoritative.

## Acceptance and verification

| Criterion | Evidence | Status |
| --- | --- | --- |
| Three files from one edit produce one ordered group | Isolated protocol regression | passed |
| Text-only SSE can reach authenticated file resolution | Stream regression | passed |
| Previous/user/other-branch files cannot become outputs | Provenance regression | passed |
| Missing files/HTML/private redirects are rejected | Download regression | passed |
| Singles and later groups respect count and partial results | Group-selection and log-projection regression | passed |
| Log details satisfy the strict HTTP response contract | CallDetail validation for grouped and superseded attempts | passed |
| File readiness and log normalization | Same-conversation retry, deadline, authentication, timing and LoggedCall storage-boundary regression | passed |
| Existing backend behavior | Complete local pytest suite, 50 passed | passed |
| Historical file recovery with the new methods | Separate server process resolved and decoded 3 WebP files, without changing the running service | passed |
| Fresh generation before readiness retry fix | One HTTP request returned three decoded WebP images in 107.6 seconds after one account switch | passed |
| Fresh generation after readiness retry fix and user outcome | Live request and user verification | pending |

The six final-reply files from the two historical text-only attempts were also
independently downloaded and verified. This establishes recoverable artifacts,
not that every future upstream generation will produce the intended image set.
The checks above did not include browser inspection. Rollout verification is
separate from user acceptance.

## Documentation and rollback

Update the upstream SSE reference, failure handling, critical-flow map and
Unreleased changelog. No new ADR is required because ownership and persistence
remain unchanged. Reverting these code changes restores previous scheduling
and parsing; no data migration is needed.
