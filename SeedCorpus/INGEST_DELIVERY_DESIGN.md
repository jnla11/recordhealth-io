# INGEST_DELIVERY_DESIGN.md — Server-to-Device Delivery Layer (v1)

Status: DRAFT v1
Last verified: 2026-08-07

**Provenance:** produced in one Fable design session on 2026-08-07, against INGEST_LIVENESS_DESIGN.md v5, WORKER_ARCHITECTURE.md (L6/L7 state as of 2026-08-06), the app repo through `d3db472`/`308d0a9`, and ROADMAP items F-NEW-LI, F-NEW-OI, F-NEW-LJ. Shape-not-spec: this doc fixes the architecture, the invariants, and the phase boundaries; exact copy, exact numbers marked as rulings, and code-level naming are decided at implementation or by the owner rulings in §9.

---

## 0. Problem

The liveness contract's server half heals jobs; nothing built ever *reaches the phone*. Incident 2026-08-06 (staging job `8f7a760d`, F-NEW-OH/OI): a 6m42s vendor parse blew the client's 150s poll ceiling, the phone rendered terminal failure, the server's auto-retry healed the job to `complete` — and the record stayed "couldn't read this document" indefinitely, because the phone never re-polls a terminal job and no server-to-device channel exists.

The phone-initiated half now ships (app `d3db472`): the check-on-open reconcile and the `/retry` `already_complete` refusal both adopt a server-completed job onto a record parked as failed, fetching the withheld result instead of re-parking the failure. This design is the server-initiated half: APNs push (F-NEW-LI, owner-ruled first-class), stranded-result detection, and the retention guard that keeps the unacked-success arm from deleting results the phone simply hasn't heard about.

**Constraints, owner-ruled, not revisitable:**

1. **No new polling loops.** Everything here is event-armed one-shot alarms, hooks on writes that already happen, or a query added to the already-ruled L7 infrequent dead-DO catch cron.
2. **No vendor names or vendor concepts on any user-facing surface** — push copy included.
3. **Bytes leave the device only on explicit user action.** A push never triggers an upload; a nudge tap opens the app, and any re-upload remains a user act.
4. **Existing wire meanings unchanged.** `running` still means "processing, no action needed" — and therefore no push may fire for a state whose wire meaning is no-action (Site A dispatch holds push nothing).

---

## 1. The layering principle (locked posture)

**Check-on-open is the reliability floor. Push is the accelerator. Push is never the sole channel for anything.**

Silent pushes are documented-unreliable (iOS throttles `content-available` to a small hourly budget, drops them under Low Power Mode, and guarantees nothing); visible pushes are reliable-ish but the user can decline permission entirely. So nothing in the system may *depend* on a push arriving. The layering:

- **Floor:** the shipped `IngestRecoveryCoordinator.sweep(trigger:)` on cold launch and foreground — `listJobs` (complete + `fetched=false`), the `d3db472` adoption path, the reattach planner. Correctness lives here. It already handles every outcome this design pushes about; the design adds zero new client recovery machinery.
- **Accelerator:** a push is only ever a *poke to run the floor sooner*, plus user-visible copy where the user should be told. The push payload is never a data channel — the result always travels over the existing authenticated `/result` fetch.
- **Degradation is the floor by construction:** permission denied, token stale, APNs down, or the whole send path broken → behavior is exactly today's shipped behavior. No fallback code path exists to write.

Consequence for the client: the push handler's entire job is `sweep(trigger: .push)` (a new trigger case on the existing coordinator) — idempotent, reentrancy-guarded, ordering unchanged. A push arriving while the app is foreground-polling is a no-op sweep.

---

## 2. APNs infrastructure

### 2.1 Feasibility, validated honestly

APNs' provider API is HTTP/2-only with ES256-JWT (token-based) auth. Both halves check out for a Cloudflare Worker:

