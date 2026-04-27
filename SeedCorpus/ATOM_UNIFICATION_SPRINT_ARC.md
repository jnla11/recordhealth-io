# ATOM UNIFICATION — Sprint Arc Plan

**Purpose:** decompose the six-sprint v1.0 arc into mini-sprints small enough to vibe-code, each with audit and smoke test requirements called out. This is the execution plan; detail sprint briefs happen per mini-sprint at commit time.

**Source document:** `SeedCorpus/ATOM_UNIFICATION_DESIGN.md` v1.0
**Last revised:** 2026-04-27
**Scope:** execution planning only. No new architectural decisions.

> **Status (as of 2026-04-27):** U.1 and U.2 arcs complete on iOS.
> Worker schema migration (U.1b/c) complete on staging. Next:
> U.3 (review_phi_detections → data_atoms migration). U.F.*
> runnable in parallel.

---

## Principles driving the decomposition

**Each mini-sprint is independently shippable.** Can commit, tag, merge. If something breaks, rollback is one git revert, not a multi-day unwinding. This is the core vibe-coder protection.

**Each mini-sprint touches one repo where possible.** Cross-repo mini-sprints exist where they must (e.g., the transit payload handshake) but most live in iOS-only or Worker-only or console-only scope. Single-repo sprints are safer.

**Each mini-sprint either adds or removes, never both.** Addition sprints add new code paths while leaving old paths working. Removal sprints delete deprecated paths once nothing uses them. Mixing addition and removal in one sprint is where bugs hide.

**Audit before, smoke test after.** Every sprint gets one or the other at minimum; most get both. The audit confirms reality hasn't drifted since the last audit. The smoke test confirms the sprint did what it claimed.

**Dummy data lets us move faster.** Per your note that all current data is dev, U.3 data migration is lightweight and some sprints that would require careful production handling can be more aggressive.

---

## Dependency map

```
U.1a ──► U.1b ──► U.1c ──► U.1d
                              │
                              ├──► U.2a ──► U.2b ──► U.2c
                              │
                              ├──► U.F.1 ──► U.F.2 ──► U.F.3 ──► U.F.4
                              │
                              └──► U.3
                                    │
                                    └──► U.4a ──► U.4b ──► U.4c ──► U.4d
                                                                      │
                                                                      └──► U.5
```

U.F runs in parallel with U.2 once U.1 completes. U.3 depends on U.1 but not U.2 or U.F. U.4 depends on U.3 (needs unified schema in place). U.5 is cleanup at the end.

Rough total: **17 mini-sprints.**

---

## U.1 — Schema preparation

**Goal:** canonical vocabulary exists in iOS and Worker. Worker accepts both old and new payload shapes. Nothing user-facing breaks.

### U.1a — Define canonical vocabulary constants

**Repo:** iOS + Worker (shared vocabulary).

**Scope:**
- iOS: create `AtomKind.swift` and `AtomSubtype.swift` enums per v1.0 §4
- iOS: create `PHIType.swift` enum with expanded ~25 types per v1.0 §5
- iOS: create `AccessTier.swift`, `ClassificationCertainty.swift` enums
- Worker: matching JS constants in `src/constants/atom_vocabulary.js`
- Both: constant `ATOM_SCHEMA_VERSION = "2.0"`

**No runtime code changes.** Just the vocabulary definitions. Nothing reads them yet.

**Pre-sprint audit:** none needed. Audit 1 covered current vocabulary.

**Smoke test:**
- iOS builds cleanly with new enums
- Worker deploy succeeds
- Cross-check: every value in iOS enum has exact match in Worker constant (manual grep diff)

**Commit shape:** one commit per repo. Tag `u1a-vocabulary-defined`.

---

### U.1b — Worker schema migration (ADI `data_atoms` columns)

**Repo:** Worker only.

**Scope:**
- Create migration file `migrations/u1_unification_columns.sql`
- ALTER `data_atoms` add columns: `is_phi`, `phi_type`, `phi_token_uid`, `access_tier`, `subtype`, `classification_certainty`, `structured_payload`, `regex_hints`, `supersedes`, `produced_by`, `produced_at`, `schema_version`
- All nullable or default-valued so existing rows stay valid
- `canonical_codes` column already exists — no change, just start populating
- Add index on `supersedes` for chain queries
- Add index on `(document_id, supersedes)` for "latest in chain" queries

