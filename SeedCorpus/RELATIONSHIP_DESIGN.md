# Relationship Design

Status: design v1.1 (shape, not spec), owner rulings applied, phone-side inventory folded, nothing shipped
Date: 2026-09-05 (v1.0 same day; v1.1 supersedes it in place after the phone-side inventory R1a)
Repo home: `RecordHealth.IO/SeedCorpus/RELATIONSHIP_DESIGN.md`

Owns the relationship model for Record Health: how a relationship between two things is recorded, declared, authored, inferred, graded, indexed, and exported. One home for the definition; every other doc points here and restates nothing. Supersedes the edge mechanics in `RecordHealth_App/docs/DATA_MODEL.md` §3.3.1 (AtomEdge becomes a display projection, §8), the relationships list in `PACKAGE_DESIGN.md` §6, the edge addressing sentence in `ADI_GRADING_DESIGN.md` §3, and the link-authoring proposal audited 2026-09-05 (F-NEW-RM). `EVENTS_INTERACTIONS_DESIGN.md` keeps the semantics of events and keystone confirmation; its membership edges register here (§3). Grounded in two inventories of 2026-09-05: Worker side (43 sites, 13 test pins, 7 doc statements, no two of which agreed on shape; recordhealth-api SESSION_LOG 2026-09-05) and phone side (R1a: 92 production lines across 11 files, 19 pinning tests, 24 doc statements of which 6 are stale, and eleven relationship shapes beside AtomEdge; RecordHealth_App SESSION_LOG 2026-09-05; the disposition of each shape is §8.1).

**Owner rulings, fixed points (2026-09-05):**

- RL-1. A relationship is its own object, never a field on either participant. It names a source, a kind, a target, and who asserted it. This replaces child-pointer edges (`atom_edges` on the atom) and is chosen over FHIR's container-list serialization; both are one party's serialization of a two-party fact, and storing a two-party fact on one party is what produced the drift.
- RL-2. One declared vocabulary, the registry (§2). A kind that is not in the registry does not exist. Emitters can only emit registered kinds; the census reads its closed list from the registry; the published schema is generated from it; the console builds its controls from the published schema; the phone decodes against the published schema and refuses unknown kinds loudly; a test fails the build when any emitter produces an unregistered kind.
- RL-3. Two homes, one shape. A relationship between two things inside one document lives in that document's package (core or amendment log). A relationship that crosses documents, or joins a document to a person, an interaction, or an event, lives in the patient-level relationship store on the phone. The registry declares which home each kind is allowed. A cross-document relationship never enters a package.
- RL-4. Asserted and inferred are distinct statuses of the same entry. AI never asserts a relationship. It may infer one, with a confidence score and the evidence it rests on, and no consumer treats an inferred relationship as fact. A keystone question is not a relationship; the user's confirmation is. This restates the app's sacred rule 8 with the inference case named.
- RL-5. Inferences are a derived layer. Assertions are source of truth; inferences are recomputed from assertions and atoms and are never the only record of anything. An inference that cannot be regenerated or re-derived from stored evidence has become a fact nobody asserted, and that is forbidden.
- RL-6. People are entities, names are atoms. A name on a page is a PHI atom in a package. A person is a patient-level entity with aliases. "Which one is the provider" is a role relationship between a person and a document or interaction, per document, never a property of the name. People and roles never leave the phone.
- RL-7. Endpoints need ids that mean the same thing in every package and at every rebuild. Sections do not have that today (minted per rebuild, addressed by ordinal). Stable section identity is a precondition for any cross-package relationship touching a section and for any export (§10, open ruling on mechanism).
- RL-8. FHIR is the door, not the model. Export reproduces FHIR's container lists by a filter over the list by kind and a direction flip declared per kind in the registry. Import walks FHIR's lists and writes relationship entries. Asserted relationships export; inferred ones do not unless a kind's registry entry says otherwise.
- RL-9. Timing. This lands before ADI console step 3 (the first console code that reads edges) and while both ADI databases hold no relationship rows. Zero migration, zero scaffolding; that window closes when the console learns the old shape.
- RL-10. One relationship model on the phone. The care graph is absorbed: its edge kinds register, its edges become entries in the patient store, its own store retires, and its traversal reads the relationship index. Every other relationship shape the phone carries today (§8.1) is either registered as a kind or retired; none survives as a parallel definition. Ruled 2026-09-05 (absorb over derive).
- RL-11. An entry's id is minted once, by its author, at the moment it is first stored, and persisted. Decode never mints. Today AtomEdge.id is a fresh uuid at every decode and every rebuild, so no edge on the device has an identity; that ends at R3.
- RL-12. FHIR ingest writes relationship entries. A lab panel that arrives as a FHIR bundle and a lab panel extracted from a PDF are one object inside the app: same kinds, same store, same index. Today FHIR ingest reads no relationship at all (hasMember, DiagnosticReport.result, Composition sections unread; encounter kept as a raw id string); that is R4.

