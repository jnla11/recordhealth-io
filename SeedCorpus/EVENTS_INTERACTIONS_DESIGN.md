# EVENTS_INTERACTIONS_DESIGN.md — F-NEW-MF Events/Interactions Design Pass (v3)

Status: design-locked
Last verified: 2026-07-26

**Version: v3 — design-locked.** Amends v2 in place: all ten open questions v2 carried at its end are now owner-ruled (2026-07-25/26) and folded into the body. Where a ruling contradicted a v2 proposal (Q3's classification-call cap, Q9's log-and-proceed recommendation), the ruling wins and the superseded text is rewritten with a one-line supersession note — dead reasoning is not preserved; read v2 in git history if it's needed. This is still shape, not spec: field lists are illustrative contracts, not final Swift/JS declarations. Judgment calls no ruling covers remain marked **PROPOSED** with the rejected alternative. No open questions remain; the resolved-rulings ledger at the end records each question, ruling, and date.

**Ruling set carried in (ROADMAP F-NEW-MF + 2026-07-25 amendment + the 2026-07-25/26 design-lock rulings — ledger at end):** keystone-question flow (no manual event creation; AI proposes, user confirms; rejected stays rejected; low-confidence asks nothing); many-to-many complaint membership; sub-document interaction splitting; stitched-fact summaries (every fact traces to a record, no unstated causation, gaps visible); forward assignment with the BAA-envelope handshake (may run server-side, same posture as the ingest pipeline, not required to ride the tokenized path); VisitContext disposition ruled here (F-NEW-MH).

**Post-lock stamp (2026-07-26):** one owner ruling arrived after design lock — citation resolution discipline, folded in at §G.4. It constrains rendering only (no new mechanism, no reopened question); the lock and version number stand unchanged.

**Ground truth anchored to:** `recordhealth-api/docs/archive/FNEWMF_GROUNDTRUTH_RESULT.json` — a real 29-page multi-encounter Cedars-Sinai compilation: 187 sections (9 kinds observed), 222 atoms, 48 dateAtoms across 33 distinct date strings spanning 2017–2026, 12 provider atoms, 1 facility atom, 1 low-confidence `kind=encounter` atom, and a single `record_type: "Lab Results"` flattening at least seven distinct clinical encounters (Jul 2026 labs, Nov 2025 imaging arc, Nov 2024–Jan 2025 arc, 2018–2019 shoulder arc, and a 2026 office-visit letter).

**v2 evidence, owner-verified 2026-07-25 — treated as ground truth:** a live experiment ran one Bedrock call (Sonnet, ~18k in / 8k out, ~100s) over a 187-section manifest built from the artifact above, asking for interaction boundaries, types, attachments, and registry sections. It proposed 9 interactions, 14 attachments, 10 registry sections; mechanical validation caught one section-id corruption (a dropped hyphen) and one registry-boundary overlap (immunization/social-history ranges both claiming the same 4 sections); the model self-corrected mid-response, itself arguing for enforced structured output. The owner then graded the proposal against the source PDF — a Cedars-Sinai "Entire Care Summary" CCD whose own encounter-list registry enumerates **39 distinct encounters (2017–2026)**; roughly 30 of those exist only as encounter-list rows, with full body documentation for a handful of result sets (labs, imaging reports). The model's 9 interactions were exactly the body-documented ones — **8 of 9 correct**, including matching a source-printed same-day hospital-encounter split verbatim (04/30/2018 3:06–3:59 PM and 4:00–11:59 PM print as two rows in the encounter list — see §B.1). The one failure: it **invented** a "cardiology office visit 12/24/2024" (that date is actually a GI colonoscopy per the encounter list) to serve as an anchor for three CT-calcium-scan results that are each their own indexed hospital encounter (01/15/2025, 03/31/2022, 01/25/2019). Inventing an encounter to house orphan results is the doctrine-violating failure mode this amendment is designed against — see §B.

---

## 0. Vocabulary and the doctrine line

Two new entities, one bright line between them:

- **Interaction** — a sub-document unit: one clinical touchpoint (a visit, a draw, a study, a procedure) as documented inside one record. A 29-page compilation contains many; a single lab PDF contains one. Interactions are **structure**, like sections: derived deterministically from document evidence. They are never a clinical judgment, so — like sections — they require no user confirmation, **with one exception introduced in v2** (below).
- **Event (Complaint)** — a grouping of interactions across records into one course of care ("the shoulder thing", "the cholesterol follow-ups"). Grouping interactions asserts clinical relatedness. That **is** interpretation, so an Event exists only as a Layer 3 proposal until the user confirms it (clinical doctrine + sacred rule 8). Membership is many-to-many by ruling: one visit can serve multiple complaints.

This line — *interactions are structural facts, events are confirmed interpretations* — is still the load-bearing decision of the whole design. v2 sharpens what "structural fact" means once a document's own registries enter the picture.

**PROPOSED, reaffirmed with a carve-out (doctrine application, not covered explicitly by a ruling):** interaction splitting does not get a confirmation prompt — **when the split is asserted by the document itself.** A registry row (§B.1) *is* the document stating "this is a distinct touchpoint," the same way a dated, signed page is. Attaching body sections to a registry-asserted row (§B.2) is containment/classification, not invention. Neither needs confirmation, for the same reason v1 gave: the app asserts nothing clinical by recognizing what the source already asserts.

**Supersedes v1 §0's blanket rule for the no-registry case.** v1 reasoned that *all* splitting is document-stated fact and therefore never needs confirmation, because its only splitting mechanism was a deterministic date-clustering pass reading source-stated dates and providers. v2 retains a case the deterministic pass never had: a document with **no** registry, where a Bedrock call itself proposes that a single document actually contains more than one touchpoint (§B.3). That proposal is model inference over prose and date signals — nothing on the page asserts the split the way a registry row does. It is the same class of interpretive judgment event-grouping already gates, so it is gated the same way: a keystone question, not a silent split. This is the one place v2 narrows v1's confirmation-free claim; everywhere a registry exists, v1's original reasoning holds and is strengthened, because the source is now doing the asserting instead of a heuristic re-deriving it.

---

## A. Data model

### A.1 Interaction

Produced server-side during ingest (see §B.5 for why), shipped in the result blob, persisted on device verbatim as a per-record sidecar — the same lifecycle as sections.