**`entity_kind_enum` migration is separate (U.1c)** because ALTER TYPE ADD VALUE has Postgres-specific constraints.

**Pre-sprint audit:** confirm current `data_atoms` schema matches Audit 1 §4.1. Check for any migrations added between Audit 1 and now.

**Smoke test:**
- Run migration against `RecordHealth-ADI / staging` via Neon SQL Editor
- Verify new columns exist via `\d data_atoms`
- Verify existing row count unchanged
- Verify existing INSERTs still work (test with a POST to `/v1/admin/atoms` using old shape)

**Commit shape:** one commit. Tag `u1b-schema-migrated`.

---

### U.1c — Enum migration for canonical vocabulary

**Repo:** Worker only.

**Scope:**
- Create migration `migrations/u1c_entity_kind_expansion.sql`
- ALTER TYPE `entity_kind_enum` ADD VALUE for each new canonical kind
- Values added (serialized, one per statement):
  - `finding`, `encounter` (resolves current drift)
  - `patientDemographic`, `patientIdentifier`, `patientContact`, `patientAddress`
  - `guardianInfo`, `emergencyContact`
  - `providerContact`, `documentReference`
  - Plus any others from v1.0 §4 not present today
- Migration is forward-only (Postgres enum removals require table rewrite)

**Pre-sprint audit:** list current `entity_kind_enum` values from Neon. Compare against v1.0 §4 to produce exact ADD VALUE list.

**Smoke test:**
- Run migration on staging via Neon SQL Editor
- Verify `SELECT enum_range(NULL::entity_kind_enum)` returns full canonical vocabulary
- Test INSERT with new value (e.g., `patientIdentifier`) succeeds
- Existing data unaffected

**Commit shape:** one commit. Tag `u1c-enum-expanded`.

---

### U.1d — Transit version string validation

**Repo:** Worker + iOS.

**Scope:**
- **Worker:** `POST /v1/admin/documents/upload` validates `atom_schema_version` header. If missing: accept with warning (backward compat). If present and mismatched: reject with 400 and clear error.
- **iOS:** `DocumentTransitService` includes `atom_schema_version: "2.0"` header on every submission
- Worker accepts both old payload shape (no schema_version) and new (with schema_version). During U.1-U.2 window, both work.

**Pre-sprint audit:** confirm `DocumentTransitService.submitForReview` implementation matches Audit 3 §5.

**Smoke test:**
- Submit a test document from iOS with new header → Worker accepts
- Manually craft a payload with wrong version → Worker rejects with 400
- Submit a payload with no version header → Worker accepts (backward compat)

**Commit shape:** one commit per repo (Worker first, iOS second). Tag `u1d-version-validated`.

---

## U.2 — iOS unification

**Goal:** iOS produces unified atoms. PDF ingest pipeline produces atoms with PHI flags set, codings array, all new fields. Old paths deprecate but remain for fallback.

### U.2a — Extend iOS atom models

**Repo:** iOS only.

**Scope:**
- Add new optional fields to `HealthFact`, `FactInterpretation`, `PendingInterpretation`:
  - `subtype: String?`
  - `classificationCertainty: ClassificationCertainty` (default `.specific`)
  - `isPhi: Bool` (default false)
  - `phiType: PHIType?`
  - `phiTokenUid: String?`
  - `accessTier: AccessTier?`
  - `codings: [Coding]` (default empty)
  - `structuredPayload: Data?` (Codable-encoded kind-specific payload)
  - `regexHints: [RegexHint]` (default empty)
  - `producedBy: String`
  - `producedAt: Date`
  - `schemaVersion: String` (default "2.0")
- Update Codable conformance for back-compat on existing encrypted data (missing fields decode to defaults)
- No behavioral change yet — nothing produces these fields

**Pre-sprint audit:** confirm FactStore/FactInterpretation/PendingInterpretation shapes match current state.

**Smoke test:**
- iOS builds cleanly
- Load existing encrypted FactStore from device, verify all records decode without error (back-compat works)
- Create a new atom programmatically with new fields, verify round-trip through encryption

