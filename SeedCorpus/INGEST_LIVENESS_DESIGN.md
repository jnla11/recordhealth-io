# INGEST_LIVENESS_DESIGN.md — Ingest Liveness, Spend, and Observability Design (v1)

Status: DRAFT v1
Last verified: 2026-07-29

**Provenance:** produced across two Fable design sessions on 2026-07-29; revised against audits of F-NEW-MR and the duplicate-ingest question.

---

## 0. Verification of the ruling's claims (two corrections, one incompleteness)

The four historical claims all check out: F-NEW-KO's design doc rules server-owned recovery (INGEST_FAILURE_POLICY_DESIGN.md, with §D's one-automatic-resubmit as an interim); F-NEW-KU Phase 3 (865166c/001449f) deleted that client resubmit machinery — ROADMAP:2249 records it as "retired in favor of the fully server-owned recovery it was always meant to hand off to," and ARCHITECTURE.md:681 records the owner ruling "no client ever resubmits" as applied without exception; the 2026-07-23 UX ruling is at ARCHITECTURE.md:675 (reverses F-NEW-KP ruling D); `.freshSubmission` is at :671 with exactly the claimed safety argument, resting on `DEDUPE_TERMINAL_STATES` at ingest-queue-state.mjs:94-97. Note §3.8 currently holds both ":681 no client ever resubmits, without exception" and ":671 the client re-uploads on manual retry" — this ruling resolves that internal contradiction; the doc amendment should say so.