---

## 0. Framing: the logic problem

A relationship is a fact with three parts: this thing, is related in this way, to that thing. Every prior shape in this codebase wrote the fact on one of the two things. The pipeline wrote it on the child (a lab row carries `belongs_to_panel`), because the child was in hand when the fact was discovered. FHIR writes it on the parent (`Observation.hasMember`, `Composition.section.entry`), because a lab system composes the panel first. Both store a two-party fact as a property of one party, and three consequences follow with no way around them: the fact can only exist if its host exists, so a relationship between two non-atoms has nowhere to live; the host's cardinality limits the fact, so one result in two panels cannot be said; and every consumer must know which host to look on, which is why the ADI console read the same field two opposite ways.

The 2026-09-05 inventory is the evidence. The address edge mints an id nothing reads. One emitter lowercases its target, the other does not. The ADI column the console reads is NULL on every row because the package projection stopped writing it, so every grouping feature has been dark since sprint 6. The server's edge-kind list has two members, the phone's has five, and the server's census is closed, so a phone date edge in a package would census as drift. The server declares edge authors it cannot produce. The amendment route accepts an edge as a target with no rule for naming one. None of this was carelessness. It was the shape.

The correction is to store the fact as its own object (RL-1), declare the vocabulary once (RL-2), and derive or test every dependent from it. Values got this discipline with the vocabulary dictionary, fields got it with the schema layer; relationships are the third leg.

---

## 1. The relationship entry

```
Relationship (illustrative, not wire)
id             : uuid, lowercase, minted by the author at creation
kind           : registry kind (§2)
source         : { entity, id }
target         : { entity, id }
status         : asserted | inferred
author         : pipeline | walker | reviewer | user | system
authored_at
confirmed_via  : keystone | forwardAssignment | reviewer_console    (asserted only, when a person confirmed)
confidence     : 0..1                                                (inferred only, required)
evidence       : [ { entity, id } ]                                  (inferred only, required, non-empty)
inferred_by    : { engine, version }                                 (inferred only, required)
supersedes     : relationship id                                     (optional; §4)
```

Endpoints are addressed by the identity rules in `ADI_GRADING_DESIGN.md` §3 (atom by id; section by stable id once §10 lands, ordinal until then; table row by `table_id:row_index`; cell by `table_cell_ref`; person and interaction by their patient-level ids). An entry stores ids, never values (the value lives only on the endpoint; unchanged from the prior edge rule).

Uniqueness: at most one live asserted entry per (kind, source, target). The id is the identity of the entry; the triple is the identity of the fact. Two asserted entries for one triple is a refusal at every door. Any number of inferred entries may exist for one triple across time; the fold shows the newest (§4).

Where the list sits:

- In the ingest result (the package core): a top-level `relationships` array beside `atoms` and `sections`, emitted by the Worker. `atom_edges` on the atom retires from the wire.
- In the amendment log: reviewer entries as `op: add, target.entity: relationship`, value = the entry; withdrawal as `op: remove` on the entry id; verdicts on a pipeline entry target the entry id. Shape per `PACKAGE_DESIGN.md` §3.
- On the phone, patient level: the relationship store (§3), append-only, encrypted like every sidecar, holding user, keystone, system, and inferred entries whose kinds are declared patient-home.

---

## 2. The registry