- **ES256 signing:** Workers WebCrypto supports P-256 ECDSA (`importKey` pkcs8 + `sign`) natively. Definitive.
- **HTTP/2 to APNs:** Workers' outbound `fetch` negotiates HTTP/2 with `api.push.apple.com`, and this is a proven working pattern — a Workers-native APNs client exists (FiveSheepCo/cloudflare-apns2), Cloudflare's own Agents documentation describes sending APNs pushes directly from Workers, and workerd issue #4841 records APNs HTTP/2 requests *working* in Workers (the bug was a local-dev discrepancy). Caveat, stated honestly: this is observed platform behavior, not a contractual Cloudflare guarantee of HTTP/2 to arbitrary origins. Phase P0 is therefore a half-day throwaway spike, not an article of faith — and if it ever regresses, the layering in §1 means delivery degrades to the floor, not to data loss.

No third-party push relay is designed or wanted. If P0 fails, that becomes an owner decision (§9 ruling 10), not a silent substitution.

### 2.2 Token registration and custody

- **App side:** standard `UNUserNotificationCenter` authorization + `registerForRemoteNotifications`; the APNs device token posts to `POST /v1/push/register` (behind the blanket JWT gate) and re-registers on every launch (tokens rotate silently). The `aps-environment` entitlement follows the build: DEBUG builds mint *sandbox* tokens and talk to the staging Worker (`BackendEnvironment`), RELEASE builds mint *production* tokens and talk to the production Worker — token environment and Worker environment align by construction, no environment field needs trusting.
- **Storage: the user's `IngestQueueDO` coordinator, `qstate.push`** — `{device_token, updated_at, last_send_outcome}`. Latest-writer-wins, refresh-on-request posture (the same lesson as `internal_user_id`: never fossilize a captured identifier). Why the coordinator and not Neon: (a) every trigger site in §3 already terminates at the coordinator (`/job-terminal`, hold transitions, dispatch refusals); (b) it is per-user, single-threaded custody that dies with the account teardown E.6 already requires; (c) the coordinator is addressed by Apple sub, which `ingest_jobs.user_id` carries — so the dead-DO cron (§4) can reach the right coordinator from a bare Neon row. No second copy of the token exists anywhere; NCC never needs it.
- **Custody posture:** a device token is not PHI, but it is a device-routable identifier — never logged, never exported, never written to Neon, cleared on APNs `410 Unregistered` and on account deletion. v1 stores one token per user (latest device wins); multi-device token sets are a ruling (§9.5).

### 2.3 The send path

One module (`src/apns.mjs`-shaped), used only from the coordinator:

- **JWT:** minted from `APNS_TEAM_ID` / `APNS_KEY_ID` / `APNS_PRIVATE_KEY` (wrangler secrets, per env; the .p8 key is account-level and may serve both environments — provisioning is an owner act in the Apple Developer portal, production secret handling per the existing credential rules). Cached in-isolate and refreshed on Apple's 20–60-minute reuse window; a cold isolate mints fresh, which is fine.
- **Endpoint:** staging Worker → `api.sandbox.push.apple.com`, production Worker → `api.push.apple.com`; `apns-topic: com.recordhealth.app`.
- **Response handling is evidence, not control flow:** `200` → record success (this is "token valid, app installed" evidence — load-bearing for §5); `410 Unregistered` → record the uninstall evidence with Apple's timestamp and clear the stored token (**this is the uninstall signal iOS otherwise lacks**, and §A's "iOS provides no uninstall signal" premise is now only true for users who never granted push); `400 BadDeviceToken` → clear + loud log (environment mismatch, a config bug); `403` → our auth broke — this one feeds the L7 ntfy alert path, it is an ops outage of the accelerator; `429`/`5xx` → drop, no retry queue in v1 (the nudge ladder in §4 retries naturally, and the floor exists).
- **Observe, never gate** — same standing rule as `error_events` and L7 alerting: sends fire on `waitUntil` after state is persisted; no push outcome ever touches job state, blocks a turn, or burns an attempt of anything. The APNs fetch goes through an injectable seam so the test harness can script outcomes (same discipline as `vendorFetch`, even though this is not a pipeline vendor call).

---

## 3. Triggers and the visible/silent policy