**Correction 1 — "matches with no age bound" is true of the in-flight arm only, and it explains F-NEW-MU only indirectly.** `findDuplicate` (ingest-queue-state.mjs:201-213) has two arms. The in-flight arm (queued + active entries) has no age bound. The completed arm is bounded at `RECENT_TTL_MS` = 15 minutes (:24, :217-221) — a completed job of arbitrary age cannot be adopted through the recent ring as written. The mechanism that fits the MU incident is an entry stuck in active whose job DO had in fact completed (the coordinator's reconcile never retired it), matched by the ageless in-flight arm, with the result blob still present because F-NEW-MJ's GC doesn't exist. So the in-flight arm resolves MU's mystery only jointly with a reconcile stall — which is itself an instance of the liveness failure this parent design fixes. MU's audit half should confirm the entry was in active; the design below moots the current mechanism either way.

**Correction 2 — there is not one R2 deletion site, there are four, and two of them delete on exactly the failures we must now retry.** The ruling names the post-createMeta delete (ingest-do.js:1795-1801, confirmed). Additionally the coordinator deletes parked bytes at: the /enqueue rollback (ingest-queue-do.mjs:251 — this one stays; custody was never confirmed to the phone), retireToRecent-to-failed paths including coordinator-failed and dispatch failure (:481, :524 — these must go; those are retryable failures under B), and blocked-entry expiry. There is also a live R2 lifecycle rule `expire-park-2d` (prefix `park/`, 172800s — wrangler.toml:17-24) that hard-deletes everything at 2 days. Any retention design that doesn't reconfigure that rule silently reintroduces re-upload on day 2. It is dashboard config, not code — it needs an explicit deploy step.

**Incompleteness — no deletion surface exists to hang the edge-case rulings on.** The Worker has no record-deletion, app-data-deletion, or account-deletion endpoint (verified by route grep). E's rulings below therefore specify new surface, flagged as a dependency.

One boundary confirmation the ruling asked for: the custody point is the R2 put inside /enqueue (ingest-queue-do.mjs:212-233, sha256-sealed, server-recomputed). The 202/409 response is the checksum confirmation. If the phone never received that response, the server may or may not hold the bytes, and the phone must retain and resend — confirmed outside this ruling's scope, and the design keeps that path.

---

## 1. Liveness contract: the step lease

Every phase — parse, extract, assembly, repair, and any future phase — runs its expensive work as a sequence of steps, where a step is one vendor round trip or one bounded local operation. The contract:

1. **Claim before work.** A phase attempt begins with a persisted, OCC-guarded claim that bumps that phase's generation.
2. **Renew before every paid step, declaring the step's budget.** Before each step, the invocation calls `renewLease(phase, gen, stepName, stepBudgetMs)` through `applyMeta`. The renewal sets the phase's watchdog to now + stepBudgetMs + slack. A Bedrock section call declares ~120s; a poll declares ~15s; a shard-write batch declares ~10s.
3. **The step enforces its own declared budget.** Every vendor fetch runs under an `AbortController` with timeout = the declared budget.
4. **Renewal failure = claim lost = stop before spending.** `renewLease` returning not-ok means the invocation aborts immediately. This is the pre-spend fence.
5. **Watchdog fires only on lease expiry.** An expired lease means either the invocation died mid-step, or a step overran its self-enforced timeout, which is a bug not an operating mode.

Stuck = a lease that expired without renewal. The wall clock only enters through per-step budgets.

Why per-step declaration rather than a bigger flat watchdog: a flat 10-minute watchdog would stop false reverts but make genuine death detection take 10 minutes for a job that died during a 3s poll. Declared budgets give fast detection for cheap steps and correct tolerance for expensive ones, from one mechanism.

The Bedrock no-interior-checkpoint constraint is accepted. A single section call has no interior progress signal; the lease budget covers the whole call and the AbortController bounds it. Detection latency for death-mid-Bedrock-call is the declared budget. Deliberate tradeoff: slower detection of one dead job, in exchange for making false reverts structurally impossible.

**Death detection and reclaim:** DO eviction / deploy / crash mid-call → no renewal → the alarm fires `expireLease` → revert to WAITING/re-claimable, gen bumps on the next claim, attempt counter draws from the job budget. Reclaim speed = declared step budget + slack. Depends on DO alarms surviving eviction and restarts.

**Generations stay per-phase.** Parse and extract are genuinely concurrent arms; a unified job-level generation would force serialization. What unifies is the mechanism: one claimLease/renewLease/completeLease/expireLease applier family replaces the four hand-built variants. Per-phase watchdog keys collapse into one `leases[phase] = {gen, step, deadline}` shape. Attempt counting unifies into the job attempt budget, so layers can no longer multiply.

**Correlation ID:** root is `jobId`, minted at `/v1/ingest/start`. Attempt id is `{jobId}:{phase}:{gen}`, derivable, labeling every lease renewal, ledger row, log line, and phase event row. Propagation via an `X-RH-Job-Id` header on every internal DO hop, already embedded in LlamaCloud webhook URLs, recorded against the vendor job id in the spend ledger at submit time. Neither vendor accepts a client correlation tag on the call itself.

Conformance checklist for any new phase:

1. Claims via `claimLease` before any work; the claim bumps gen and draws an attempt from the job budget.
2. Every network call is preceded by a `renewLease` naming the step and its budget, and runs under an `AbortController` set to that budget.
3. No await on a non-storage operation between reading meta and acting on it without re-validating through `applyMeta`.
4. Every vendor call writes a ledger intent row before the call and a result row after.
5. Completion and failure both go through OCC-guarded appliers keyed on (phase, gen).
6. Every terminal path classifies into the failure taxonomy and cancels live controllers via the abort registry.
7. All shards it writes are gen-tagged with its lease gen; it registers its shard bases in the sweep floor table.
8. No PHI in any log line, ledger row, or event row it emits.

---

## 2. Retry and spend policy

**The spend ledger:** a per-job, append-only ledger in DO storage. Before any vendor call, write an intent row `{attemptId, vendor, op, estUnits, unitType, t}`. After it returns, write a result row `{attemptId, vendor, op, actualUnits, vendorJobId?, errorClass?, t}`. Rules:

- Intent writes are fenced: they happen inside/immediately after a successful `renewLease`, so a superseded invocation cannot record new intent and therefore cannot make the call.
- Once written, ledger rows are never dropped or gen-guarded. They record what happened, including a loser generation's spend. This fixes "the most expensive runs record zero": usage no longer rides the completion write.
- Ledger rows are storage writes, so they are cheap and OCC-safe by construction.

The ledger is simultaneously the attempt counter, the spend meter, the idempotency record, the cost-attribution source, and the `llama_parse_calls` fix.

**Single attempt budget, all layers draw from it:**

- Vendor submits: hard cap approximately 2 each per job, ever, across all layers and generations, counted as ledger intents, so a submit that died ambiguously still counts as spent. LlamaCloud has no idempotency keys, so the rule is "an intent row of unknown outcome is presumed billed." On reclaim after an ambiguous submit, poll the vendor job id if captured, else burn the attempt, never blind resubmit.
- Bedrock calls: `callBedrockWithRetry`'s internal 3-attempt loop stays but takes a budget hook; each physical invocation records a ledger intent and checks the job's Bedrock-call and token ceilings first.
- Watchdog reclaims: an expired lease's re-claim draws an attempt.
- Phone resubmits: governed by admission control, not the job budget.

**Hard spend ceiling**, vendor-native units, two per-job ceilings checked at intent-write time, terminal on breach:

- LlamaCloud credits: ceiling = pages_estimate × per-page rate × submit cap × safety factor. Locked now (ruling 1) — enforced from rung 1.
- Bedrock tokens: running sum of ledger actualUnits plus projected cost of the call about to be made. Deferred (ruling 1): no real cap is enforced until rung 1's own ledger data gives a basis for one. Rung 1 ships with a deliberately loose placeholder ceiling that logs breaches without terminating the job — it observes, it does not gate. This dependency carries forward into F-NEW-MX and F-NEW-MY.

Because the check happens at intent time and intents are fenced, unbounded spend requires either a ledger bypass or a vendor billing us for calls we never made. Exact numeric values for both ceilings remain an open ruling; what's locked is that LlamaCloud enforces from the start and Bedrock does not until rung-1 data exists.

**Circuit breaker per vendor boundary.** Breaker state must be cross-job and cross-user, so one VendorHealthDO per vendor, consulted before submits:

- Trip: 3 consecutive deterministic-vendor failures (402, 401/403) trips immediately; 5 transient failures within 5 minutes trips for transients.
- Open behavior: submits are not attempted. The queue entry parks as blocked with reason `vendor_unavailable`, reusing the F-NEW-KO blocked-entry machinery. The user-facing meaning is locked (ruling 4): "Processing delayed due to server issues. We will resolve and process your records shortly. No action is needed on your part." Exact wording is deferred to F-NEW-MV — design against the meaning, not the string.
- Probe: half-open admits one real job on a backoff schedule (60s doubling to 15 min). Probe success closes the breaker and pokes coordinators to re-evaluate blocked entries.
- One extra DO hop per submit. Submits are rare; acceptable.

**Admission control:** instant slot refill stays for successes. For failures, the terminal path gains a failure-class-keyed cooldown in the recent ring:

- vendor_fault / our_timeout / spend_cap: resubmit of the same content_hash is held for 15 minutes (locked ruling 2).
- document_fault: no clock (locked ruling 2) — resubmit stays blocked until something changes on our side (prompt version, app version, pipeline version), never merely until a timer expires.
- superseded / canceled: no cooldown.
- The slot itself still frees immediately; cooldown gates admission of the same bytes, not slot capacity.

**F-NEW-MS fold-in, the failure-signature memo:** each failed step records a failure signature = hash of (section_id, error_class, stable error discriminator). Retry/repair eligibility excludes any unit whose signature has already failed 2 times across all generations and tiers. Two, not one, because Bedrock output is nondeterministic. A second identical failure parks the section terminal.

**Tension with the 2-revolution cap:** no conflict, orthogonal axes. The revolution cap bounds across-pass re-ingests; the signature memo bounds within-repair identical retries; the job budget bounds within-job total attempts. Worst-case total spend per record = revolution cap (2) × per-job ceiling. Signature memos do not carry across revolutions.

---

## 3. Supersession and fencing

Within one DO instance, superseded work can be stopped. All events for a given DO id are delivered to the same in-memory object instance, and `AbortController` works on in-flight `fetch` in Workers. The DO keeps an in-memory abort registry: `this.liveRuns: Map<"{phase}:{gen}", AbortController>`. When a re-claim bumps a gen, or `markTerminal` runs, the caller aborts every registered controller for older gens.

**Limits:** the registry is memory-only, so it does nothing across eviction/deploy, but in that case the old invocation is dead. It cannot claw back vendor-side spend: Bedrock bills tokens already generated, and LlamaCloud has no cancel endpoint for the per-job parse/extract API (cancel exists only on the beta batch API).

**Fence placement, three layers:**

1. **Pre-spend fence (new, primary):** `renewLease` + budget check + ledger intent before every paid call.
2. **Active abort (new):** the registry above.
3. **Write fence (existing):** OCC-guarded completion, now protecting state consistency only.

**Partial work of a superseded generation:** discarded, with one exception: content-addressed section checkpoints — locked ruling 3, BUILD, not defer. Reasoning: a restart must not re-pay for sections that already succeeded. The Atom Pass gains section checkpoints keyed by (content hash of section input, prompt version) rather than generation, so any later generation reuses a completed section for free. Converts the worst multiplier into at-most-once per section per prompt version. (Ladder placement: Rung 6.)

**Terminal-while-live:** allowed, with a defined cleanup obligation. `markTerminal` and `notifyIfNewlyTerminal` acquire three obligations: abort all registered controllers; rely on lease renewals to fence unreachable stragglers; schedule the post-terminal sweep.

**Orphan shard reclamation:** sweep moves from "inside `assemble()` only" to the terminal transition itself. On any terminal, the DO schedules one final alarm at t + grace that deletes every shard except, for successful jobs, the winning-gen result shard.

---

## 4. Observability

Two surfaces. Logs reconstruct one job's path. Metrics/events answer "is ingest slow today" and live in Postgres via the NCC pattern: strict column allowlist, no free-form JSONB, scrubbed, waitUntil, observe-never-gate.

NCC is the right surface and needs extension, not replacement. It gains three panels: ingest health, queue/concurrency, and spend. It does not do alerting/paging.

**Two new tables:**

- `ingest_phase_events`: one row per phase transition (claimed, completed, expired, failed, superseded), carrying job_id, phase, gen, event, duration_ms, step_count, error_class, environment, t. Not per-step, not per-poll. Roughly 10 rows/job. "Which stage of which phase is slow" comes from duration_ms per phase plus a slowest_step column stamped at completion. Granularity is locked (ruling 5): staging carries full per-step detail permanently; production carries transitions only for successful routine work, plus full step detail on anything that fails.
- `ingest_spend_events`: the ledger flush, per attempt, per vendor, units + unit type + vendor job id. Flushed at terminal by the DO, and by the existing sweeper for jobs whose DO died before flushing. Spend is recorded in DO storage at intent time and exported at terminal-or-sweep. `ingest_jobs` cost columns become a rollup of ledger rows.

**Queue and concurrency:** the coordinator emits transitions to the same phase-events table (enqueued, dispatched, blocked(reason), terminal), with waited_ms stamped at dispatch. Queue depth over time falls out of event timestamps in SQL. Current-state is a small live admin route.

**Failure classification**, one taxonomy stamped at every terminal: vendor_fault, vendor_billing, vendor_auth, our_timeout, document_fault, spend_cap, superseded, canceled, unknown_crash. The classifier runs where the information exists, not at the terminal write.

**Log volume:** state transitions and errors always logged, structured, one line each. Per-poll and per-heartbeat logging removed. Payload-bearing diagnostics removed. Workers Logs bills per event and sheds under load with short retention, therefore nothing operational may depend on logs.

**PHI:** event tables have strict column allowlists, ids/enums/counts/durations only. No document text, section titles, atom values, filenames, or vendor payloads in any event, metric, or log line.

---

## 5. Verification

F-NEW-MP (replay harness) must record/replay at the HTTP boundary, not at adapter-output level, because the things this design most needs tested live between our logic and the wire. MP must provide: an injectable fetch seam in the vendor helpers; scripted fault sequences (N consecutive 402s, ambiguous submit, slow response exceeding a declared budget, a poll sequence that never completes); virtual time driving the alarm loop; recorded real fixtures from staging for happy paths.

**Per-rung verifiability:** pure appliers under `node --test`, call-site invariants enforced by grep-able rules, end-to-end behavior under the MP harness with scripted faults.

**F-NEW-MW sequencing confirmed:** MW's fix adds a new paid-submit call site and must not land before the fence exists. Refinement: MW needs only rungs 1-3, so it can ship mid-ladder.

---

## A. Document retention

*(Absorbs F-NEW-MJ; F-NEW-MU's adoption dependency becomes explicit.)*

One retention mechanism, two artifact classes, one clock. A job owns two durable artifacts: the source bytes in R2 (`park/{userId}/{jobId}.pdf`) and the result/working shards in DO storage. Both are governed by a single per-job retention state, recorded in the coordinator entry and mirrored to `ingest_jobs` (columns `retention_state`, `delete_after`) so retention is queryable and auditable. F-NEW-MJ's GC is this mechanism — it does not get a second one. The MJ owner ruling (2026-07-25: delete after client-confirmed receipt via `fetched`, plus a grace window, without breaking repair) is honored as the success arm below.

The clock and the triggers:

- **Clock starts at the custody point.** The source object lives as long as the job is non-terminal or terminal-retryable (per B). This deletes the post-createMeta delete at ingest-do.js:1800 and the coordinator's failure-path `deleteParked` calls — the bytes are no longer "released to the job DO," they are the job's recovery root.
- **Success:** delete source bytes AND result shards together at `fetched` + grace. Grace proposed at 72 hours after ack (owner number, flagged). Rationale for deleting source on success at all: the device is the system of record and retains the document; post-success server retention has no recovery purpose, only PHI liability. The repair executor operates on shards, and repair concludes before terminal success — the MJ constraint ("GC must not break repair") is satisfied by keying deletion to terminal-plus-ack, which is strictly after repair ends.
- **Unacked success (abandonment):** no `fetched` ever arrives (app deleted — iOS provides no uninstall signal). Retention cap: 30 days from terminal, then delete both artifact classes and mark the job `failed_final(retention_expired)` if unacked-failed, or leave complete with artifacts gone if unacked-success. 30 days is the abandonment definition (owner number, flagged).
- **Terminal-retryable failure:** bytes retained for the same 30-day window from last state change. The window restarts on any server retry (state changed). This window is also the outer stopping rule for fix-gated failures (B).
- **Genuinely final failure (B's list):** artifacts deleted at final-transition + a short grace (72h, same knob) — kept briefly only so a just-failed job's forensics (staging replay via F-NEW-MP fixtures) can capture what's needed; production forensic value lives in the ledger and phase events, which are PHI-free and retained.
- **User deletion (record / account):** immediate deletion, no grace — E.1/E.6.

The lifecycle rule becomes a backstop, not a policy. `expire-park-2d` is raised to 45 days (retention max 30d + margin) and kept — it is the guarantee that a crashed coordinator can never leak an object forever. Enforcement of the real policy is a coordinator sweep (the existing alarm loop already visits entries; the recent-ring prune extends to artifact deletion at `delete_after`). **Deploy-order constraint:** the lifecycle change must land before any code stops eagerly deleting, or nothing; but code must not start relying on retention until the rule is raised — this is Rung 0 in the ladder.

**Compliance posture.** This changes PHI-at-rest duration, not category — raw un-tokenized health documents already sit in this bucket up to 2 days; they will now sit up to ~30. Stated implications: (1) R2 server-side encryption (AES-256, Cloudflare-managed keys) covers the objects, but the Cloudflare BAA must be verified to cover R2 — this joins the existing release-checklist BAA verification item (flagged, blocking for this design's ship, grouped with F-NEW-MJ's launch-blocker status). (2) Access is exclusively via the coordinator/job-DO service path; no admin listing or fetch route over `park/` exists and none may be added without an owner ruling. (3) The keying (`park/{userId}/{jobId}.pdf`) means account-scoped enumeration for deletion is a prefix list — deliberate, keep it. (4) This deepens the already-noted tension with the local-first framing in ARCHITECTURE.md; the ruling accepts server custody explicitly, and the doc amendment should record that the "processing pass-through" description is superseded by "custody until success-ack or retention expiry."

**Storage cost.** R2 at ~$0.015/GB-month: at a generous 5 MB/document and 10,000 documents simultaneously inside a 30-day window, ~50 GB ≈ $0.75/month, plus negligible class-A/B ops. Storage is not the spend story; one avoided duplicate LlamaParse of a 29-page agentic-tier document pays for months of it. The binding constraint on the retention window is compliance surface, not dollars — which is why the design does not lean toward "keep forever."

**F-NEW-MU interaction:** adoption (§C) is gated on artifact existence, checked inside the coordinator DO in the same single-threaded turn that would retire or delete — the "adopts against stored result blobs" behavior stops being an accident of missing GC and becomes a checked precondition.

---

## B. Failed is no longer terminal-dead

**State model.** `failed` splits into `failed_retryable(class)` and `failed_final(class)`. A retryable job's DO meta and coordinator entry persist (with artifacts, per §A). Re-entry into processing is mechanically a lease re-claim with a bumped generation — the same claim/renew/complete machinery from §1; no new execution path. The job keeps its `job_id` forever. Alternative considered: mint a fresh job per retry and link them — rejected because it breaks the phone's bookmark invariant, the dedupe identity, and the whole-job spend ledger, for no benefit; the generation counter already provides attempt identity (`{jobId}:{phase}:{gen}`).

Who moves a failed job back, by failure class:

| Class | Mover | Mechanism |
|---|---|---|
| vendor_fault, our_timeout, unknown_crash | Server, automatic | Coordinator-scheduled retry with backoff (15 min first, doubling; the ruled 15-minute cooldown is the floor) |
| vendor_billing, vendor_auth | Server, breaker-mediated | Parks as `blocked(vendor_unavailable)`; the VendorHealthDO's half-open probe success pokes coordinators, which re-dispatch |
| document_fault | Server, version-gated | No clock (locked ruling 2). Job stamps the pipeline/prompt/app-schema version at failure; a version-change sweep (run at deploy or by cron) re-dispatches parked document_fault jobs whose failure-version < current, once per version change |
| Any retryable class | User, via the retry control | §D's endpoint; draws the same budget, respects the same cooldowns |
| spend_cap | Owner only | Not auto-retried; a cap breach means policy said stop. Unparked only by an explicit cap change (rate-card update per F-NEW-MX/MY, or owner action). The ruled 15-min cooldown applies to admission of the bytes, not to auto-retry of the job |
| superseded, canceled, retention_expired, budget_exhausted, signature-terminal | Nobody | failed_final |

The stopping rule — three bounds, all pre-existing, now doing double duty:

1. **Failure-signature memo (§2, F-NEW-MS):** two identical failures of a unit → that unit terminal. Memos persist across server-retry generations of the same job — inputs are identical by definition. (They reset only across revolutions, locked ruling 6 — a revolution changed the inputs.) This is what makes a deterministic failure structurally unable to loop: the second identical failure converts the class to `failed_final(signature_terminal)` regardless of remaining budget. For document_fault under the version gate, a version change resets the memo for affected units — the version change is an input change.
2. **Job attempt budget (§2):** every retry — watchdog reclaim, auto-retry, breaker re-dispatch, version-sweep, user poke — draws from the one budget. Proposed: 4 dispatch epochs per job lifetime (owner number, flagged). Exhaustion → `failed_final(budget_exhausted)`.
3. **Vendor billed-submit cap (§2):** unchanged at ~2 billed submits per vendor per job across all generations, counted as ledger intents. One refinement forced by retryability: a known-unbilled deterministic rejection (a clean 402/401/403 with no vendor job created) does not consume the billed-submit cap — the breaker bounds those — otherwise a credit-exhaustion outage (the exact 2026-07-28 incident) would permanently burn every in-flight job's parse budget before the breaker even trips. Ambiguous outcomes remain presumed-billed.

The outer bound for document_fault (which has no clock) is §A's 30-day retention window: if no our-side version change arrives within retention, the job exits as `failed_final(retention_expired)` with honest copy. So every failed job provably reaches a terminal user-visible truth within max(budget, 30 days).

**Budget and ceiling accounting.** Nothing new: the ledger is per-job and append-only across generations, ceilings are computed over whole-ledger sums at intent time. Server-side retry is precisely why §2 defined them per-job rather than per-attempt — this section adds no accounting machinery, only more generations. The honest terminal state carries the taxonomy class; wording is F-NEW-MV's problem, meaning is locked (ruling 4).

---

## C. Dedupe inversion

DEDUPE_TERMINAL_STATES and the recent-ring TTL as an adoption window are deleted concepts. New semantics for `/enqueue` with a colliding `content_hash`:

| Existing job state | Action |
|---|---|
| In-flight (queued / active / blocked) | Adopt: 409 with `job_id` + state. No age bound — stays (resolves F-NEW-MU's ask). The unbounded match was only ever dangerous because a job could be silently stuck forever; §1's leases remove that state from the system. Explicit dependency: rung 2 lands before or with this rung |
| failed_retryable | Adopt and treat the enqueue as a retry poke, subject to §B's cooldowns and gates. The user re-importing the file is the retry intent; it costs nothing to adopt (no bytes accepted, no spend), and the poke either schedules a retry or returns the honest parked state |
| Terminal success, artifacts still retained (pre-GC per §A) | Adopt: phone gets the completed job and fetches the result. Window = artifact existence, checked in the same coordinator turn — not a ring TTL |
| Terminal success, artifacts GC'd; or failed_final (except below) | No adoption; fresh job minted. This is a genuine new import of a document the server honestly finished with; the phone owns the bytes and sends them — that is not failure recovery and doesn't violate the ruling |
| failed_final(document_fault…) | No adoption, and admission of the same bytes is version-gated via a content-hash tombstone stamped with the failure version (this is §2's admission cooldown, re-keyed): re-admission only after an our-side version change. Waiting does not make a broken document readable (locked ruling 2), and neither does re-uploading it |

**Keying gains the patient profile.** Current matching is hash-only; `metadata.patientId` is ignored, so identical bytes uploaded under a different profile would adopt a job bound to the wrong profile's record. New key: `(content_hash, patientId)`. Tradeoff: byte-identical documents across two profiles are processed twice (double vendor spend) versus correctness of record/profile association and zero cross-profile result sharing. Correctness wins; the case is rare. (Cross-user adoption is impossible by construction — the coordinator is per-user — and stays that way; see E.3.)

**Force-fresh (F-NEW-MU's dev flag).** `metadata.forceFresh: true`, honored only when the environment sets `INGEST_ALLOW_FORCE_FRESH="true"` (staging/dev vars; never production). Bypasses adoption and tombstones, mints a fresh job. In production the flag is rejected loud (400 `force_fresh_disabled`) rather than silently ignored, so a mis-pointed test run says why it didn't do what the tester expected.

What dies with the inversion: the :94-97 comment's rationale, the 15-minute RECENT_TTL_MS as a dedupe concept (the recent ring survives only as reconcile bookkeeping), and `.freshSubmission`'s safety argument — which is fine, because §D deletes `.freshSubmission`'s mechanism anyway. The ordering matters: the dedupe inversion must not ship before §D's retry endpoint exists on both ends, or an old-app `.freshSubmission` re-upload would adopt the dead job it is trying to escape and the user's retry button would do nothing. Old-app compatibility during rollout: adoption of a failed_retryable job returns 409 with a state the old client reads as a live job to poll — acceptable, because the adopt-poke schedules the actual retry server-side; the old client's UX is merely un-improved, not broken.

---

## D. Wire and client contract

New action: `POST /v1/ingest/jobs/{jobId}/retry` (JWT auth, routed to the caller's coordinator; the coordinator owns retry admission because it owns slots and cooldowns). No body. Responses:

- `202 {job_id, state, retry_at?}` — retry admitted (immediately dispatched, or scheduled; `retry_at` when a cooldown holds it).
- `409 {error:"job_final", reason_class}` — genuinely final; phone renders the F-NEW-MV meaning for the class. Honest refusal, not an error to retry.
- `404` — the server has no such job (wiped DO, pre-retention job, or a job that never existed). This is the one corner where the phone falls back to a fresh upload — which is also the never-confirmed-upload path, confirmed still required.

A second new action: `POST /v1/ingest/jobs/{jobId}/cancel` — required by E.1 (record deletion). Marks `canceled` (final), aborts live work through the abort registry, deletes both artifact classes immediately.

**Status contract addition:** `GET /v1/ingest/status/{jobId}` gains `attempt_epoch` (the job's dispatch-generation counter). Reason: the phone's choke-point guard (772ee81) refuses working-state writes over a settled record — a server-initiated resurrection observed by a poll would be misread as exactly the stale-progress stomp that guard exists to kill. The epoch lets the client distinguish "the server legitimately revived this job" (epoch advanced → pass `recovery: true`) from a stale write (epoch unchanged). Without this field, §B's auto-retries are invisible to a phone that already settled the record.

What the phone sends, receives, polls: on retry — the job id only, never bytes, never a hash; it keeps the bookmark, does not ack (`markJobFetched`) the job, and resumes the existing 3s status poll and result fetch unchanged.

**iOS requirement list (for the app repo, requirements not design):**

1. Replace the body of `IngestRetryMode.freshSubmission`: call `/retry`; keep the bookmark; do not ack; resume polling. The ack+clear+re-upload sequence is deleted.
2. Handle the three retry responses: 202 → working ("Retrying…" copy path already exists); 409 `job_final` → needsAttention terminal with the class-mapped copy (F-NEW-MV); 404 → fresh upload (the only surviving client-upload-on-retry path).
3. Consume `attempt_epoch`; an epoch advance on a settled record re-enters working state through the choke point with `recovery: true`.
4. On user deletion of a record with a live or retryable `serverJobId`, call `/cancel`; queue the call durably if offline.
5. Tolerate additively: `blocked(vendor_unavailable)` (render the locked ruling-4 meaning), `failed_final` reason classes, `retry_at`.
6. Amend ARCHITECTURE.md §3.8: `.freshSubmission` mechanism replaced; the "dedupe excludes failed jobs" safety argument deleted; the :671/:681 contradiction resolved in favor of :681.

---

## E. Edge cases, ruled

1. **User deletes the record while a job is live or retryable:** phone calls `/cancel` → `canceled` (final), live controllers aborted, both artifact classes deleted with no grace — deletion intent outranks forensic grace; PHI minimization wins. Ledger/phase-event rows (PHI-free) are retained. App deleted: iOS gives no signal; the job runs to terminal and §A's 30-day abandonment cap cleans up. Deliberately no heartbeat-based earlier detection — an absent phone is indistinguishable from a phone in a drawer, and 30 days of encrypted storage is the cheaper error.
2. **Retention expires while parked user-actionable:** flip to `failed_final(retention_expired)`, delete artifacts, honest copy on next poll or `/retry` (409). A subsequent identical upload mints a fresh job — except a document_fault tombstone survives its job's expiry and stays version-gated (§C); re-uploading a document we deterministically cannot read must not re-spend until something on our side changed.
3. **Same bytes, different user:** no interaction, by construction (per-user coordinator, per-user R2 prefix), and this is a privacy boundary, not an optimization gap — cross-user adoption would leak one account's processing results to another on the strength of a hash. A global content-addressed processing cache is flagged as a possible future cost optimization requiring its own PHI-boundary ruling; explicitly not designed here.
4. **Same bytes, different patient profile (same user):** distinct job under the `(content_hash, patientId)` key (§C). Costs a duplicate processing run; buys correct profile binding.
5. **Adoption races GC:** structurally excluded — adoption check, retention transition, and artifact deletion for a given user's jobs all execute inside the single-threaded coordinator DO; existence is checked in the same turn that answers 409. Residual race (phone adopted, then grace expired before its result fetch): the result endpoint returns a distinct 410 `result_expired`, and the phone's 404/410 handling falls back to fresh upload.
6. **Account deletion with documents in retention:** no such endpoint exists in the Worker today (verified) — flagged as a dependency this design cannot absorb. Requirements for whoever builds it: delete the `park/{userId}/` prefix, destroy the coordinator's state, purge job-DO shards for that user's jobs, scrub `ingest_jobs` rows; PHI-free ledger export rows may be retained for accounting.
7. **Duplicate upload while blocked (balance):** in-flight arm adopts; the phone receives the blocked state and shows subscription messaging. Already correct under the inversion; noted because blocked entries live in the queued array and thus the in-flight arm.
8. **Retry storm from the UI:** `/retry` during a cooldown returns 202 with `retry_at` — adoption of intent, no spend, no budget draw (a poke that admits nothing draws nothing; only an actual dispatch epoch draws).

---

## F. Atom Pass re-entry — verified cost mechanics

Direct audit of whether a retry re-pays for already-succeeded work, produced against the live codebase to verify the claim underlying Rung 6 below.

**Files opened (and why):**

- `src/ingest-do.js` (full, 2663 lines) — the orchestrator; every entry into the Atom Pass and every re-claim path lives here.
- `src/pipeline-shared.js` lines 660–830 — `runAtomPass` itself, to check whether it does any internal per-section memoization (it doesn't).
- `src/ingest-job-state.mjs` (full) — pure state transforms (`planPollOutcome`, `planWatchdogRevert`, `deriveJobState`), needed to know exactly what a watchdog revert does to the parse arm.
- `src/ingest-occ.mjs` (full) — the OCC appliers (`doClaimProcessing`, `applyParseCompleted`, `claimRepair`, etc.), needed to confirm whether a re-claim bumps `gen` and what the completion guard actually blocks.
- grep over `src/index.js` and `src/*.js` for `runAtomPass(` — to enumerate every call site (confirmed: exactly two, both in `ingest-do.js`; the old `/v1/ingest/atoms` route was deleted per the comment at `src/index.js:14-15`).

No other files touch the repair path or the Atom Pass entry points.

### F.1 Every way the Atom Pass can be entered

`grep -rn "runAtomPass(" src/` returns exactly two call sites, both in `ingest-do.js`, plus a comment confirming a third was deleted:

**Site A — `processParse`, `src/ingest-do.js:759`**
```
const res = await runAtomPass(this.env, pagesByIndex, atomPassSections, label, provByIndex);
```
`atomPassSections` (line 753) is:
```
const atomPassSections = sections.filter((s) => !LLAMA_EXTRACT_COVERED_KINDS.has(s.kind));
```
i.e. all non-Extract-covered sections in the document, rebuilt from the codex fresh at `processParse:741-742`. This is entered whenever the parse arm is claimed into PROCESSING — from a webhook (`webhook() → applyMeta "claim" action → processParse()` at `ingest-do.js:2521`), from the alarm's poll loop (`alarm() → toProcess.push("parse") → processParse()` at `ingest-do.js:2647`), or from a watchdog-reverted re-claim (see §F.4). Section set: ALL sections, every single time, with no reference to any prior run's outcome.

**Site B — `_repairAttemptBody`, `src/ingest-do.js:2139`**
```
const res = await runAtomPass(this.env, pagesByIndex, failedSections, label, provByIndex);
```
`failedSections` (line 2125) is:
```
const failedSections = sections.filter((s) => eligibleIds.has(s.id));
```
where `eligibleIds` comes from the persisted `repair:<section_id>` records filtered by error class (line 2122-2124). Entered only from `runRepairAttempt`, itself entered only from `driveRepairAlarm` (Tier 1, alarm-driven) or the dormant `/repair` route (Tier 2, sweeper-driven) — both of which require `jobState === COMPLETE_PARTIAL` (`claimRepair`, `ingest-occ.mjs:507`). Section set: only the sections still marked failed/failed_repairable.

**Retired third site:** `src/index.js:14-15` — "`runAtomPass` was dropped when `POST /v1/ingest/atoms` was deleted — the DO is now its sole caller." No live code path there.

`runAtomPass` itself (`pipeline-shared.js:713`) has zero internal skip/memoization logic — it partitions only on `ATOM_PASS_SKIP_KINDS` (non-atomic section kinds, e.g. table-only sections handled elsewhere), then calls Bedrock once per remaining section unconditionally (`pipeline-shared.js:717-804`). Any "run only what's needed" behavior is entirely the caller's responsibility — there is no cheaper path inside the function.

### F.2 Section-level reuse — does a succeeded section ever get skipped on a later run?

Only on one of the two entry paths. The `section_status` shard is written unconditionally by `processParse` (`ingest-do.js:780`) but `processParse` never reads it — grep confirms the only reads are at `ingest-do.js:1105` (`assemble()`, merging PHI failures) and `ingest-do.js:2116` (`_repairAttemptBody`, selecting which sections to re-run). So:

- **Via `processParse` re-entry:** no reuse mechanism exists. Every claim reruns the Atom Pass over the full section list, full stop.
- **Via the repair path:** yes, `_repairAttemptBody` reads `section_status@{resultGen}` (line 2116) and re-runs only the sections flagged failed/failed_repairable in it (line 2122-2125).

### F.3 The repair path specifically

Reused inputs, from storage — no LlamaCloud calls of any kind:
```
const codexPages = (await this.readJsonSharded(keys.codex)) || [];
const sections = (await this.readJsonSharded(keys.sections)) || [];
const priorResult = (await this.readJsonSharded(keys.result)) || null;
```
(`ingest-do.js:2117-2119`) — all read from DO storage shards written by the original `processParse`, never re-fetched from the vendor.

Granularity: section-level. `runAtomPass` is called with only `failedSections` (line 2139), and downstream PHI classification is scoped the same way — `runPHIClassification(this.env, repairedAtoms, sections)` (line 2153) receives only the newly-produced `repairedAtoms`, not the full atom set. KT coding likewise runs only `repairedAtoms` (line 2189). Result "surgery" then splices the fresh atoms over the survivors of the prior result (lines 2174-2182) rather than rebuilding it.

**Answer: Bedrock per failed section only, not a broader pass. Claim A is correct for this path.**

### F.4 The parse-arm re-claim path specifically

`planWatchdogRevert` (`ingest-job-state.mjs:150-157`) reverts a stuck PROCESSING parse arm to WAITING, not IDLE:
```
return submitting ? "revert-idle" : "revert-waiting";
```
`applyWatchdogDecision` (`ingest-occ.mjs:383-386`) applies it: `meta.arms[arm].state = ARM_STATE.WAITING;`. The parse arm keeps its LlamaCloud job id, so the next alarm poll re-observes the (already-completed) upstream job:
```
// planPollOutcome, ingest-job-state.mjs:130-133
if (status === "COMPLETED") {
  if (arm === "extract" && parseState !== ARM_STATE.DONE) return "park";
  return "claim";
}
```
That "claim" re-enters `doClaimProcessing` (`ingest-occ.mjs:114-121`), which unconditionally bumps the generation:
```
a.state = ARM_STATE.PROCESSING;
a.gen = (a.gen || 0) + 1;
```
and the alarm then calls `processParse()` again (`ingest-do.js:2647`). Inside `processParse`, the section set is recomputed from scratch — same as §F.1 Site A:
```
const codexPages = buildCodexFromParsedPages(adaptedPages).pages;
const sections = buildSectionsFromCodex(codexPages);
...
const atomPassSections = sections.filter((s) => !LLAMA_EXTRACT_COVERED_KINDS.has(s.kind));
```
(`ingest-do.js:741-753`). It receives the full section set, identical to the first invocation — there is no diffing against a prior attempt's `section_status`. The only guard that can short-circuit this re-entry is the chain-mode idempotency check at `ingest-do.js:715-718`, which bails only if Extract has already advanced past IDLE — it says nothing about whether the Atom Pass itself already ran; if the first invocation is still in-flight (its Extract chain-submit hasn't landed yet), the guard does not fire and the second invocation runs the entire Atom Pass concurrently with the first.

The completion write is gen-guarded (`applyParseCompleted`, `ingest-occ.mjs:201-212`: `if ((p.gen || 0) !== gen) return "parse_gen_mismatch..."`), but that guard sits after the Bedrock calls in `runAtomPass` — it prevents a stale attempt from corrupting the persisted arm state, it does not prevent the stale attempt from having already paid for the Bedrock round-trips.

It does not resubmit to the vendor — `fetchLlamaParseResult(this.env, meta.arms.parse.jobId)` (line 727) is a GET against the same already-completed parse job id, not a new `submitParse`. So the vendor-resubmission half of the question is "no" on this path; the full-Atom-Pass-rerun half is "yes."

### F.5 Reconciling A and B

Both are correct — they describe two disjoint code paths that fire in disjoint job states:

| | Claim A (repair) | Claim B (parse-arm re-claim) |
|---|---|---|
| Entry | `driveRepairAlarm` / `/repair`, gated on `jobState === COMPLETE_PARTIAL` (`claimRepair`, `ingest-occ.mjs:507`) | `alarm()` poll-claim or webhook-claim on the parse arm, reachable while the job is still RUNNING/pre-assembly |
| Sections re-run | Only ones flagged failed in `section_status` | All sections, unconditionally |
| Vendor resubmit | None | None (re-fetches the same job id) |
| Guard against duplicate cost | N/A — narrow by construction | None — the gen guard only blocks the write, not the compute |

The 2026-07-26 incident shape — "parse arm watchdog reverts, three concurrent `processParse` invocations" — is, by definition, not the repair path. The repair executor cannot even be entered until a job has reached COMPLETE_PARTIAL, i.e. until assembly has already run once. Three concurrent `processParse` invocations means the job hasn't assembled yet at all — this is squarely Claim B's path: each of the (up to `MAX_PROCESSING_RETRIES = 3`, `ingest-do.js:144`) watchdog-revert-driven re-claims triggers its own full-document Atom Pass. Claim B is the one that fires in that incident shape; Claim A is true but describes a different, later-stage mechanism that this incident never reaches.

(Inference: I did not find a session-log or ROADMAP entry actually describing a "2026-07-26 incident" in the files I read — the prior 2026-07-20 incident documented in CLAUDE.md and the `ingest-occ.mjs` header comments is about a duplicate Extract submission, not duplicate Atom Pass compute. I'm treating "2026-07-26" as the scenario given in this prompt and reasoning about it structurally from the state machine; I have not independently confirmed a logged incident with that date.)

### F.6 Cost consequence, 30-section document, 1 section fails

Reasoning from the code above (`runAtomPass` = 1 Bedrock call per processable section, `pipeline-shared.js:797-804`):

- **Repair pass:** 1 Bedrock Atom-Pass call (only the 1 failed section, `ingest-do.js:2139`), plus a PHI-classification call scoped to that section's atoms (`ingest-do.js:2153`). The 29 succeeded sections cost nothing again.
- **Parse-arm re-claim (one re-entry):** 30 Bedrock Atom-Pass calls — the entire section set, because `processParse` doesn't know 29 of them already succeeded elsewhere (no read of `section_status` at entry). For the incident shape with three concurrent invocations, that's up to 3 × 30 = 90 Atom-Pass Bedrock calls before OCC drops the losing writes — the compute, not just the write, is duplicated per invocation.
- **Full fresh re-ingest:** a brand-new `dispatch()` (`ingest-do.js:1594`) — new `uploadToLlama` + `submitParse`/`submitExtract` (vendor parse + extract credits paid again, `jobMetrics`, `ingest-do.js:1446-1447`), plus a fresh `processParse` → 30 Bedrock Atom-Pass calls, plus a fresh PHI pass over all atoms, plus KT coding and record-summary synthesis again. This is strictly the most expensive: vendor credits and the full 30-call Bedrock cost, on top of whatever the original run already spent.

### F.7 section_status shard

**What it records:** per-section rows (`section_id`, `status` ∈ succeeded/skipped/failed/failed_repairable, `atom_count`, `error`, `error_class`) — produced by `runAtomPass`'s `perSection` return and, for PHI failures, patched in by `applyPhiFailuresToSectionStatus` (`ingest-job-state.mjs:264-278`).

**When written:**
- `ingest-do.js:780` — by `processParse`, tagged `@{parseGen}`, every single Atom-Pass invocation (this is a base layer, pre-PHI).
- `ingest-do.js:1114` — by `assemble()`, tagged `@{assembleGen}`, the PHI-merged version.
- `ingest-do.js:2245` — by the repair executor, tagged `@{gen}`, the repair-merged version.

**Is it read by a subsequent run before that run decides what to do?** Only by `assemble()` (line 1105, reads the parse-gen base to merge PHI failures) and by the repair executor (line 2116, reads the assembly-merged `section_status_result` to pick eligible sections). `processParse` itself never reads this shard. So it is exactly the "obvious candidate for section-level reuse" the question anticipates — but it is wired to gate reuse only downstream of assembly (the repair executor), and is not consulted by the mechanism that actually re-executes the Atom Pass pre-assembly (`processParse` re-entry). That gap is the root of the two claims' apparent contradiction: the shard exists and is used for section-level reuse — just on one path, not the other.

### Plain-language summary of what gets re-paid on each retry path

- **Repair retry** (a job that already finished as complete_partial and is being healed by the Tier-1/Tier-2 repair executor): cheap and narrow. It reuses the stored parse/codex output, touches Bedrock only for the sections still marked failed, and never talks to LlamaParse/LlamaExtract again. Claim A describes this correctly.
- **In-flight parse-arm retry** (a watchdog reverts a stuck PROCESSING parse arm back to WAITING, and a later poll or webhook re-claims it before the job has ever assembled): expensive and blunt. `processParse` has no memory of which sections already succeeded in a concurrent or prior attempt over the same document — it rebuilds the codex and reruns the Atom Pass over every section, every time it's re-entered. It does not re-submit the PDF to LlamaParse/LlamaExtract (same vendor job id, just re-fetched), but it does re-pay Bedrock for every section, including ones that already succeeded. Claim B describes this correctly, and this is the path that produces "N re-claims × 30 Bedrock calls" duplication, not the repair path.
- **A full fresh re-ingest:** pays for everything again — vendor parse/extract credits plus a full 30-section Bedrock Atom Pass plus PHI/KT/summary passes — the ceiling case.

---

## Implementation ladder, restated where changed

- **Rung 0** (new, config + deploy step): raise the R2 lifecycle rule `expire-park-2d` → `expire-park-45d`. No code. Must precede any code that retains past 2 days.
- **Rung 1:** unchanged (ledger + taxonomy, recording only) — plus the `retention_state`/`delete_after`/`attempt_epoch` columns land here as recording-only groundwork.
- **Rung 2:** unchanged (leases). Now also the stated safety precondition for keeping the ageless in-flight adoption.
- **Rung 3:** budgets + ceilings + signature memo, then 3b (new): failed-retryable state split, epoch-aware re-claim, the `/retry` and `/cancel` endpoints, removal of the eager R2 deletes (bytes now retained; the 45-day rule is the only deleter until rung 5). F-NEW-MW still lands at the end of 3; the known-unbilled-rejection refinement to the submit cap lands with it.
- **Rung 4:** breaker + admission cooldown + dedupe inversion + force-fresh flag — adoption, tombstones, and cooldowns are one admission-control mechanism and ship together. iOS's §D changes track against the rung-3b contract and must be live before rung 4's inversion reaches production (rollout-order note in §C).
- **Rung 5:** observability export + NCC panels + the retention sweeper (principled GC begins; F-NEW-MJ closes here). Granularity per locked ruling 5: staging full-step always; production transitions-only on success, full step detail on failure.
- **Rung 6:** section checkpoints — BUILD (locked ruling 3). Direct answer to the ruling's question: yes, the current design re-runs already-successful sections on a re-claim — a re-claimed assembly re-executes the whole Atom Pass, so a 30-section document that failed on one section re-pays the Bedrock cost of the 29 that succeeded, on every retry. §B makes re-claims a designed-for event rather than an anomaly, which converts checkpoints from optimization to spend control; if rung-1 ledger data shows retry-driven re-runs dominating Bedrock spend, pull rung 6 forward ahead of rung 4 (flagged as an owner call at that checkpoint).

---

## Does not solve

Sunk vendor spend; Bedrock 429 quota policy; alerting/paging; cross-user fairness; already-leaked shards.

---

## Contradictions requiring owner ruling

- **R2 deletion site count (§0, Correction 2):** the text asserts "there are four" R2 deletion sites, then enumerates five — the post-createMeta delete (ingest-do.js:1795-1801), the `/enqueue` rollback (ingest-queue-do.mjs:251), retireToRecent-to-failed on coordinator-failed (:481), retireToRecent-to-failed on dispatch failure (:524), and blocked-entry expiry. The list above is preserved verbatim; the count is not reconciled here — needs an owner ruling on which figure, or which list item, is wrong.

---

## Open rulings

1. Ceiling numbers — exact LlamaCloud-credit and Bedrock-token spend ceilings (§2).
2. Success-ack grace window — proposed 72h (also the final-failure forensic grace).
3. Retention / abandonment window — proposed 30 days (this is also document_fault's outer stopping bound; the R2 backstop rule is retention + margin).
4. Job attempt budget — proposed 4 dispatch epochs per job lifetime.
5. BAA coverage of R2 — verification required before ship; grouped with the existing release-checklist BAA item.
6. Account-deletion surface — required by E.6, doesn't exist, out of this design's scope; needs filing as its own item.
7. Rung-6 pull-forward — decide at end of rung 1, on ledger data.
8. spend_cap unpark authority — designed as owner-only (rate-card change); confirm that's the intent, since the 15-minute-cooldown ruling could be read as implying auto-retry.