The single declared vocabulary of relationship kinds. Lives in the Worker as a declaration the schema generator reads (`recordhealth-api/src/result-schema.mjs`, beside ENTITIES), published on `GET /v1/schema` as a top-level `relationships` key, versioned with `SCHEMA_VERSION`. Hand-kept lists anywhere else (`EDGE_KINDS` in ingest-vocab, the console's grouping code, the phone's `EdgeKind` enum as a closed set) retire or become generated from it.

One registry entry:

```
kind             : string, snake_case, the wire value
source           : [entity]           allowed source entities
target           : [entity]           allowed target entities
cardinality      : one | many          live asserted targets per (source, kind)
home             : package | patient   where an entry of this kind may live (RL-3)
emitted_by       : pipeline | walker | null
authoring        : [reviewer | user]   who may assert one through a log or store write
inferable        : bool                whether the inference engine may propose one
confirm_at       : 0..1 | null         confidence at which a keystone question fires (inferable only)
consumer_policy  : asserted_only | show_inferred_labeled   what a summary, query, or export may use
adi_visible      : bool                whether entries of this kind may travel to the ADI (people roles: false)
fhir             : { element, direction: same | inverse | flatten } | null   (§9)
since            : schema version
doc              : one line
```

Initial registry (v1). Kinds the pipeline emits today, registered as they are; kinds other designs already define, registered so they stop being private mechanisms; kinds this design introduces, marked.

| kind | source → target | card. | home | emitted_by | authoring | inferable | fhir | note |
|---|---|---|---|---|---|---|---|---|
| belongs_to_panel | atom_extract → atom_extract | one | package | pipeline | reviewer | no | Observation.hasMember, inverse | today's edge |
| belongs_to_address | atom_extract → atom_extract | one | package | pipeline | reviewer | no | Patient.address, flatten | today's edge |
| member_of_section | atom_narrative, atom_extract → section | one | package | pipeline (as `section_id` today; becomes an entry) | reviewer | no | Composition.section.entry, inverse | §5 of ADI_GRADING already lists it as a class |
| collected_at | atom → atom (date) | one | patient (walker, Layer 2) | walker | none | no | Observation.effectiveDateTime, same | phone date edge, unchanged |
| reported_at | atom → atom (date) | one | patient | walker | none | no | DiagnosticReport.issued, same | phone date edge |
| observed_at | atom → atom (date) | one | patient | walker | none | no | Observation.effectiveDateTime, same | phone date edge |
| same_clinical_event | atom → atom | many | patient | walker | user | yes | null | phone, existing |
| member_of_event | document, interaction, section, atom → event | many | patient | null | user (keystone) | yes | null | EVENTS_INTERACTIONS §A.2 EventMembership; granularity is the source entity |
| part_of_interaction | document → interaction | one | patient | null | user (keystone) | yes | Encounter, same | new: the fragmented-report case (§4) |
| continues | document → document | one | patient | null | user | yes | DocumentReference.relatesTo, same | new: a report that extends another |
| has_role | person → document, interaction | many | patient | null | user (keystone) | yes | PractitionerRole / Observation.performer / ServiceRequest.requester by role | new, §6; role value on the entry |
| affiliated_with | person → organization | many | patient | null (today: id lists on ProviderEntity / OrgEntity) | user | yes | PractitionerRole.organization, same | absorbs the entity id lists, §8.1 |
| section_references | section → section | many | package | pipeline (today: SectionRef on the parent, open string kinds) | reviewer | no | per sub-kind | absorbs SectionRef; its sub-kinds (requester, basedOn, performer, subject, encounter) become registered kinds at R2, one row each |
| (care graph kinds) | per CareGraphEdgeKind | per kind | patient | walker (CareGraphBuilder) | none | yes (carries confidence today) | per kind | the 16 CareGraphEdgeKind cases register under their existing names at R5 (RL-10); rows generated then, not hand-listed here |
| row_in_table | table_row → table | one | package | null until sprint 10 (today: TableCellRef composite key, which is what actually groups lab rows) | reviewer | no | null | sprint 10 |
| table_in_section | table → section | one | package | null until sprint 10 | reviewer | no | null | sprint 10 |
| section_in_section | section → section | one | package | pipeline (as `parentId` today) | reviewer | no | Composition.section.section, inverse | sprint 10 makes it an entry |

`inferable`, `confirm_at`, `consumer_policy`, and `adi_visible` per kind are proposed values pending the inference sprint's own design; the columns are ruled, the numbers are not.

