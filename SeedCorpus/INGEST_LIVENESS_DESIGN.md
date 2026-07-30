# INGEST_LIVENESS_DESIGN.md — Ingest Liveness, Spend, and Observability Design (v3)

Status: DRAFT v3
Last verified: 2026-07-30

**Provenance:** produced across two Fable design sessions on 2026-07-29; revised against audits of F-NEW-MR and the duplicate-ingest question. v2 same day: incorporates the owner rulings on success-ack grace (12h), retention (5 days), the attempt ceiling (4, composed not flat), no-silent-permanent-bans, the two hold kinds, and the F-NEW-MX boundary; incorporates the Rung-6 call-site audit, re-verified against the live codebase (see §F.8 for two facts the audit did not carry). v3 (2026-07-30): incorporates the five owner rulings from the rung-3 (F-NEW-NE) pre-implementation review — Bedrock ceiling enforcement timing, dispatch-attempts as a separate pre-epoch gate, watchdog counters as the inner retry tier, epoch ownership at the job DO, and the recovery_pending epoch-draw signal.

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

**Death detection and reclaim:** DO eviction / deploy / crash mid-call → no renewal → the alarm fires `expireLease` → revert to WAITING/re-claimable, gen bumps on the next claim, and if the job had already left forward progress (a recovery re-claim, not a first claim), the re-claim draws a recovery epoch (§B). Reclaim speed = declared step budget + slack. Depends on DO alarms surviving eviction and restarts.

**Generations stay per-phase.** Parse and extract are genuinely concurrent arms; a unified job-level generation would force serialization. What unifies is the mechanism: one claimLease/renewLease/completeLease/expireLease applier family replaces the four hand-built variants. Per-phase watchdog keys collapse into one `leases[phase] = {gen, step, deadline}` shape. Attempt counting unifies into the recovery-epoch ceiling (§B) at the outer tier — so *layers* can no longer multiply. It does not replace the existing per-phase crash counters: **ruling 3 (rung-3 pre-implementation review)** absorbs `processingRetryCount` and `assembleRetryCount` as the inner tier, generalizing repair's existing two-tier pattern — capped at 3 crash-retries within a single epoch, reset to 0 on each epoch draw. The poll ladder's `retryCount` and `meta.repair.attempts` sit outside both tiers, unchanged.

**Correlation ID:** root is `jobId`, minted at `/v1/ingest/start`. Attempt id is `{jobId}:{phase}:{gen}`, derivable, labeling every lease renewal, ledger row, log line, and phase event row. Propagation via an `X-RH-Job-Id` header on every internal DO hop, already embedded in LlamaCloud webhook URLs, recorded against the vendor job id in the spend ledger at submit time. Neither vendor accepts a client correlation tag on the call itself.

Conformance checklist for any new phase:

1. Claims via `claimLease` before any work; a recovery re-claim draws a recovery epoch from the job's ceiling (§B).
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
- Ledger rows are written unconditionally — including for work a user is never charged for (a token-gate hold, a comped retry). Internal cost capture and user billing are different questions asked of the same rows; the ledger answers the first, F-NEW-MX answers the second (§G).

The ledger is simultaneously the spend meter, the idempotency record, the cost-attribution source, and the `llama_parse_calls` fix. It is deliberately **not** the attempt counter — attempts are counted as recovery epochs (§B), because the paths an attempt can take are not cost-equivalent (one repair call vs a 30-section pass vs a full re-ingest) and a counter that pretended they were would say nothing about spend. Spend is bounded only in vendor-native units, here.

**Per-layer spend rules, all reading the one ledger:**

- Vendor submits: hard cap approximately 2 each per job, ever, across all layers and generations, counted as ledger intents, so a submit that died ambiguously still counts as spent. LlamaCloud has no idempotency keys, so the rule is "an intent row of unknown outcome is presumed billed." On reclaim after an ambiguous submit, poll the vendor job id if captured, else burn the attempt, never blind resubmit.
- Bedrock calls: `callBedrockWithRetry`'s internal 3-attempt loop stays but takes a budget hook; each physical invocation records a ledger intent and checks the job's Bedrock-call and token ceilings first.
- Watchdog reclaims: an expired lease's re-claim draws a recovery epoch (§B), not a spend unit — its actual spend lands in the ledger as it happens.
- Phone resubmits: governed by admission control, not the job's epoch ceiling.

**Hard spend ceiling**, vendor-native units, two per-job ceilings checked at intent-write time:

- LlamaCloud credits: ceiling = pages_estimate × per-page rate × submit cap × safety factor. Locked now (ruling 1) — enforced from rung 1.
- Bedrock tokens: running sum of ledger actualUnits plus projected cost of the call about to be made. Deferred (ruling 1): no real cap is enforced until rung 1's own ledger data gives a basis for one. Rung 1 ships with a deliberately loose placeholder ceiling that logs breaches without stopping the job — it observes, it does not gate. This dependency carries forward into F-NEW-MX and F-NEW-MY.

A ceiling breach is not a silent terminal: it places the job on **administrative hold** (`spend_cap`, §B2) with an NCC notice — policy said stop, and a human sees that it did. Because the check happens at intent time and intents are fenced, unbounded spend requires either a ledger bypass or a vendor billing us for calls we never made. Exact numeric values for both ceilings remain an open ruling; what's locked is that LlamaCloud enforces from the start and Bedrock does not until rung-1 data exists.

**Rung-3 ceiling scope (ruling 1, rung-3 pre-implementation review, 2026-07-30):** rung 3's "ceilings" work is the epoch ceiling (§B) plus the already-enforcing LlamaCloud gate above — rung 3 does **not** flip `gateBedrock` to enforcing. Bedrock spend enforcement lands separately, at F-NEW-MX, which hard-triggers immediately once rung 3b (L4) ships: hard, not soft, because refusal requires the hold machinery (§B2, built in 3b) and because a real ceiling number requires ledger data that only accumulates once rung 1's placeholder has been running in production. (The ROADMAP F-NEW-NE scope line will be corrected to match, in a separate commit in the app repo.)

**Circuit breaker per vendor boundary.** Breaker state must be cross-job and cross-user, so one VendorHealthDO per vendor, consulted before submits:

- Trip: 3 consecutive deterministic-vendor failures (402, 401/403) trips immediately; 5 transient failures within 5 minutes trips for transients.
- Open behavior: submits are not attempted. The queue entry parks as blocked with reason `vendor_unavailable`, reusing the F-NEW-KO blocked-entry machinery. This blocked state is error-hold-kind for retention and visibility purposes (§B2), but its release is automatic (the probe). The user-facing meaning is locked (ruling 4): "Processing delayed due to server issues. We will resolve and process your records shortly. No action is needed on your part." Exact wording is deferred to F-NEW-MV — design against the meaning, not the string.
- Probe: half-open admits one real job on a backoff schedule (60s doubling to 15 min). Probe success closes the breaker and pokes coordinators to re-evaluate blocked entries.
- One extra DO hop per submit. Submits are rare; acceptable.

**Admission control:** instant slot refill stays for successes. For failures, the terminal path gains a failure-class-keyed cooldown in the recent ring:

- vendor_fault / our_timeout / spend_cap: resubmit of the same content_hash is held for 15 minutes (locked ruling 2).
- document_fault: no clock (locked ruling 2) — resubmit stays blocked until something changes on our side (prompt version, app version, pipeline version), never merely until a timer expires. The block is a **visible tombstone** (§C), never a silent one — ruling 4.
- superseded / canceled: no cooldown.
- The slot itself still frees immediately; cooldown gates admission of the same bytes, not slot capacity.

**F-NEW-MS fold-in, the failure-signature memo:** each failed step records a failure signature = hash of (section_id, error_class, stable error discriminator). Retry/repair eligibility excludes any unit whose signature has already failed 2 times across all generations and tiers. Two, not one, because Bedrock output is nondeterministic. A second identical failure parks the section terminal. The memo extends to the job level: each failed recovery epoch records an epoch signature = hash of (failure class, stable discriminator); two epochs failing with the same signature stop the job immediately (§B) — the same memo mechanism with unit = job, not a new counter.

**Gap — the stable discriminator is not the raw error string.** The signature's "stable error discriminator" component requires normalizing raw errors into a fixed vocabulary (on the order of ~8 classes — e.g. `json_parse_failure`, `upstream_5xx`, `throttled`, `auth`, `our_timeout`) before hashing. Raw messages must never be hashed directly: a V8 `SyntaxError` carries a byte position in its message text, so two occurrences of the identical failure produce different raw strings and never converge on a signature, silently defeating the "2" bound. The vocabulary itself is not fixed here — it is finalized at rung-3 implementation.

**Tension with the 2-revolution cap:** no conflict, orthogonal axes. The revolution cap bounds across-pass re-ingests; the signature memo bounds identical retries; the epoch ceiling bounds total recovery attempts; the ledger ceilings bound spend. Worst-case total spend per record = revolution cap (2) × per-job ceiling. Signature memos do not carry across revolutions.

---

## 3. Supersession and fencing

Within one DO instance, superseded work can be stopped. All events for a given DO id are delivered to the same in-memory object instance, and `AbortController` works on in-flight `fetch` in Workers. The DO keeps an in-memory abort registry: `this.liveRuns: Map<"{phase}:{gen}", AbortController>`. When a re-claim bumps a gen, or `markTerminal` runs, the caller aborts every registered controller for older gens.

**Limits:** the registry is memory-only, so it does nothing across eviction/deploy, but in that case the old invocation is dead. It cannot claw back vendor-side spend: Bedrock bills tokens already generated, and LlamaCloud has no cancel endpoint for the per-job parse/extract API (cancel exists only on the beta batch API).

**Fence placement, three layers:**

1. **Pre-spend fence (new, primary):** `renewLease` + budget check + ledger intent before every paid call.
2. **Active abort (new):** the registry above.
3. **Write fence (existing):** OCC-guarded completion, now protecting state consistency only.

**Partial work of a superseded generation:** discarded, with one exception: completed Atom-Pass section work — locked ruling 3, BUILD, refined by the Rung-6 audit into two mechanisms (§F.8 carries the code facts that force the split):

