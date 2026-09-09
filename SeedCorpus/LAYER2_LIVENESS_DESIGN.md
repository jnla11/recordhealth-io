# LAYER2_LIVENESS_DESIGN.md — On-device context layer rebuild failure, heal ladder, and the phone error channel (v1.2)

Status: DRAFT v1.2 (shape, not spec; owner rulings 1–7 fixed, the five 2026-09-09 v1.1 rulings closed into §4, five further 2026-09-09 flagged items now ruled; no open rulings)
Last verified: 2026-09-09

v1.2 (2026-09-09): the copy table now matches `IngestProgressPresentation`'s own convention exactly (title, body and action punctuation and case, no divergence note left to justify one), the two no-stored-summary rows share their second line with their stored-summary counterparts instead of "no action needed", and a merely owed rebuild shows no warning line on any surface until its first failed attempt — closing `F-NEW-SL`.

v1.1 (2026-09-09): the five rulings §5 held open are closed — a record completes when its Layer 2 rebuild fails, `failure_id` is the seventh ntfy field, the ladder numbers stand, the copy is re-ruled with "out of date" struck from every user-visible string, and P1–P4 stay ahead of R3 step 7 — and the copy ruling reverses the emergency card: it hides nothing, keeping every clinical row with the warning line above them.

Date: 2026-09-08. Specified against `RecordHealth_App @ 029af4d` (R3 steps S, 0–6 shipped; steps 7–9 open; suite 1821 passed / 151 classes / 1 excluded, TEST_LOG 2026-09-08) and `recordhealth-api @ 573d34e`. Every line cited below was re-read at those commits. Where this doc and shipped code disagree, `docs/ARCHITECTURE.md` §3.2 / §3.8 is authoritative for what shipped, and this doc is authoritative for what is ruled.

**What this doc owns.** Two roles no living doc owns today: (1) the liveness of the phone's derived layers — a `ContextLayerBuilder.rebuild` that fails, what marks it, what heals it, what the user sees; (2) the phone-to-server error channel — the one sender, its second event class, the Worker route that receives it, and how it reaches the NCC feed and ntfy. `INGEST_LIVENESS_DESIGN.md` owns server ingest liveness and the NCC pattern; `INGEST_VOCABULARY_DESIGN.md` §6 owns the vocabulary beacon's event classes and PHI gates; `PACKAGE_DESIGN.md` §2.1 owns rebuilding views from a package; `RELATIONSHIP_DESIGN.md` and `docs/archive/R3_RELATIONSHIPS_SPEC.md` own the relationship homes the rebuild writes. This doc points at each and restates none.

---

## 0. Verification of the brief's ground truth (re-read, five corrections, one sharpening)

The 2026-09-09 audit lines were re-read against the code. They hold, with these corrections:

1. **Stage numbering.** `rebuild(for:)` (`ContextLayerBuilder.swift:26-373`) has nine stages in this order, and this doc uses these names everywhere: **1 atoms** (loads + atom construction, `:28-241`), **2 walker log** (`WalkerLogWriter.reconcile` + `RelationshipProjectionMaterializer.materialize`, `:249-291`), **3 stale-others** (`UnsortedContextInvalidator.markAllStale(except:)`, `:302`), **4 linker** (`ClinicalEventLinker.link`, `:310`), **5 patient file** (`replaceWalkerEntries`, `:321-330`), **6 index** (`RelationshipIndex.load`, `:335`), **7 save** (`ContextStore.save`, `:355`), **8 care-graph mark** (`:361`), **9 eager rebuild** (`:363-371`). The brief's "stage 5" and "stage 7" match this numbering.
2. **Stage 2 is already loud in the ring; stage 5 is not.** A walker-log write failure emits `.catchFired` at site `walkerLogWriter.writeFailed` and self-heals by diff (R3 spec §C.1 finding 33). The patient-file write failure at stage 5 is `print` only — no ring event, no counter (`:326-329`). Stage 8 (`CareGraphStore.markStale`) cannot throw, but its cached branch flips the flag **in memory only** and never re-saves (`CareGraphStore.swift:101-108`); `ContextStore.markStale` re-saves with `try?` and swallows a failed save with no log line (`ContextStore.swift:96-109`).
3. **Four callers load the pre-move layer after a failed rebuild, not one.** `SegmentationMatchEvaluator.performAutoAssign` (`:73-91`), `SegmentationConfirmView.rebuildContexts` (`:664-676`), `SettingsView` FHIR wipe (`:724-729`) and `UnsortedContextInvalidator.eagerRebuild` (`:49-61`) all call `ActiveContextLayer.load` **outside** their `do/catch`; `load` takes its `!cached.isStale` fast path (`ActiveContextLayer.swift:30`) and serves whatever `.context.enc` held before the move, flagged fresh. The two segmentation paths that route through `unsortedSetDidChange` mark stale first, so a failed rebuild there blanks the layer (`current = nil`) instead — a different wrong.
4. **`error_events` has no allowlist constraint in SQL.** `migrations/ncc1_error_events.sql` declares no CHECK on `source` or `environment`; the allowlist is the three literal writers (`worker`, `ingest_do`, `ingest_queue_do`) plus the migration's comment block. The rule stands as a convention enforced by code and tests, and a fourth writer joins it the same way.
5. **ntfy has no `error_events` reader and no spike rule.** `src/ingest-alerts.mjs` never touches the table; every alert is a hook at an ingest hold/terminal site (WORKER_ARCHITECTURE § L7 alerting, leg (a)). "Exhaustion reaches the existing ntfy path" therefore means a new hook at the receive route, not a query — §3.I.
6. **Sharpening: `.storageFailed` has exactly one producer**, the rebuild double-failure at `RecordIngestPipeline.swift:2513`, and a manual "Try again" on it forks to `.freshSubmission` (`IngestRetryMode.swift:68-70` — the bookmark was released at fetch, and the no-bookmark guard answers before the cause is read). A Layer 2 disk failure today re-uploads the PDF and re-pays the whole server pipeline. That is the wrong-shaped retry §3.D retires.

R3 state, verified: steps S, 0, 1–6 shipped (`fa2a557` → `fd77537`, plus the 2026-09-08 drift-fix set and `029af4d`); `hasRunR3RelationshipWipe` and `RelationshipProjectionSweep` do not exist in the tree. Steps 7, 8, 9 are open.

---

## 1. Owner rulings (fixed; this doc designs inside them)

1. Rebuild failure is loud on every path, not only ingest.
2. Granularity is per stage: the design names which stages can fail independently, and a retry targets the failed stage through its existing door, never by writing a home directly.
3. Healing is an on-device retry ladder, persisted across launches, with a bounded attempt count. Exhaustion leaves a user-visible out-of-date state, never a fresh-looking wrong layer.
4. Every failure attempt and every heal outcome is reported to the server and shown in the NCC feed, grouped under one id per failure. Only ladder exhaustion sends an owner push (ntfy). Spike alerting is later, under F-NEW-LJ.
5. NCC covers staging and production.
6. The care graph is marked stale on the rebuild's failure path, and a record move between patients marks the affected layers and graphs stale on its own, independent of whether the rebuild succeeds.
7. All data is dev data. No migration code, no compatibility shims. Wipe and re-ingest.