Registry discipline, mechanical, not advisory: the registry is the source the generator reads; the emitters import their kind constants from it; the census reads its closed list from it; a coverage test asserts every emitted kind is reached by the rich fixture and every registered `emitted_by: pipeline` kind is actually emitted; the console reads the published registry and holds no kind list (grep-pinned); the phone decodes the published registry and treats an unregistered kind as a loud drop, never a silent one. When the registry changes, `SCHEMA_VERSION` bumps, and per PACKAGE_DESIGN OR-2 (ruled 2026-09-05, schema snapshot per version) every package is read under the registry it was minted against.

---

## 3. Two homes, one shape (RL-3)

**Package home.** The core's `relationships` array holds what the pipeline asserted about this document. The amendment log holds what a reviewer asserted, withdrew, or judged about this document. Both are sealed under `package_hash` (R15). Nothing in a package refers to anything outside it.

**Patient home.** The phone's relationship store holds every entry whose kind is `home: patient`: walker date edges, event membership, interaction and document joins, person roles, and every inferred entry. It is append-only, device-encrypted, part of the essential CloudKit set, and exported in the `.rhpkg` archive beside the packages (the archive already carries the patient index slice; the store joins it). It never travels to the ADI (`adi_visible: false` kinds) except where a kind explicitly allows it.

`EVENTS_INTERACTIONS_DESIGN.md` §A.2's `EventMembership` and §A.4's `EventEdge` are entries in this store under `member_of_event` and a future `related_to_event`; their confirmation flow, tombstones, and "values never live on events" rule are unchanged and stay in that doc. This doc owns the entry shape and the registry; that doc owns what an event is.

---

## 4. Asserted and inferred (RL-4, RL-5)

**Asserted** entries come from an author with standing: the pipeline deterministically (a row under its header), the walker deterministically (a date next to a result), a reviewer through the console, or the user confirming a keystone question. They have no confidence field; they are true until superseded.

**Inferred** entries come from the inference engine, a derived layer on the phone that reads atoms, codes, dates, and asserted relationships, and proposes relationships the pipeline could not see because the evidence spans documents. Each carries `confidence`, non-empty `evidence`, and `inferred_by`. Consumers read `status`: a summary, a query, an export, or a keystone prompt uses an inferred entry only as its kind's `consumer_policy` allows, and shows it as inferred when it shows it at all.

**Lifecycle.** The worked case: document one is a lab sheet with hemoglobin, LOINC 718-7, a collection date, no visit context. The engine infers `part_of_interaction` toward a known visit at 0.4, evidence: the date atom and the visit's date. Document two arrives, a visit summary with the same date, the same provider, a line ordering a CBC. The engine reruns; a new inferred entry lands at 0.9 with `supersedes` pointing at the 0.4 entry and evidence naming document two's atoms. At the kind's `confirm_at` a keystone question fires once. The user confirms; an asserted entry lands with `author: user, confirmed_via: keystone`, and the inference's evidence is carried as its provenance. The inferred entries are superseded, not deleted; history shows the picture sharpening. A later document that contradicts the picture produces a lower-confidence entry superseding the higher one, and a keystone question if an asserted entry is now in doubt (the user, never the engine, retracts an assertion).

**Derived, precisely.** An inference produced by deterministic code is rebuildable from the store. An inference produced by a model call is not bitwise reproducible; it is stored with its evidence and engine version, and the rule that protects the doctrine is not reproducibility but standing: an inferred entry is never the only record of a fact, never exported as fact, never treated as fact by a consumer, and can be regenerated by re-running the engine over the same assertions. Wipe the inferred entries and nothing the user or a reviewer said is lost.

**Guardrail.** Inferring structure (which visit a result belongs to, which report continues which, which name is the ordering physician) is the app's job. Inferring clinical meaning is not. The registry's `inferable` column is where that boundary is written; a kind that would let the engine assert meaning does not get the flag.

---

## 5. Authors and the sacred rule

Sacred rule 8 ("AI never proposes edges") is restated for both repos' CLAUDE.md as:

> Relationships are entries in the relationship list, declared in the registry, never fields on an entity. AI never asserts a relationship. It may infer one with confidence and evidence; no consumer treats an inferred relationship as fact; a person's confirmation is what makes it asserted. `RELATIONSHIP_DESIGN.md` owns the model; point, do not restate.

Author values and what they may do: `pipeline` asserts package-home kinds deterministically at emit; `walker` asserts patient-home date and event kinds deterministically on device; `reviewer` asserts, withdraws, and judges package-home kinds through the amendment log; `user` asserts patient-home kinds by confirming a keystone or forward-assignment question, or by drawing one directly where the UI allows; `system` writes inferred entries and the reconciliation entries sprint 9 needs (token maps, imports). No author may write an asserted entry of a kind whose registry row does not list it.

---

## 6. People and roles (RL-6)

Three layers. The name atom, PHI, in the package with its token. A person entity at patient level, with the names it has been seen under as aliases, the same raw-observed-strings-with-keys-re-derived pattern `PatientProfile.confirmedAliases` uses; the patient is the first person. Role relationships: `has_role` from a person to a document or interaction, the role carried on the entry (`patient`, `treating_provider`, `ordering_provider`, `performing_technician`, `interpreting_provider`, `facility`), roles per document because one doctor orders on Tuesday and treats on Thursday.

The guessing game runs as inference with evidence. First report from a practice: two names, one under "ordered by," one in a signature block; `ordering_provider` 0.6, `performing_technician` 0.5, evidence is label position. Fifth report from the same practice, same "ordered by" name every time, never in a visit note, never in a signature: the practice's default ordering physician, non-treating, 0.9, evidence five documents and zero encounters. A name recurring in visit notes with clinical language attached climbs toward `treating_provider`. The patient's own name resolves against the profile and its aliases from document one. At `confirm_at` a keystone question fires once ("Is Dr. X one of your doctors?"); the answer is an asserted entry the engine treats as fixed evidence thereafter.

Roles that a summary may show on an inference are a registry decision per role, not a code decision: "your treating provider" on a 0.6 guess costs trust; "ordering physician" at 0.6 costs nothing. People, aliases, and roles never leave the phone (`adi_visible: false`); corpus grading has no use for who the user's doctor is and the ADI's BAA posture should not have to cover it.

---

## 7. Grading (points at ADI_GRADING_DESIGN)

A relationship is one gradeable class, `relationship`, with a per-kind breakdown in the scores (`by_kind`), because `belongs_to_panel` measures the extractor and `member_of_section` measures the Atom Pass and one merged number hides which regressed. Kinds with `emitted_by: null` report under `authored_only` and stay out of the class aggregate until something emits them.

A verdict targets the entry id (`target: { entity: relationship, id }`). A reviewer-authored entry is `op: add` and counts as a discovery for recall. Withdrawal is `op: remove` on the id. Re-homing a pipeline entry is either a `corrected` verdict on `target` or reject-then-add; both stay legal, and the uniqueness rule (§1) refuses an add while a live asserted entry of that kind exists on the source with `cardinality: one`. A verdict on a reviewer-authored entry targets the amendment id, never the entry id, so it cannot supersede the add in the fold (this hazard exists for discoveries today and is fixed in the same step). Authoring an entry the pipeline already emitted is refused (`relationship_already_in_core`); the console offers accept. The write route reads the core when a batch carries a relationship entry so endpoints can be verified; a bad endpoint in an append-only log is permanent.

Everything else (ops table, fold rule, F1 definitions, "Accept N shown") is `ADI_GRADING_DESIGN.md` §3, §4, §6, unchanged.

---

## 8. Derived layers on the phone

Three, all rebuildable, none a source of truth:

- **AtomEdge on ContextAtom** (DATA_MODEL §3.3.1) becomes a display projection: when Layer 2 rebuilds, every relationship whose source is this atom is hung on it for rendering. `SegmentedFact.atom_edges` retires; Layer 1 carries no relationships. `EdgeKind` stops being a closed Swift enum and decodes against the published registry; an unregistered kind is a loud drop.
- **The patient relationship index** unions every package's `relationships` array, each package's folded amendment log, and the patient store, and is what queries walk. It is rebuilt from those three sources, the same rule ContextStore lives under. It lives on the phone, which is what lets the anonymized AI query walk the graph locally and send tokens out.
- **The inference engine** (§4) reads the index and writes inferred entries to the patient store. Its own design is a later doc; this doc fixes its inputs, outputs, and standing.