**Structural decision: completion pushes are not fired at the terminal write — they are the first rung of the stranded-nudge ladder (§4).** At terminal, the coordinator arms a one-shot alarm at +T₁ (short — minutes); when it fires, it checks `fetched` and pushes only if the phone hasn't already collected the result. A user who watched the import finish (the normal 12–33s case) fetches within seconds and *no push ever exists* — the redundant-notification problem is solved structurally, not with client-side dedup. "Job complete" and "heal after the phone gave up" collapse into one trigger: both are "terminal-success with `fetched=false` at T₁" — the server never needs to know whether the phone gave up, rendered failure, or was simply closed; `fetched=false` is the only fact that matters, and it is already recorded.

| Event | Push | Class | Notes |
|---|---|---|---|
| Terminal success (incl. heal/repair convergence, which already resets `fetched=FALSE`), still unfetched at T₁ | **Visible** | "document ready" meaning | The F-NEW-OI fix's server half. Tap → app open → floor sweep → `d3db472` adoption path lands the heal on the failed-parked record |
| `failed_final` (true dead end, incl. `retention_expired`) | **Visible** (ruling §9.3) | "needs your attention" meaning | No `fetched` equivalent exists for failure observation — the phone doesn't ack failures it renders. v1 recommendation: push after the same T₁ delay unconditionally (dead ends are rare, high-value); a failure-observation ack is the alternative, listed as a ruling |
| Administrative hold **waiting on the user** (subscription/balance; token gate when F-NEW-MX ships; `needs_reupload` after artifacts expire) | **Visible** | "needs your attention" meaning | The user is the releaser (§B2) — telling them is the release path. Copy meanings only; wording is F-NEW-MV's |
| ERROR holds, Site A dispatch holds, breaker parks | **None** | — | Wire meaning is `running` / "no action needed" (locked). A push would contradict the locked meaning. The server is the releaser; the user has nothing to do |
| Hold released / auto-retry started / epoch drawn | **None** | — | Interior states. The eventual terminal's nudge covers the outcome |
| Stranded past later thresholds | **Visible** (nudge 2..N) | "document ready" meaning | §4's ladder, capped |

**Silent pushes: none in v1** (ruling §9.6 to confirm). Rationale: every silent-push use case here ("wake the app to reconcile early") is an optimization of the accelerator, the mechanism is documented-unreliable, and it adds a background-execution surface (background fetch, budget management) for no correctness gain — the floor already reconciles on open. A v2 may attach `content-available` to visible pushes so a delivered-but-untapped notification still pre-runs the sweep; explicitly out of v1.

### 3.1 Payload rules — locked invariant

The push payload carries **job ids / phase / hold kind only. NEVER PHI, never document names, never user content, never vendor names.**