Sacred rules that bind hardest here: 2 (no cohabitation — one sender, one marker, one retry regime), 5 (two states of one fact — the ingest path's inline retry versus the ladder), 8 (Layer 2 is regenerable and never load-bearing for Layer 1), 10 (a stage that drops its work names the drop), and the encryption-at-rest invariant for every new file.

---

## 2. The rebuild as it stands: nine stages, what each writes, what each does on failure

| # | Stage | Durable write | Can fail? | Today on failure | Door a retry re-enters |
|---|---|---|---|---|---|
| 1 | atoms | none | no (loads answer `[]`) | — | `rebuild(for:)` |
| 2 | walker log | package header (log + re-seal) per record; `records/{id}.relationships.enc` projection | yes, per record | `.catchFired` `walkerLogWriter.writeFailed`; triples kept in memory this pass; **heals by diff next pass** | `WalkerLogWriter.reconcile`, inside `rebuild` |
| 3 | stale-others | other patients' `.context.enc` / `.graph.enc` stale flags | `try?` inside `markStale` | silent | next `rebuild` (step 3 re-marks) |
| 4 | linker | none | no | — | — |
| 5 | patient file | `profiles/{id}.relationships.enc` (walker partition replaced whole) | yes | **print only**, `linkOutcome` zeroed, build continues | `replaceWalkerEntries`, inside `rebuild` (replace-whole is idempotent) |
| 6 | index | none | no | — | — |
| 7 | save | `profiles/{id}.context.enc` (atomic) | yes | **throws out of `rebuild`**; old file and old cache survive, flagged as they were | `ContextStore.save`, inside `rebuild` |
| 8 | care-graph mark | `.graph.enc` stale flag (cached branch: memory only) | `try?` | silent; **skipped entirely when 7 threw** | next `rebuild` |
| 9 | eager rebuild | another patient's layer (recursive `rebuild`) | its own outcome | print | that patient's own ladder |

Stages before 7 are never rolled back on a later failure, and that is correct: each is idempotent and re-entered by the next pass (2 by diff, 3 by re-mark, 5 by replace-whole). The rebuild's unit of retry is therefore **the whole door**, `rebuild(for:)` — not because the stages are one thing, but because every stage's door is inside it and each stage converges on re-entry. Ruling 2 is satisfied by naming the stage in the outcome (so the caller, the ring, and the NCC feed all say *which* stage), not by minting per-stage entry points, which would be the "writing a home directly" the ruling forbids.

**The independently failing stages, named:** 2 (per record), 5, 7, 8. Stage 3 is a set of stage-8-class marks on other patients. Stages 1, 4, 6, 9 do not fail on their own.

---

## 3. Decisions

### A. Doc home — a new SeedCorpus doc

**Decision: this file, `SeedCorpus/LAYER2_LIVENESS_DESIGN.md`.** The anti-creep rule allows a new doc only for a role no doc owns. Two roles are unowned: derived-layer liveness on the device, and the phone's error channel to the server. The candidates each own something adjacent and none owns these: `INGEST_LIVENESS_DESIGN.md` is server ingest liveness (leases, holds, L7) and its §4 defines the NCC *pattern* this doc reuses; `INGEST_VOCABULARY_DESIGN.md` §6 owns the beacon's *event classes and gates*, and a rebuild-failure event is not vocabulary; `PACKAGE_DESIGN.md` §2.1 owns rebuilding views *from a package*; `docs/ARCHITECTURE.md` §3.2/§3.8 are current-state and gain pointers at step D1. Putting §3.H's sender under the vocabulary doc would make the vocabulary doc own a transport whose first non-vocabulary class is the reason the transport is being generalized. The header carries the two lines the convention asks for.

### B. Relation to R3 — a sibling spec; R3 step 7 is amended to v2.2 and *marks*, it does not rebuild

**Decision: sibling, interleaved; R3 step 7 becomes a gate plus a marker-writer, and the standing heal sweep (§3.E) is the one launch sweep that serves both.** R3 §F's companion sweep is one-shot (a `UserDefaults` key) and "best-effort": it rebuilds every patient itself and writes no state. The heal ladder needs a sweep that runs on every launch and foreground, reads a persisted ledger, and counts attempts. Expanding step 7 into that sweep would put a permanent liveness mechanism under a one-shot gate's key, and a second rebuild loop beside it would be cohabitation. So the split is: **R3 step 7** = the wipe gate exactly as §F specifies, plus the record-level half of its sweep (`PackageRebuildService.rebuildViews(for:, rebuildLayer2: false)` per packaged record), and then **one `ContextRebuildLedger.markOwed(patient, reason: .r3Projection)` per patient** instead of its own per-patient `ContextLayerBuilder.rebuild` + `ActiveContextLayer.load` + `markStale`; the standing `ContextLayerHealSweep` drains those entries on the same launch. The §12 close condition ("wipe, rebuild, identical by entry id") is unchanged — the rebuild still happens on that launch, through the one door, with a ledger row saying it is owed until it lands.

**The R3 spec needs a v2.2 amendment** (the spec is "superseded in place" by convention, v1 → v2 → v2.1). Lines, at v2.1 as read: line 3 (Status: v2.2, and the same-session note gains "step 7 reads LAYER2_LIVENESS_DESIGN §3.B/§3.E for the sweep"), line 4 (Last verified), line 336 (§C.1 failure posture — add: "and the failure is named in `ContextRebuildOutcome.findings` for the pass, §3.C of that doc"), line 466 (§F companion sweep paragraph — the per-patient tail "then one `ContextLayerBuilder.rebuild` + `ActiveContextLayer.load` + `CareGraphStore.markStale` per patient" becomes "then `ContextRebuildLedger.markOwed(_:reason:.r3Projection)` per patient; the standing `ContextLayerHealSweep` rebuilds through the one door and the sweep's own flag is set only after every mark landed"; the "same best-effort posture, no `ingestState` written" clause stays true and gains "a rebuild that fails there is a ledgered failure, not a skipped one"), line 557 (§H step 7 file list gains nothing new but the test line becomes "sweep selection; every packaged patient marked owed"), line 559 (§H step 8 items (b) and (c): the build line and the ContextDump are read after the heal sweep's rebuild; (c) adds "the ledger shows no open entry"), line 561 (§H step 9: ARCHITECTURE §3.7's gate row and a pointer to this doc under §3.2), and §I "Consequences derived from the rulings" (lines 589–598) gains one line: "The R3 sweep marks Layer 2 owed rather than rebuilding it; a failure on that launch is the ladder's, not the gate's." Nothing in §A–§E, §D's tail order, or the single-home table moves.

**Ordering consequence — owner-ruled 2026-09-09 (§4 #9), accepted as designed:** this doc's phone steps P1–P4 land **before** R3 step 7, so step 7 is written once against the ledger rather than as an eleventh throwing caller that P1 would then rewrite. Cost: R3's close moves behind four phone prompts. The alternative (close R3 first, retrofit) was rejected because it builds a caller this design deletes.

### C. Rebuild outcome shape — an outcome value, never a throw, with loudness *inside* the door

**Decision: `rebuild(for:)` returns `ContextRebuildOutcome` and does not throw. The marker write, the stale marks, the ring event and the report are all performed inside `rebuild` — no caller can swallow them, because there is nothing for a caller to swallow.** This is the same move `029af4d` made for the care-graph mark: the pass that replaced (or failed to replace) the layer owns every consequence of that fact.

```swift
// Domain/Models/ContextRebuildOutcome.swift
enum ContextRebuildOutcome {
    /// Stage 7 landed. `findings` names every stage that failed INSIDE a built
    /// layer — a per-record stage-2 write, the stage-5 patient file, a stage-8
    /// mark — each already re-entered by the next pass. Empty means clean.
    case built(ContextLayer, findings: [ContextRebuildFinding])
    /// Stage 7 (today the only throwing stage) did not land. The ledger entry
    /// is already open and the stale marks already attempted when this returns.
    case failed(ContextRebuildFailure)
}
struct ContextRebuildFinding: Equatable { let stage: ContextRebuildStage; let site: String; let errorType: String }
struct ContextRebuildFailure: Equatable { let stage: ContextRebuildStage; let errorType: String; let failureId: UUID; let attempt: Int; let ladder: ContextRebuildLadder.State }
enum ContextRebuildStage: String { case atoms, walkerLog = "walker_log", staleOthers = "stale_others", linker, patientFile = "patient_file", index, save, careGraphMark = "care_graph_mark", eagerRebuild = "eager_rebuild" }
```

Why not a per-section state machine (spec finding 33's convention): a finding is a row, not a state — the next pass re-enters the stage and either the finding recurs or it does not. The outcome carries the findings of *this* pass so a caller (the DEBUG self-check, the archive import report, the build log) can say "built, with the patient file not written" instead of "built". A stage-5 failure inside a `.built` is a finding **and** is emitted to the ring as `.catchFired` at site `replaceWalkerEntries.writeFailed` (closing the print-only gap in §0 item 2) — it is not a ladder failure, because the layer is fresh and correct and the file heals by replace-whole on the next pass. Only stage 7 opens the ladder, because only stage 7 leaves the user with no correct layer.

What each of the ten callers does with it (the eleventh, R3's sweep, is §3.B):

| Caller | Today | Under this doc |
|---|---|---|
| `RecordIngestPipeline.runDownstream:2494` | retry once at 5 s → `needsAttention(.storageFailed)` | reads the outcome; completion per §3.D; no inline retry |
| `ActiveContextLayer.load / refresh` | `current = nil` | publishes freshness (§3.E); never nil on failure when a stored layer exists |
| `PackageRebuildService.rebuildViews:275` | print, counts as success | returns `layer2: .built / .failed(failureId)` in its result; the schema sweep counts `layer2Failed` honestly |
| `ResultSchemaRebuildSweep` | via the above | report gains `layer2Failed`; still never fatal |
| `PatientPackageImporter:373` | print | `ArchiveImportReport` gains `layer2Failed: [patientId]`; per-record outcomes unchanged |
| `AppleHealthImportView:591` | propagates, "Import failed before completing" | Layer 1 and the ledger entry are the import; the summary says the health summary will update automatically; `phase = .error` only for a Layer 1 write failure |
| `UnsortedContextInvalidator.eagerRebuild` | print; loads pre-move layer | reads outcome; `load` after it is honest because §3.F marked stale first |
| `SegmentationMatchEvaluator:75`, `SegmentationConfirmView:664` | print; load pre-move layer | same as above |
| `SettingsView` FHIR wipe (DEBUG) | print | shows the outcome |

Every `_ = try await` becomes `let outcome = await`; the Swift compiler enumerates the callers, which is the proof that none was missed.

### D. Failure marker — a device-global ledger outside the layer; the ingest path's regime retires

**Where.** `Data/Persistence/ContextRebuildLedger.swift`, `@MainActor`, encrypted through `EncryptionService`, at `Documents/diagnostics/layer2_heal.enc` — the same directory, posture and exclusions as `IngestEventLog` (device-global; not in `BackupManifest.essentialPatterns`, which matches nothing under `diagnostics/`; not in `.rhpkg`; survives patient deletion for *other* patients). One entry per patient:

```swift
struct ContextRebuildLedgerEntry: Codable, Equatable {
    let patientId: UUID
    let failureId: UUID?          // nil while merely OWED (no failure yet); minted at the first failed attempt
    var reason: Reason            // .rebuildFailed(stage) | .owed(OwedReason)   — OwedReason: r3Projection | staleMarkFailed
    var attempts: Int
    var openedAt: Date
    var lastAttemptAt: Date?
    var lastErrorType: String?
    var nextAttemptAt: Date?      // nil = due on the next trigger
    var exhausted: Bool
}
```

Why not the alternatives: a key on `ContextLayer` needs a `ContextSchemaVersion` bump and lives in the file whose write just failed; a `profiles/{id}.heal.enc` sidecar needs a `BackupManifest.isDerived` row and a `PatientDeletionService` line and still has nothing to mark when the patient has never had a layer; `patient_index.enc` is the membership authority and must carry nothing else; `UserDefaults` is unencrypted and the encryption-at-rest invariant covers app-derived files. `PatientDeletionService` gains `ContextRebuildLedger.shared.remove(patientId)` beside `ContextStore.deleteAll` (§0 of `PatientDeletionService.swift:85`).

**Relation to `isStale`.** They answer two questions. `isStale` is a property of a *stored layer*: "do not serve this without rebuilding." The ledger is a property of the *rebuild process*: "a rebuild is owed, and here is its heal state." A ledger entry implies the layer must not be served fresh; the converse is not true (a membership move marks stale with no ledger entry, and the next rebuild succeeds silently). The ledger must live outside `.context.enc` because stage 7 is the write that failed, and because a patient with no layer file yet has nothing to flag. So the read side computes one answer from both: `ActiveContextLayer` publishes `freshness` (§3.E) as `.fresh` only when the stored layer is not stale **and** the ledger holds no open entry for the patient. On the failure path `rebuild` still calls `ContextStore.markStale` (best effort) so a later reader that consults only the file is not lied to; the ledger is the floor beneath it, the same "honest floor" `persistStateOrEscalate` names for the index.

**The sacred-rule-5 consolidation.** Two states of one fact exist today: the ingest path's inline 5 s retry plus `needsAttention(.storageFailed(detail: "context_rebuild"))`, and the marker this doc adds. **The ledger survives.** The ingest path's retry regime existed only because no derived-layer liveness existed; with one, it is the retired-regime state. What the ingest state machine loses: the inline 5 s retry (`RecordIngestPipeline.swift:2494-2521`); `AttentionCause.storageFailed` (deleted, not retained producerless — `processingIncomplete`'s retention was a consumer-exhaustiveness convenience, and a second one makes a habit; the `RecordDeletionLiveness`, `IngestRetryMode`, `IngestProgressBar`, `IngestProgressPresentation`, `RecordV2` and `SettingsView` arms go with it); `IngestPass.contextRebuild` as a `needsAttention` stage; the `IngestDiagnostics.storageFailed` process counter and its Settings row. What it keeps: `contextRebuildInProgress` as a Working checkpoint — the rebuild still runs where it runs. What `IngestRecoveryCoordinator` loses: the `.storageFailed` arm of its `manualOnly` switch (`:716`), and nothing else — it never healed a Layer 2 failure and does not start now; the ladder is patient-scoped and has its own sweep (§3.E). A dev device holding a record parked `needsAttention(.storageFailed)` decodes it to `.notStarted` (the lenient `IngestState` decode, ARCHITECTURE §3.8 H.1) and the coordinator adopts it — ruling 7 in action, no shim.

**The completion transaction changes one precondition — owner-ruled 2026-09-09 (§4 #13).** `IngestCompletionGate` today requires "rebuild returned success" (§E.3 point 3) so that `.complete` is never false-green. Under the ruling the record **completes**: Layer 1 and the sealed package are the record (PACKAGE_DESIGN §0.1), Layer 2 is regenerable from them (sacred rule 8), and the thing §E.3 guarded against — a green badge over data nobody can see — is now answered where the data is not visible: the health summary and the record detail each carry the warning line of §3.E, and the ladder is healing. **The precondition becomes "rebuild returned an outcome and, on `.failed`, the ledger entry is open"** — the gate refuses `.complete` if the ledger write itself failed (the floor breach), which is the one case where a green badge would again say something nothing else can contradict. The rejected alternative — keep the record in `needsAttention` and have the ladder flip it to `.complete` on heal — would make the ladder a second `ingestState` writer outside the pipeline (the archive importer is deliberately the only one, CLAUDE.md) and would keep the re-upload "Try again" of §0 item 6. **That "Try again" is retired for this cause**, which is what deleting `AttentionCause.storageFailed` above accomplishes: a Layer 2 disk failure no longer re-uploads the PDF and re-pays the server pipeline; the ladder rebuilds from Layer 1, which is already durable.

**The overrule is recorded, as this doc said it must be.** This ruling overrules `F-NEW-KO` §E.3 point 3's wording. Step D1 (§3.J) writes that overrule into `INGEST_FAILURE_POLICY_DESIGN.md`'s rulings in these words — "a record completes when its Layer 2 rebuild fails; the Layer 2 failure is carried by `ContextRebuildLedger` and the §3.E warning line, never by `ingestState`" — and `F-NEW-SJ` (§7) is that edit's filed id.

### E. The ladder — attempts counted at the door, spacing by rung, one sweep, one copy mapping

**Every call to `rebuild(for:)` for a patient with an open ledger entry is an attempt on that patient's ladder, and the door admits or refuses it.** The ladder is a pure type, `Domain/Services/ContextRebuildLadder.swift`: `admit(entry, now, trigger) -> .attempt(n) | .notDue(until) | .exhausted` and `after(entry, outcome, now) -> entry`. `rebuild` consults it first: a refused attempt returns `.failed` with the existing failure id and no stage run (nothing written, nothing reported — a refusal is not an attempt), except that a **demand** trigger (the user tapped "Update Now") is always admitted and resets an exhausted entry, because a user act is new information, the same reasoning that lets a reconnect reset an exhausted transport budget (ARCHITECTURE §3.8 §B).

| Rung | Admitted when | Spacing after a failure at this rung |
|---|---|---|
| 1 | the failing call itself (any caller) | due on the next trigger, not before 1 min |
| 2 | next trigger at or after +1 min | +10 min |
| 3 | +10 min | +1 h |
| 4 | +1 h | +6 h |
| 5 | +6 h | **exhausted** |

**Owner-ruled numbers, 2026-09-09** (§4 #14): five attempts, spacing 1 min / 10 min / 1 h / 6 h, the one-minute floor on rung 1, no jitter. The shape follows `IngestRetryScheduler`'s series, jitterless (one device, one patient, no thundering herd). No inline immediate retry: the retired 5 s retry was a transport-blip idiom applied to a disk or key failure, and a save that failed 50 ms ago failing again proves nothing. The rung-1 minimum spacing is what stops a foreground/launch flurry from burning the budget in a minute.

**Triggers, and who fires them.** (a) **Any rebuild request for the patient** — the ingest tail (a new Layer 1 write for that patient; a success closes the entry, and a Layer 1 write on an *exhausted* patient re-opens a fresh ladder because new data is new information), a patient switch (`ActiveContextLayer.load`), a membership move's eager rebuild. (b) **`ContextLayerHealSweep.sweep(trigger:)`** (`Domain/Services/`, `@MainActor`, single-flight like the coordinator) — enumerates due entries and owed entries, rebuilds each through the door; called from `RecordHealth.swift`'s launch `.task` immediately after `IngestRecoveryCoordinator.shared.sweep(trigger: .coldLaunch)` (`:1098`), on the scenePhase `.active` edge beside `.foreground` (`:1177`), on patient switch (`:1158`), and from a **self-armed wake timer** at the earliest `nextAttemptAt` (the coordinator's `scheduledRetry` idiom) so a rung does not wait for the user to background the app. It is a separate sweep from the coordinator on purpose: the coordinator's subject is records and server jobs, this one's is patients and derived layers; folding the second into the first would make a record-recovery planner enumerate patients. What they share is the lifecycle sites and the single-flight idiom, not a loop. (c) **Demand** — the "Update Now" action.

**User-visible state at each rung, one mapping.** `ActiveContextLayer` gains `@Published private(set) var freshness: ContextLayerFreshness` beside `current`:

```swift
enum ContextLayerFreshness: Equatable {
    case fresh
    case notCurrent(ContextLayerNotCurrentReason)   // a stored layer is served; it is not current
    case unavailable(ContextLayerNotCurrentReason)  // no stored layer exists for this patient
}
enum ContextLayerNotCurrentReason: Equatable { case healing(attempt: Int, of: Int); case owed; case exhausted }
```

**One rename, under ruling 4(e).** At v1.0 these were `case outOfDate` and `ContextLayerOutOfDateReason`. The copy ruling bars "out of date" from every user-visible string, and these two names do not stay internal: the case name is what a `ContextLayerFreshnessPresentation` test failure, the DEBUG self-check line and a future ring `site` string would print. They are renamed to `notCurrent` / `ContextLayerNotCurrentReason` — the phrase this doc's own comment already used for the state — so no name in this design carries a word the product may not say. Nothing else in the design is renamed; `freshness`, `ContextLayerFreshnessPresentation`, `ContextRebuildLedger` and the ladder types carry no such word.

`load` never sets `current = nil` on a failure when a stored layer exists: it serves the stored layer **with `freshness = .notCurrent(...)`**, and a view that renders atoms from it renders **one warning line above them and keeps rendering every one of them**. Copy through one pure mapping, `Views/ContextLayerFreshnessPresentation.statusCopy(for:) -> (title, body, action?)?`, the `IngestProgressPresentation` convention in full — calm, em dash, no vendor names, no document names, a title with no trailing period, a body that is a stopped sentence, an action label in Title Case — rendered identically by the Dashboard patient summary card, `PatientProfileView`, the record-detail margin-dot header and the emergency card — owner-ruled copy, 2026-09-09 (§4 #16, punctuation and the two rulings below):

| Freshness | Title | Second line | Action |
|---|---|---|---|
| `.notCurrent(.healing)` | Health summary couldn't be updated | Retrying automatically. | — |
| `.notCurrent(.exhausted)` | Health summary couldn't be updated | Tap to update. | Update Now |
| `.unavailable(.healing)` | Health summary isn't ready yet | Retrying automatically. | — |
| `.unavailable(.exhausted)` | Health summary couldn't be built | Tap to update. | Update Now |

The two `.notCurrent` rows are the ruled strings, quoted exactly, now in `IngestProgressPresentation`'s own house style throughout — no divergence-from-convention note survives to justify keeping one. The two `.unavailable` rows drop their v1.0 second line — owner-ruled 2026-09-09: a no-stored-summary surface says the same thing a stored-summary surface does, "Retrying automatically." while the ladder runs and "Tap to update." with Update Now once it is exhausted; only the title still says whether a summary exists to fall back on. P2 spells the strings from this table and from nowhere else.

`.notCurrent(.owed)` and `.unavailable(.owed)` are not in this table because they render **no copy at all** — owner-ruled 2026-09-09, closing `F-NEW-SL` (§7) rather than leaving it open. A merely owed rebuild — a ledger entry with `reason: .owed`, `failureId == nil`, no attempt yet failed — has nothing to report: `statusCopy(for:)` returns `nil`, and the surface renders exactly as it would with no open entry: the stored layer served silently, or the surface's own empty state if none exists. The warning line turns on at the *first failed attempt*, which mints `failureId` and promotes the reason to `.healing`. This is why `.owed(.r3Projection)` — the reason R3 step 7 marks every packaged patient (§3.B) — never shows "Health summary couldn't be updated" on the first launch after the R3 wipe: the sweep marks the entry owed, not failed, and the heal sweep gets its own pass at rebuilding before there is anything to warn about.

The attempt number is not shown (the ingest surfaces show none either). Ruling 3's guarantee is structural: the only way `freshness` reads `.fresh` is a stored layer with `isStale == false` and no open ledger entry, and the only writer of that pair is a `.built` outcome that closed the entry. `.owed` renders no copy but is not `.fresh` — the entry is still open, so a later failed attempt on it has a `freshness` value to promote rather than a fact to invent.

**The emergency card hides nothing — owner-ruled 2026-09-09 (§4 #16), reversing v1.0.** It carries the same warning line as every other surface and renders **every** row beneath it at every freshness, user-entered and derived alike. v1.0 had it render the title *in place of* its clinical rows when `freshness != .fresh` and justified that by ARCHITECTURE §12.5; **both the behaviour and that justification are struck.** §12.5's "disclaimers don't work under stress; the only safe treatment is absence" is a rule about *unconfirmed* atoms — data that may belong to a different person — and the card's hard exclusion of those is untouched by this doc and not extended by it. A layer that is merely not current holds this patient's own confirmed data; withholding an allergy the card is already holding is the worse outcome under stress, and the warning line is what makes the state honest.

**A DEBUG fault lever** (`ContextRebuildFaultLever`, `#if DEBUG`, a Settings toggle "Fail the next Layer 2 save", one-shot) exists so the ladder can be driven end to end on a device — the phone half of the Worker's `INGEST_FORCE_SECTION_FAILURE` idiom, compiled out of RELEASE rather than refused at runtime.

### F. Stale marks — the failure path marks inside `rebuild`; membership marks are the index's

**Failure path.** On `.failed`, before returning, `rebuild` calls `CareGraphStore.markStale(for: careGraphStaleTarget(afterRebuildFor: patientId))` and `ContextStore.markStale(for: patientId)` — the same target the success path marks, so `careGraphStaleTarget` keeps its one answer and the 2026-09-08 "a rebuild that threw marks nothing" behaviour (TEST_LOG, care-graph entry) is reversed by ruling 6. Two hardenings ride along: `CareGraphStore.markStale`'s cached branch persists (today memory-only, §0 item 2), and a `markStale` whose re-save fails is no longer `try?`-silent — it opens an `.owed(.staleMarkFailed)` ledger entry, so a layer that could not be flagged is still not served fresh (the ledger is the read side's second input, §3.D).

**Membership mutation.** **Owner: `PatientRecordIndex`.** The one-home rule as `029af4d` stated it — the pass that replaces the fact owns the consequence — applies to membership exactly: the index is the sole membership authority (CLAUDE.md, Sprint A step 4), so the invalidation a membership change implies is written where the change is persisted, inside `mutate` after `save` succeeds. A pure `MembershipStaleTarget.patients(before:after:allPatients:)` (`Domain/Services/`) names the set: A → B yields {A, B}; unsorted → B or B → unsorted yields every patient (an unsorted record rides in every layer, ARCHITECTURE §12.5); `remove` yields the owner or every patient; `removePatient(.moveRecordsToUnsorted)` yields every patient. The index marks each through `ContextStore.markStale` and `CareGraphStore.markStale`. Consequences: `UnsortedContextInvalidator.unsortedSetDidChange(eagerRebuildFor:)` loses its mark half (`markAllStale` is now the index's for membership, and stays the builder's at stage 3 for a walker write) and keeps the eager-rebuild half; `SegmentationMatchEvaluator`, `SegmentationConfirmView`, `PatientPackageImporter`, `AppleHealthImportView` and `RecordsStore`'s four `assign` sites write no mark of their own (`RecordsStore`'s five membership-adjacent `CareGraphStore.markStale` lines at `:173, :328, :502, :631` and `:1107` — the four creates and `deleteRecord`'s `remove` — are deleted as copies; the sixth at `:676` sits on a record *update* that moves no membership and stays, because the index never sees that write). Ruling 6's independence is then structural: the mark lands in `mutate` before any caller reaches its rebuild, and a failed rebuild after a move finds a stale layer, a stale graph, and — after `rebuild` returns `.failed` — an open ledger entry. `QuarantineService.moveToUnsorted` marks like any other (a quarantine record carries no facts, so the marks cost a rebuild that changes nothing; a special case would be a second rule).

### G. The phone event class — three ring kinds, one failure id, a payload with no place for identity

**Kinds** added to `IngestDiagnosticEvent.Kind` (closed enum, `IngestDiagnosticEvent.swift:32-112`): `contextRebuildFailed` (one per admitted attempt that failed; `context`: `stage`, `attempt`, `failureId`, `trigger`), `contextRebuildHealed` (a `.built` that closed an open entry; `context`: `attempt`, `failureId`), `contextRebuildExhausted` (the ladder's last failure; `context`: `attempts`, `failureId`). All three are immediate-flush kinds (rare, high value, the `manualRetry` reasoning). `site` is the caller (`runDownstream`, `activeContextLayer.load`, `healSweep.coldLaunch`, `healSweep.timer`, `segmentation.autoAssign`, `demand`); `errorType` is `IngestDiagnosticEvent.errorTypeName(error)` — the Swift type or typed case name, never `localizedDescription`; `detail` is **not populated** for these kinds (on-device the ring may hold a description for other kinds; this class never has one anywhere, so the wire builder cannot leak one). `patientId` rides on the ring row, on device, as it does for every kind today; it never leaves.

**The failure id** is minted once, at the first failed attempt that opens a ledger entry, stored on the entry, stamped on every attempt's row and on the heal or exhaustion row, and retired when the entry closes. A later failure for the same patient mints a new id. It is the only correlator on the wire.

**Decode consequence and the rule.** `Kind` is `String, Codable` with no lenient `init`; a ring holding a kind a build does not know fails to decode as a whole, and `loadIfNeededLocked` resets the ring to empty and appends a `.sweepAnomaly` breadcrumb (`IngestEventLog.swift:254-271`). Adding three kinds means a ring written by this build resets on an older build. **Rule:** `Kind` is closed and only ever grows; the decode stays strict; no tolerant `init`, no per-row skip (sacred rule 3 — the ring is dev diagnostics, and R3 step 7's gate wipes it in the same release window regardless). A build that adds a kind states the reset in its commit message and nothing else.

**The wire payload** (`Domain/Models/ContextRebuildReportPayload.swift`), keys 1:1 with the columns §3.I adds, structurally unable to carry identity — no `record_id`, `patient_id`, `job_id`, `detail` or free-text field exists on the type, pinned by a test that hashes its `CodingKeys`:

```jsonc
{ "app_version": "1.4.2 (871)",
  "events": [ { "failure_id": "<uuid>", "event": "context_rebuild_failed", "stage": "save",
                "site": "healSweep.coldLaunch", "error_type": "EncryptionError.keyUnavailable",
                "attempt": 2, "observed_at": 1788912345 } ] }
```

`event` is the closed three-value vocabulary above in snake case; `stage` the nine of §2; `attempt` an integer; `observed_at` epoch seconds, the device's clock (the beacon's "client owns the clock" ruling, F-NEW-PP requirement 3). Never `localizedDescription`; never a count of atoms or records (a count is a fact about the patient).

### H. The sender — one actor, two classes, two watermarks, two routes, three triggers

**Decision: `VocabularyBeacon`'s flush skeleton is lifted into `Domain/Services/DeviceReportSender.swift` (an actor), and `VocabularyBeacon` as a type is retired into it (sacred rule 2).** What stays vocabulary-specific moves whole into `VocabularyDriftReport` — `build()` with its two gates, the `Drift`/`Anomaly` arrays, the reserved-namespace refusal, the `recordId` refusal, `VocabularyBeaconOutbox`'s per-dedup-key count watermark, and the route `/v1/client-drift`; not one gate or payload line changes, and `test/client-drift.test.mjs`'s contract is untouched. The sender owns what was never vocabulary: the in-flight guard, the never-block posture, the ack-on-2xx rule, the transport call, and the triggers.

```swift
protocol DeviceReportClass {
    static var route: String { get }                              // "/v1/client-drift" | "/v1/client-errors"
    func build(ring: [IngestDiagnosticEvent], appVersion: String) -> (body: Data, watermark: Watermark, suppressed: Int)?
    func recordSent(_ watermark: Watermark)                        // advances ONLY on 2xx; never called otherwise
}
actor DeviceReportSender { static let shared; func flush(reason:) async }   // iterates the two classes; one in-flight bit per class
```

`ContextRebuildReport` is the second class: its watermark is the set of ring event ids already acknowledged, persisted encrypted at `Documents/diagnostics/report_outbox.enc` (bounded to the ring's 500; an id evicted from the ring is dropped from the set), so each flush sends exactly the rows not yet acked and a refused batch stays owed. `LLMClient.postClientDrift` (`LLMClient+Vocabulary.swift:109`, the hardcoded path) generalizes to `LLMClient.postDeviceReport(route:body:)` with the same four-case never-throwing outcome; the class supplies the route.

**Flush triggers.** The two existing sites stay (`VocabularyRefreshService.swift:99`, `ResultSchemaRefreshService.swift:125` — refresh, then report) and two are added: **emission** — `IngestEventLog.emit` of any immediate-flush kind belonging to a report class schedules a flush after the ring's own 2 s debounce, so a failure attempt reaches the server within seconds of happening rather than at the next hourly dictionary refresh; **background** — the scenePhase → background handler calls `flush(reason: .background)` after `IngestEventLog.flushNow()` (`RecordHealth.swift:1168`), fire-and-forget, never awaited past the handler. Never-block and ack-on-2xx are unchanged in wording and in test. The vocabulary class gains the two new triggers for free, which is the design's intended side effect.

**Doc drift retired in the same step:** `VocabularyBeacon.swift:14-21` and `LLMClient+Vocabulary.swift:12-17` say the route does not exist; `docs/ARCHITECTURE.md:743` says "The Worker route does not exist yet — OR-19 cut it … Tracked as `F-NEW-PP`." All three are false since 2026-08-22 (WORKER_ARCHITECTURE § Client drift beacon) and are rewritten by P4, the step that touches the files.

### I. Server route and table — a fourth writer into `error_events`, five named columns, one alert hook

**Decision: `error_events`, not a new table.** Ruling 4 says "shown in the NCC feed", and the feed, its trend, its filters and its console already exist over this table; a new table would need a sixth panel and a second read path for what is, by its own definition, an error event. `vocabulary_misfire_events` is not touched — its write semantics are upsert over observation classes and its purpose is curation (INGEST_VOCABULARY_DESIGN §6, the L7 seam), and a rebuild failure is neither.

**Migration `migrations/ncc2_error_events_device_reports.sql`** (committed; the owner applies staging then production before the route deploys, per DATABASE_LAYOUT's workflow; ruling 7 — no data touched, no backfill):

| Column | Type | Why it is a column and not a message |
|---|---|---|
| `app_version` | `TEXT` | the axis every device-side row is read by; already a column on the misfire log |
| `failure_id` | `TEXT` | the group key ruling 4 asks for; indexed `(failure_id, created_at)` |
| `stage` | `TEXT` | ruling 2's granularity, filterable; a suffix on `error_code` would fragment the feed's exact-match filter |
| `attempt` | `INT` | orders a failure's rows and shows the rung |
| `observed_at` | `TIMESTAMPTZ` | the device's clock, clamped as the beacon clamps (`[2025-01-01, now]`); a device offline for a day reports five attempts in one flush, and `created_at` alone would collapse them to one minute |

Existing columns carry the rest: `source = 'ios'` (the fourth conventional value, hardcoded at the route, never client-supplied), `environment` from `env.ENVIRONMENT`, `error_code` = the event (`context_rebuild_failed` / `_healed` / `_exhausted`), `message` = `error_type` (a Swift type name, the one string the row carries), `route` = the device site (the column already means "where it happened"; the console renders `${method} ${route}` and a null method renders the site alone — no new column, no overloaded meaning), `method`/`status_code`/`request_id`/`job_id`/`import_id` null. The standing rules apply unchanged: no user identifiers (the payload type has no slot), no JSONB, fire-and-forget for the *logger* — with the beacon's one stated exception carried over: the route **awaits its own write**, because the answer is the product and the device advances its watermark on it.

**Route `POST /v1/client-errors`** (`src/client-errors.mjs`), registered beside `/v1/client-drift` behind the blanket `/v1` JWT gate (`src/index.js:7960`). Body cap 64 KB (Content-Length pre-check, 413), event cap 50. Validation from scratch, trusting nothing: `event` in the closed three-value set, `stage` in the closed nine, `attempt` a positive integer ≤ 100, `failure_id` a UUID, `observed_at` clamped, `error_type` an identifier-shaped string ≤ 200 chars (the beacon's `ident()`), `site` likewise, `app_version` ≤ 200; unknown keys dropped; a malformed event refuses the batch **whole** (400, `stored: 0`) — deterministic, so the device learns rather than looping. The ack contract is the beacon's verbatim: **200 only after the one transaction committed and `stored === received`**; anything else is non-2xx with `stored: 0`. Refused (non-2xx) responses are themselves logged by the choke point as `source = 'worker'`, which is how a misbehaving app build shows up beside its own rows.

**NCC feed grouping.** `GET /v1/admin/ncc/errors` returns the five new columns and gains `?failure_id=`; `resolveNccRange`/`resolveFeedLimit` unchanged. The console's feed table adds a **failure** column (first 8 characters of the id, click-to-filter, the source-filter idiom), and **collapses rows sharing a `failure_id` into one group row** — the group shows attempts, the latest `error_code`, first and last `observed_at`, `stage`, `app_version`, and expands to its attempt rows. Nothing else in the console or the trend changes; the trend's `by_source` picks up `ios` on its own. Spike alerting over these rows is F-NEW-LJ (c), later, as ruled.

**Exhaustion → ntfy.** After the commit, for each stored `context_rebuild_exhausted` row the route calls `publishAlert(env, ctx, ALERT_KIND.CONTEXT_REBUILD_EXHAUSTED, fields)` — a new kind in the closed title map (priority 4, `failed_final`'s), the eighth emission site, and the first outside ingest. Held to the standing rules: `sanitizeAlertFields` is the only builder, the payload stays inside the allowlist, nothing branches on the publish. `phase` carries the stage and `environment` its stamp. **`failure_id` becomes the seventh field in the ntfy payload — owner-ruled 2026-09-09 (§4 #23).** The failure id had no slot in the six-field allowlist, and CLAUDE.md's own words ("adding a seventh field is an owner ruling, not a refactor") required the ruling; it is given. The field is a UUID minted on the device that names no person, no document and no job. With it the `Click` header deep-links to `#errors&failure_id=<id>&env=<environment>`, built from the sanitized row exactly as `nccJobDeepLink` builds from `job_id`; `sanitizeAlertFields` gains the field and remains the only builder. Failed and healed rows never alert (ruling 4; the same "a channel that fires on ordinary operation is one nobody reads" reasoning as leg (a)).

**Both environments** by construction: `BackendEnvironment` sends a DEBUG build to staging and a RELEASE build to production; the route deploys to both Workers, staging first.

### J. Sequencing — ten prompts across two repos, Worker first, R3 close after P4

Suite green at every boundary; counts per CLAUDE.md § Testing; one `TEST_LOG.md` entry per phone step and one `SESSION_LOG.md` entry per Worker step. Baselines: app 1821 / 151 classes / 1 excluded; Worker per its last `SESSION_LOG` entry (this doc does not guess it).

| # | Repo | Step (one prompt each) | Tests named |
|---|---|---|---|
| W1 | api | **Migration + route.** `migrations/ncc2_error_events_device_reports.sql`; `src/client-errors.mjs` (validation, clamps, the whole-batch refusal, the ack contract); `insertErrorEvent` gains the five columns (existing callers pass null); route registered beside `/v1/client-drift`; `wrangler.toml` untouched. Owner applies the migration staging → production; deploy staging → production. | `test/client-errors.test.mjs` (closed vocabularies, every refusal class, clamping, the strict column allowlist incl. a PHI-shaped negative control, `stored === received` on 200, never-throws sweep); `test/error-log.test.mjs` (+ the five columns, null for legacy callers) |
| W2 | api | **Feed grouping + the alert hook.** `GET /v1/admin/ncc/errors` `?failure_id=` + columns; `ncc-console/app.js` failure column, click-filter, group collapse; `ALERT_KIND.CONTEXT_REBUILD_EXHAUSTED` + the route's post-commit hook; the seventh ntfy field `failure_id` and its deep link (§3.I, ruled). Pages deploy explicit. | `test/ncc-queries.test.mjs` (filter resolution), a grep pin that the four L7 panel bodies still read no DO; `test/ingest-alerts.test.mjs` (+ the kind, the negative case for failed/healed rows, the PHI-shaped payload sweep against the new caller); `test/client-errors.test.mjs` (+ the hook fires once per exhausted row, never on 4xx) |
| P1 | app | **Outcome shape.** `ContextRebuildOutcome`, `ContextRebuildFinding`, `ContextRebuildFailure`, `ContextRebuildStage`; `rebuild` never throws; stage 5 emits `.catchFired` `replaceWalkerEntries.writeFailed` and a finding; the ten callers read the outcome (table in §3.C); `PackageRebuildService`/`ResultSchemaRebuildSweep`/`ArchiveImportReport` count `layer2Failed`; `AppleHealthImportView` stops overstating. No ledger yet — a `.failed` is returned and logged only. | `ContextRebuildOutcomeTests` (stage vocabulary raw values pinned; a stage-5 throw yields `.built` with one finding), `PackageRebuildServiceTests` (+ layer2 outcome), `ResultSchemaRebuildSweepTests` (+ `layer2Failed`), `ArchiveImportReportTests` (+ field) |
| P2 | app | **Ledger, ladder, sweep, freshness, ingest consolidation.** `ContextRebuildLedger` (+ `PatientDeletionService` line), `ContextRebuildLadder` (pure), `ContextLayerHealSweep` (+ the four lifecycle sites and the wake timer), `ActiveContextLayer.freshness`, `ContextLayerFreshnessPresentation`, the warning line on Dashboard / `PatientProfileView` / record detail / emergency card (which keeps every clinical row beneath it), "Update Now"; the DEBUG fault lever; the ingest path loses the 5 s retry and `.storageFailed` with every arm (§3.D), `IngestCompletionGate`'s third precondition per §3.D. | `ContextRebuildLedgerTests` (round trip, remove-on-delete, floor breach named), `ContextRebuildLadderTests` (every rung boundary, refusal is not an attempt, demand admits and resets exhaustion, a Layer 1 write re-opens), `ContextLayerHealSweepTests` (single-flight, due selection, owed drain, timer arming), `ActiveContextLayerFreshnessTests` (`.fresh` only from a `.built` that closed the entry; never nil with a stored layer), `ContextLayerFreshnessPresentationTests` (every non-owed case has copy; no copy while owed and unfailed; no case says "fresh" while an entry is open; no string in the mapping contains "out of date"), `EmergencyCardViewModelTests` (+ every row renders at every freshness — the warning line is above the rows, never instead of them), `IngestCompletionGateTests` (edited precondition), `AttentionCauseTests` (case gone), `IngestRetryModeTests` (arm gone) |
| P3 | app | **Stale marks.** Failure-path marks inside `rebuild`; `CareGraphStore.markStale` cached branch persists; a failed mark opens `.owed(.staleMarkFailed)`; `MembershipStaleTarget` (pure) + the `PatientRecordIndex.mutate` hook; the caller-side mark copies and `unsortedSetDidChange`'s mark half deleted. | `MembershipStaleTargetTests` (A→B, unsorted↔B, remove, removePatient), `CareGraphStaleMarkTests` (+ the failure path marks the same target), `PatientRecordIndexTests` (+ marks land after save, not before; none on a refused mutation), `UnsortedContextInvalidatorTests` (eager half only) |
| P4 | app | **Event class + sender.** The three `Kind` cases; `ContextRebuildReportPayload`; `DeviceReportSender` with `VocabularyDriftReport` and `ContextRebuildReport`; `VocabularyBeacon` retired; `LLMClient.postDeviceReport(route:body:)`; emission and background triggers; the three doc-drift lines rewritten (`VocabularyBeacon.swift` header → the new file's, `LLMClient+Vocabulary.swift:12-17`, `ARCHITECTURE.md:743`). | `DeviceReportSenderTests` (two classes, two watermarks, one in-flight bit each, 2xx-only advance, 404/5xx/URLError acknowledge nothing, never throws), `ContextRebuildReportPayloadTests` (CodingKeys hash pinned; no identity slot exists — a negative control that tries to encode a record id fails to compile is documented, the runtime pin is the key set), `VocabularyDriftReportTests` (the beacon's existing tests retargeted byte-for-byte: gates, refusals, watermark), `IngestEventLogTests` (+ the three kinds are immediate-flush; a foreign kind still resets the ring) |
| R3-7 | app | **R3 step 7 as amended (v2.2).** The wipe gate per §F; `RelationshipProjectionSweep` runs `rebuildViews(rebuildLayer2: false)` per packaged record and `markOwed(.r3Projection)` per patient; the heal sweep drains on the same launch. | R3 §G's sweep-selection test, plus "every packaged patient is marked owed and the sweep flag is set only after the last mark" |
| R3-8 | — | **Device proof (owner, no commit)**, R3 §H step 8 (a)–(e) as written, plus (f): arm the DEBUG fault lever, trigger a rebuild, observe the warning line (and the emergency card still showing every row beneath it), the ring rows, the staging feed group, then clear the lever and observe heal and the healed row; (g): arm it five times through foreground/timer rungs to observe exhaustion, the ntfy push, and "Update Now" healing it. | numbers into `TEST_LOG.md` / `SESSION_LOG.md` |
| R3-9 | app | **R3 step 9 docs** as written, plus the ARCHITECTURE §3.7 gate row saying the sweep marks owed. | — |
| D1 | app + api | **This doc's docs.** `CLAUDE.md` (architecture rule block: outcome-not-throw, ledger, ladder, sender; Key Files rows; Storage Paths for `diagnostics/layer2_heal.enc` and `report_outbox.enc`; the Layer 2 refresh snippet at CLAUDE.md § Known Architectural Constraints loses `CareGraphStore.markStale` — already the builder's — and gains "read the outcome"), `docs/ARCHITECTURE.md` §3.2 (always-current invariant restated as: always current, or served under a warning line that says it could not be updated), §3.8 (swallow-point policy: Layer 2 failure is loud through the ledger, not through `ingestState`), §12.5 (one sentence: the hard-exclusion rationale covers unconfirmed atoms only and does not extend to a layer that is merely not current — the emergency card hides no row for freshness), `INGEST_FAILURE_POLICY_DESIGN.md` §E.3 point 3 (the overrule recorded in the words of §3.D), `docs/DATA_MODEL.md` §7.10.2 (the route's wire shape), `recordhealth-api/CLAUDE.md` (the fourth `source`, the eighth alert site, the seventh ntfy field now that it is ruled), `WORKER_ARCHITECTURE.md` § NCC v1 (pointer), `INGEST_VOCABULARY_DESIGN.md` §6 and §11.7 (the beacon's build lives in `VocabularyDriftReport`; the transport is this doc's), `ROADMAP.md` (F-NEW-LJ status note: error feed grouping shipped; file §7's items from `F-NEW-SG`), `R3_RELATIONSHIPS_SPEC.md` v2.2 header note that D1 closed. | — |

Why W1/W2 precede P4 and not merely P1: the sender must have a route to answer 2xx or its watermark never advances, and the device proof in R3-8 reads the feed. Why P1–P3 precede R3-7: §3.B. Why P4 precedes R3-7: the proof at R3-8 (f) needs the rows on the feed. P3 could land before P2 with no compile dependency; it is placed after so the ledger's `.owed(.staleMarkFailed)` writer exists when the mark-failure path is written.

---

## 4. Rulings table

| # | Ruling | Kind | Where applied |
|---|---|---|---|
| 1 | Loud on every path | **owner** | §3.C — loudness inside the door; ten callers enumerated by the compiler |
| 2 | Per-stage granularity; retry through the existing door | **owner** | §2 (the four independently failing stages), §3.C (stage named in the outcome; the door is `rebuild`) |
| 3 | Persisted, bounded on-device ladder; exhaustion visible, never fresh-wrong | **owner** | §3.D (ledger), §3.E (ladder, freshness) |
| 4 | Every attempt and outcome to the server and NCC, grouped by one id; only exhaustion pushes | **owner** | §3.G (kinds, failure id), §3.I (columns, grouping, hook) |
| 5 | NCC covers staging and production | **owner** | §3.I (both Workers; `BackendEnvironment` routes builds) |
| 6 | Failure-path graph mark; membership marks independent of rebuild | **owner** | §3.F |
| 7 | Dev data; no migration code, no shims | **owner** | §3.D (lenient decode adopts parked records), §3.G (strict ring decode), §3.I (migration adds columns, touches no rows) |
| 8 | Doc home: new `SeedCorpus/LAYER2_LIVENESS_DESIGN.md` | designer | §3.A |
| 9 | Sibling to R3; step 7 marks owed; v2.2 amendment at the lines in §3.B; this doc's P1–P4 land before R3-7 | designer, except the step order: **owner** (2026-09-09) — P1–P4 land before R3 step 7 as designed | §3.B, §3.J |
| 10 | `rebuild` returns `ContextRebuildOutcome`, never throws; only stage 7 opens the ladder; stage 5 becomes a finding plus a ring event | designer | §3.C |
| 11 | Ledger at `diagnostics/layer2_heal.enc`, device-global; `isStale` and the ledger are two questions, one read-side answer | designer | §3.D |
| 12 | The ingest path's 5 s retry and `.storageFailed` retire; `AttentionCause.storageFailed` deleted, not retained | designer | §3.D |
| 13 | The record completes on a Layer 2 failure; `IngestCompletionGate`'s third precondition becomes "outcome returned, ledger open on failure"; the re-upload "Try again" retires for this cause; `F-NEW-KO` §E.3 point 3 is overruled and the overrule is recorded at D1 | **owner** (2026-09-09) | §3.D, §3.J D1 |
| 14 | Five rungs, 1 min / 10 min / 1 h / 6 h, the one-minute floor on rung 1, no inline retry, no jitter; demand admits and resets; a Layer 1 write re-opens an exhausted ladder | **owner** (numbers, 2026-09-09); the shape designer | §3.E |
| 15 | `ContextLayerHealSweep` is its own sweep at the coordinator's lifecycle sites, not a coordinator step | designer | §3.E |
| 16 | `ActiveContextLayer.freshness`; the ruled copy table; "out of date" appears in no title, body or button; **the emergency card keeps every clinical row** and carries the warning line above them (v1.0's hide, and its §12.5 justification, struck) | **owner** (2026-09-09); the `freshness` mechanism designer | §3.E |
| 17 | Membership marks are `PatientRecordIndex.mutate`'s; `MembershipStaleTarget` names the set; caller copies deleted | designer | §3.F |
| 18 | `CareGraphStore.markStale` persists its cached branch; a failed mark opens `.owed(.staleMarkFailed)` | designer | §3.F |
| 19 | Three ring kinds; strict decode stays; a kind addition resets older builds' rings and says so | designer | §3.G |
| 20 | `DeviceReportSender` replaces `VocabularyBeacon`; two classes, two watermarks, two routes; emission + background triggers added | designer | §3.H |
| 21 | `error_events` gains `app_version`, `failure_id`, `stage`, `attempt`, `observed_at`; `source = 'ios'`; `route` carries the device site | designer | §3.I |
| 22 | The route awaits its own write and acks whole batches only (the beacon's contract) | designer | §3.I |
| 23 | Exhaustion alerts through a new `ALERT_KIND` hook at the route; failed/healed never alert; the payload carries `failure_id` as its seventh field | designer, except the seventh field: **owner** (2026-09-09) | §3.I |
| 24 | Feed grouping: a failure column, click-filter, collapsed group rows; no new panel | designer | §3.I |
| 25 | A DEBUG-only fault lever for the device proof | designer | §3.E, §3.J R3-8 |
| 26 | Copy table punctuation matches `IngestProgressPresentation` exactly — title with no trailing period, body a stopped sentence, action Title Case ("Update Now"); reverses the divergences v1.1 left as ruled | **owner** (2026-09-09) | §3.E |
| 27 | The two `.unavailable` rows drop their v1.0 second line and share their counterpart's body ("Retrying automatically." / "Tap to update."); "no action needed" dropped from the copy table | **owner** (2026-09-09) | §3.E |
| 28 | `.notCurrent(.owed)` / `.unavailable(.owed)` render no copy at all; the warning line turns on only at the first failed attempt; closes `F-NEW-SL` | **owner** (2026-09-09) | §3.E, §7 |

---

## 5. Ruling status — nothing open

Every ruling this doc opened at v1.0 was ruled by the owner on 2026-09-09 and now lives in §4 as an owner ruling, each with its section pointer:

| v1.0 open ruling | Ruled | Now |
|---|---|---|
| 1. Does a record complete when its Layer 2 rebuild fails? | **yes**, the recommended path as written | §4 #13 → §3.D; the re-upload "Try again" for this cause retires; `F-NEW-KO` §E.3 point 3 overruled, recorded at D1 |
| 2. A seventh ntfy payload field, `failure_id` | **yes** | §4 #23 → §3.I; the `Click` deep link is built |
| 3. Ladder numbers | **accepted as designed** | §4 #14 → §3.E; five attempts, 1 min / 10 min / 1 h / 6 h, one-minute floor on rung 1, no jitter |
| 4. Copy, and the emergency card | **ruled, and it changed the design** | §4 #16 → §3.E; "out of date" struck from every string, one warning line on every surface, and the emergency card keeps its rows |
| 5. Step order versus R3's close | **accepted as designed** | §4 #9 → §3.B, §3.J; P1–P4 land before R3 step 7 |

Ruling 4 was not a wording pass. It reversed the emergency card (v1.0 rendered a title in place of the card's clinical rows; the card now hides nothing and the ARCHITECTURE §12.5 justification for hiding is struck), it collapsed the two stored-summary states onto one warning line, and it retired a phrase: "out of date" appears in no title, body or button anywhere in this doc. The one internal name that carried the phrase was renamed under 4(e) — `ContextLayerFreshness.outOfDate` / `ContextLayerOutOfDateReason` are now `notCurrent` / `ContextLayerNotCurrentReason` (§3.E).

Decided here and reversible by the owner without a redesign: the doc's name (§3.A), `route` carrying the device site rather than a `site` column (§3.I), `observed_at` as a column (§3.I), the heal sweep as its own type (§3.E), and deleting `.storageFailed` rather than retaining it producerless (§3.D). The one copy question the v1.1 ruling did not reach — whether `.notCurrent(.owed)` should share the failure title — is reached at v1.2 (§4 #28): it shares no copy at all, per §3.E.

---

## 6. What this doc deliberately does not own

- **Spike and rate alerting** over `error_events` (F-NEW-LJ amendment (c)) — later, as ruled; the columns here are what a spike rule would group on.
- **Server-side healing** of any kind. The rebuild is on-device by construction (ARCHITECTURE §3.2: no AI, deterministic, from Layer 1); the server learns and the owner is told; nothing on the server acts.
- **Layer 1 write failures.** A `SegmentedFactStore` or package write failure stays the ingest state machine's (ARCHITECTURE §3.8; PACKAGE_DESIGN §2.1's "a package write failure is FATAL"). This doc begins where Layer 1 is durable.
- **Care graph rebuild failures.** `CareGraphStore.graph(for:)`'s incremental update is a Layer 3-adjacent derivation with its own `try?`s; it is marked stale here and healed on read as today. R5 absorbs the care graph into the relationship index (RELATIONSHIP_DESIGN RL-10) and gets its own liveness reading then.
- **The vocabulary beacon's semantics** — gates, dedup key, misfire log, OR-3/OR-9/OR-19 — stay in `INGEST_VOCABULARY_DESIGN.md` §6/§11.7. This doc moves its transport, not its meaning.
- **A general phone→server event bus.** Two classes, two routes, one sender. A third class (a share-extension failure, a Keychain failure) is a new `DeviceReportClass` and, if it is an error, a row in `error_events` under a fifth `source` — filed, not built.

## 7. Items to file (next free id `F-NEW-SG`, ROADMAP.md:19; each names its owner doc)

- `F-NEW-SG` — spike/rate alerting over `error_events` grouped by `source`/`error_code`/`failure_id` (this doc §3.I hands F-NEW-LJ (c) its columns). Owner: F-NEW-LJ.
- `F-NEW-SH` — a third `DeviceReportClass` (the first non-rebuild phone error), and the fifth `source`. Owner: this doc §6.
- `F-NEW-SI` — `CareGraphStore` liveness (its own `try?` set, its read-side incremental update) — folds into R5's audit. Owner: RELATIONSHIP_DESIGN §12 R5.
- `F-NEW-SJ` — `INGEST_FAILURE_POLICY_DESIGN.md` §E.3 point 3 rewording, now **ruled** (§4 #13): the overrule is recorded there at step D1, in the words §3.D fixes. Owner: that doc.
- `F-NEW-SK` — the ring's strict decode versus a future need to read an older ring after a kind addition without the gate — filed with no owner, so the idea has a number and sacred rule 3 stays the answer until a reason appears.
- `F-NEW-SL` — **closed 2026-09-09** (§4 #28 → §3.E). Filed at v1.1 as open: `.notCurrent(.owed)` shared the ruled failure title although an `.owed(.r3Projection)` entry records no failure yet, only a rebuild that is owed. Ruled at v1.2: `.notCurrent(.owed)` and `.unavailable(.owed)` render no copy at all — `statusCopy(for:)` returns `nil` — and the warning line turns on only at the first failed attempt, which is why the R3-wipe sweep's `.owed(.r3Projection)` entries show nothing on the first post-wipe launch. Owner: this doc §3.E.