### 8.1 Phone-side shapes and their disposition (R1a, 2026-09-05)

The inventory found eleven relationship shapes on the phone beside AtomEdge. Each is dispositioned here so none survives as an undeclared parallel definition (RL-10).

| Shape today | What it encodes | Disposition | Sprint |
|---|---|---|---|
| `SegmentedFact.sectionId` | atom → section, scalar on the child | registered as `member_of_section`; field stays as the pipeline carrier until hard question 1 is ruled | R2, R3 |
| `DocumentSection.parentId` | section → section, scalar on the child | registered as `section_in_section`; field stays as carrier | R2 |
| `SectionRef` (`references[]` on the parent, open string kinds, zero consumers) | section → section typed references | absorbed: each sub-kind registers; entries move to the core's `relationships` list; `SectionRef` retires | R2 |
| `TableCellRef` (composite key; what actually groups lab rows) | cell → row → table | stays as the containment carrier until sprint 10 registers `row_in_table` and `table_in_section`; the panel edge that duplicates it is judged for retirement at R2 (hard question 6) | sprint 10 |
| `FHIRSourcedFact.encounterId` (raw id string) | fact → encounter | becomes a `part_of_interaction` entry written by FHIR ingest; the string stays as provenance | R4 |
| `FHIRSourcedFact.pairedRecordId` + `bundleKey` | fact → record | record membership stays an index fact (below); the bundle key is a record identity, not a relationship | none |
| `PatientRecordIndex` | record ↔ patient | stays: an index, not a relationship; the patient is the root of the store | none |
| `CareGraphEdge` (16 kinds, confidence, inference provenance, own store) | condition-rooted care graph | absorbed (RL-10): kinds register, edges become inferred or asserted entries in the patient store, `.graph.enc` retires, traversal reads the index | R5 |
| `ProviderEntity.organizationIds / visitIds`, `OrgEntity.providerIds` | person ↔ org ↔ visit, id lists on the container | absorbed: `has_role`, `affiliated_with`, `part_of_interaction` entries; the lists retire | R5 |
| `RecordV2.providerName / facilityName / serviceDate / reportDate` | document → person, document → time, denormalized display strings | stay as display cache; a `has_role` or date entry is the truth once R5 lands, and the cache is rebuilt from it | R5 |
| `TreatmentTree` | condition-rooted subgraph with node annotations | rebuilt as a traversal over the index once the care graph is absorbed; its own persistence retires | R5 |

Two more findings the phone half must carry: the Worker's two edge kinds have zero consumers on the phone (lab grouping uses `TableCellRef`), and the phone's four consumed kinds are the four the Worker cannot produce; and `bestDate` answers the same question by two unrelated mechanisms depending on lineage (edge walk for documents, scalar for FHIR). R4 collapses that to one walk.

Longitudinal queries are walks over the index filtered on any entry field: kind, time (the date kinds), author, status, confidence. What the index does not give: meaning. "Hemoglobin over three years" is a match on the code carried by each atom (`kt_coding`, LOINC) across packages, then a walk to each atom's date. Relationships get from a value to its context; codes get from one document to the same thing in another. Both are needed; the registry does not replace coding.

---

## 9. FHIR mapping (RL-8)

Each registry row carries `fhir: { element, direction }`. `same` means the FHIR reference sits on the source (dates on the Observation). `inverse` means FHIR lists members on the container (`hasMember`, `section.entry`), so export gathers every entry of that kind by target and writes the list on the target's resource; import walks the list and writes one entry per member. `flatten` means FHIR has no relationship at all (Address is an embedded datatype): export folds the parts into the anchor's datatype; import splits them back into atoms plus entries. `null` means no FHIR counterpart; the kind stays internal.

Export carries asserted entries only unless a kind's `consumer_policy` allows labeled inferred entries, and no FHIR profile has a slot for "inferred," so in practice inferred never exports. Relationships are the small part of a FHIR export; atom kinds already map one-to-one to resource types (DATA_MODEL §3.4), and payloads to `Observation.value`, `kt_coding` to `CodeableConcept`, sections to `Composition`, and people to `Patient` and `Practitioner` are each their own audit. This doc makes the relationship part a table lookup and nothing more.