- Custom keys: `{job_id, kind: ready|attention, hold_kind?}` — ids and closed-enum members, nothing else. The payload is produced by one pure builder with an exact allowlist, pinned by a grep-able test, same posture as the receipts route's `RECEIPT_FIELDS` and the L7 alert-payload rule (design §4 amendment 2026-08-06: "job id, phase, and hold kind/reason ONLY"). A new field means editing the allowlist and its test, on purpose.
- Alert copy is generic by construction ("A document finished processing" / "A document import needs your attention" — *meanings*; wording joins F-NEW-MV's copy scope). No interpolation of anything user- or document-derived into copy, ever. No vendor names or vendor concepts (constraint 2).
- This invariant is pinned here as a sibling of §4's PHI allowlist rule in the liveness design; any future push type inherits it.

---

## 4. Stranded-result detection

**Definition:** a job in terminal success (`complete`, or `complete_partial` converged to `complete`) with `fetched = FALSE` past a threshold. `ingest_jobs` already carries both facts; nothing new is needed to *define* stranded — only to *surface* it.

Two legs, honoring "no new polling loops":

- **Leg 1 — event-time (primary).** At terminal-success notification (`/job-terminal`, and the repair-convergence path that resets `fetched=FALSE`), the coordinator records a nudge state on the entry/`job_index` and arms a one-shot alarm at +T₁. On fire: read `fetched`; if false, send nudge 1 (visible) and arm +T₂; ladder capped at N nudges (T₁/T₂/…/N are ruling §9.1; shape suggestion: minutes → hours → ~a day, N=3). The existing `POST /v1/ingest/jobs/:id/fetched` route additionally pokes the coordinator (`/job-fetched`, best-effort) to clear pending nudge alarms — event-driven cancellation, with the alarm's own `fetched` re-read as the backstop when the poke is lost. One-shot alarms armed by events are not polling loops; an idle coordinator arms nothing (same discipline as `HELD_REEVAL_INTERVAL_MS`).
- **Leg 2 — dead-DO catch (backstop).** The L7-ruled infrequent catch cron (alerting leg (c), interval pending the Neon-autosuspend ruling) gains one query: `status='complete' AND fetched=FALSE AND age > threshold`. For each hit whose coordinator never ran its ladder (wiped DO, pre-design job), the cron pokes the user's coordinator — addressable because `ingest_jobs.user_id` *is* the Apple sub the coordinator is keyed by — and the coordinator runs its normal nudge logic. The cron never sends pushes itself; one sender, one custody point.

**Consumers:**

1. **The push nudge ladder** (above).
2. **The NCC stranded panel** (owner-ruled: NCC covers BOTH staging and production). A read-only `GET /v1/admin/ncc/stranded` per Worker over `ingest_jobs` — job id, age since terminal, nudge count/outcomes, last push evidence class (§5's vocabulary), environment — joining the existing five NCC routes (`isADIAdminAuthorized`, user-flow `sql` binding, `ncc-queries.mjs` pattern). For NCC to render nudge evidence, the coordinator mirrors it to `ingest_jobs` (columns like `nudge_count`, `last_nudge_at`, `push_evidence` — recording-only, best-effort, DO-authoritative; the same mirror posture as `hold_kind`/`attempt_epoch`; DDL is a committed migration + owner-run per the Neon write rule).
3. **Owner alerting via ntfy — integrate, don't redesign.** The L7 alerting scope (owner ruling 2026-08-06) already defines the delivery (ntfy push to owner's phone), the payload rule (ids/phase/hold-kind only), and the observe-never-gate posture. Stranded adds one alert *class* to that machinery: a job stranded past a higher owner-threshold (ruling §9.8, e.g. 24h) fires through the same emitters. No second alerting path.

---

## 5. The retention guard — stranded vs. abandoned

§A's unacked-success arm reads "no `fetched` within 5 days of terminal" as app-deleted abandonment and deletes both artifact classes. That inference was the best available when iOS provided no uninstall signal. **The push channel changes the evidence:** every send returns exactly the missing fact.

**Evidence vocabulary** (recorded per job by the send path, mirrored for NCC):

| Evidence | Meaning |
|---|---|
| `uninstalled` — last send returned APNs `410 Unregistered` | The app is gone. Abandonment **confirmed**, no longer inferred |
| `reachable` — last send returned `200`, still unfetched | Token valid, app installed: the phone simply hasn't heard/opened. **Stranded, not abandoned** |
| `no_channel` — no token ever registered (permission denied, pre-push app) | No evidence either way — today's world |
| `undelivered` — sends attempted but failing for *our* reasons (403 auth, send path broken) | Our machinery is the reason the phone hasn't heard. Must never silently justify deletion |

**Retention arm, redesigned (supersedes §A's bare 5-day timer for unacked success — must be ruled before the L7 retention sweeper builds this arm):**

- `uninstalled` → delete at the 5-day mark per §A, unchanged — now standing on evidence instead of inference.
- `no_channel` → delete at 5 days per §A, unchanged. Honest: without a channel the floor cannot be improved, and the phone retains the source (re-upload on next open's 410 stays the named consequence).
- `reachable` → **the case this design exists to protect.** The user paid for this result; deletion forces a re-upload and a re-pay for work whose output we are holding *and whose owner we can prove is still installed*. Recommendation (ruling §9.2): extend retention to a hard outer cap (owner picks the number; the tension is real — every extension day is PHI-at-rest, the same compliance surface §A priced), keep nudging on the ladder's tail cadence, and surface the job on the NCC stranded panel + an ntfy alert as it approaches the cap. At the outer cap, delete honestly (`retention_expired`, tombstone-free — re-add is sanctioned recovery). Rejected alternative: keep-forever-while-reachable — unbounded PHI retention keyed to user inaction, the exact posture §A already rejected.
- `undelivered` → the 5-day delete does **not** proceed silently: the job surfaces as an owner alert (our delivery bug is the cause), and the delete is deferred to the same outer cap. A deletion justified by a channel we broke would be the retention design lying to itself.

Interlock with §A's other arms: the acked-success 12h grace, the repair-quiescence guard, terminal-retryable 5-day windows, `/cancel`'s immediate delete, and administrative-hold metadata persistence are all untouched. This section refines exactly one classification — "never fetched" — from one meaning into four.

---

## 6. Interaction with the shipped check-on-open reconcile

Explicitly, because the seam between the two halves is where F-NEW-OI lived:

- **Push adds a trigger, not a path.** The app's push handler calls `IngestRecoveryCoordinator.sweep(trigger: .push)` and nothing else. Ordering (orphans → `listJobs` reconcile → planner), the reentrancy guard, per-patient serialization, and the `isComplete` duplicate guard are all the shipped ones. A push and a foreground event racing produce two idempotent sweeps.
- **The heal lands through `d3db472`'s adoption path.** A healed-after-giveup job is a completed-unfetched job whose local record is parked failed; reconcile (or the `/retry` `already_complete` refusal) already adopts it and fetches the withheld result. The push merely collapses "until the user next opens the app" to "within a notification tap."
- **Resurrection writes stay guarded.** The choke-point guard + `attempt_epoch`/`recovery: true` contract (L5, design §D) is unchanged — a push-triggered sweep observing an epoch advance re-enters working state through the same gate as a poll would. No push-special write path exists.
- **`/fetched` closes the loop both ways:** it already clears the client bookmark; it now also pokes the coordinator to cancel pending nudges (§4 leg 1), so the accelerator stands down the moment the floor has done the work.
- **Permission denied** (or any channel failure) degrades to precisely the shipped behavior — the fallback *is* the floor, no code represents it.

---

## 7. What this design does not do

Fix the 150s poll ceiling or re-poll-after-giveup (F-NEW-OH — related, separate); fix the dead Try Again button (F-NEW-OJ); background-fetch/silent-push reconcile (v2 candidate, §3); Android/web push; marketing/engagement notifications of any kind (this channel is ingest-outcome-only by design — widening it is an owner decision); the ntfy owner-alert machinery itself (L7's, integrated not redesigned); badge-count management (deliberately none in v1 — a wrong badge is worse than no badge).

---

## 8. Phased build plan

Phases sized for single Claude Code sessions; app and api work separated; each api phase deploys staging-first per the standing rule. Doc updates ride each phase per convention.

- **P0 — api, throwaway spike (gate for P2+).** From the staging Worker: import the .p8 via WebCrypto, mint the ES256 JWT, `fetch` a visible push to a hand-captured sandbox device token; observe it on hardware. A scratch dev-build Xcode run supplies the token (not a shipped app phase). Exit criterion: documented 200 + banner on the device, and the JWT-cache reuse verified across two sends. If it fails: stop, ruling §9.10.
- **P1 — app: registration + trigger plumbing.** `aps-environment` entitlement, permission request (placement per ruling §9.4), `registerForRemoteNotifications`, re-register on every launch, `POST /v1/push/register` via `BackendEnvironment`, push handler → `sweep(trigger: .push)` (new trigger case). Buildable and device-testable against P0's spike sender before any server triggers exist.
- **P2 — api: registration route + send module.** `/v1/push/register` behind the JWT gate → coordinator `qstate.push` (latest-wins); productionized `src/apns.mjs` (JWT cache, env-split endpoints, outcome/evidence recording incl. 410-clear, injectable fetch seam); pure payload builder with the locked allowlist + grep-able pin test.
- **P3 — api: triggers + nudge ladder.** Terminal-success one-shot alarm at T₁, ladder to N with `fetched` re-read, `/fetched` → coordinator cancel poke, `failed_final` and user-action-hold visible pushes per §3's table, suppression-by-ladder verified (a fast fetch sends nothing).
- **P4 — api: stranded surfacing.** Dead-DO cron query + coordinator poke (leg 2); `ingest_jobs` nudge/evidence mirror columns (committed migration, owner-run in Neon per the write rule); `GET /v1/admin/ncc/stranded` + NCC console panel (both environments); stranded alert class wired into the L7 ntfy emitters.
- **P5 — api: retention classification arm.** §5's four-way evidence classification implemented as the precondition of the L7 retention sweeper's unacked-success arm. **Sequencing constraint: the sweeper's unacked-success arm must not build before this phase's design is ruled** — building the bare 5-day timer first would ship exactly the deletion this design forbids.
- **P6 — app + device: verification pass** (F-NEW-NR pattern). Matrix: kill-app-mid-job → complete → push → tap → result persisted; heal-after-rendered-failure → push → `d3db472` adoption corrects the card; permission-denied → floor-only behavior verified; DEBUG/sandbox + RELEASE/production alignment; uninstall → staging-side 410 evidence recorded; foreground race → no duplicate handling.

Dependencies: P1 ∥ P0; P2 → P3 → P4; P5 gates only the L7 retention arm; P6 gates calling F-NEW-LI/OI done. F-NEW-MX's token-gate hold, when it ships, inherits the user-action-hold push from §3's table with zero new design.

---

## 9. Decisions requiring owner ruling before build

1. **Nudge ladder numbers:** T₁ (first-nudge delay), subsequent spacing, and the cap N. Shape recommended in §4 (minutes / hours / ~a day, N=3); numbers are the owner's.
2. **Stranded-but-`reachable` at retention (§5):** confirm the extend-to-outer-cap recommendation over delete-at-5d and keep-while-reachable, and pick the outer cap number. This is a PHI-at-rest duration decision, same compliance surface as §A's original 5-day ruling. Also: confirm `undelivered` defers deletion to the same cap.
3. **`failed_final` pushes:** confirm push-unconditionally-after-T₁ for dead ends (no failure-observation ack exists), or commission a failure-seen ack as its sibling suppression signal; and rule which `failed_final` classes push (include `retention_expired`?).
4. **Permission prompt placement:** at first import completion-in-background risk (contextual, recommended) vs. first launch; and whether to use provisional (quiet) authorization as a middle path.
5. **Multi-device:** single latest-wins token (v1 recommendation) vs. a token set per user. Latest-wins means a user's iPad can silently steal the channel from their iPhone.
6. **Silent pushes:** confirm none-in-v1 (§3), with `content-available`-assisted background reconcile parked as v2.
7. **NCC stranded panel:** the display threshold, and whether the panel gets an owner action (e.g. force-renudge) or stays read-only in v1 (recommended: read-only).
8. **Owner-alert threshold:** the stranded age that fires ntfy (§4 consumer 3), distinct from the panel threshold.
9. **APNs provisioning:** owner creates the APNs auth key (one account-level .p8 for both environments) and sets the three wrangler secrets per env — production values user-handled per the standing credential rules. Confirm the single-key-both-envs posture.
10. **Only if P0 fails:** whether HTTP/2 unavailability is met by a minimal self-hosted relay (new infrastructure), deferral of the whole layer, or something else. Not decided in advance; listed so failure has a named owner path instead of an improvised one.
11. **Mirror columns on `ingest_jobs`** (`nudge_count`, `last_nudge_at`, `push_evidence`): confirm the recording-only Neon mirror (needed by NCC and the cron), per the committed-migration + owner-run rule.
12. **Copy:** confirm push alert wording joins F-NEW-MV's copy scope (meanings locked here: "document ready" / "needs your attention"; no document names, no vendor names — invariant §3.1).

---

## 10. Doc and backlog follow-ups (not in this commit)

ROADMAP: annotate F-NEW-LI with this design pointer + phase plan; annotate F-NEW-OI (server half designed here; app half is P1/P6); cross-reference F-NEW-OH (poll ceiling — untouched here). INGEST_LIVENESS_DESIGN.md: §A's unacked-success arm gains a pointer to §5 here (the four-way classification supersedes the bare timer *when ruled*); the "iOS provides no uninstall signal" premise gains the push-evidence caveat. DATA_MODEL.md: `/v1/push/register` wire shape when P2 ships (joins the F-NEW-OG contract-doc gap). All follow the single-file-commit rule for this session and land with their own phases.