**Commit shape:** one commit. Tag `u2a-ios-models-extended`.

---

### U.2b — Update AI extraction prompt and parser

**Repo:** iOS only.

**Scope:**
- Update `AIExtractionService.swift` prompt to request unified output per v1.0 §3.1:
  - Request `kind`, `subtype`, `classification_certainty`, `is_phi`, `phi_type`, `structured_payload`, plus existing fields
  - Prompt remains one AI call per document (no breakdown pass split, per v1.0)
- Update response parser to populate new fields on `PendingInterpretation`
- Tokenization post-processing: after AI produces atoms with `is_phi` set, walk atoms and assign `phi_token_uid` via PHITokenStore. Stable token IDs, deterministic, no AI involvement.
- RecordTokenizer's old PHI identification paths remain but are no longer primary — they run alongside for fallback safety during U.2 window. Full retirement in U.5.

**Pre-sprint audit:** confirm current `AIExtractionService` prompt matches Audit 1 §6 and Audit 3 §2.3.

**Smoke test:**
- Ingest a test PDF with known PHI (patient name, DOB, MRN, provider name)
- Verify AI produces unified atoms with correct `kind`, `subtype`, `is_phi`, `phi_type` assignments
- Verify tokenization post-processing assigns stable `phi_token_uid` values
- Verify PHITokenStore has entries for each token
- Compare to pre-U.2b behavior on same document — no atoms lost

**Commit shape:** one commit. Tag `u2b-ai-unified-output`.

---

### U.2c — DocumentTransitService emits unified payload

**Repo:** iOS only.