---

## 10. Stable identity (RL-7, open ruling)

Atoms carry server-minted uuids that survive every rebuild. Sections are minted per rebuild and addressed by ordinal, which is fine inside one package and meaningless across two, or after an export and re-import. Options for the mechanism, owner to rule at the relationship sprint's audit: (1) a content-derived section id (hash of kind, page, and line range) minted by the Worker and carried in the core, stable across rebuilds of the same parse and different across parses, which matches how LlamaParse's own non-determinism (F-NEW-RH) already bounds comparability; (2) a package-scoped ordinal promoted to a stable id by pairing it with `package_id` (`package_id:ordinal`), stable forever, but a re-ingest mints a new package and the join to the prior one is a `continues` relationship, not an id match. Tables and rows follow the same ruling.

---

## 11. Drift discipline: what makes this canon

- One doc owns the model (this one). `PACKAGE_DESIGN.md` §6, `ADI_GRADING_DESIGN.md` §3 and §5, `EVENTS_INTERACTIONS_DESIGN.md` §A.2, `DATA_MODEL.md` §3.3.1 and §7.13, `WORKER_ARCHITECTURE.md`, and `DATABASE_LAYOUT.md` point here and restate nothing. A second definition of a relationship anywhere is a bug to file, not a convention to reconcile.
- The registry is the code's source and the doc's table. §2's table is regenerated from the declaration at every sprint close (a script, not a hand edit), so the doc and the code cannot disagree.
- Every dependent is generated from or tested against the registry (§2 discipline). "Be careful" is not a mechanism; a failing test is.
- Both CLAUDE.md files carry the §5 rule and a pointer. No architecture payload in CLAUDE.md.
- New kinds are registry rows plus a version bump. A kind that needs code outside the registry, the emitter that produces it, and the UI that draws it is a design smell to explain in the rulings log before it ships.
- `data_atoms.atom_edges` is dropped in the relationship sprint's baseline; no projection row holds a relationship (GR-1: the log and the core are the homes). The three reviewer-create routes that wrote projection rows outside the log are deleted in the same sprint (ruled 2026-09-05).

---

## 12. Effect on the sprint series

Inserted before ADI console step 3 (PACKAGE_DESIGN §9 sprint 7 is paused at step 2, shipped `6800ede`):

| # | Repo | Ships | Close condition | Model |
|---|---|---|---|---|
| R1a | app | **DONE 2026-09-05.** Phone-side edge inventory, FHIR ingest included; findings folded into v1.1 (§8.1) | Done | Opus 5 |
| R1b | api | Stable identity options (§10) prepared for ruling; the section-id mechanism chosen | §10 ruled | Fable |
| R2 | api | Registry declaration (today's kinds plus `SectionRef`'s sub-kinds), generator emits `relationships`, `SCHEMA_VERSION` bump, emitters write the top-level `relationships` array and `atom_edges` retires from the wire, `SectionRef` retires into the list, census and misfire read from the registry, coverage tests, baseline drops `data_atoms.atom_edges`, the three reviewer-create routes deleted, amendment validator and scores handle `relationship` (§7) | A staging ingest serves `relationships` with every registered pipeline kind and no `atom_edges`; suite green; the console step 3 audit can begin | Opus 5, Fable reviews the registry declaration first |
| R3 | app | Decode the `relationships` array; entry ids persisted, never minted at decode (RL-11); AtomEdge becomes a projection (§8); `EdgeKind` decodes against the registry; patient relationship store created with the walker's date kinds and `same_clinical_event` moved into it; archive and CloudKit carry it; `bestDate` walks the index only | Ingest on staging renders panels and addresses grouped from the list; wipe, rebuild, identical by entry id | Opus 5 |
| R4 | app | FHIR ingest writes relationship entries: `Observation.hasMember` → `belongs_to_panel`, `DiagnosticReport.result` → membership, `encounter` → `part_of_interaction`, `Composition.section.entry` → `member_of_section`; the scalar FHIR date branch in `bestDate` retires (RL-12) | A FHIR lab panel and a PDF lab panel of the same structure produce identical relationship entries by kind; one `bestDate` path | Opus 5 |
| R5 | app | Care graph absorbed (RL-10): 16 kinds registered, edges become entries, `.graph.enc` retires, traversal reads the index; provider and org id lists become `has_role`, `affiliated_with`, `part_of_interaction` entries; `TreatmentTree` rebuilt as a traversal; display caches on `RecordV2` rebuilt from entries | Care graph screens identical before and after on a real patient; no second edge type in code (grep-pinned) | Opus 5, Fable reviews the kind registration first |