```
Interaction (wire + device, illustrative)
id                    : UUID        server-minted (same rule as atom ids)
record_id             : UUID        owning document
origin                : registryIndex | tier3SplitProposal | tier3WholeDocument   which tier minted this (§B)
registry_entry_id     : UUID?       back-reference into RegistrySection.entries (§A.1a) — set iff origin = registryIndex
is_index_only         : bool        true until ≥1 section is attached (§B.2); an interaction may live here indefinitely
attached_section_ids  : [UUID]      stored explicitly for registryIndex/tier2 origins (see Edges, below); empty while index-only
page_range            : {first, last}?   DERIVED CACHE — union of attached sections' pages; nil while index-only
anchor_date           : ISO date?   printed registry date (registryIndex) or detected anchor (tier3, §B.3)
anchor_date_role      : string?     which role won, tier3 only (collection|service|visit|report|study)
printed_type          : string?     registry's own Type/Department text, verbatim — set iff origin = registryIndex
provider_atom_ids     : [UUID]      provider atoms observed inside attached sections (empty while index-only)
facility_atom_id      : UUID?       organization atom if one scopes this span
record_type           : string?     per-interaction, closed 26-value taxonomy (§E) — set only once body-documented; nil while index-only
summary_bullets       : [string]?   per-interaction recordSummary output (§E) — nil while index-only
indexer_version       : string      provenance of the tier that minted this interaction (registry parser or tier3 splitter)
```