**Scope:**
- Update `DocumentTransitService.submitForReview(record:)` to emit unified `atoms[]` array per v1.0 §10.3
- Each atom carries all new fields
- For transition window: also emit legacy `extractions[]` + `detected_phi[]` (Worker still accepts both, but we're preparing for Worker-side unification later)
- Version header `atom_schema_version: "2.0"` on request (already landed in U.1d)

**Pre-sprint audit:** confirm U.2a and U.2b landed cleanly; unified atoms exist in PendingInterpretation.

**Smoke test:**
- Submit a test document via superuser path
- Inspect payload (log or proxy) — unified `atoms[]` array present, populated, all fields correct
- Worker accepts submission (backward-compat handles both shapes)
- `data_atoms` rows populated correctly — new columns have values

**Commit shape:** one commit. Tag `u2c-ios-unified-transit`.

---

## U.F — FHIR import unification

**Goal:** FHIR import produces unified atoms. Raw FHIR preserved. Codings wired end-to-end. Patient/Practitioner/Organization resource branches added.

**Parallel-safe:** runs parallel to U.2 once U.1 lands. Can ship before or after U.2.

### U.F.1 — Raw FHIR preservation sidecar

**Repo:** iOS only.

**Scope:**
- Create `FHIRRawStore.swift`, `@MainActor` singleton
- Encrypted sidecar at `Documents/profiles/{patientUUID}.fhir_raw.enc`
- On every FHIR resource ingestion (from `AppleHealthImportView.performImport`), persist raw JSON verbatim before any mapping
- Each entry: `{resource_id, resource_type, raw_json, imported_at, mapping_status: "unprocessed"}`
- `mapping_status` will be updated by later sprints as mapper handles each type

**No mapper changes in this sprint.** Just safety-net persistence.

**Pre-sprint audit:** confirm FHIR import entry point in `AppleHealthImportView.swift` matches Audit 3 §1.2.

**Smoke test:**
- Import a synthetic FHIR bundle (create one if no real Apple Health test data available)
- Verify `.fhir_raw.enc` file created
- Decrypt and inspect — every resource present verbatim
- Restart app, verify sidecar loads without error

**Commit shape:** one commit. Tag `uf1-raw-preservation`.

---

### U.F.2 — Add missing resource-type branches

**Repo:** iOS only.

**Scope:**
- `FHIRRecordMapper.swift`: add resource branches for:
  - `Patient` — decompose into multiple candidates (name, DOB, MRN, address, phone, email as separate candidates with matching subtypes)
  - `Practitioner` — decompose into name, NPI, credentials candidates
  - `Organization` — decompose into facilityName, address, phone candidates
- `FHIRBackgroundData.swift`: corresponding `ObservationType` cases if needed, or skip (these are identity atoms, not observations)
- `FHIRSynthesisEngine.swift`: ensure new resource types don't break visit synthesis (probably don't enter synthesis at all — they're identity-level, not visit-level)
- Update `mapping_status` in `FHIRRawStore` to reflect what's now handled

**Pre-sprint audit:** re-verify current mapper behavior after U.F.1 lands. Confirm no new drift.

**Smoke test:**
- Import synthetic FHIR bundle containing Patient, Practitioner, Organization
- Verify candidates produced for each
- Verify `FHIRRawStore` shows `mapping_status: "processed"` for these
- Verify no regression on existing resource types

**Commit shape:** one commit. Tag `uf2-resource-branches-added`.

---

### U.F.3 — FHIR-to-atom bridge with codings

**Repo:** iOS only.

**Scope:**
- Create `FHIRImportCandidateAtomBridge.swift`
- For each `FHIRImportCandidate`, produce one or more unified atoms:
  - `kind` + `subtype` from resource type / candidate subtype
  - `verbatim_value` from candidate title/value
  - `codings[]` populated from `FHIRSourceCode` triples (with `source: "fhir_import"`)
  - `structured_payload` populated from structured FHIR fields (reference ranges for labs, dosage for meds, etc.)
  - `confidence: 1.0`
  - `classification_certainty: .specific`
  - `produced_by: "pipeline.fhir_import.v1"`
  - `is_phi` + `phi_type` set for identity atoms (patient name/DOB/MRN etc.)
- Atoms write directly to FactStore via `InterpretationAcceptanceService` (skip review queue — FHIR is trusted)
- Unmapped-field logging: dropped FHIR paths logged to diagnostic sidecar

**Pre-sprint audit:** confirm `InterpretationAcceptanceService` still writes through to FactStore as Audit 1 described.

**Smoke test:**
- Import synthetic FHIR bundle with Condition, Observation, Patient, Practitioner
- Verify atoms appear in FactStore with correct kinds, subtypes, codings, structured payloads
- Verify `codings[]` contains FHIR source code triples
- Verify PHI atoms (patient name, provider name) have `is_phi: true` and `phi_type` set
- Tokenize these atoms via existing PHITokenStore pathway — tokens generated
- Verify `fhir_raw.enc` still has full raw data (sacred rule — nothing discarded)

**Commit shape:** one commit. Tag `uf3-fhir-atoms-bridged`.

---

### U.F.4 — Worker FHIR transit endpoint (optional)

**Repo:** Worker only.

**Scope:**
- New endpoint `POST /v1/admin/atoms/fhir-import`
- Accepts batch of FHIR-sourced atoms without PDF precondition
- Writes to `data_atoms` with `canonical_codes` populated, `produced_by: "pipeline.fhir_import.v1"`
- Returns atom IDs
- **iOS side:** optional call from superuser submission path — if document has FHIR atoms, submit them alongside the PDF atoms

**Decision point:** skip this sprint entirely if FHIR training corpus isn't near-term priority. Deferrable to post-v1.

**Pre-sprint audit:** confirm `data_atoms` schema after U.1b includes all fields needed.

**Smoke test:**
- POST a sample FHIR atom batch to the endpoint
- Verify rows in `data_atoms` with `canonical_codes` populated
- Verify `produced_by` tag correct

**Commit shape:** one commit. Tag `uf4-fhir-transit-endpoint`. Skippable.

---

## U.3 — Data migration

**Goal:** existing `review_phi_detections` rows collapse into `data_atoms`.

**Dev data only today, so migration is lightweight.**

### U.3 — `review_phi_detections` → `data_atoms`

**Repo:** Worker only.

**Scope:**
- Create migration script `migrations/u3_phi_detections_merge.sql`
- For each `review_phi_detections` row:
  - Find `data_atoms` row with same `document_id` and overlapping coordinates
  - If match: INSERT new atom row with `supersedes` → original atom, `is_phi: true`, `phi_type` from token_type, `phi_token_uid` from token_placeholder
  - If orphan: INSERT new atom row (no supersedes), `kind` inferred from `token_type` via a mapping table
- Leave `review_phi_detections` table in place (will drop in U.5)
- Data integrity checks: every PHI detection accounted for

**Pre-sprint audit:**
- Snapshot current `review_phi_detections` row count and `token_type` distribution via Neon SQL Editor
- Snapshot current `data_atoms` row count
- Manual overlap estimation on a sample (e.g., 10 random PHI rows checked against atoms by coordinate)

**Smoke test:**
- Run migration on staging
- Post-migration: `SELECT COUNT(*) FROM data_atoms WHERE is_phi = true` matches pre-migration PHI detection count (modulo orphan handling)
- Spot-check 10 former PHI detections: verify they appear as atom rows with correct supersedes chains
- Load a test document in ADI console: PHI detections render correctly (console still reads old paths, should work transparently)

**Commit shape:** one commit containing migration script + rollback script. Tag `u3-phi-merged`.

---

## U.4 — ADI console unification

**Goal:** PHI tab collapses into unified Atoms tab. Hybrid inline + drill-down interaction. Red-for-PHI preserved.

### U.4a — Worker grading submit handler accepts unified payload

**Repo:** Worker only.

**Scope:**
- `POST /v1/admin/grading/submit`:
  - Accept unified `verdicts[]` with per-entry `is_phi` flag
  - Keep accepting legacy split `verdicts[]` + `phi_verdicts[]` during transition
  - `validateRejectReasons` branches per-entry (uses PHI allowlist for `is_phi: true`, clinical otherwise)
  - `computeGradingSummary` partitions by `is_phi` for two F1 blocks — already produces both, just change input partitioning
  - `grading_submissions` INSERT: continue writing to existing columns (`verdicts`, `phi_verdicts`) populated from unified input during transition
- No console changes yet; this just prepares Worker for unified input

**Pre-sprint audit:** confirm grading submit handler matches Audit 4 §5 and §8.3.

**Smoke test:**
- POST a unified-shape submission to `/v1/admin/grading/submit`
- Verify it accepts and writes to `grading_submissions`
- Verify F1 blocks computed correctly
- POST a legacy-shape submission — still works

**Commit shape:** one commit. Tag `u4a-worker-unified-submit`.

---

### U.4b — Console state model unification

**Repo:** Console only.

**Scope:**
- `adi-console/app.js`:
  - Remove `phiVerdicts`, `phiDiscoveries`, `selectedPhiIndex`, `hoveredPhiIdx`, `stablePhiIndexByKey` state variables
  - Unify into `verdicts` (still atom-UUID keyed) with `is_phi` flag per entry
  - Unify discoveries similarly
  - `saveWorkspace` serializes unified shape to sessionStorage
  - Keep `phiReverseMap` for detokenization
  - Keep `PHI_TOKEN_PATTERN` for rendering

**No UI changes yet** — just state model collapse. Tab still renders separately but reads from unified state.

**Pre-sprint audit:** confirm state model matches Audit 4 §1.

**Smoke test:**
- Load a test document with existing PHI detections and atoms
- Open in console — both tabs still render (backward compat)
- Click a PHI row, verdict it — verdict appears in unified `verdicts` state with `is_phi: true`
- Refresh page — state persists via sessionStorage
- Submit to server — unified payload accepted by U.4a

**Commit shape:** one commit. Tag `u4b-console-state-unified`.

---

### U.4c — Unified atom list + inline PHI verdicts

**Repo:** Console only.

**Scope:**
- Remove PHI tab from index.html (`#tab-btn-phi`, `#phi-count`, `#tab-phi`, `#phi-list`)
- `renderAtoms`: unified list now shows PHI-flagged atoms alongside clinical
- PHI-flagged atoms get inline quick-verdict buttons in list view (preserves throughput)
- Clinical atoms retain existing pattern (click → drill-down)
- All atoms support drill-down on click
- Add PHI filter to `#kind-filter` area: "All / PHI only / Non-PHI only"
- Add PHI-type filter (shown when PHI-only active): populated from `PHI_TYPES`
- Drawing discriminator: modal picker on mouseup asks "Clinical atom or PHI?" (replaces `activeTab === 'phi'` branch)

**Pre-sprint audit:** confirm audit 4 §8 tab-dependency list; verify each dependency addressed.

**Smoke test:**
- Load test document in console
- Atoms and PHI render in one list
- Inline verdict on a PHI atom — state updates
- Drill-down a PHI atom — full correction form available
- Filter by "PHI only" — non-PHI atoms hidden
- Draw a new region on PDF — modal appears, pick "PHI," discovery created correctly
- Submit — unified payload sent, Worker accepts

**Commit shape:** one commit. Tag `u4c-console-unified-list`.

---

### U.4d — Red-for-PHI overlay cleanup

**Repo:** Console only.

**Scope:**
- `styles.css`: change `region-rejected` from red variant to gray/strikethrough
- PHI-flagged atoms render red on overlay regardless of kind color (overlay logic in `updateOverlay`)
- Kind color still used for non-PHI atoms
- Remove `focus-atoms` / `focus-phi` CSS classes (no longer have tab-switching)
- `#show-phi` toggle: retained, now filters PHI atoms from the list (in addition to existing overlay dim behavior)

**Pre-sprint audit:** confirm current overlay implementation matches Audit 4 §2.4-2.5.

**Smoke test:**
- Load test document with mix of clinical and PHI atoms
- Overlay: PHI atoms red, clinical atoms in kind colors
- Reject a clinical atom — shows gray/strikethrough, not red
- Toggle `#show-phi` off — PHI atoms hidden from list and overlay
- Reviewer muscle memory check: red still = PHI, confirmed visually

**Commit shape:** one commit. Tag `u4d-red-for-phi`.

---

## U.5 — Cleanup

**Goal:** drop deprecated paths. Remove legacy code.

### U.5 — Drop deprecated paths

**Repo:** Worker + iOS + Console (three commits).

**Scope:**

**Worker:**
- Drop `review_phi_detections` table (migration script)
- Remove legacy payload shape handlers from `/v1/admin/documents/upload`
- Remove legacy grading submit shape acceptance (only unified accepted)
- Keep `phi_verdicts` / `phi_discoveries` columns on `grading_submissions` for historical row reads — decide whether to backfill from unified column or leave historical rows as-is

**iOS:**
- Remove legacy `DocumentTransitService` payload shape (`extractions[]` + `detected_phi[]`)
- Remove legacy RecordTokenizer PHI-identification paths (tokenizer is bookkeeping-only)
- Clean up legacy FHIR mapper dual-switch code if U.F cleanup didn't cover it
- Remove legacy `Anonymizer.swift` if fully unused post-unification

**Console:**
- Remove backward-compat rendering for pre-U.4 document loads (if still present)
- Remove `phi_verdicts` / `phi_discoveries` reading paths (read from unified columns)

**Pre-sprint audit:** grep for any callers of deprecated paths. If any found, don't drop; fix callers first.

**Smoke test:**
- Build all three repos cleanly
- End-to-end flow on a fresh document: ingest → submit → grade → lock. No errors.
- Historical grading submission still renders in console (reads legacy columns if not backfilled)

**Commit shape:** three commits, one per repo, in order (Worker → iOS → Console). Tags `u5-worker-cleanup`, `u5-ios-cleanup`, `u5-console-cleanup`.

---

## Summary — sprint count and sequencing

| Sprint | Scope | Repo | Audit | Smoke | Status |
|---|---|---|---|---|---|
| U.1a | Vocabulary constants | iOS + Worker | No | Yes | ✅ COMPLETE (ca9fd57 iOS / 0af52cc Worker) |
| U.1b | Worker data_atoms columns | Worker | Yes | Yes | ✅ COMPLETE (40d9561) |
| U.1c | Worker enum expansion | Worker | Yes | Yes | ✅ COMPLETE (c0d127a) |
| U.1d | Transit version validation | Worker + iOS | Yes | Yes | ✅ COMPLETE (30788bf Worker / 47fc703 iOS) |
| U.1e | Vocabulary extension | iOS + Worker | Yes | Yes | ✅ COMPLETE (b0cc89c+4267ec9 iOS / 5513155+53a4f10 Worker) — unplanned but landed |
| U.2a | iOS model extension | iOS | Yes | Yes | ✅ COMPLETE (2a6b44d) |
| U.2a.5 | FactKind→AtomKind collapse | iOS | — | — | ✅ COMPLETE (8ba536f) — unplanned but landed |
| U.2a.6 | InterpretationKind→AtomKind collapse | iOS | — | — | ✅ COMPLETE (2712e82) — unplanned but landed |
| U.2b | iOS AI unified output | iOS | Yes | Yes | ✅ COMPLETE (decomposed into U.2b.1–3.c) |
| U.2b.1 | Pass 2 prompt restructure | iOS | — | — | ✅ COMPLETE (40b1812) |
| U.2b.2 | Pass 2 parser update | iOS | — | — | ✅ COMPLETE (b798d26) |
| U.2b.3.a | Token vocabulary bridge | iOS | — | — | ✅ COMPLETE (938a880) |
| U.2b.3.b | AI tokenization driver | iOS | — | — | ✅ COMPLETE (8a03320) |
| U.2b.3.c | Regex PHI identification deleted | iOS | — | — | ✅ COMPLETE (d5a11f2) |
| U.2c | iOS unified transit | iOS | Yes | Yes | ✅ COMPLETE (absorbed into U.2b.3.a/b/c) |
| U.F.1 | FHIR raw preservation | iOS | Yes | Yes | pending |
| U.F.2 | FHIR resource branches | iOS | Yes | Yes | pending |
| U.F.3 | FHIR-to-atom bridge | iOS | Yes | Yes | pending |
| U.F.4 | Worker FHIR transit (optional) | Worker | Yes | Yes | pending |
| U.3 | Data migration | Worker | Yes | Yes | pending |
| U.4a | Worker unified submit | Worker | Yes | Yes | pending |
| U.4b | Console state unification | Console | Yes | Yes | pending |
| U.4c | Console unified list | Console | Yes | Yes | pending |
| U.4d | Red-for-PHI cleanup | Console | Yes | Yes | pending |
| U.5 | Cleanup (3 commits) | All | Yes | Yes | pending |

17 mini-sprints in the original plan (16 if U.F.4 skipped). Eight unplanned sub-sprints landed during U.1/U.2 execution: U.1e (vocabulary extension), U.2a.5/6 (enum collapses), and the U.2b.1–3.c decomposition of the original U.2b row.

## Sprint sizing

- **Small (~1 conversation):** U.1a, U.1c, U.1d, U.2a, U.3, U.4a, U.4d, U.F.1
- **Medium (~1-2 conversations):** U.1b, U.2c, U.4b, U.4c, U.F.2, U.F.4, U.5 (each repo)
- **Large (~2+ conversations):** U.2b, U.F.3

U.2b is largest because it's the full AI prompt overhaul plus tokenization post-processing. U.F.3 is large because bridging FHIR to atoms touches many code paths.

## Recommended path

Linear for simplicity: U.1a → U.1b → U.1c → U.1d → U.2a → U.2b → U.2c → U.F.1 → U.F.2 → U.F.3 → U.3 → U.4a → U.4b → U.4c → U.4d → U.5.

Parallel opportunities (once U.1 done):
- U.2 and U.F can run in parallel (different code paths)
- U.3 independent of U.2 and U.F
- U.4 waits for U.3 but U.4a can start after U.1 if U.3 isn't done yet (Worker-only, no data dependency)

## Rollback strategy

Each sprint tagged. Rollback = git revert to previous tag, plus migration reversal SQL where applicable. Migration scripts authored with companion rollback scripts (`u1b_rollback.sql`, etc.) in the same commit.

For Worker schema changes (U.1b, U.1c, U.3), rollback on staging is cheap (drop columns, restore from before-migration snapshot if needed). Production untouched throughout (all ADI work is staging-only per DATABASE_LAYOUT).

## When to pause and reassess

- **After U.1d:** full schema and transit layer in place. Last chance to change vocabulary before iOS and Worker are both pinned to it.
- **After U.2c:** iOS side of unification done. Before starting U.F, confirm atom quality in practice — review a few documents' worth of produced atoms.
- **After U.3:** data migration complete. Before U.4, smoke test ADI console with migrated data to catch anomalies.
- **After U.4d:** console unified. Before U.5 cleanup, confirm full end-to-end works with unified paths only (disable legacy in a test build first).

---

**End of sprint arc plan.** Ready for sprint-by-sprint commit.