Ordering: R1b then R2 in the api repo; R3, R4, R5 in the app repo in that order. PACKAGE_DESIGN §9 sprint 7 resumes at step 3 as soon as R2 ships (the console needs only the Worker side); R3 through R5 run beside the console steps and must land before sprint 9 (graded import folds reviewer relationship entries). Sprint 10's containment units are registry rows. The inference engine, person entities, and keystone wiring are their own designs and sprints after the package series; this doc fixes what they read and write.

---

## 13. Hard questions

1. **List size.** A 400-atom lab report produces about 400 `member_of_section` entries plus panel entries. The core grows by a few hundred KB. R14: watched via `package_size_bytes`, not ruled. If it matters, `member_of_section` for pipeline-emitted atoms could stay implicit in `section_id` and be materialized on the phone; the registry row would say `emitted_by: pipeline, carrier: field`. Not taken in v1 because one shape is the point.
2. **Inference by model.** A Bedrock-produced inference is not reproducible. §4's standing rule covers it; the inference engine's design must say which kinds are inferred by deterministic code and which by a model, and a model-inferred kind gets a higher `confirm_at`.
3. **Two reviewers, two authored entries for one triple.** The uniqueness rule refuses the second; the second reviewer sees the first's entry and judges it. Arbitration stays out of scope (GT.2 parked).
4. **Kinds the phone knows and the Worker does not.** Walker date kinds live in the registry with `emitted_by: walker`, so the Worker's census recognizes them without ever emitting them. The registry is the union, not the Worker's subset.
5. **Cardinality flips.** `belongs_to_panel` is `one` today. If a real document puts one result under two panels, the row flips to `many` with a version bump; consumers that assumed one target get a labeled second edge, not a broken decode.
6. **Two carriers for one fact.** Lab-row grouping on the phone uses `TableCellRef`; the Worker's `belongs_to_panel` edge says the same thing and nothing reads it. Under one shape both cannot stay as truth. R2 rules whether `belongs_to_panel` is the entry and the cell ref is presentation, or the reverse until sprint 10 registers `row_in_table`. The ADI grades panels either way; the console must read whichever is ruled.
7. **Absorbing the care graph is the largest phone change in this design.** Fourteen date lookups, three stores, a traversal API, and the treatment tree all move. It is ruled (RL-10) because a second edge model with its own confidence field is the exact inference shape §4 defines, living where nothing else can read it. R5 gets its own audit prompt before implementation and Fable reviews the kind registration.

---

## 14. Not in this design

The inference engine's algorithms, thresholds, and model use. Person entity resolution beyond aliases. Keystone question wording and cadence (EVENTS_INTERACTIONS). Arbitration between reviewers. A full FHIR export design. Any UI.

---

## 15. Rulings log

- RL-1 through RL-9: ruled 2026-09-05 in chat, text above. RL-1 supersedes the 2026-09-05 link-authoring proposal's derived triple id (the triple is the fact's identity; the entry id is minted) and its "extend the two edge entities" fallback.
- RL-10 through RL-12: ruled 2026-09-05 in chat after the phone-side inventory (R1a). RL-10 chose absorb over derive for the care graph.
- v1.1 (2026-09-05): §8.1 added; §2 gains `affiliated_with`, `section_references`, and the care-graph placeholder row; §12 resequenced to R1a, R1b, R2 through R5; hard questions 6 and 7 added.
- Open: §10 stable identity mechanism (rule at R1b). §2 per-kind `inferable`, `confirm_at`, `consumer_policy`, `adi_visible` values (rule with the inference engine design). Hard question 1 (`member_of_section` explicit or field-carried) and hard question 6 (panel edge versus cell ref), both ruled at R2's audit.