**Identity:** server-minted UUID, passed through like atom UUIDs so edges resolve. **Provenance:** `indexer_version` names the deterministic pass version — producer provenance captured at source, per doctrine (renamed from v1's `splitter_version`; same role, now covering the registry parser as well as the retired-to-salvage splitter).

**Index-only rendering.** An interaction with `is_index_only = true` renders as a single line built entirely from the registry row's own printed fields — date, `printed_type`, department/care-team text, as printed — with a tap-to-source region resolving to the registry row itself (`RegistryEntry.source_region`, §A.1a), not to a body section, because none is attached yet. No `record_type` classification call runs against it (§E) — there is nothing to classify. If §B.2's attachment call (same-ingest) or a later reingest attaches ≥1 section, the interaction **promotes in place**: same id, `is_index_only` flips false, `record_type`/`summary_bullets`/`page_range` populate. No migration, no new row. Phase 2 (§H) renders index-only interactions interspersed chronologically with body-documented ones, visually distinguished (no drill-in affordance) since there is nothing to open yet.

**Edges — supersedes v1 §A.1.** v1 derived section→interaction and atom→interaction purely by page-range containment (a stored `interaction_id` FK was rejected as redundant with a pure geometric test), reasoned as regenerable and staleness-free. That reasoning assumed every interaction boundary came from one deterministic page-range pass. Registry-first breaks the assumption for `origin = registryIndex`: a registry row is a printed *fact* (a date, a type, a provider) with no inherent page range of its own — Tier 2's job (§B.2) is to *judge* which sections evidence it, which is a classification, not a geometric test. Containment cannot do that job, so it is no longer the mechanism for these origins:

- **`origin = registryIndex`:** `attached_section_ids` is stored explicitly — Tier 2's output, or reingest's. Atom→interaction resolves one hop further than v1: `atom.section_id → section → interaction.attached_section_ids` membership.
- **`origin = tier3SplitProposal | tier3WholeDocument`:** v1's page-range-containment mechanism survives unchanged. Tier 3's splitter (§B.3, salvaged from v1 §B) still produces literal contiguous page ranges, so containment remains a pure, regenerable function exactly as v1 designed it. `attached_section_ids` is a cached materialization of the same containment test, not a second source of truth.
- **`page_range`** is now a **derived cache** everywhere (union of attached sections' pages), not the source of truth for `registryIndex` origins — kept because Phase 2's "tap scrolls PDF to `page_range.first`" UX shouldn't need a join at render time. Recomputed whenever `attached_section_ids` changes.
- **interaction → complaint:** unchanged from v1 — held on the Event side (§A.2), never on the interaction. Interactions are pipeline output; pipeline output must not carry interpretation-layer membership (rule 8, layer 3 never mutates downward).

**Layer placement:** unchanged from v1 — Layer-1-adjacent, exactly like `{recordId}.sections.enc`. Not Layer 2, not Layer 3.

**Device persistence:** `Documents/records/{recordId}.interactions.enc`, unchanged from v1. **Server persistence:** unchanged from v1 (§A.3 table below, extended with the registry-section row).

### A.1a Registry Section (new in v2)

A registry — an encounter list, a problem list, a medications table — is a first-class structural concept, not a specialization of "table" or "narrative." It is identified once per document (§B.1, §B.2) and its rows are the source of both the Tier 1 interaction index and complaint-layer seeding (§C.2b).

```
RegistrySection (wire + device, illustrative)
id             : UUID
record_id      : UUID
registry_kind  : encounterList | problemList | visitDiagnoses | medications | allergies
                 | immunizations | socialHistory | vitals | careTeams | documentMetadata
section_ids    : [UUID]      body sections (typically a table_headers section + its observation rows) this registry occupies
identified_via : tier1Deterministic | tier2Bedrock
                 -- encounterList is always tier1Deterministic; the other nine kinds are tier2Bedrock (§B.2)
entries        : [RegistryEntry]

RegistryEntry
id                    : UUID
registry_section_id   : UUID
fields                : [{ column: string, value: string }]   ordered, as printed; column labels are the registry's
                                                                own headers (a registry's shape varies — encounterList
                                                                prints Date/Type/Department/Care Team/Description;
                                                                medications prints Dispense/Medication/Sig/Quantity/
                                                                Refills/Last Filled/Start Date/End Date/Status)
status                : string?     printed qualifier when the registry prints one (medications' Active/Discontinued,
                                     an immunization's checked/unchecked "Next Due" — pulled out of `fields` into its
                                     own slot because it is load-bearing, see below)
source_region         : SourceRegion   same shape as an atom's citation region — this row's printed location,
                                        for §G.4 deep-link citation and for §A.1's index-only tap-to-source
linked_interaction_id : UUID?     encounterList entries only; set at Tier 1 mint time (§B.1)
```

**The F-NEW-MK dependency, stated explicitly.** Every `fields`/`status` value on a `RegistryEntry` is a verbatim extraction read of the source table — this design layers no clinical inference on top of it. Registry-seeding means list-status fidelity is now load-bearing at the *root* of the tree it seeds: if F-NEW-MK's table extraction drops a "Discontinued" qualifier, mis-reads a checked/unchecked box, or mis-splits a multi-line cell, the corruption flows straight into the Tier 1 interaction index (`encounterList`) and into every complaint candidate seeded off Visit Diagnoses / Active Problems (§C.2b). Nothing downstream in this design catches a wrong-but-well-formed status value — a wrong "Active" still parses, still tables cleanly, still looks like a printed fact. This is a genuinely new dependency v1 didn't have (v1's date-clustering pass consumed only `dateAtom`/`provider` atoms, already hardened by the Atom Pass's own validation); F-NEW-MK's table-cell extraction accuracy is now a precondition for this track, not merely for a display list.

**Detection reality, from the artifact.** Registry headings are not uniformly clean even in a well-formed CCD: `Encounters`, `Visit Diagnoses`, `Immunizations`/`Social History` render as clean `heading` text elements (pages 2, 27, 8), but `Allergies` (page 6) renders only as an inline `text` run, and `Medications`' heading (page 7) collapsed into its own table's header row, repeated once per column, with no standalone heading element at all. A detector keyed on heading text alone is fragile. Tier 1's `encounterList` detector (§B.1) therefore keys primarily on **column-header shape** (Date + Type + Department/Care-Team-shaped columns), with heading text as corroboration when it survives extraction, not as the primary signal.

### A.2 Event / Complaint

Device-only, never held server-side, keystone-confirmed — lifecycle unchanged from v1. **One shape change, ruled 2026-07-26 (the Q4 addendum):** membership edges now carry a granularity (below, and §C.6). See §C.2b (new in v2) for a second candidate-generation path that feeds proposals into this same store; the store, confirmation flow, and tombstone semantics below are exactly as v1 designed them.

EventMembership is a relationship entry of kind `member_of_event`; shape and registry in RELATIONSHIP_DESIGN.md §1-§3; this section owns what an event is and how membership is confirmed.

```
Event (device, illustrative)
id               : UUID       device-minted at confirmation
patient_id       : UUID
title            : string     the user-confirmed phrase (from the keystone question)
status           : confirmed              (proposals live elsewhere — below)
members          : [EventMembership]
related_events   : [EventEdge]            comorbidity chains; empty in v1/v2 (§A.4)
created_at       : date
confirmed_via    : keystone | forwardAssignment   provenance of confirmation

EventMembership
target_kind      : document | interaction | section | atom   edge granularity — ruled 2026-07-26 (§C.6)
target_id        : UUID       the document/interaction/section/atom this edge binds
record_id        : UUID       denormalized for one-hop record resolution
added_via        : keystone | forwardAssignment
added_at         : date
```

Membership is many-to-many by ruling, and — **ruled 2026-07-26, superseding v2's interaction-granular wording** — membership edges exist at **every granularity**: document, interaction, section, and individual atom (`target_kind` above, mechanism at §C.6). The owner's example: one lipid line inside a general-screening panel speaks to a blood-pressure complaint while the panel's own membership belongs elsewhere — an atom-level edge captures that without misfiling the panel. Interaction remains the default granularity keystone proposals arrive at; finer edges confirm through the same flows. `EventMembership.added_via` is otherwise unchanged — a registry-seeded candidate (§C.2b) still confirms via `keystone`; seeding only changes where the *candidate* came from, not who confirms it or what the confirmed record looks like.

**Layer placement, rejection tombstones, "values never live on events":** unchanged from v1 in full. Not repeated here.

### A.3 What the server holds, and for how long

| Artifact | Where | Lifetime |
|---|---|---|
| `interactions[]` + per-interaction `record_type`/`printed_type` | ingest result blob | until F-NEW-MJ GC (fetch-ack + grace) |
| `registrySections[]` (§A.1a) | ingest result blob | until F-NEW-MJ GC (fetch-ack + grace) — same shape-delta class as `interactions[]` |
| Event digests (forward assignment, §D) | request-scoped in the DO | never persisted; discarded at response |
| Events, memberships, tombstones | — | never server-side |

F-NEW-MJ's "design GC once against the post-MF shape" note is satisfied identically to v1: the blob shape gains `interactions[]`, `registrySections[]`, and per-interaction classification fields; nothing else changes about the blob's lifecycle.

### A.4 Comorbidity chains (complaint → complaint)

Unchanged from v1 — shape reserved, empty, deferred. Not repeated here.

---

## B. Interaction indexing — registry-first hierarchy

**Supersedes v1 §B in full.** v1 designed interaction boundaries as a universal deterministic date-clustering pass over `dateAtom`/provider/section signals, primary for every document. The 2026-07-25 evidence showed that when a compilation carries its own encounter-list registry, the source document already prints an authoritative interaction index — 39 rows, 2017–2026 — and that re-deriving boundaries from date clustering would, at best, reproduce a lossier copy of what the document already asserts, and at worst (the live experiment) invents an encounter the source never states, to give orphan results somewhere to live. Registry presence now gates which of three tiers runs. Deterministic date clustering is **retired as the primary mechanism** and survives as salvage: it is Tier 3's fallback splitter, and its signal table (§B.4) still informs Tier 2's attachment judgment.

### B.1 Tier 1 — registry-as-index (registry present)

**When an encounter-list registry is present, it *is* the interaction index.** One interaction per printed row — date, type, department, provider, exactly as printed — minted deterministically, no Bedrock call, no confirmation. This is v1's doctrine line applied more literally than v1's own mechanism achieved it: the document is stating the boundary, not a heuristic re-deriving one from date proximity.

**Detection.** Scoped to the `encounterList` registry kind only — the one kind whose structure is stable enough to detect deterministically: a table with Date + Type-or-Department-shaped columns (confirmed against the artifact's page-2 table: `Date | Type | Department | Care Team | Description`), located via column-header pattern match with heading-text corroboration when present (§A.1a — heading text alone is not reliable enough in real OCR output). The other nine registry kinds are **not** attempted deterministically; they are Tier 2's job (§B.2).

**Detector on probation (ruled Q10, 2026-07-26).** The detector is deterministic classification over LlamaParse's structured output — parsed tables with typed columns — **not** free-text regex. Even so, deterministic-seam brittleness is a named risk: the owner's prior experience with deterministic identification (regex PHI identification, retired in favor of AI Pass 0 after missing real-world variation) is the precedent. The detector's survival is decided by its Phase 1a audit against real documents (§H.2); the promotion path if it proves brittle is Tier 2's model-based registry identification taking over detection. Either way, the standing safety net is Tier 2's independent registry identification plus §B.6's flag-and-repass.

**Minting.** For each row: mint an `Interaction` with `origin = registryIndex`, `registry_entry_id` pointing at the row's `RegistryEntry`, `anchor_date`/`printed_type`/provider text copied verbatim from the row's fields, `is_index_only = true`, `attached_section_ids = []`. **Same-day, same-type rows mint separately** — the artifact proves this is correct, not a bug to collapse: page 6 prints two `Hospital Encounter` rows for 04/30/2018, one 3:06–3:59 PM and one 4:00–11:59 PM, and the model in the live experiment matched this exactly when it read the encounter list. Tier 1 doesn't need to "match" it — it mints both rows because the registry prints both rows.

**Index-only rendering** is specified once, at §A.1, and applies uniformly regardless of tier.

**On this artifact:** 39 interactions minted at Tier 1, all `is_index_only = true`, before Tier 2 ever runs.

### B.2 Tier 2 — single Bedrock call: attach + identify

One Bedrock call per document, over a manifest of all sections (id, kind, page, brief excerpt, `containedLineRanges`) plus the Tier 1 interaction list (id, printed date/type/department/provider). Two jobs in one call, matching the live experiment's two outputs beyond raw interaction proposal:

1. **Attach** orphan body sections to the Tier 1-minted interactions they document.
2. **Identify** the other nine `registry_kind`s (§A.1a) — which sections constitute the Medications table, the Visit Diagnoses table, the Care Teams table, and so on. (The live experiment's "10 registry sections" is read as direct evidence this is tractable in one call alongside attachment — 10 is exactly the size of the taxonomy in §A.1a.)

**Hard constraint, mechanically enforced, not merely prompted: Tier 2 may never emit an `interaction_id` absent from the Tier 1 list it was handed.** It cannot invent an interaction. Sections it cannot confidently attach to any Tier 1 interaction go to an explicit **unattributed bucket** — surfaced (not hidden, not force-attached to the nearest plausible row). This is the direct fix for the live experiment's one real failure: under this design, the three orphan CT-calcium-scan results are each already their own Tier 1 interaction (each has its own encounter-list row), so nothing needed inventing; had one genuinely lacked a registry row, it would land in the unattributed bucket, visible, rather than be given a fabricated home. **Owner addition (ruled Q7, 2026-07-26):** the unattributed bucket is an explicit, visible tag on each affected section — troubleshooting reads the bucket, not logs.

**Structured-output enforcement.** Forced JSON via the existing `requiresStructuredResponse` path (same posture as §C.3's tokenized call) — no free-text preamble is parsed. Output shape:

```json
{
  "attachments": [ { "section_id": "...", "interaction_id": "...", "confidence": 0.0 } ],
  "registry_sections": [ { "registry_kind": "medications", "section_ids": ["..."], "confidence": 0.0 } ],
  "unattributed_section_ids": [ "..." ]
}
```

**Echo-validation.** Every `section_id`/`interaction_id` the model returns must exact-string-match an id from the manifest/Tier-1 list it was handed. This is the direct fix for the live experiment's other real failure — a dropped hyphen corrupting a section id. **Ruled (Q7, 2026-07-26): reject-and-bucket, not fuzzy-repair.** An id that fails to resolve is dropped from its claim and the section falls to `unattributed_section_ids`. Alternative rejected: string-distance repair ("looks like it meant `abc-123`") — repairing a corrupted id is itself a guess, and the whole point of the unattributed bucket is that this design never guesses where it can instead say "unknown."

**Overlap resolution.** Mechanical validation checks `registry_sections` claims for pairwise `section_id` overlap. This is the direct fix for the live experiment's registry-boundary overlap (immunization/social-history both claiming the same 4 sections). **Ruled (Q7, 2026-07-26): symmetric rejection**, not a tie-break — no overlap arbitration. Any section claimed by two `registry_kind`s is stripped from both claims and logged to a `registry_overlap` list surfaced for owner audit. Alternative rejected: a heuristic tie-break (e.g., "first-claimed wins") — a tie-break invents certainty the model didn't have; the experiment's own overlap is between two genuinely adjacent, plausible registries, and silently arbitrating that would hide real model uncertainty from the one person positioned to resolve it by reading the page.

**Self-correction as evidence, not just anecdote.** The experiment's mid-response self-correction — the model itself flagging that structured output should be enforced — is read as validating, not merely suggesting, the `requiresStructuredResponse` design above, in the same way the echo-validation and overlap fixes above are read as direct responses to specific observed failures rather than general hardening.

**Failure posture.** Malformed JSON, timeout, or a response that violates the interaction-invention constraint: discarded wholesale (fail closed). The document falls back to Tier 1-only — every interaction still renders (index-only), nothing partial. Retriable at next natural trigger, same posture as §C.5.

**Cost, and the real deviation from v1.** v1's splitter cost 0 Bedrock calls. Tier 2 costs one real Bedrock call per document (~18k in / 8k out / ~100s on this artifact) — this is new spend and new latency in the ingest envelope, and the design should not paper over it. Set against this artifact's existing OCR+atom-pass wall clock of ~4 minutes (`wall_clock_ms: 241300`), one added ~100s call is proportionally real but not disqualifying. See §B.5 for placement and §H for the phasing consequence.

### B.3 Tier 3 — no-registry fallback (the common one-off case)

When no `encounterList` registry is detected, the whole document defaults to **one interaction**, identical to today's whole-document behavior and to v1's original fallback rule (v1 §B.3 step 5). This is the overwhelmingly common case — a single lab PDF, a single imaging report — and it is unchanged from v1's design in outcome.

**Split proposal.** The same Bedrock call class as §B.2 (or a variant prompt — implementation shape) may propose that the one-off document actually contains more than one touchpoint (e.g., a combined lab+imaging PDF with no summarizing registry). **This proposal is Layer 3 territory and requires the keystone confirmation** — see §0's supersession note for why: nothing on the page asserts the split the way a registry row does, so it is model inference indistinguishable in kind from event-grouping. It reuses §C.3/§C.4's machinery verbatim (schema, 0.7 floor, one-per-session throttle) applied to a splitter's proposal instead of a clusterer's. Until confirmed, the document renders as the ungated default: one interaction, whole-document span, `origin = tier3WholeDocument`. On confirmation, the members promote to `origin = tier3SplitProposal` with page-range-derived spans.

### B.4 Salvaged signals and hazards (from v1 §B.1–B.2, still true)

v1's date-clustering signal table and hazards remain accurate observations about the artifact; they no longer run as a universal primary pass, but they are exactly the material Tier 2's attachment judgment and Tier 3's fallback splitter need.

| Signal | Ground-truth evidence | Use in v2 |
|---|---|---|
| `dateAtom.date_role` | 48 atoms; roles report(27), study(12), narrativeReference(6), collection(2), service(1) | Tier 2 attachment-confidence input; Tier 3 anchor selection |
| dateAtom page position | dates cluster tightly by page | Tier 3 anchoring; Tier 2 corroboration |
| provider atoms + page | 12 providers, page-scoped | attachment/anchor corroboration, not a boundary alone |
| section adjacency / page order | 187 sections in reading order | Tier 3 span construction |
| organization atom | 1 (`facility`, p29) | facility attribution |
| `kind=encounter` atom | 1, low-confidence, AI-emitted | still excluded — not deterministic, not reliable at n=1 |

**Hazards, unchanged and still load-bearing for Tier 2/3:**

1. **`study` dates reference comparison priors** — a Nov 2025 report can carry a `study`-role date of 4/30/2018 referencing a prior. Tier 2 must not let a `study`-role date pull a section toward the wrong registry interaction; `study` corroborates, never anchors. This is precisely the signal that would have prevented the live experiment's invented-encounter failure had Tier 1 not already existed — the CT-calcium-scan sections' `study` dates reference the same imaging history the invented "cardiology visit" was meant to explain.
2. **`narrativeReference` dates are historical prose** — excluded outright from anchoring, same as v1.
3. **Multiple same-page roles disagree; role priority is clinical-first** (`collection > service > visit > admission/discharge > report`, `report` last) — unchanged, still governs Tier 3's anchor selection and Tier 2's attachment-confidence weighting.

**Same-touchpoint window — ruled (Q1, 2026-07-26): 1 calendar day**, unchanged from v1's value, scoped to Tier 2's attachment-confidence heuristic and Tier 3's fallback splitter only. Tier 1 needs no window — the registry's own rows are the boundary (§B.1's same-day double-row mint proves window logic has no role there).

**Body-part ruling: unchanged from v1, deferred, filed as a follow-up F-item.** Nothing in v2 improves same-day multi-study disambiguation; it remains out of scope for the same reason v1 gave (real Atom Pass surface, doubles this track).

### B.5 Where each tier runs; ordering guarantee

Server-side, inside `IngestDO.assemble()`, same class as `buildSectionsFromCodex` for the deterministic parts. Strict order, because Tier 2 depends on Tier 1's output and §E depends on both:

1. **Tier 1** (deterministic `encounterList` parse) mints the interaction index, or is skipped if no registry is found.
2. **Tier 2** (single Bedrock call) runs iff Tier 1 minted ≥1 interaction — attaches sections, identifies the other nine registry kinds. Skipped (not attempted) when Tier 1 found no registry; that document falls straight to Tier 3.
3. **Tier 3** (salvaged deterministic splitter, §B.3) runs iff Tier 1 found no registry — produces the one-off default and, on confirmation, the split.
4. **§E's per-interaction `runRecordSummary`** runs last, over whichever interactions ended up body-documented (Tier 1+2's attached interactions, or Tier 3's document/split spans).

### B.6 Detector miss → flag-and-repass (ruled Q9, 2026-07-26)

Supersedes v2's open-question-9 recommendation (log for pattern-tuning and simply proceed) — the ruling keeps the proceed half and adds a bounded repair loop:

- **The ingest completes as-is, never rewinds mid-flight.** If Tier 2's registry identification independently flags an `encounterList` that Tier 1's deterministic detector missed, this ingest's result stands — the ordering guarantee above is never broken retroactively, and Tier 2 still never mints interactions.
- **The miss becomes a flag** carrying the triggering section references, and the record queues for a re-pass through the existing repair path — extending the standing repair-before-new-records pattern from failed jobs to under-structured successes.
- **Re-passes are capped at 2 revolutions** (the ruled X; nothing in this design surfaced a reason for 3). A record hitting the cap parks in a terminal needs-review state with its full flag history visible — bounded attempts, honest parking, the same philosophy as Q7's bucket.
- **Two caps, two axes — stated explicitly:** Q3's per-job call ceiling (§E) bounds *within-job* calls; this cap bounds *across-pass* revolutions. They are independent, and both terminate in a flagged, visible state rather than degraded output.

**Ruled (Q8, 2026-07-26): Tier 2 blocks ingest completion** (does not run async / fire-and-forget with a later patch). Alternative rejected: ship Tier 1's index-only result immediately, patch in Tier 2's attachments as a background follow-up — that introduces a self-revising result blob after client fetch, exactly the "blob shape self-revises after GC-eligible fetch" problem v1 explicitly avoided in §B.5's own reasoning, and the added latency (~100s against an existing ~4-minute wall clock on this artifact) doesn't clear the bar for that complexity. **Owner additions:** a user-facing "this is a large record and may take longer" message, keyed to upload-time size signals, ships with the phase that adds the latency (Phase 1b, §H.2); future latency optimization is permitted, but never via result rewriting — no post-fetch self-revision, ever.

---

## C. Keystone-question flow

### C.1 Where each stage runs

| Stage | Where | Why |
|---|---|---|
| Tier 1 registry index | server (ingest DO), deterministic | §B.1 |
| Tier 2 attach + registry-identify | server (ingest DO), one Bedrock call | §B.2 |
| Tier 3 fallback split / whole-document | server (ingest DO), salvaged deterministic + Bedrock proposal | §B.3 |
| Event candidate clustering (device affinity) | device, deterministic | §C.2 — cross-record corpus exists only on device |
| Registry-seeded complaint candidates | device, deterministic seed | §C.2b — new in v2 |
| Coherence verification + question phrasing (events, and Tier 3 splits) | one Bedrock call via the **tokenized path** | ruled in F-NEW-MF scope; chat-class Layer 3 call |
| Confirmation UI | device, root-attached modal FIFO host | system-initiated modal per the coexistence rule |

### C.2 Device-side candidate clustering (deterministic) — unchanged from v1

Runs after ingest completes and Layer 2 rebuilds. Groups interactions by affinity (date proximity, shared providers, shared facility, record-category kinship); emits candidate clusters with a cohesion score; sub-floor or single-member clusters are dropped before Bedrock ever sees them. Not repeated in full here — see v1's reasoning (git history), unchanged.

**One addition in v2:** Tier 1 index-only interactions participate in this clustering on equal footing with body-documented ones. Their date/provider/department fields are printed facts, arguably a cleaner affinity signal than anything derived, since there's no extraction step between them and the source.

### C.2b Registry-seeded complaint candidates (new in v2)

A second, independent source of Event candidates, alongside §C.2's affinity clustering — grounded directly in the document's own diagnosis and problem registries rather than derived from interaction metadata.

- **Visit Diagnoses seeding.** Each `VisitDiagnoses` `RegistryEntry` prints a diagnosis phrase and a date (e.g., "Left shoulder pain, unspecified chronicity — 4/18/2018"). Where that date matches a Tier 1 interaction's `anchor_date`, it seeds a `diagnosis-anchored` candidate edge between the printed phrase and that interaction — a deterministic date-equality join over two already-printed facts, not an inference.
- **Recurring-diagnosis seeding.** The same diagnosis phrase recurring across multiple dates (the artifact's "Internal derangement of left shoulder" chain across 12/2/2025, 12/30/2025, and 7/2/2026, or the 2018 "Left shoulder pain" chain) seeds a **multi-interaction** complaint candidate spanning all the dates it recurs on — this is the printed evidence a confirmed Event is meant to represent (§A.2), and it is the strongest candidate signal available because it is document-asserted, not affinity-derived.
- **Active Problems seeding.** Entries on the Active Problems list seed *standing* candidate complaints independent of any single interaction — a complaint that predates the current document and should keep absorbing future interactions. This is the natural device-side counterpart to forward assignment (§D): a standing complaint exists to match against before any Event has multiple confirmed members.
- **What renders without confirmation, what doesn't.** The printed diagnosis text and its date/interaction linkage render immediately, same as any Tier 1 fact — no confirmation needed, it's source-asserted. **Grouping those interactions into a confirmed Event still requires the keystone question**, unchanged from v1's doctrine line (§0). Registry seeding changes *where candidates come from*; it does not change *who confirms grouping*.
- **Feeds §C.3.** Registry-seeded candidates enter the same Bedrock coherence call as device-affinity clusters, tagged `seed_source: registryDiagnosis | registryProblemList`, with `proposed_title` **pre-filled from the printed diagnosis phrase** rather than model-composed when seeded this way — copying a printed phrase carries less hallucination surface than composing one.

### C.3 The single Bedrock call

Unchanged in shape from v1, extended with the seed-source tag from §C.2b:

```json
{ "clusters": [ { "cluster_ref": "...", "seed_source": "deviceAffinity",
                  "coherent": true, "confidence": 0.0,
                  "proposed_title": "...", "question": "..." } ] }
```

The model verifies the candidate makes clinical sense as one course of care and phrases the question; for `registryDiagnosis`/`registryProblemList` seeds, `proposed_title` arrives pre-filled and the model's job narrows to coherence-check + question phrasing only. It may not add or remove members in either case — a response proposing membership edits is `coherent: false` (fail-closed), unchanged from v1.

### C.4 Question UX and thresholds — ruled

Phrasing, actions (Group/No/Not now), the 0.7 confidence floor, the one-question-per-session throttle, and the tombstone semantics are unchanged from v1 and now **ruled (Q2, 2026-07-26)** for everything the floor governs: event/complaint grouping and Tier 3 split proposals (§B.3). The 0.7 value is an explicit starting dial, expected to tune against real use — not a derived constant. Phrasing may differ by `seed_source` — a registry-seeded question can cite the source directly ("Your visit-diagnoses list shows 'Internal derangement of left shoulder' on three dates — group these?") rather than describing derived affinity — but this is copy, not a mechanism change.

### C.5 Failure posture — unchanged from v1, now shared with §B.2/§B.3

Bedrock failure or malformed JSON: discard, retry at next natural trigger. Never a visible error. This posture is now shared by three call sites (event coherence, Tier 2 attachment, Tier 3 split proposal) rather than one.

### C.6 Membership granularity (ruled 2026-07-26, the Q4 addendum)

Complaint membership edges exist at **every granularity** — document, interaction, section, and individual atom (§A.2's `target_kind`). A complaint's citation list can therefore reference a single lab value inside a panel whose panel-level membership belongs elsewhere — the owner's example: one lipid line speaking to a blood-pressure complaint out of a general-screening panel. Confirmation doctrine is unchanged by granularity: whatever the level, a membership edge is a Layer 3 proposal until keystone-confirmed, and §G's citation chain resolves each edge at its own level (an atom-level edge cites that atom's source region directly).

---

## D. Forward assignment

Unchanged from v1 in mechanism (§D.1–D.4: event digests on `/start`, server-side deterministic matcher, `membership_proposals` on the result blob, additive compat). Not repeated in full here.

**One bridging note, v2:** §C.2b's *standing* candidate complaints (seeded from Active Problems, independent of any single interaction) are the natural device-side counterpart to forward assignment's server-side digest matching — both exist to let a new interaction find its complaint without waiting for a fresh keystone round. They are separate mechanisms (one server-side/digest-based, one device-side/registry-seeded) and neither supersedes the other; no change to §D's design is needed to accommodate this.

---

## E. record_type rescoping

**Today:** unchanged framing from v1 — one `runRecordSummary` call per document, one `record_type` stamped over documents that are actually multi-encounter.

**Design, revised for v2's interaction counts.** The splitter (now: §B's three tiers) runs first; `runRecordSummary` runs once per **body-documented** interaction only — index-only interactions (§A.1) get no classification call, because there is nothing to classify; they render `printed_type` instead. This distinction matters more in v2 than it would have in v1: Tier 1 can mint up to the full registry row count (39 on this artifact) where v1's estimate was ~7–9 total interactions. Scoping the call to attached interactions only keeps the call count anchored to what's actually documented in the body — on this artifact, that's the same handful (~8–9) the owner's grading found body-documented, regardless of how many index-only rows exist alongside them. Per-interaction `summary_bullets` only is **ruled (Q5, 2026-07-26)** — there is no document-level bullet list; index-only interactions simply have none, same as any not-yet-attached interaction.

Each call returns that interaction's `record_type` + `summary_bullets`, stored on the interaction. The document-level `record_type` remains in the result for wire compat, computed as the type of the *primary* interaction — **ruled (Q4, 2026-07-26): most-atoms wins for ordinary visit-shaped documents.** Index-only interactions have zero atoms by construction and structurally cannot win this comparison — the rule reliably resolves to a body-documented interaction. **Ruled exception:** registry-dominant documents — compilations whose substance *is* their registries, like the ground-truth CCD — take registry-shaped labels instead ("Care Summary", "Visit History"), because most-atoms over a registry-dominant document would elect one lab panel to speak for a 39-encounter history. Whether these labels already exist in the closed 26-value `record_type` taxonomy or need adding is checked at implementation, not assumed here.

**Cost governance — ruled (Q3, 2026-07-26): the cap is REJECTED and replaced.** Supersedes v1/v2's proposed 8-call classification cap in one line: there is **no cap** on per-interaction classification calls. Owner's rationale: a large document is a decoder for the patient's whole history; degrading its labels destroys the highest-value signal. Two protections replace the cap:

1. **Pre-processing consent gate.** When a document exceeds a size threshold, the app estimates token spend from upload-time signals — page count / file size, available before any AI runs — and asks the user: "This document is unusually large, estimated processing cost X. Proceed?" Spend is consented, never silently incurred.
2. **Runaway protection.** An absolute per-job call ceiling that hard-aborts and flags the job rather than degrading labels — a circuit breaker against pipeline bugs, not a quality dial.

This is complementary to, not duplicative of, the existing metering-gate work (app ROADMAP F-NEW-LT). Note the two-cap structure (§B.6): this ceiling bounds *within-job* calls; Q9's revolution cap bounds *across-pass* re-ingests.

**Backward compatibility.** Unchanged from v1 — absence of the sidecar ⇒ the document is one interaction, by construction; existing `record_type` stands; per-interaction types for old records arrive only via reingest (F-NEW-GO precedent, sacred rule 3).

**RecordCategory writeback:** unchanged from v1.

---

## F. VisitContext (F-NEW-MH ruling)

Unchanged from v1 in full — **Ruling: DELETE.** Nothing in the registry-first amendment touches this; the reasoning (VisitContext superseded as a signal, cohabitation with `record_type`, its one real concept surviving as Event) is orthogonal to how interactions get indexed. Timing unchanged: Phase 1's opening cleanup commit.

---

## G. Stitched-fact summaries

The Event detail page. Deterministic rendering — **no AI call in the render path.** §G.1–G.3 are unchanged from v1 in doctrine and mechanism, with one dereference-chain update and one new subsection.

### G.1 Data consumed (from §A) — dereference chain updated

`Event → members[] → Interaction (anchor_date, record_type/printed_type, provider_atom_ids, facility_atom_id, summary_bullets) → Layer 2 atoms via attached_section_ids membership (registryIndex origin, §A.1) or page containment (tier3 origins) → Layer 1 → source`. For index-only interactions, the chain terminates one hop earlier: `Interaction → RegistryEntry.source_region → source` — no atom hop, because the fact *is* the printed row, not an extraction from it. Membership edges finer than interaction-granular (§C.6, ruled 2026-07-26) enter the same chain at their own level — a section-level edge starts at the section, an atom-level edge at the atom, each citing its own source region directly. Every rendered fragment is still one dereference chain from a tappable source region, by every path.

### G.2–G.3 The rendering contract, placement — unchanged from v1

Connective-grammar-free templates, visible gap markers, no cross-record synthesis, pure Layer 3 view logic with no new persistence. Not repeated here.

### G.4 Synthesis rendering target (owner vision, 2026-07-25 — design, not implementation)

The target shape, stated by the owner: **top-level complaint/diagnosis → stitched-fact summary → enumerated list of every supporting record → citations that deep-link into the source document with the cited region highlighted.**

**What already exists, reused as-is:** atoms already carry `source_region` (confirmed throughout the ground-truth artifact — every atom above carries `citation_bounding_boxes`); the app already derives tap-to-source highlights from atom source regions today; §G.1's dereference chain already enumerates every supporting interaction/record for a given Event; §A.1a's `RegistryEntry.source_region` (new in v2) extends the same precedent one level down to index-only interactions and registry rows, closing what would otherwise be a citation gap for the ~30 of 39 encounters that exist only as registry rows. None of this needs building — it needs assembling into the view below.

**What's missing — named as design surface, not implemented here:**

1. **A complaint-level enumerated "sources" affordance.** The data to enumerate every supporting record already exists (§G.1's chain); what's missing is a view that renders it as an explicit, always-present list — not folded into narrative prose, and not silently collapsed for interactions that lack a summary or failed classification (no-partial-records doctrine applied at this new surface: an interaction with nothing to say about it still gets a row, showing that gap rather than omitting it).
2. **Multi-region citation resolution for a synthesized sentence.** Today's tap-to-source is atom-granular — one tap, one region. A stitched-fact sentence (§G.2) is a template composed over several atoms/fields at once; "the citation" for that sentence may need to resolve to several source regions, one per contributing value. This is a UX pattern to design (cycle through regions? one primary region with secondary regions reachable from the sources list in point 1?), not a data gap — every contributing value already carries its own region.

Both are scoped as Phase 3 additions (§H) once the Event detail page exists to hang them on.

**Citation resolution discipline — ruled (owner, 2026-07-26, post-lock).** (1) A citation always resolves to the finest granularity holding the membership — the single lab value, the specific note paragraph, the individual section — never the whole document when a finer-grained member exists. (2) Click-through lands focused: the source document opens scrolled to the cited region with it highlighted, not at page one. (3) Whole-document citations are reserved for the rare case where the document as a whole is the member, and are treated as a design smell otherwise. **Rationale (owner):** physicians and patients must reach focused information immediately; a 29-page care summary cited as a monolith defeats the synthesis view. This is a constraint on rendering and membership-edge resolution, not a new mechanism — it rides the existing atom-granularity membership (§C.6) and sourceRegion dereference chain (§G.1), and sharpens point 2 above: the "one tap, one region" pattern already resolves at atom grain today, and index-only interactions already terminate one hop earlier at `RegistryEntry.source_region` rather than the whole document (§G.1) — this ruling makes that behavior a named requirement rather than an incidental consequence, and rules out ever falling back to a document-level citation as a shortcut.

---

## H. Migration and phasing

### H.1 Existing device records when this ships — unchanged from v1

Sacred rule 3, no migration code. No sidecar ⇒ one implicit interaction (now specifically `origin = tier3WholeDocument`, for terminology consistency with v2's field). Per-interaction splitting/registry-indexing for old multi-encounter records: reingest only. `EventStore` starts empty everywhere; first keystone questions fire from the retroactive pass on first post-ship launch. Wipe gates extend to `registrySections.enc` alongside the existing `interactions.enc` and `events.enc`.

### H.2 Phased sprints — the v1 ship line stands through v3: **ships at Phases 1–3, unchanged.** What each phase contains changes; the shipping boundary does not.

**Phase 1 — Indexing (api repo, no UI).** Grown from v1's single-mechanism Phase 1 into three tiers; **split ruled (Q10, 2026-07-26): 1a/1b stands, detector on probation:**

- **Phase 1a — deterministic only.** VisitContext deletion (§F). Server: Tier 1 `encounterList` detection + minting (probationary detector, §B.1 — deterministic classification over LlamaParse's structured output), `RegistrySection`/`RegistryEntry` model, Tier 3 salvaged fallback splitter, `interactions[]`/`registrySections[]` on the result blob. iOS: persist both sidecars verbatim; nothing reads them yet. **Zero new Bedrock calls** — same cost profile v1 claimed for its whole Phase 1. Every interaction already renders something (index-only or whole-document) — satisfies no-partial-states on its own, which is exactly why it can ship independently of Tier 2.
- **Phase 1b — Tier 2 attachment, plus every ruled guard whose cost this phase introduces.** The single Bedrock attachment/registry-identify call (§B.2), echo-validation, overlap handling, per-interaction `runRecordSummary` scoped to body-documented interactions — uncapped per Q3 (§E). Because 1b is where real Bedrock spend and blocking latency enter the ingest envelope, the rulings' guards land here, with their cost: the pre-processing consent gate and the runaway per-job ceiling (§E), the "large record, may take longer" message keyed to upload-time size signals (§B.5), and the detector-miss flag with its 2-revolution capped re-pass loop (§B.6 — Tier 2's registry identification is what raises the flag, so the mechanism cannot land earlier). Pure quality improvement layered on 1a's already-shippable behavior contract — nothing renders differently in kind, only in completeness.

Rejected alternative: ship Tier 1+2 as one Phase 1, matching v1's structure. Rejected because it reintroduces exactly the kind of bundling v1's own phasing philosophy ("each independently shippable") argues against, now that Tier 2 is a real cost/latency line v1 didn't have.

*Audit point (both sub-phases):* reingest the ground-truth source PDF; owner verifies the 39-row Tier 1 index against the real encounter list (1a) — **this audit decides the probationary detector's survival (Q10): if it proves brittle against real documents, Tier 2's model-based registry identification takes over detection** — then verifies attachment/registry-identification accuracy and the echo-validation/overlap mechanics against the live experiment's two known failure modes (1b). Splitter and Tier 1 parser are `node --test`-covered against the captured artifact.
*Ships alone:* both — invisible, additive.

**Phase 2 — Interactions surfaced (app repo).** Unchanged in scope from v1, with index-only interactions now part of what's rendered: record detail shows the sub-document structure (interaction list: date, type, provider; index-only rows shown without a drill-in affordance, per §A.1; tap on a body-documented row scrolls the PDF to `page_range.first`; tap on an index-only row highlights the registry row via `RegistryEntry.source_region`). No events.
*Audit point:* multi-encounter record on device shows correct touchpoints including index-only rows; single-interaction (Tier 3) records render exactly as today; no partial states.
*Ships alone:* yes.

**Phase 3 — Events + keystone flow + synthesis (app repo). This closes the v1/v2 line.** `EventStore` + proposals + tombstones; device affinity clusterer (§C.2) **and** registry-seeded candidate generation (§C.2b); tokenized Bedrock verify call (now also covering Tier 3 split proposals, §B.3); keystone modal; Events surface (list + stitched-fact detail per §G, including §G.4's enumerated-sources view and multi-region citation); retroactive first-run pass; wipe gates; deletion cascade.
*Audit points:* rejected-stays-rejected on restart; low-confidence silence verified with a deliberately incoherent corpus; the shoulder recurring-diagnosis chain proposes as one candidate (§C.2b); Tier 3 split proposals correctly gate on keystone confirmation rather than auto-splitting; every stitched fact and every §G.4 source-list entry taps to source; doctrine sweep of all user-facing copy.

——— **The v1 ship line, restated at design lock: Phases 1–3.** ———

**Phase 4 (deferred) — Forward assignment.** Unchanged scope from v1. Deferred for the same reason: needs Phases 1–3 live plus accumulated events to match against.

**Phase 5 (deferred) — Body-part extraction** (§B.4). **Phase 6 (deferred) — comorbidity-edge UX** (§A.4). Both unchanged from v1. F-item IDs for all deferred phases are assigned at the next doc pass, `F-NEW-MM` onward (ruled Q6, 2026-07-26).

---

## Constraints compliance summary

- **Clinical doctrine:** groupings are proposals; keystone confirm gates every event and every membership, and now also every Tier 3 split proposal (§B.3, new in v2); low-confidence asks nothing; stitcher is connective-grammar-free; comorbidity edges require user or document assertion; a registry row's own printed fact never needs confirmation, but an interaction the *model* proposes without a registry backing it does.
- **Sacred rule 8:** proposals are Layer 3 until confirmed; confirmed events hold ids and user-authored titles only; interactions and registry entries carry classifications/verbatim reads about spans, never restated content; nothing here writes Layer 1/2.
- **Provenance:** `indexer_version` on interactions, `identified_via` on registry sections, `added_via`/`confirmed_via` on memberships, edge-style dereference for every rendered value including index-only interactions (via `RegistryEntry.source_region`); attachment is stored explicitly for registry-origin interactions (§A.1's edges supersession) rather than reconstructed by containment, because containment stopped being a valid test the moment interaction identity stopped being page-range-shaped.
- **No partial records:** Tier 1/3 fallback guarantees every interaction renders something even if Tier 2 never runs or fails; Tier 2's unattributed bucket is an explicit visible tag on affected sections, never force-attached (Q7); oversized jobs gate on user consent before spend, and the runaway ceiling hard-aborts and flags rather than shipping degraded labels (§E, Q3); capped re-passes park in a terminal needs-review state with full flag history visible (§B.6, Q9); deleted members render as visible stubs; unconfirmed proposals are invisible everywhere.

## Resolved rulings ledger

All ten open questions carried by v2 were owner-ruled 2026-07-25/26 — this is the design lock. Every ruling is folded into the body above; this ledger is the permanent record. Where a ruling contradicted a v2 proposal (Q3, Q9), the ruling won and the superseded text was rewritten in place with a one-line supersession note.

| # | Question | Ruling | Folded at | Date |
|---|---|---|---|---|
| 1 | Same-touchpoint window | **ACCEPTED** — 1 calendar day, scoped to Tier 2 attachment confidence and Tier 3's fallback splitter only | §B.4 | 2026-07-25/26 |
| 2 | Keystone confidence floor + cadence | **ACCEPTED** — 0.7 floor (an explicit starting dial, expected to tune against real use), one keystone question per session; governs event/complaint grouping and Tier 3 split proposals | §C.4, §B.3 | 2026-07-25/26 |
| 3 | Per-document classification-call cap | **REJECTED, replaced** — no cap; a large document is a decoder for the patient's whole history, and degrading its labels destroys the highest-value signal. Replaced by the pre-processing consent gate + runaway per-job ceiling (hard-abort and flag, never degraded labels); complementary to F-NEW-LT's metering gate | §E | 2026-07-25/26 |
| 4 | Primary-interaction rule for compat `record_type` | **ACCEPTED WITH EXCEPTION** — most-atoms wins for visit-shaped documents; registry-dominant documents take registry-shaped labels ("Care Summary", "Visit History"; taxonomy fit checked at implementation). Plus a new ruled requirement: complaint membership edges exist at every granularity — document, interaction, section, atom | §E, §A.2, §C.6 | 2026-07-25/26 |
| 5 | `summary_bullets` scope | **ACCEPTED** — per-interaction only; no document-level bullets | §E | 2026-07-25/26 |
| 6 | F-item IDs for deferred phases | **ACCEPTED** — filed at the next doc pass, `F-NEW-MM` onward | §H.2 | 2026-07-25/26 |
| 7 | Tier 2 corruption/overlap posture | **ACCEPTED** — reject-and-bucket; no fuzzy id repair, no overlap arbitration. Owner addition: the unattributed bucket is an explicit, visible tag on affected sections — troubleshooting reads the bucket, not logs | §B.2 | 2026-07-25/26 |
| 8 | Tier 2 blocking vs. async | **ACCEPTED** — Tier 2 blocks ingest completion; no post-fetch self-revision, ever. Owner addition: a user-facing "large record, may take longer" message keyed to upload-time size signals ships with the phase that adds the latency; future optimization permitted but never via result rewriting | §B.5, §H.2 | 2026-07-25/26 |
| 9 | Tier 1 detector miss / Tier 2 disagreement | **ACCEPTED WITH AMENDMENT** — ingest completes as-is, never rewinds mid-flight; the miss becomes a flag carrying the triggering section references and the record queues for a re-pass through the existing repair path. Amendment: re-passes capped at 2 revolutions; a record hitting the cap parks in a terminal needs-review state with full flag history visible. Two-cap structure: Q3's ceiling bounds within-job calls, this cap bounds across-pass revolutions | §B.6 | 2026-07-25/26 |
| 10 | Phase 1a/1b split | **ACCEPTED, DETECTOR ON PROBATION** — the split stands. The Tier 1 detector is deterministic classification over LlamaParse's structured output (parsed tables with typed columns), not free-text regex, but deterministic-seam brittleness is a named risk (precedent: regex PHI identification retired for AI Pass 0). Phase 1a's audit against real documents decides its survival; the promotion path if brittle is Tier 2's model-based registry identification taking over detection | §B.1, §H.2 | 2026-07-25/26 |