- **6a — prior-generation shard reuse (cheap, ships at rung 3b).** On re-entry, `processParse` looks for a prior generation's completed `codex`/`sections`/`atoms_narrative`/`section_status` shards whose stamped Atom-Pass prompt version matches the current one. If present, it adopts the stored codex and sections instead of rebuilding (this is what makes reuse sound — section ids are `crypto.randomUUID()` per rebuild and cannot be matched across rebuilds; adopting the stored shard is exactly how the repair executor already gets id-aligned sections), runs the Atom Pass over only the non-succeeded sections, and splices the fresh atoms over the prior generation's — the identical read-subset-splice pattern `_repairAttemptBody` already implements. Covers every sequential re-claim after a completed pass.
- **6b — content-addressed incremental checkpoints (deferred, decided on rung-1 ledger data).** 6a helps only when a prior pass *completed* — all shards are written strictly after `runAtomPass` returns, so an invocation that dies at section 17 of 30 leaves nothing. 6b writes a per-section checkpoint as each Bedrock call returns, keyed by (content hash of the section's input text, prompt version) — content-keyed because a mid-pass death means the current generation's sections shard never landed and a later rebuild has different ids; the input text is deterministic across rebuilds even though the ids are not. This is the only remaining place content-addressing is required.

The concurrent-invocation storm is not Rung 6's problem: the losing invocations start before the winner has written anything, so there is nothing for them to reuse — §1's pre-spend fence and the abort registry (rung 2) are what kill the storm.

**Terminal-while-live:** allowed, with a defined cleanup obligation. `markTerminal` and `notifyIfNewlyTerminal` acquire three obligations: abort all registered controllers; rely on lease renewals to fence unreachable stragglers; schedule the post-terminal sweep.

**Orphan shard reclamation:** sweep moves from "inside `assemble()` only" to the terminal transition itself. On any terminal, the DO schedules one final alarm at t + grace that deletes every shard except, for successful jobs, the winning-gen result shard.

---

## 4. Observability

Two surfaces. Logs reconstruct one job's path. Metrics/events answer "is ingest slow today" and live in Postgres via the NCC pattern: strict column allowlist, no free-form JSONB, scrubbed, waitUntil, observe-never-gate.

NCC is the right surface and needs extension, not replacement. It gains four panels: ingest health, queue/concurrency, spend, and **holds & tombstones**. It does not do alerting/paging — a hold notice is a durable row that stays visible until explicitly resolved, not a page.

**Two new tables:**

- `ingest_phase_events`: one row per phase transition (claimed, completed, expired, failed, superseded, held, released), carrying job_id, phase, gen, event, duration_ms, step_count, error_class, hold_kind, hold_reason, environment, t. Not per-step, not per-poll. Roughly 10 rows/job. "Which stage of which phase is slow" comes from duration_ms per phase plus a slowest_step column stamped at completion. Granularity is locked (ruling 5): staging carries full per-step detail permanently; production carries transitions only for successful routine work, plus full step detail on anything that fails.
- `ingest_spend_events`: the ledger flush, per attempt, per vendor, units + unit type + vendor job id. Flushed at terminal by the DO, and by the existing sweeper for jobs whose DO died before flushing. Spend is recorded in DO storage at intent time and exported at terminal-or-sweep. `ingest_jobs` cost columns become a rollup of ledger rows.

**Holds & tombstones panel (ruling 4's visibility surface):** every hold entry — both kinds — emits an NCC notice row (job id, hold kind, hold reason, epoch history as class+signature pairs, ledger rollup, age). Every document_fault tombstone is a listed row (job id, error class, failure version, enqueue count, created-at) with an owner clear action. The duplicate-submission counter (§C) surfaces here at threshold. Nothing in the system can be stopped-and-forgotten: a hold without a row is a bug, and the sweeper cross-checks held jobs against notice rows.

**Queue and concurrency:** the coordinator emits transitions to the same phase-events table (enqueued, dispatched, blocked(reason), held(kind, reason), terminal), with waited_ms stamped at dispatch. Queue depth over time falls out of event timestamps in SQL. Current-state is a small live admin route.

**Failure classification**, one taxonomy stamped at every terminal or hold: vendor_fault, vendor_billing, vendor_auth, our_timeout, document_fault, spend_cap, superseded, canceled, unknown_crash. The classifier runs where the information exists, not at the terminal write.

**Log volume:** state transitions and errors always logged, structured, one line each. Per-poll and per-heartbeat logging removed. Payload-bearing diagnostics removed. Workers Logs bills per event and sheds under load with short retention, therefore nothing operational may depend on logs.

**PHI:** event tables have strict column allowlists, ids/enums/counts/durations only. No document text, section titles, atom values, filenames, or vendor payloads in any event, metric, or log line. Hold and tombstone rows carry hashes and ids only.

---

## 5. Verification

F-NEW-MP (replay harness) must record/replay at the HTTP boundary, not at adapter-output level, because the things this design most needs tested live between our logic and the wire. MP must provide: an injectable fetch seam in the vendor helpers; scripted fault sequences (N consecutive 402s, ambiguous submit, slow response exceeding a declared budget, a poll sequence that never completes, a gate hold at §G's P2 followed by a resume); virtual time driving the alarm loop; recorded real fixtures from staging for happy paths.

**Per-rung verifiability:** pure appliers under `node --test`, call-site invariants enforced by grep-able rules, end-to-end behavior under the MP harness with scripted faults.

**F-NEW-MW sequencing confirmed:** MW's fix adds a new paid-submit call site and must not land before the fence exists. Refinement: MW needs only rungs 1-3, so it can ship mid-ladder.

---

## A. Document retention

*(Absorbs F-NEW-MJ; F-NEW-MU's adoption dependency becomes explicit.)*

One retention mechanism, two artifact classes, one clock. A job owns two durable artifacts: the source bytes in R2 (`park/{userId}/{jobId}.pdf`) and the result/working shards in DO storage. Both are governed by a single per-job retention state, recorded in the coordinator entry and mirrored to `ingest_jobs` (columns `retention_state`, `delete_after`) so retention is queryable and auditable. F-NEW-MJ's GC is this mechanism — it does not get a second one. The MJ owner ruling (2026-07-25: delete after client-confirmed receipt via `fetched`, plus a grace window, without breaking repair) is honored as the success arm below.

The clock and the triggers:

- **Clock starts at the custody point.** The source object lives as long as the job is non-terminal or terminal-retryable (per B). This deletes the post-createMeta delete at ingest-do.js:1800 and the coordinator's failure-path `deleteParked` calls — the bytes are no longer "released to the job DO," they are the job's recovery root.
- **Success:** delete source bytes AND result shards together at `fetched` + grace. Grace is **12 hours** after ack (locked). The window exists for exactly one purpose — recovery if the phone acks and then loses the result locally — and 12 hours covers a same-day restore; lower retention surface is the preferred posture. Rationale for deleting source on success at all: the device is the system of record and retains the document; post-success server retention has no recovery purpose, only PHI liability.
- **Success-arm repair guard.** For a `complete_partial` job the 12-hour timer alone is not sufficient: Tier-2 repair is sweeper-driven and can trail the phone's ack. Deletion at `fetched` + 12h additionally requires **repair quiescence** — no live repair watchdog, and every repair-eligible section either resolved, signature-terminal, or the repair cap reached. `claimRepair` requires COMPLETE_PARTIAL and repair attempts are bounded (TOTAL_REPAIR_CAP + the signature memo), so quiescence arrives quickly; the sweep checks it before deleting. This is the one dependency for which a bare 12-hour timer would have broken the MJ "GC must not break repair" constraint; everything else that touches the grace (post-ack re-fetch, §C success-adoption, E.5's 410 fallback) either fits inside 12 hours or has a fresh-upload fallback.
- **Unacked success (abandonment):** no `fetched` ever arrives (app deleted — iOS provides no uninstall signal). Retention cap: **5 days** from terminal (locked), then delete both artifact classes and mark the job `failed_final(retention_expired)` if unacked-failed, or leave complete with artifacts gone if unacked-success. Named consequence: a phone offline for more than 5 days after import re-uploads and re-pays on its next poll's 410 — accepted; the phone retains the source.
- **Terminal-retryable failure and error holds:** bytes retained for the same **5-day** window from last state change. The window restarts on any server retry (state changed). This window is also the outer stopping rule for fix-gated failures (B) — named consequence, per the owner: a `document_fault` job waiting on a fix from us now has **5 days**, not 30, before its artifacts go. Our fix cadence has to beat 5 days or the user re-uploads after we ship the fix; the tombstone's version gate admits that re-upload the moment our version changed.
- **Administrative holds:** the artifacts still follow the same 5-day clock; the hold itself does not (§B2). At expiry the artifacts go and the hold survives as PHI-free metadata.
- **Genuinely final failure (B's list):** artifacts deleted at final-transition + a short grace (**12h**, same knob) — kept briefly only so a just-failed job's forensics (staging replay via F-NEW-MP fixtures) can capture what's needed; production forensic value lives in the ledger and phase events, which are PHI-free and retained.
- **User deletion (record / account):** immediate deletion, no grace — E.1/E.6.

The lifecycle rule becomes a backstop, not a policy. `expire-park-2d` is raised to **7 days** (retention max 5d + margin) and kept — it is the guarantee that a crashed coordinator can never leak an object forever. Enforcement of the real policy is a coordinator sweep (the existing alarm loop already visits entries; the recent-ring prune extends to artifact deletion at `delete_after`). **Deploy-order constraint:** the lifecycle change must land before any code stops eagerly deleting, or nothing; but code must not start relying on retention until the rule is raised — this is Rung 0 in the ladder.

**Compliance posture.** This changes PHI-at-rest duration, not category — raw un-tokenized health documents already sit in this bucket up to 2 days; they will now sit up to ~5. Stated implications: (1) R2 server-side encryption (AES-256, Cloudflare-managed keys) covers the objects, but the Cloudflare BAA must be verified to cover R2 — this joins the existing release-checklist BAA verification item (flagged, blocking for this design's ship, grouped with F-NEW-MJ's launch-blocker status). (2) Access is exclusively via the coordinator/job-DO service path; no admin listing or fetch route over `park/` exists and none may be added without an owner ruling. (3) The keying (`park/{userId}/{jobId}.pdf`) means account-scoped enumeration for deletion is a prefix list — deliberate, keep it. (4) This deepens the already-noted tension with the local-first framing in ARCHITECTURE.md; the ruling accepts server custody explicitly, and the doc amendment should record that the "processing pass-through" description is superseded by "custody until success-ack or retention expiry."

**Storage cost.** R2 at ~$0.015/GB-month: at a generous 5 MB/document and 10,000 documents simultaneously inside a 5-day window, ~50 GB peak but a much smaller steady state ≈ well under $1/month, plus negligible class-A/B ops. Storage is not the spend story; one avoided duplicate LlamaParse of a 29-page agentic-tier document pays for months of it. The binding constraint on the retention window is compliance surface, not dollars.

**F-NEW-MU interaction:** adoption (§C) is gated on artifact existence, checked inside the coordinator DO in the same single-threaded turn that would retire or delete — the "adopts against stored result blobs" behavior stops being an accident of missing GC and becomes a checked precondition.

---

## B. Failed is no longer terminal-dead

**State model.** `failed` splits into `failed_retryable(class)`, `held(kind, reason)` (§B2), and `failed_final(class)`. A retryable or held job's DO meta and coordinator entry persist (artifacts per §A). Re-entry into processing is mechanically a lease re-claim with a bumped generation — the same claim/renew/complete machinery from §1; no new execution path. The job keeps its `job_id` forever. Alternative considered: mint a fresh job per retry and link them — rejected because it breaks the phone's bookmark invariant, the dedupe identity, and the whole-job spend ledger, for no benefit; the generation counter already provides attempt identity (`{jobId}:{phase}:{gen}`).

**Epoch ownership (ruling 4, rung-3 pre-implementation review).** The job DO, not the coordinator, owns the authoritative epoch count and the epoch-draw decision — claims, and therefore draws, happen at the job DO. The coordinator entry and `ingest_jobs.attempt_epoch` are best-effort mirrors of that count, same degradation posture as the L1 liveness mirror: they may lag or drop a write without the job DO's own accounting being wrong, and nothing downstream may treat the mirror as the source of truth for a stop/hold decision.

Who moves a failed job back, by failure class:

| Class | Mover | Mechanism |
|---|---|---|
| vendor_fault, our_timeout, unknown_crash | Server, automatic | Coordinator-scheduled retry with backoff (15 min first, doubling; the ruled 15-minute cooldown is the floor) — until the signature memo or epoch ceiling stops it into a hold |
| vendor_billing, vendor_auth | Server, breaker-mediated | Parks as `blocked(vendor_unavailable)` (error-hold-kind, §B2); the VendorHealthDO's half-open probe success pokes coordinators, which re-dispatch |
| document_fault | Server, version-gated | ERROR HOLD, no clock but bounded by §A's 5-day retention. Job stamps the pipeline/prompt/app-schema version at hold; a version-change sweep (run at deploy or by cron) releases holds whose failure-version < current, once per version change. Automatic release does not reset the epoch count |
| Any retryable class | User, via the retry control | §D's endpoint; draws the same epochs, respects the same cooldowns |
| spend_cap / ledger ceiling breach | Gate or owner | ADMINISTRATIVE HOLD (§B2, §G). Released by a rate-card/cap change (F-NEW-MX/MY) or explicit owner action; owner release resets the epoch count |
| epoch ceiling / duplicate-submission threshold | Owner only | ADMINISTRATIVE HOLD (owner investigation); owner release resets the epoch count |
| superseded, canceled, retention_expired | Nobody | failed_final — the only silent terminals left, and none of them is a ban: superseded/canceled record a user action, retention_expired records an honest expiry that was visible as a hold first |

**The stopping model — one model, three orthogonal bounds, every stop loud (rulings 3 and 4).** The ceiling is **4**, and it is not a flat counter; the three bounds measure different things and every one of them terminates in a hold a human sees, never a silent countdown to death:

1. **Spend is bounded by the ledger ceilings (§2), in vendor-native units, at intent time.** This is the only spend bound. The paths a retry can take cost wildly different amounts — one repaired section is 1 Bedrock call, a pre-assembly re-claim is up to 30, a fresh re-ingest is vendor credits plus 30 plus PHI/KT/summary (§F.6) — and the ledger prices each truly. An attempt counter is deliberately not asked to mean anything about spend.
2. **Repetition is bounded by the failure-signature memo (§2, F-NEW-MS) at 2.** Two identical failures of the same unit — section-level within repair, or job-level across recovery epochs (epoch signature = hash of failure class + stable discriminator) — stop that line immediately. Four failures for the same reason never happen: the same reason is a pattern, and the pattern stops at two, well under the ceiling. Memos persist across generations of the same job (inputs identical by definition; they reset only across revolutions, locked ruling 6, and a version change resets memos for affected units — the version change is an input change).
3. **Lifetime is bounded by the recovery-epoch ceiling of 4 (locked).** A recovery epoch is any failure-driven re-entry into processing: a watchdog reclaim, an auto-retry, a breaker re-dispatch, a version-sweep release, a user retry poke that dispatches. The initial dispatch is free; forward-progress claims (first claim of each phase) are free; repair attempts within a COMPLETE_PARTIAL job are free (bounded by the memo and TOTAL_REPAIR_CAP — they are the cheap path and must not be rationed like re-ingests). The ceiling is only reachable by failures with *different* signatures — else bound 2 stopped it earlier — and when the 4th epoch fails, the job goes to ADMINISTRATIVE HOLD (owner investigation) with the full epoch history (class + signature per epoch) in the NCC notice. Four failures for four different reasons are therefore visible by construction: they are the only way to reach the ceiling, and reaching it produces a notice that lists all four.

**Dispatch-mechanics failures never draw an epoch (ruling 2, rung-3 pre-implementation review).** The coordinator-to-job-DO `/dispatch` POST failing is a separate, pre-epoch gate: `dispatch_attempts`, capped at `MAX_DISPATCH_ATTEMPTS = 3`. The job DO was never claimed and has no processing state to revert, so exhausting `dispatch_attempts` cannot be a recovery epoch — there is no forward progress to have lost. Dispatch-exhausted entries join the visible-hold/retry surface when it ships in rung 3b, so this failure class is neither invisible nor unretryable.

**The epoch-draw signal is an explicit marker, not generation arithmetic (ruling 5, rung-3 pre-implementation review).** "Forward progress" above is not inferred from gen numbers. Watchdog and failure appliers that revert work which had left forward progress stamp a `recovery_pending` marker (phase + failure class) on job meta. The next claim that observes the marker draws an epoch, clears the marker, and resets the inner-tier counters (§1's `processingRetryCount`/`assembleRetryCount`). A claim that observes no marker never draws an epoch — this is what makes first claims, and routine non-failure re-claims (e.g. a chain-extract `revert-idle` resubmit, §F.4), free by construction, without needing a special case. Gen counters are never consulted for epoch decisions; they remain the write-fencing mechanism (§3) only.

No fourth counter exists. The vendor billed-submit cap (~2, §2) is a spend rule inside bound 1, with one refinement forced by retryability: a known-unbilled deterministic rejection (a clean 402/401/403 with no vendor job created) does not consume the billed-submit cap — the breaker bounds those — otherwise a credit-exhaustion outage (the exact 2026-07-28 incident) would permanently burn every in-flight job's parse budget before the breaker even trips. Ambiguous outcomes remain presumed-billed. TOTAL_REPAIR_CAP stays as the pre-existing repair-path backstop inside the memo's bound.

Epoch resets: a **human** release (owner clearing a hold, a cap change) resets the epoch count to zero — a person decided this job deserves a fresh run. **Automatic** releases (version sweep, breaker probe) do not reset — a document that fails across 4 version changes should land in front of a human, and does.

The outer bound for document_fault (which has no clock of its own) is §A's 5-day retention window: if no our-side version change arrives within retention, the hold exits as `failed_final(retention_expired)` with honest copy, and the visible tombstone survives (§C). So every failed job provably reaches either a human's queue or a terminal user-visible truth within max(4 epochs, 5 days).

**Budget and ceiling accounting.** Nothing new: the ledger is per-job and append-only across generations, ceilings are computed over whole-ledger sums at intent time. Server-side retry is precisely why §2 defined them per-job rather than per-attempt — this section adds no accounting machinery, only more generations. The honest terminal state carries the taxonomy class; wording is F-NEW-MV's problem, meaning is locked (ruling 4).

---

## B2. The hold model — two kinds, both loud

A hold is a stopped-but-not-dead state: the job keeps its identity, its ledger, and its coordinator entry; work is not scheduled; the phone sees an honest held status (§D); NCC receives a durable notice row at hold entry (§4). Nothing is permanently banned without a human seeing it — a hold without an NCC row is a bug. Two kinds, distinguished by *who* the job is waiting on:

**ERROR HOLD — waiting on a fix from us.**

- Lands here: `document_fault` (version-gated), a job-level signature stop whose class is ours (`our_timeout` pattern, deterministic pipeline errors), anything version-gated; `blocked(vendor_unavailable)` is classified error-hold-kind for retention and visibility, though its release stays automatic via the breaker probe.
- Release: version-change sweep (deploy/cron), breaker probe, or owner action. Automatic release does not reset the epoch count; owner release does.
- Retention: **subject to §A's 5-day window.** When retention expires, the artifacts go and the job resolves honestly as `failed_final(retention_expired)` — the user is told the truth rather than left pointing at a hold we never fixed. A document_fault tombstone survives the job (§C), visible in NCC.

**ADMINISTRATIVE HOLD — waiting on the user or the owner.**

- Lands here: token gate pending (F-NEW-MX, §G), `spend_cap` / ledger ceiling breach, subscription/balance blocks (the OD-1 balance gate's blocked entries), owner investigation (epoch-ceiling breach, duplicate-submission threshold).
- Release: the user clears the gate (buys tokens, restores subscription), or the owner acts. Human release resets the epoch count.
- Retention: **the hold does not expire on the retention clock — ever.** The hold record is PHI-free metadata (job id, `(content_hash, patientId)` key, kind, reason, epoch history, ledger rollup) and persists indefinitely in the coordinator and NCC until resolved. The *artifacts* are not exempt: source bytes and shards still delete at §A's 5-day mark even under an administrative hold. The hold survives artifact deletion as metadata-only.
- Resume after artifact deletion: the hold's key persists; when the gate clears, the job cannot silently resume (nothing to process) — its status reports `needs_reupload`, and the next `/enqueue` of the same `(content_hash, patientId)` adopts the held job's identity, supplies fresh bytes, and re-enters via a new dispatch under the reset epoch count. Named consequence for the token gate: a user who clears the gate within 5 days resumes from the stored parse shards at zero extra vendor cost (§G's P2 persists them before holding); after 5 days they re-upload and the vendor parse is re-paid. Tradeoff, decided: keeping bytes alive as long as the hold would save that re-parse but creates unbounded PHI retention keyed to user inaction — the posture that chose 12h and 5 days rejects that. Could have gone the other way; if gate-clear-after-day-5 turns out common, revisit with data.

Placement of every stop, both kinds:

| Stop | Kind | Clock on artifacts | Hold expires? | Release |
|---|---|---|---|---|
| document_fault | ERROR | 5d → failed_final(retention_expired), tombstone survives | Yes, with the artifacts | Version change; owner |
| Job-level signature stop (our classes) | ERROR | 5d → failed_final(retention_expired) | Yes | Version change; owner |
| blocked(vendor_unavailable) | ERROR-kind | 5d | Yes | Breaker probe (automatic) |
| Token gate (F-NEW-MX) | ADMIN | 5d (hold persists) | No | User clears gate |
| spend_cap / ledger ceiling | ADMIN | 5d (hold persists) | No | Cap change; owner |
| Subscription / balance | ADMIN | 5d (hold persists) | No | User restores; owner |
| Epoch ceiling (4) | ADMIN | 5d (hold persists) | No | Owner investigation |
| Duplicate-submission threshold (4) | ADMIN (on the admission key) | n/a (key-level) | No | Owner investigation |

---

## C. Dedupe inversion

DEDUPE_TERMINAL_STATES and the recent-ring TTL as an adoption window are deleted concepts. New semantics for `/enqueue` with a colliding `content_hash`:

| Existing job state | Action |
|---|---|
| In-flight (queued / active / blocked / held) | Adopt: 409 with `job_id` + state (a held job returns its hold kind and reason — the honest answer). No age bound — stays (resolves F-NEW-MU's ask). The unbounded match was only ever dangerous because a job could be silently stuck forever; §1's leases and §B2's loud holds remove that state from the system. Explicit dependency: rung 2 lands before or with this rung |
| failed_retryable | Adopt and treat the enqueue as a retry poke, subject to §B's cooldowns and gates. The user re-importing the file is the retry intent; it costs nothing to adopt (no bytes accepted, no spend), and the poke either schedules a retry or returns the honest parked state |
| Administrative hold, artifacts gone | Adopt the held identity: accept the bytes as the job's fresh recovery root and hold position pending release (`needs_reupload` satisfied). No processing until the gate clears |
| Terminal success, artifacts still retained (pre-GC per §A) | Adopt: phone gets the completed job and fetches the result. Window = artifact existence, checked in the same coordinator turn — not a ring TTL |
| Terminal success, artifacts GC'd; or failed_final (except below) | No adoption; fresh job minted. This is a genuine new import of a document the server honestly finished with; the phone owns the bytes and sends them — that is not failure recovery and doesn't violate the ruling |
| failed_final(document_fault…) | No adoption; admission of the same bytes is version-gated via the content-hash tombstone (below): re-admission only after an our-side version change. Waiting does not make a broken document readable (locked ruling 2), and neither does re-uploading it |

**The admission record — tombstones and the duplicate-submission counter, both visible (ruling 4).** The coordinator keeps one PHI-free admission record per `(content_hash, patientId)` key: enqueue count, first/last seen, tombstone (failure class + failure version, when present), hold pointer. Two rules hang on it:

- **Tombstones are never silent.** A document_fault tombstone blocks re-admission until an our-side version change, but it is a listed, investigable row in NCC's holds & tombstones panel (job id, error class, failure version, enqueue count, age) with an owner clear action, and the phone always receives an honest blocked state, never a quiet swallow. The tombstone survives its job's retention expiry — re-uploading a document we deterministically cannot read must not re-spend until something on our side changed — but it survives *visibly*.
- **Repeated submission surfaces at 4 (locked).** The 4th enqueue of the same key — regardless of what each enqueue resolved to — emits an NCC notice and places the key on administrative hold (owner investigation). If the key is attached to a live healthy job, the hold does not kill that job; it gates further admissions of the key and flags the pattern. Tradeoff, decided: counting all arrivals will occasionally flag an impatient user double-importing a slow document — accepted, because the alternative (counting only failure-driven arrivals) hides exactly the confused-user loop the owner wants seen; the NCC row costs an investigation glance, not a user-facing block on the live job. "Apparently-same" beyond exact hash equality (recompressed exports of the same document) is not detectable by this key — flagged as an open ruling; hash-only for now.

**Keying gains the patient profile.** Current matching is hash-only; `metadata.patientId` is ignored, so identical bytes uploaded under a different profile would adopt a job bound to the wrong profile's record. New key: `(content_hash, patientId)`. Tradeoff: byte-identical documents across two profiles are processed twice (double vendor spend) versus correctness of record/profile association and zero cross-profile result sharing. Correctness wins; the case is rare. (Cross-user adoption is impossible by construction — the coordinator is per-user — and stays that way; see E.3.)

**Force-fresh (F-NEW-MU's dev flag).** `metadata.forceFresh: true`, honored only when the environment sets `INGEST_ALLOW_FORCE_FRESH="true"` (staging/dev vars; never production). Bypasses adoption and tombstones, mints a fresh job. In production the flag is rejected loud (400 `force_fresh_disabled`) rather than silently ignored, so a mis-pointed test run says why it didn't do what the tester expected.

What dies with the inversion: the :94-97 comment's rationale, the 15-minute RECENT_TTL_MS as a dedupe concept (the recent ring survives only as reconcile bookkeeping), and `.freshSubmission`'s safety argument — which is fine, because §D deletes `.freshSubmission`'s mechanism anyway. The ordering matters: the dedupe inversion must not ship before §D's retry endpoint exists on both ends, or an old-app `.freshSubmission` re-upload would adopt the dead job it is trying to escape and the user's retry button would do nothing. Old-app compatibility during rollout: adoption of a failed_retryable job returns 409 with a state the old client reads as a live job to poll — acceptable, because the adopt-poke schedules the actual retry server-side; the old client's UX is merely un-improved, not broken.

---

## D. Wire and client contract

New action: `POST /v1/ingest/jobs/{jobId}/retry` (JWT auth, routed to the caller's coordinator; the coordinator owns retry admission because it owns slots and cooldowns). No body. Responses:

- `202 {job_id, state, retry_at?}` — retry admitted (immediately dispatched, or scheduled; `retry_at` when a cooldown holds it).
- `409 {error:"held", hold_kind, reason}` — the job is on hold; retry is not what unblocks it. Administrative holds name what does (token gate, subscription); error holds say we're on it. Phone renders the F-NEW-MV meaning for the reason.
- `409 {error:"job_final", reason_class}` — genuinely final; phone renders the F-NEW-MV meaning for the class. Honest refusal, not an error to retry.
- `404` — the server has no such job (wiped DO, pre-retention job, or a job that never existed). This is the one corner where the phone falls back to a fresh upload — which is also the never-confirmed-upload path, confirmed still required.

A second new action: `POST /v1/ingest/jobs/{jobId}/cancel` — required by E.1 (record deletion). Marks `canceled` (final), aborts live work through the abort registry, deletes both artifact classes immediately.

**Status contract additions:** `GET /v1/ingest/status/{jobId}` gains `attempt_epoch` (the job's recovery-epoch counter, served from the coordinator/`ingest_jobs` mirror — the job DO is authoritative per §B's epoch-ownership ruling (rung-3 review), but status reads go through the coordinator, so the field reflects the mirror's latest write) and, when held, `hold_kind` + `hold_reason` (+ `needs_reupload: true` when an administrative hold has outlived its artifacts). The epoch field's reason: the phone's choke-point guard (772ee81) refuses working-state writes over a settled record — a server-initiated resurrection observed by a poll would be misread as exactly the stale-progress stomp that guard exists to kill. The epoch lets the client distinguish "the server legitimately revived this job" (epoch advanced → pass `recovery: true`) from a stale write (epoch unchanged). Without this field, §B's auto-retries are invisible to a phone that already settled the record. A mirror lag means the client's `recovery: true` transition may trail the job DO's actual draw by one poll cycle — acceptable, since the guard only needs to see the epoch advance eventually, not instantly.

What the phone sends, receives, polls: on retry — the job id only, never bytes, never a hash; it keeps the bookmark, does not ack (`markJobFetched`) the job, and resumes the existing 3s status poll and result fetch unchanged.

**iOS requirement list (for the app repo, requirements not design):**

1. Replace the body of `IngestRetryMode.freshSubmission`: call `/retry`; keep the bookmark; do not ack; resume polling. The ack+clear+re-upload sequence is deleted.
2. Handle the retry responses: 202 → working ("Retrying…" copy path already exists); 409 `held` → needsAttention with the hold-reason-mapped copy (F-NEW-MV); 409 `job_final` → needsAttention terminal with the class-mapped copy; 404 → fresh upload (the only surviving client-upload-on-retry path).
3. Consume `attempt_epoch`; an epoch advance on a settled record re-enters working state through the choke point with `recovery: true`.
4. On user deletion of a record with a live, retryable, or held `serverJobId`, call `/cancel`; queue the call durably if offline.
5. Tolerate additively: `blocked(vendor_unavailable)` (render the locked ruling-4 meaning), `held(kind, reason)`, `needs_reupload` (re-offer the import flow for that document), `failed_final` reason classes, `retry_at`.
6. Amend ARCHITECTURE.md §3.8: `.freshSubmission` mechanism replaced; the "dedupe excludes failed jobs" safety argument deleted; the :671/:681 contradiction resolved in favor of :681.

---

## E. Edge cases, ruled

1. **User deletes the record while a job is live, retryable, or held:** phone calls `/cancel` → `canceled` (final), live controllers aborted, both artifact classes deleted with no grace — deletion intent outranks forensic grace; PHI minimization wins. Ledger/phase-event rows and hold/tombstone rows (PHI-free) are retained. App deleted: iOS gives no signal; the job runs to terminal and §A's 5-day abandonment cap cleans up. Deliberately no heartbeat-based earlier detection — an absent phone is indistinguishable from a phone in a drawer, and 5 days of encrypted storage is the cheaper error.
2. **Retention expires while held:** ERROR hold → flip to `failed_final(retention_expired)`, delete artifacts, honest copy on next poll or `/retry` (409); a document_fault tombstone survives, visible (§C). ADMINISTRATIVE hold → artifacts deleted, hold persists as metadata; status reports `needs_reupload`; a subsequent identical upload adopts the held identity (§C). A fresh upload of a non-held, honestly-finished document mints a fresh job.
3. **Same bytes, different user:** no interaction, by construction (per-user coordinator, per-user R2 prefix), and this is a privacy boundary, not an optimization gap — cross-user adoption would leak one account's processing results to another on the strength of a hash. A global content-addressed processing cache is flagged as a possible future cost optimization requiring its own PHI-boundary ruling; explicitly not designed here.
4. **Same bytes, different patient profile (same user):** distinct job under the `(content_hash, patientId)` key (§C). Costs a duplicate processing run; buys correct profile binding.
5. **Adoption races GC:** structurally excluded — adoption check, retention transition, and artifact deletion for a given user's jobs all execute inside the single-threaded coordinator DO; existence is checked in the same turn that answers 409. Residual race (phone adopted, then grace expired before its result fetch): the result endpoint returns a distinct 410 `result_expired`, and the phone's 404/410 handling falls back to fresh upload.
6. **Account deletion with documents in retention:** no such endpoint exists in the Worker today (verified) — flagged as a dependency this design cannot absorb. Requirements for whoever builds it: delete the `park/{userId}/` prefix, destroy the coordinator's state (including admission records and holds), purge job-DO shards for that user's jobs, scrub `ingest_jobs` rows; PHI-free ledger export rows may be retained for accounting.
7. **Duplicate upload while blocked (balance):** in-flight arm adopts; the phone receives the held state (administrative, subscription) and shows subscription messaging. Already correct under the inversion; noted because blocked entries live in the queued array and thus the in-flight arm.
8. **Retry storm from the UI:** `/retry` during a cooldown returns 202 with `retry_at` — adoption of intent, no spend, no epoch draw (a poke that admits nothing draws nothing; only an actual dispatch draws). Repeated re-*enqueues* of the same bytes are counted by the admission record and surface at 4 (§C).

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

### F.8 Identity and persistence facts governing Rung 6's shape (verified 2026-07-29)

Two code facts the call-site audit did not carry, both load-bearing for how Rung 6 must be built:

1. **Section ids are not stable across codex rebuilds.** `buildSectionsFromCodex` mints every section id with `crypto.randomUUID()` (`pipeline-shared.js:1840`, Pass C: `g.id = crypto.randomUUID()`). The rebuild is deterministic in *content* — same stored vendor parse result, same line text, same ordering — but not in *identity*. Therefore a prior generation's `section_status` rows cannot be matched by `section_id` against a freshly rebuilt section list. The repair path never hits this because it reads the *stored* `sections@{gen}` shard (`ingest-do.js:2118`), whose ids are the same ones `section_status` was written with. Any pre-assembly reuse must do the same — adopt the stored shards — or match sections by content instead of id.
2. **Nothing is persisted mid-pass.** `processParse` writes all its shards — `codex`, `parsed_pages`, `sections`, `atoms_narrative`, `section_status` — strictly after `runAtomPass` returns (`ingest-do.js:779-784`, call at :759). An invocation that dies at section 17 of 30 leaves nothing reusable; and in the concurrent-storm shape, the second and third invocations start before the first has written anything, so a read-prior-status check at entry buys them nothing. `runAtomPass` is a pure function with no persistence hook (`pipeline-shared.js:713-804`).

Also verified: `ATOM_PASS_PROMPT_ID = "pass1_atomization"`, `ATOM_PASS_PROMPT_VERSION = "v4"` (`pipeline-shared.js:104-105`) exist as constants — the version stamp Rung 6a's reuse gate needs is one field on the shard header. Atoms carry `section_id` (`pipeline-shared.js:777`), so a prior generation's completed atoms are section-attributable and splice-able, exactly as the repair path already exploits (`ingest-do.js:2174-2182`).

Consequences, folded into §3 and the ladder: reading prior-generation `section_status` at `processParse` entry is *almost* sufficient for the sequential re-claim case, provided the stored codex+sections are adopted along with it (id alignment) and the prompt version matches (staleness); that is Rung 6a, and it is a transplant of mechanics the repair path already proves out. Content-addressing remains required only for mid-pass checkpoint durability (Rung 6b), where by definition no completed shard set exists to adopt. The concurrent storm is bounded by rung 2's pre-spend fence, not by either reuse mechanism.

### Plain-language summary of what gets re-paid on each retry path

- **Repair retry** (a job that already finished as complete_partial and is being healed by the Tier-1/Tier-2 repair executor): cheap and narrow. It reuses the stored parse/codex output, touches Bedrock only for the sections still marked failed, and never talks to LlamaParse/LlamaExtract again. Claim A describes this correctly.
- **In-flight parse-arm retry** (a watchdog reverts a stuck PROCESSING parse arm back to WAITING, and a later poll or webhook re-claims it before the job has ever assembled): expensive and blunt. `processParse` has no memory of which sections already succeeded in a concurrent or prior attempt over the same document — it rebuilds the codex and reruns the Atom Pass over every section, every time it's re-entered. It does not re-submit the PDF to LlamaParse/LlamaExtract (same vendor job id, just re-fetched), but it does re-pay Bedrock for every section, including ones that already succeeded. Claim B describes this correctly, and this is the path that produces "N re-claims × 30 Bedrock calls" duplication, not the repair path.
- **A full fresh re-ingest:** pays for everything again — vendor parse/extract credits plus a full 30-section Bedrock Atom Pass plus PHI/KT/summary passes — the ceiling case.

---

## G. Token gate plug points — the F-NEW-MX contract

This design does **not** design the token gate. F-NEW-MX designs it separately. What is fixed here, so MX can build against a defined contract without reopening this design, is *where* the gate attaches, *what it is called with*, *what it can return*, and *what the pipeline does with each return*. For context only (MX's to design, not consumed here): the owner's stated shape is estimate-before-spend; a ~20% overrun tolerance where under-tolerance completes and over-tolerance holds; no token deduction while a user is at the gate — the document comes back pending, never half-processed; internal cost capture continues regardless of what the user is charged.

**The gate is a pure decision function.** It holds no counters, owns no spend records, and has no state machine of its own: spend truth lives only in the §2 ledger (which it reads), stop states live only in §B2's hold machinery (which it triggers), classification lives only in §4's taxonomy (`spend_cap` / a token-gate reason under the administrative kind), and its decisions are recorded as §4 phase events. Until MX ships, the gate function is absent and every point below defaults to proceed — the plug points are inert, not stubbed policy.

Three plug points:

| Point | Where (exact) | Called with | May return | Pipeline action per return |
|---|---|---|---|---|
| **P1 — admission** | Coordinator dispatch loop, where the OD-1 balance gate already sits (`ingest-queue-do.mjs:360-387`), checked per entry before `dispatchOne` | `{userId, jobId, key, point:"admission", estimate:{llama_credits_est: pages_estimate × tier rate}, ledger: empty rollup}` | `proceed` / `hold(reason)` / `defer` | proceed → dispatch. hold → entry becomes `held(administrative, reason)`, no vendor spend, phone polls the held state. defer (transient, e.g. account state unreadable) → skip this fire, retry next alarm — exactly the balance gate's existing "skip this tick" behavior |
| **P2 — post-parse, pre-Atom-Pass** | `processParse`, between the section-set computation (`ingest-do.js:753`) and `runAtomPass` (`:759`) | `{jobId, attemptId, point:"pre_atom_pass", estimate:{bedrock_tokens_est over atomPassSections: section count, capped input chars (ATOM_PASS_PER_SECTION_CHAR_CAP), plus projected PHI/KT/summary}, ledger: rollup to date (includes the vendor parse already spent)}` | `proceed` / `hold` | proceed → run the pass. hold → persist the parse shards already in memory (codex/sections/parsed_pages/parse_vendor_meta — fetched and built, sunk cost preserved), complete the lease cleanly, job → `held(administrative, token_gate)`, no Bedrock intent ever written. The phone sees pending-held, not a half-processed document |
| **P3 — intent-write backstop** | The §2 ledger-intent ceiling check, before every paid call | `{attemptId, vendor, op, estUnits, ledger: running actuals}` | `proceed` / `hold` | hold → abort before the call (this *is* the pre-spend fence; the gate check co-locates with the existing ceiling check, one code path), job → held. This is where MX's overrun tolerance bites mid-pass: actuals exceeding estimate × tolerance stop before the next call, never mid-call |

Why P2 exists and where it sits: the hard constraint is that a job must not walk deep into processing before hitting a gate, and Bedrock cost is only knowable after parse — the section list is the cost basis, and `ingest-do.js:753` is the first line where it exists. P2 is the last moment a hold is completely clean: everything spent so far (vendor parse) is persisted and reusable, and nothing downstream has started. What P2 needs from the ledger to decide there: the job's rollup to date (the parse spend already recorded at intent time) plus the estimate basis it computes from the section set — both already exist under rung 1; no new accounting.

Resume semantics: gate-clear releases the administrative hold (§B2; human/user release resets the epoch count). Within §A's 5-day retention the job re-claims and — with Rung 6a — adopts the persisted codex/sections and runs the Atom Pass from zero completed sections at no repeated vendor cost. After retention, the hold has outlived its artifacts: status says `needs_reupload`, the next enqueue of the same key adopts the held identity (§C), and the vendor parse is re-paid. P3 holds are the one lossy case pre-6b: sections completed by the current invocation before the hold are not persisted and will be re-run on resume — acceptable until 6b, and one more datum for the rung-1 decision on 6b.

Billing separation, restated as the invariant MX must honor: ledger rows are written unconditionally (§2) — a held, comped, or under-tolerance-completed job's internal cost is captured identically; what the user is charged is computed by MX from those rows, never the other way around. A `spend_cap` or token-gate stop is an administrative hold with full ruling-4 visibility (NCC notice, holds panel). No second budget process, no separate meter, no gate-private counters exist anywhere in this design.

---

## Implementation ladder, restated where changed

- **Rung 0** (config + deploy step): raise the R2 lifecycle rule `expire-park-2d` → `expire-park-7d` (retention 5d + margin). No code. Must precede any code that retains past 2 days.
- **Rung 1:** ledger + taxonomy, recording only — plus the `retention_state`/`delete_after`/`attempt_epoch`/`hold_kind`/`hold_reason` columns land here as recording-only groundwork.
- **Rung 2:** leases. Now also the stated safety precondition for keeping the ageless in-flight adoption, and the mechanism that bounds the concurrent-storm shape (§F.8) — Rung 6 does not address the storm and doesn't need to.
- **Rung 3:** epochs (job-DO-owned, per §B's rung-3-review epoch-ownership ruling) + ceilings (epoch ceiling and the already-enforcing LlamaCloud gate only — Bedrock enforcement is F-NEW-MX's, not rung 3's, per §2's rung-3-review ceiling-scope ruling) + signature memo (section- and job-level), then 3b: failed-retryable state split, the hold model's state + NCC notice rows (§B2 — required by the epoch ceiling, which stops into holds), epoch-aware re-claim, the `/retry` and `/cancel` endpoints, removal of the eager R2 deletes (bytes now retained; the 7-day rule is the only deleter until rung 5), dispatch-exhausted entries joining the visible-hold/retry surface (§B's rung-3-review dispatch-attempts ruling — so no failure class is invisible or unretryable), and **Rung 6a — prior-generation shard reuse in `processParse`** (§3): adopt stored codex/sections/atoms/section_status when the prompt-version stamp matches, run only non-succeeded sections, splice — a transplant of the repair path's proven mechanics, pulled forward because §B makes re-claims a designed-for event and 6a is what makes a re-claim epoch cost (sections remaining) instead of (all sections). F-NEW-MW still lands at the end of 3; the known-unbilled-rejection refinement to the submit cap lands with it.
- **Rung 4:** breaker + admission control (admission records: cooldowns, tombstones, duplicate-submission counter) + dedupe inversion + force-fresh flag — one admission-control mechanism, ships together. iOS's §D changes track against the rung-3b contract and must be live before rung 4's inversion reaches production (rollout-order note in §C).
- **Rung 5:** observability export + NCC panels (including holds & tombstones) + the retention sweeper (principled GC begins — 12h/5d enforcement with the repair-quiescence guard; F-NEW-MJ closes here). Granularity per locked ruling 5: staging full-step always; production transitions-only on success, full step detail on failure.
- **Rung 6:** now **6b only** — content-addressed incremental section checkpoints, keyed (hash of section input text, prompt version), written during the pass (§3, §F.8). Build/skip decided at end of rung 1 on ledger data: it pays only if death-mid-pass and P3 mid-pass holds are material Bedrock spend after 6a and the leases land.
- **F-NEW-MX** hard-triggers immediately once rung 3b (L4) ships — not a soft "after rung 3," per §2's rung-3-review ceiling-scope ruling: it needs the hold machinery (§B2) for refusal and ledger data for a real Bedrock ceiling number. Its plug points (§G) exist from rung 3b and default to proceed until MX ships.

---

## Does not solve

Sunk vendor spend; Bedrock 429 quota policy; alerting/paging (hold notices are durable NCC rows, not pages); cross-user fairness; already-leaked shards; the token gate's policy itself (F-NEW-MX); near-duplicate document detection beyond exact content-hash equality.

---

## Contradictions requiring owner ruling

- **R2 deletion site count (§0, Correction 2):** the text asserts "there are four" R2 deletion sites, then enumerates five — the post-createMeta delete (ingest-do.js:1795-1801), the `/enqueue` rollback (ingest-queue-do.mjs:251), retireToRecent-to-failed on coordinator-failed (:481), retireToRecent-to-failed on dispatch failure (:524), and blocked-entry expiry. The list above is preserved verbatim; the count is not reconciled here — needs an owner ruling on which figure, or which list item, is wrong.

---

## Open rulings

1. Ceiling numbers — exact LlamaCloud-credit and Bedrock-token spend ceilings (§2).
2. BAA coverage of R2 — verification required before ship; grouped with the existing release-checklist BAA item.
3. Account-deletion surface — required by E.6, doesn't exist, out of this design's scope; needs filing as its own item.
4. Rung 6b — build/skip at end of rung 1, on ledger data showing whether death-mid-pass and mid-pass gate holds are material spend after 6a + leases (§3, §G).
5. "Apparently-same" documents beyond exact `(content_hash, patientId)` equality — the duplicate-submission counter (§C) is hash-exact; recompressed or re-scanned duplicates of the same document evade it. Needs its own detection design if it matters.
6. Rung 6a placement — designed into rung 3b here (it is cheap and §B makes re-claims routine); confirm, or push back to its original rung-6 slot.
