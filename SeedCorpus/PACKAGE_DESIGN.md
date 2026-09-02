# Document Package Design

Status: design v1.2 (shape, not spec), owner rulings applied, four audits folded, sprint series in §9
Date: 2026-08-27 (v1 same day; v1.1 supersedes it in place); v1.2 supersedes v1.1 in place, 2026-09-02; sprints 1-4 shipped (§9)
Repo home when adopted: `RecordHealth.IO/SeedCorpus/PACKAGE_DESIGN.md`

Absorbs F-NEW-MQ (app-side result package import) and F-NEW-QG (per-document package fidelity), and is the precondition for F-NEW-QF (ADI grading sprint) and for the bakeoff in VENDOR_ABSTRACTION_DESIGN §4. Grounded in four audits run 2026-08-26/27: the Worker-side ADI gap matrix, the phone-side field trace, the repair failsafe audit (repair sprint shipped), and the ADI package-storage audit.

**Owner rulings, fixed points of the design:**

- R1. Every ingested document produces one package: the full, complete container of everything the pipeline made from it. Nothing is left behind on the server that the package does not carry.
- R2. The phone is the system of record. It receives the package whole, stores it whole, exports it whole.
- R3. Three doors out, one format: voluntary ADI submission, an archive another phone can import in its entirety, iCloud backup. One door in: a graded package from the ADI, importable in full.
- R4. The Worker never submits to the ADI. Users control their data; ADI submission is voluntary for users, if offered at all. Development submits from the device.
- R5. A graded package returning from the ADI replaces the original. The ADI is a ground-truth process, not a routine user path; most packages will never be graded; grading takes the user's amendments into account.
- R6. Field-level schema drift between Worker, phone, and ADI is unacceptable. The server sets the schema; the phone and the ADI consume it; a new field reaches a deployed phone without a release.
- R7. A partial document never reaches a user's tree. Repair completes on the Worker or the document fails visibly (shipped 2026-08-27, WORKER_ARCHITECTURE § Repair executor).
- R8. Grading granularity is set by what the record contains, never by reviewer effort. Ground truth must be able to assert structures the incumbent pipeline does not emit (checkbox state first).
- R9. User changes ride as versioned amendments. The original and every amended version are both visible and both searchable. An amendment is data: training signal and a longitudinal edge (a provider's recurring misspelling becomes an alias case).
- R10. User amendments always travel with an ADI submission.
- R11. PHI values travel inside the package to the ADI, and the phone's token assignments travel with them as part of the package.
- R12. ADI storage extends the existing structure (shape (b) below); nothing parallel.
- R13. The package's server sprint precedes the vendor abstraction refactors.
- R14. Size is watched, not ruled: the ADI records package size per package.

---

## 0. Framing

### 0.1 The package is the record; rows are a catalog built from it

The package stays intact: one sealed, self-contained unit. It is what travels through every door, what is hashed, what is backed up, what a reviewer grades.

Every table, row, sidecar, and store on either side is a projection of the package: built from it, rebuildable from it, never holding anything the package does not. If a projection and the package disagree, the package is right and the projection is regenerated. This is the Provenance Doctrine applied to the container: the original capture is the only source, nothing is reconstructed from anything else, nothing is overwritten.

The current architecture has this backwards on both sides. On the phone the decoded stores are the only copy and the result body is discarded. On the ADI the atom rows are the only copy and no package exists. That inversion is why a field with no slot dies.

### 0.2 Why verbatim and why a published schema, together

The phone-side trace found the loss chain: the Worker emits a result; the phone decodes it into the Swift slots that exist and drops the rest; the ADI transit forwards a subset of what the phone kept. The vocabulary dictionary (INGEST_VOCABULARY_DESIGN v7, shipped 2026-08-22) closed this for values. It does not cover fields; F-2's manifest intent was superseded by the dictionary sprint and the field half never landed.

Two mechanisms close it, and each backs the other. The core is stored verbatim, so a field the phone does not understand is never lost, only not yet rendered. The schema is server-published, so a field the Worker emits that the schema does not name is a drift event on the fifth NCC panel. Verbatim makes drift recoverable; the schema makes it visible.

---

## 1. The package

```
Package (illustrative, not wire)
manifest
  package_version        : version of this manifest shape
  package_id             : minted on the phone at first store; identity across doors
  record_id, patient_id  : phone identities (patient_id is never inside the core; §4 finding)
  core_hash              : SHA-256 of the core bytes as stored on the phone
  source_hash            : SHA-256 of the source document bytes (today's file_hash)
  configuration          : { parse_vendor, parse_config_bundle_version, inference_provider,
                             prompt_variant_set, pipeline_version_stamp }   (VENDOR_ABSTRACTION §1.1)
  schema_version         : server schema snapshot the core was emitted against
  vocabulary_version     : dictionary snapshot in hand at mint (F-NEW-PQ already tracks it)
  job_id, environment    : Worker job identity for NCC correlation
  minted_at, app_version, package_size_bytes
  amendment_version      : 1.0 at mint; 1.n after n amendments (§3)
core
  the Worker's GET /v1/ingest/result body, byte-exact as received, for a COMPLETE job only (R7)
source
  reference to the original document bytes (originals/{recordId}, already stored)
tokens                   (phone-authored; §2.3)
  { atom_id -> phi_token_uid } plus the document-scoped reverse map
amendments               (append-only log; §3)
```

**Verbatim, precisely.** The core is the result body served for the completed job, not a re-serialization of Swift structs. `core_hash` is over those bytes. Every view the phone builds (SegmentedFactStore, SectionsStore, ParsedPageStore, OCRResultStore) is derived from the core. The sidecar files stay as working stores and stop being the source of truth.

**What the core carries today that the phone drops** (phone trace 2026-08-27): kt_coding, codex lineProvenance, parse_vendor_meta, section_pass_version, citation boxes and page dimensions, the validation block (validated, char offsets, match_method, rejection_reason), errors, error_codes, timing, atom_class, and since the repair sprint, sections[].inventory and phi_unattributed_atom_ids. All survive under this design with no phone change beyond storing the bytes.

**Configuration identity is mandatory.** The core today names no vendor or version in a form the phone keeps. VENDOR_ABSTRACTION §3.1 already commits to threading vendor plus config-bundle version into the pipeline stamp; the manifest carries the resolved tuple so a package is comparable across bakeoff runs. This field is what makes a package a scorable unit.

**One document, possibly many packages.** A re-ingest (force-fresh, version bump, vendor change) mints a new package under the same record_id. Packages are append-only on the phone; the record points at its active package; superseded packages are retained until the user deletes the record.

---

## 2. Doors

### 2.1 Phone storage

`records/{recordId}.package.enc`: manifest, core, tokens, amendments; encrypted like every sidecar. Written when `GET /v1/ingest/result` returns 200 for a complete job, before any decode. If the write fails, the ingest fails; the phone never builds views from bytes it did not keep.

Views are built from the stored package by the existing decode path. "Rebuild views" re-runs that decode against the stored core; it is what a schema refresh or an app update triggers.

CloudKit: the package file joins the essential patterns. That closes the current exclusion of `.sections.enc` and `.parsed.enc` by making them rebuildable rather than by adding more patterns.

### 2.2 Archive (.rhpkg)

PatientPackageExporter and Importer stay as the mechanism. The unit changes: a patient archive is a bundle of document packages plus the patient index slice; each entry is the same `{manifest, core, source ref, tokens, amendments}` the phone stores. A single-document archive is the same format with one entry. Import copies packages in and rebuilds views.

### 2.3 ADI submission

The transit sends the package, not a projection. The tokens layer is not optional: the Worker never mints PHI token ids (find-or-create is app-side by sacred rule), and the upload refuses any PHI atom without one. R11 puts the PHI values and the token assignments inside the package; the ADI stores both.

The upload boundary must stop transforming the body before storing it: today `stripNullBytes` rewrites every string first, so a hash computed on the phone cannot match the stored bytes. Either the core is exempted from the strip and validated separately, or the hash is defined over the post-strip bytes and the manifest says so. The design takes the first: the core is stored as sent and sealed by the phone's hash.

### 2.4 ADI return

The ADI exports a graded package: the same manifest and core it received (core_hash unchanged) plus the reviewer's amendments appended to the log. The phone imports it through the archive importer and, per R5, replaces the record's active package and rebuilds views. Because the user's amendments travelled with the submission (R10) and the reviewer graded with them in view, the returned log is a superset of what left the phone.

---

## 3. Amendments: one log, every author

Grading and correction never modify the core. They append to the log.

```
Amendment
amendment_id, amendment_version (1.1, 1.2, ...)
author        : user | adi_reviewer | system
authored_at, app_version | grading_tool_version, reviewer_authority (adi only)
target        : { entity: atom | section | edge | span | inventory | discovery, id, field_path }
op            : correct | add | remove | flag | verdict
value         : the new value (for correct/add), the verdict (for verdict)
reason        : free text (user) or reject_reason taxonomy (adi)
provenance    : e.g. { provider_facility_atom_id } for a misspelling correction
```

The original value is never copied into the amendment; `target` points at it by path in the core, so the original is only ever the core.

**Views.** The phone builds what it shows as core plus amendments folded in order. "Show original" is the core alone. "Show history" is the log. Search indexes both the core value and the amended value, so a misspelled name finds the record under either spelling (R9).

**Longitudinal edge.** A correction carries the provider identity of the record it was made on. That is exactly the raw-observed-strings-with-keys-re-derived pattern `PatientProfile.confirmedAliases` already uses; the amendment feeds it. A later ingest from the same provider carrying the same misspelling yields a system-authored amendment proposing the correction, awaiting the user's confirmation, never applied silently. Same doctrine as keystone confirmation in EVENTS_INTERACTIONS_DESIGN.

**Reviewer discoveries** (ground-truth entities with no core counterpart) are amendments with `op: add` targeting a new id in the discovery namespace, typed by the schema like any other entity (§5).

**Derived layers** (ContextStore, care graph, prompts, summaries) are never in the package and are rebuilt from core plus amendments.

---

## 4. ADI storage: shape (b), a package row under the document row (R12)

From the ADI package-storage audit (2026-08-27). The existing structure is kept; the package is added inside it; the atom, section, and region rows become projections.

- `review_documents` stays the per-file parent: one row per source (file_hash unique), the PDF in R2 under `documents/{patient}/{record}.pdf`, uploaded_by, status.
- `document_packages` (new child): one row per package, keyed by `package_id`, carrying the manifest columns (core_hash, source_hash, configuration JSONB, schema_version, vocabulary_version, job_id, environment, package_size_bytes, amendment_version), the core in R2 under the same key scheme (`documents/{patient}/{record}/{package_id}/core.json`, sealed with the R2 sha256 option the ingest park path already uses), the tokens layer (`phi_reverse_map` moves here from the document row: it is a per-package output), and the amendments log (JSONB, append-only by handler discipline plus a trigger).
- `data_atoms`, `source_regions`, `atom_region_links`, `knowledge_gaps` gain `package_id` and project from the package. None of their `document_id` columns is a foreign key today, so this is a repoint, not a constraint migration. `grading_submissions.document_id` is a real FK and repoints to the package.
- `review_phi_detections` is retired (no longer written, still read in three places; the reads move to the tokens layer).

**Projection rules the schema must state, because the audit found them living on the phone or in hardcode:**

- `verbatim_value` = `source_text` unless absent, then the codex dereference. Today this rule is phone-side (DATA_MODEL §7.6); it becomes a schema-declared derivation.
- `created_by` / `uploaded_by` / `produced_by` come from the manifest's configuration, never the literal `ios_extraction`, `ios_ocr`, `ios_app`. A Worker-produced core stored under an iOS label is false provenance.
- `entity_kind_term_id` is resolved against the vocabulary snapshot named by the manifest's `vocabulary_version`, not the live table, so two projections of one core are identical regardless of when they ran.
- Sections project from the core's shape (camelCase `containedLineRanges` / `parentId`); the upload validator's snake_case shape and the stale u7b DDL comment both retire. Section ids are minted per rebuild on the Worker; the projection keys sections by `(package_id, ordinal)` and carries the core's id as an attribute.
- The result envelope (parse_vendor_meta, errors, error_codes, record_type, section_pass_version, timing) and codex / parsed_pages are not projected in v1; they are in the core and readable by path. F-NEW-M (sections to first-class table) stays parked on the same trigger.

**Idempotency and the second package.** Three one-per-file assumptions change together: the check-hash pre-flight answers per package (the phone's `alreadySubmitted` refusal keys on package_id), the upload idempotency gate keys on core_hash, and the R2 key carries the package_id. The console lists documents and, under each, its packages.

**Boundary hygiene folded in (audit findings 10, 11, 7, 8):** a request-body cap on the upload route (today none; only the decoded PDF is capped); the null-byte strip exempts the core; `GET /v1/admin/grading/stats` counts documents with at least one locked submission, not submissions; the two grading columns that exist only on Neon (`verdicts` / `discoveries` beside `section_verdicts` / `section_discoveries`) get their migration file, and F-NEW-AF is restated against the live shape.

**Migration posture.** Both ADI databases hold zero rows (truncated 2026-08-21). This lands as a new baseline migration, not a data migration. Wipe-and-rebuild is the sacred rule and here it costs nothing.

**Precedent.** `share1_schema.sql` already implements client-minted package id as idempotency key, manifest JSONB, per-record structured blob, and a hash plus size pair validated at upload under a manifest-is-the-contract rule. Different binding, same shape; reuse the pattern, not the tables.

---

## 5. The schema layer (R6)

The dictionary grows a second snapshot: the entity schema.

**Shape.** For each entity the result carries (envelope, codex page, parsed page, table, section, atom by producer, edge, span, inventory, token layer, amendment, discovery, manifest): field name, type, optionality, since-version, derivation rule where one exists (§4), and for grading the capability the ADI must offer (verdict, correction, authoring, none). Closed vocabularies keep pointing at the vocabulary snapshot; the schema names the field, the dictionary names its values.

**Authority: generated from the Worker's emit, never hand-written.** A generator reads the assembler's definitions and publishes the snapshot; a fixture-driven test under the replay harness asserts that every field a real assembled result carries is named. The suite fails when the schema lags the code. Same posture as the extractor tool schema generated from the vocabulary snapshot (v7 Phase 2). This forces the Extract prompt and schema carve-out VENDOR_ABSTRACTION §1.1 already commits to.

**Delivery.** `GET /v1/schema` with version negotiation, cached beside the vocabulary snapshot. Opportunistic, never blocking. The ADI feeder and console read it server-side.

**Schema change mechanics (owner question 1).** The core never changes. Adding a field: the Worker emits it, the snapshot names it, the phone refreshes and rebuilds views; old packages lack it and their manifest's `schema_version` says why. Splitting a category: if the split is a mapping (A always becomes B), the vocabulary snapshot carries it and views rebuild; the core still says A with the snapshot version it was emitted under. If the split needs judgment (A is B or C depending on the record), nothing guesses into the core: the document is re-ingested under the new configuration (new package, old retained), or a system-authored amendment proposes the new category for confirmation. The trigger for all of it is one comparison: manifest `schema_version` versus the phone's cached snapshot.

**Phone behavior.** Presence is schema-driven, rich handling is compiled: a field the schema names but the app has no slot for is preserved in the core and surfaced generically; a field the app compiles that the schema no longer names is a drift beacon event. Rich handling ships in app releases; receiving does not. See OR-7 (§11) for the sprint 4 scope this shipped under.

**Drift detection, both directions.** A Worker result carrying a field outside the schema it claims: anomaly, misfire log. A reader against a newer schema than its cache: refresh, re-decode from the core. Every case lands on the fifth NCC panel; no new surface.

---

## 6. Gradeable units (R8)

Derived from the schema, not hand-maintained in the console:

- Atoms (clinical, PHI, synthesized; synthesized graded as synthesis, never counted as extraction).
- Sections: kind, extent, parent.
- Relationships: atom to section membership; belongs_to_panel; belongs_to_address; cell identity and row grouping; region_role; dedup supersession where it exists.
- Structured payload fields, per field.
- Codes (kt_coding) per atom.
- Geometry per span, tolerance IoU.
- Section inventory: "this section should hold N of kind K."
- Amendments themselves: a reviewer can accept or reject a user's amendment, which is a verdict targeting an amendment id.

**Ground-truth-only units** (discoveries, typed by the schema): checkbox and selection state (checked, unchecked, indeterminate, geometry, bound label); negated findings; strikethrough and discontinued state; handwritten versus printed; signature and stamp presence; real table cell structure; section geometry and true extent.

**Verdict vocabulary, fixed:** accepted, rejected, corrected, with a server-side allowlist at submit; computeMetrics reads the same three.

---

## 7. Bakeoff linkage

The graded corpus is a set of packages with reviewer amendments. The resolver (VENDOR_ABSTRACTION §4.1) folds the amendment log of a graded package into ground truth and scores any candidate package with the same `source_hash` against it. The manifest's configuration tuple is the report key. The corpus can now say which vendor and prompt produced each graded core, closing the weakness §4.1 accepted for v1.

---

## 8. Hard questions and tradeoffs

1. **Size (R14).** Verbatim results with word geometry are large; the DO already shards them at 1 MB. Storage roughly doubles (blob plus projections) on both sides. The ADI records `package_size_bytes` per package; no cap in v1; compression at rest is the lever if it ever matters, never omission. No live measurement exists today (both ADI databases empty; the DO stamps result bytes on meta only).
2. **Two sources of shape.** Compiled Swift types and the published schema both describe the result. Schema is authoritative for presence, Swift for rich handling; the same split the vocabulary lives with.
3. **Same-target conflicts after a graded return.** R5 replaces; the returned log contains both the user's and the reviewer's amendments. The view shows the newest; both stay; the user can flip. This is the residual of the old OR-1.
4. **PHI at rest on the ADI (R11).** PHI values and tokens are inside the package on the ADI. This is the current BAA posture for the ADI (staging project, development-only submission, R4). It is restated here so nobody reads "sealed package" as "tokenized package."
5. **Token identity across devices.** Token ids are phone-minted and device-global. A package imported to a second phone carries the first phone's tokens; the importer reconciles them against its own vault (find-or-create by derivation, sacred rule) and records the mapping as a system amendment. Not designed further here; flagged for sprint 9.

---

## 9. Sprint series

Dependency chain: the Worker states what it emits before the phone can keep it honestly; the phone keeps it before the ADI can receive it; the ADI stores it before it can grade it; grading works before anything is exported back. Each sprint produces what the next consumes. Every sprint opens with an audit prompt naming its files and closes with one real document crossing it on staging, docs bumped, F-items filed. Unit tests passing is not a close condition.

| # | Repo | Ships | Close condition (live proof) | Model |
|---|---|---|---|---|
| 0 | both | Audits; repair sprint (shipped 2026-08-27) | Done | |
| 1 | api | **SHIPPED 2026-08-28.** Schema generator from the assembler's definitions; entity schema snapshot; `GET /v1/schema`; emit-coverage test that fails the suite when the Worker emits a field the schema does not name | Done — staging serves the snapshot (`schema_version` 1, 31 entities) and `?version=1` returns 304; the bogus-field negative control is a permanent test. Detail: `recordhealth-api/docs/WORKER_ARCHITECTURE.md § Entity schema layer` | Opus 5 |
| 2 | api | **DONE 2026-08-30.** Package identity on the result: configuration tuple (forces the Extract prompt/schema version constant, VENDOR_ABSTRACTION §1.1), schema_version, vocabulary_version, server-side core hash in a response header. Additive only | A staging job's result carries the tuple and the hash. Detail: `recordhealth-api/docs/WORKER_ARCHITECTURE.md § Result identity — the configuration tuple + the served-bytes hash` | Opus 5 |
| 3 | app | **DONE 2026-08-30.** Result bytes written to the package file before decode; hash verified; all views rebuilt from the stored core; package in the CloudKit set | Ingest on staging, delete the sidecars, rebuild from the package, hash matches, screens identical. Detail: `RecordHealth_App/docs/ARCHITECTURE.md §3.10 Document packages and view rebuild` | Opus 5; Fable reviews the decode contract first |
| 4 | app | **DONE 2026-09-02.** Schema fetched and cached; fields with no slot surfaced generically; fields the app compiles that the schema dropped raise a drift beacon | A field added to the staging schema appears on the phone with no app update. Detail: `RecordHealth_App/docs/ARCHITECTURE.md §3.11 Result schema layer` (scope amended by OR-7, §11) | Opus 5 |
| 5 | app | .rhpkg as a bundle of document packages; single-document export; importer rebuilds views; tokens layer and amendment log shapes with readers (no writer yet: the correction UI is undesigned) | Export, wipe, import; packages identical by hash | Opus 5 |
| 6 | api ADI | New baseline migration (`document_packages` under `review_documents`, `package_id` on projection tables); upload accepts a package; core to R2 sealed by hash; projections by the schema's derivation rules; boundary hygiene (body cap, null-strip exemption, provenance from manifest, term ids by vocabulary version, section shape unified) | Submit from the phone; drop the projected rows; regenerate from the package; identical | Opus 5 |
| 7 | api ADI | Grading as amendments; verdict allowlist; metrics repaired; section discovery submit fixed; AI sections rendered from line ranges; relationships gradeable; stats count documents | One real document graded end to end with a non-zero F1 (the first real number the ADI has produced) | Opus 5 |
| 8 | api ADI | Graded package export: amendments appended, core hash unchanged | Export, verify hash, diff the log | Sonnet 5 |
| 9 | app | Graded import: amendments accepted, replace per R5, tokens reconciled against the local vault, newest-wins view with history | Round trip lands on the phone with original and graded both visible | Opus 5 |
| 10 | api ADI | Ground-truth-only units: checkbox first as a typed discovery, then §6's list | A reviewer authors a checkbox on a real document and it survives export | Opus 5 |

Then VENDOR_ABSTRACTION V1 onward, with a corpus format that exists.

Ten sprints, roughly five to seven weeks at the recent pace. Sprints 1 and 2 may run while sprint 3 is being audited (different repos); nothing else overlaps safely.

Also: an unscheduled data-integrity fix shipped 2026-08-30 between sprints 1 and 2 — DO shard multi-byte corruption (`writeSharded` cut shards on raw byte length, splitting multi-byte UTF-8 characters and silently corrupting clinical text on read). See `recordhealth-api/docs/WORKER_ARCHITECTURE.md`.

---

## 10. What this design deliberately does not do

No failure-record format for the ADI (exhausted jobs produce no package; a future failure package for edge-case study is separate scope). No server-side retention of packages. No change to PHI token derivation or namespaces. No vendor abstraction. No user-facing ADI submission UI. No merge semantics between two packages of the same document. No correction UI on the phone (the amendment log is designed; its first writer ships with that UI).

---

## 11. Rulings log

- OR-1 (replacement): ruled 2026-08-27, replace (R5); residual conflict rule in §8.3.
- OR-2 (user amendments to ADI): ruled, always (R10).
- OR-3 (PHI in the ADI copy): ruled, inside the package with tokens alongside (R11).
- OR-4 (ADI storage): ruled, extend existing structure; shape (b) per audit (R12).
- OR-5 (sequencing): ruled, package first (R13).
- OR-6 (size): ruled, watch via size field (R14).
- OR-7 (sprint 4 scope): ruled 2026-09-02, sprint 4 scope split by owner ruling: schema-named atom/envelope fields with no compiled slot are preserved in the core but not displayed in v1 (Layer 1 pass-through slot deferred to F-NEW-QR); the achievable generic surface is the atom-kind lane ("Other information", shipped); §9 sprint 4's close condition is met in this amended form.
- Open: none at v1.2.

---

## 12. Side findings filed out of this design

Filed at ROADMAP 2026-08-27: F-NEW-QF, F-NEW-QG, F-NEW-QD. To file at the next ROADMAP pass: `.parsed.enc` write-only on the phone; atom_class inferred from kind instead of read; `buildAtom`'s dead `fallbackProducedAt`; DATA_MODEL §7.6 credits CellWalker as producer; ADI upload route has no request-body cap; `grading/stats` counts submissions as documents; F-NEW-AF premise stale and two grading columns exist only on Neon with no migration file; `review_phi_detections` unwritten but read in three places; token identity reconciliation across devices (§8.5).
