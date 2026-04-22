# ATOM_UNIFICATION_DESIGN — PHI as Atom Attribute

**Status:** Rough sketch v0.1 — shape-not-spec
**Created:** 2026-04-22
**Location at rest:** `SeedCorpus/ATOM_UNIFICATION_DESIGN.md`
**Related:** `PLUMBING_FIX.md` (sibling architectural debt around source_regions duplication), `CLINICAL_SHAPE_DESIGN.md` (current atom/PHI schema), `TRAINING_MEDIA_DESIGN.md` (consumer of unified training data)

---

## 1. Why this document exists

The current pipeline treats PHI detections and clinical atoms as two separate data streams, stored in two separate tables (`phi_detections` and `data_atoms`), graded through two separate UI surfaces (PHI tab and Atoms tab), with no stored link between records that describe the same underlying span of text.

This produces predictable problems:

- "Dr. Smith" appears twice — once as a PHI detection of type PROVIDER, once as a clinical atom of kind `provider` — with no record that they're the same span
- Reviewers grade the same underlying ground truth twice
- Contradictory verdicts are possible (PHI says "confirm the tokenization," atom says "reject the extraction") with no reconciliation path
- Training media export emits two parallel streams that downstream consumers must join by coordinate matching
- FHIR mapping is awkward because FHIR resources naturally combine clinical meaning and PHI attributes (a Practitioner resource has a name that is PHI)
- The ADI console's single-selection invariant becomes artificial — a reviewer clicking "Dr. Smith" must choose which track to grade

This document proposes unifying the two streams into a single atom model where PHI is a flag on an atom, not a parallel record type.

Scope: design target state. Not a sprint plan. When a future sprint executes this unification, this document provides enough design context to plan against rather than rediscover.

## 2. Target state — atoms with PHI as attribute

Every extracted span becomes a `data_atom` record. Each atom has:

- `entity_kind` — always populated (expanded taxonomy, see §4)
- `phi_token_uid` — nullable. Non-null when the atom's verbatim is tokenized PHI; references the detokenization map
- `phi_type` — nullable. Populated when `phi_token_uid` is set; identifies the HIPAA PHI category
- Existing fields: `verbatim_value`, `clinical_fields`, `source_region`, `canonical_codes`, `confidence`, etc.

### Four cases this model handles

**Case 1 — Atom only, no PHI.**
Example: "hypercholesterolemia"
```
entity_kind: "condition"
phi_token_uid: null
phi_type: null
```

**Case 2 — Atom + PHI (dual classification).**
Example: "Dr. Smith" as the attending provider
```
entity_kind: "provider"
phi_token_uid: "dr2"
phi_type: "providerName"
```

**Case 3 — PHI-dominant atom (patient identity).**
Example: patient MRN
```
entity_kind: "patientIdentifier"
phi_token_uid: "mrn1"
phi_type: "mrn"
```

**Case 4 — Administrative PHI without clinical meaning.**
Example: barcode on form containing accession number
```
entity_kind: "documentMetadata"
phi_token_uid: "barcode1"
phi_type: "accessionNumber"
```

### What this collapses

- `phi_detections` table → columns on `data_atoms`
- `grading_submissions.phi_verdicts` / `phi_discoveries` → merged into existing `verdicts` / `discoveries` structures on the unified model
- ADI console PHI tab → atom list with PHI-type filters
- iOS transit `extractions[]` + `detected_phi[]` arrays → single unified array
- Training media export streams → single atom stream with PHI attributes

## 3. Why this is cleaner than alternatives

### 3.1 Why not a peer attribute (span-with-two-classifiers)

An alternative architecture would make a "span" the primary entity with `entity_kind` and `phi_type` as peer nullable attributes. This was the initial sketch during the design conversation.

Rejected because: it makes PHI-ness a peer concept to clinical meaning, which implies they're independent dimensions. They aren't — PHI-ness is a property of the *content* of an atom (what the text says identifies someone), while clinical meaning is about the *role* of the atom in the record. PHI is a characteristic of an atom, not a parallel classification system.

The flag-on-atom model also preserves the atom as the primary unit of analysis, which aligns with how FHIR, training media, and reviewer grading all naturally operate.

### 3.2 Why not foreign keys linking the two tables

A minimal fix would add `atom_id` to `phi_detections` so the two records reference each other, without merging. The architecture stays dual-table but gains relational integrity.

Rejected because: it perpetuates the duplication cost (every dual-classified span still produces two records) while adding relational complexity. The grading UI still has two tabs, reviewers still grade twice, training media export still emits two streams. FK adds a band-aid without addressing the architectural redundancy.

### 3.3 What unification gains

- One grading UI surface — reviewer sees each atom once, grades its clinical meaning and PHI-ness together
- One training media stream — exports emit unified atom records
- Natural FHIR mapping — resource type from `entity_kind`, PHI detokenization handled orthogonally via `phi_token_uid`
- Reduced reviewer-hours — no double-grading of dual-classified spans
- Simpler state model — single-selection invariant is trivially satisfied
- Easier contradictory-verdict prevention — one atom, one verdict path

## 4. Expanded PHI taxonomy

Current `phi_type` values (from existing tokenizer) are broad: PROVIDER, ORG, DATE, PERSON, etc. Expanding for the unified schema:

### Identifier category
- `mrn` — Medical Record Number
- `ssn` — Social Security Number
- `accountNumber` — billing, insurance account, membership IDs
- `accessionNumber` — lab/imaging accession
- `licenseNumber` — DEA, medical license numbers
- `deviceIdentifier` — PHI-linked device serial numbers

### Name category
- `patientName` — the patient themselves
- `providerName` — clinicians, physicians, therapists
- `guardianName` — parent/legal guardian name
- `emergencyContactName` — emergency contact person
- `staffName` — non-provider staff (schedulers, medical assistants) where the name is recorded

### Location/Contact category
- `patientAddress` — patient home address
- `patientPhone` — patient contact phone
- `patientEmail` — patient email
- `providerAddress` — clinician office address
- `providerPhone` — clinician office phone
- `facilityName` — hospital, clinic, organization
- `facilityAddress` — facility street address

### Temporal category
- `dob` — date of birth (distinguished from other dates because of HIPAA-specific rules)
- `dateOfService` — when care was delivered
- `dateOfReport` — when the document was issued
- `dateOfAdmission` / `dateOfDischarge` — hospital-specific
- `dateSigned` — when a document was authenticated (often not clinically relevant)

### Demographic category
- `age` — when recorded as standalone demographic
- `gender` — when recorded as demographic
- `race` / `ethnicity` — demographic data

### Other
- `photograph` — if image regions are detected
- `fingerprint` — biometric identifier
- `urlOrHandle` — patient portal URLs, social handles
- `ipAddress` — if captured from portal/electronic access logs
- `otherIdentifier` — catch-all for uncommon PHI types

### Design rationale for expansion

Current PHI types conflate several distinctions the LLM extractor could use:
- Phone vs. address — different linguistic patterns, different error modes
- DOB vs. date-of-service — DOB is always PHI; dates-of-service are PHI when tied to identified patients
- Patient name vs. provider name vs. guardian name — same "name" category today, but each has different clinical significance and different tokenization rules

Expanding gives the future extractor LLM a richer schema to map to, reduces ambiguity in grading, and aligns with how HIPAA actually categorizes PHI (18 identifier types, not 5 bucket categories).

## 5. Expanded ENTITY_KINDS — new PHI-adjacent kinds

To accommodate PHI-only atoms (cases 3 and 4 in §2), ENTITY_KINDS expands beyond the current 20 clinical kinds:

### New kinds for patient identity (PHI-dominant atoms)
- `patientName`
- `patientIdentifier` (MRN, SSN, account, membership)
- `patientAddress`
- `patientContact` (phone, email)
- `patientDemographic` (age, gender, race when standalone)

### New kinds for related persons
- `guardianInformation`
- `emergencyContact`

### New kinds for document/administrative metadata
- `documentMetadata` — barcodes, accession numbers, form IDs, internal document references

### Existing kinds that gain PHI association
- `provider` — already exists; can now carry `phi_token_uid`
- `organization` — already exists; can now carry `phi_token_uid`
- `visitDate` / `reportDate` — already exist; can now carry `phi_token_uid`

Total expanded: roughly 25-28 kinds (from current 20). Worth revisiting the group structure (§5.5 in PHASE_1_DESIGN) — possibly add a "Patient Identity" group to contain the new patient-focused kinds.

## 6. FHIR mapping interaction

The unified model is compatible with FHIR mapping (§6 of the PHASE_ROADMAP Phase 2 discussion). Each atom's `entity_kind` maps to a FHIR resource type. The `phi_token_uid` is orthogonal — it tells the exporter whether to detokenize or leave tokenized in the output.

Examples:
- `entity_kind: "patientName"` + `phi_token_uid: "pt1"` → FHIR `Patient.name`, detokenize for export (if permitted by export context)
- `entity_kind: "provider"` + `phi_token_uid: "dr2"` → FHIR `Practitioner.name`, detokenize
- `entity_kind: "condition"` + `phi_token_uid: null` → FHIR `Condition`, no PHI handling needed
- `entity_kind: "patientAddress"` + `phi_token_uid: "addr1"` → FHIR `Patient.address`, detokenize

FHIR doesn't have a "is this PHI" concept at the schema level — PHI is an access-control concern layered on top. The unified atom model mirrors this: PHI-ness is metadata about how to handle the value, not an independent data category.

## 7. ADI console UI consequences

### 7.1 Tab consolidation

Today: Atoms tab and PHI tab as separate surfaces.

Target: One "Atoms" tab containing all extracted spans. Filters allow viewing by:
- Entity kind (existing filter)
- PHI status (new filter: "all / PHI only / non-PHI only")
- PHI type (new filter, when PHI-only is selected)
- Verdict status (existing filter)

### 7.2 Grading flow simplification

One correction form handles both clinical and PHI corrections:
- Corrected kind (dropdown, as in Sprint 1.3)
- Corrected value (text)
- PHI token correction (if the atom has PHI, affordance to correct the tokenization/detection)
- Rationale
- Confusion class

### 7.3 Drill-down compatibility

The Sprint 1.2 drill-down pattern extends to PHI atoms without structural changes — same header strip, same Next/Prev navigation, same correction form with additional PHI-specific fields when relevant.

### 7.4 Single-selection invariant

Trivially satisfied. Only one atom can be selected at a time; PHI tab's parallel selection state disappears.

## 8. Pipeline consequences

### 8.1 iOS extraction

Today: separate passes produce `extractions[]` (clinical atoms) and `detected_phi[]` (PHI detections).

Target: a single pass produces unified atom records. Or: the two passes remain as implementation detail but their outputs merge before transit serialization.

Transit payload changes to a single `atoms[]` array where each atom has PHI metadata when applicable.

### 8.2 Worker schema migration

Significant:
- `phi_detections` table collapses into `data_atoms` (new columns: `phi_token_uid`, `phi_type`)
- `grading_submissions.phi_verdicts` / `phi_discoveries` merge into unified `verdicts` / `discoveries`
- Existing data requires migration: match each `phi_detections` row to the corresponding `data_atoms` row by coordinates + text, merge PHI attributes; orphaned PHI detections create new atoms with PHI-dominant entity_kinds
- Reject-reason taxonomies (currently `REJECT_REASONS_CLINICAL` and `REJECT_REASONS_PHI`) may unify or remain separate depending on grading semantics

### 8.3 Training media export

Single stream of atoms with PHI attributes. Simpler schema, easier downstream consumption. Replaces the current two-stream export design implied by TRAINING_MEDIA_DESIGN §6.

### 8.4 Detokenization map

The existing `phi_reverse_map` (detokenization JSONB on documents) stays as-is. Atoms reference it via `phi_token_uid`. No structural change needed to the map itself.

## 9. Phased migration approach

This is not a single sprint. Rough sequence:

### Phase U.1 — Schema preparation
- Add `phi_token_uid` and `phi_type` columns to `data_atoms` (nullable)
- Worker accepts both old and new payload shapes during transition
- No iOS or console changes yet

### Phase U.2 — iOS unification
- iOS transit payload produces unified atoms
- Worker consumes unified shape; old `detected_phi[]` becomes deprecated input path
- ADI console still reads from both tables for a transition period

### Phase U.3 — Data migration
- One-time script: read `phi_detections` rows, match to atoms, merge attributes
- Orphaned PHI detections → create atoms with patient-identity `entity_kind`
- Validate data integrity with SQL checks

### Phase U.4 — ADI console unification
- Collapse PHI tab into Atoms tab
- Update grading form for PHI attributes
- Update filter UI
- Keep PHI tab accessible for a transition period if needed

### Phase U.5 — Cleanup
- Drop `phi_detections` table
- Remove `phi_verdicts` / `phi_discoveries` from grading_submissions
- Remove dual-stream export logic
- Update training media export to unified stream

### Phase U.6 — PHI taxonomy expansion
- Can happen alongside U.1 or later
- Add new phi_type values to tokenizer
- Update extraction prompts to use richer taxonomy
- Update ADI grading to surface new types

Rough total: 4-6 sprints depending on scope decisions and edge cases encountered. Real schema migration with data at stake.

## 10. When to do this

Not urgent for Phase 1. The ADI grading loop works today with the two-track model; it's inefficient but functional. Indicators this should promote:

- Phase 4 (negative-space annotation) development exposes the dual-classification friction — negative-spacing "Dr. Smith" requires rejecting in both tabs
- Phase 5 (training media export) runs into complexity from the two-stream schema
- Reviewer throughput measurably lags because of double-grading cost
- FHIR export becomes a near-term need and the current split doesn't support it cleanly

Probably lands between Phase 2 and Phase 3 of the main ADI roadmap, or bundled with Phase 5 when training media export forces the issue.

## 11. Open questions for detail design

1. **Patient profile becomes atoms?** Currently patient name, DOB, address live in a patient profile object separate from atoms. If patient identity becomes atom-kinds, does the profile disappear (replaced by queries over atoms) or remain as a derived view?

2. **Consent and permissions on PHI-dominant atoms.** PHI atoms may have different access rules than clinical atoms (e.g., only superuser can view raw detokenized patient identifiers). Does this warrant a separate access tier within the atom model?

3. **Atom immutability and PHI corrections.** Atoms are append-only. PHI tokenization corrections (reviewer says "the tokenizer caught this wrong") land in grading_submissions. But tokenization errors have downstream effects on other atoms that reference the same token. Does correcting one atom's PHI need to cascade or just stay as verdict metadata?

4. **Reject-reason taxonomy unification.** Current `REJECT_REASONS_CLINICAL` and `REJECT_REASONS_PHI` have different vocabulary. Merge into one taxonomy or keep separate with a scope field?

5. **Reviewer training implications.** A unified grading flow means reviewers grade more attributes per atom. Does the reviewer UI need to surface PHI concerns more prominently (e.g., "this atom is PHI" banner) or is one-column handling sufficient?

6. **Migration data loss risk.** Orphaned `phi_detections` without matching atoms represent either (a) PHI the clinical pass missed, or (b) detections that don't correspond to any clinical span. Migration needs to categorize these — creating atoms for case (a), flagging case (b) for review.

7. **Group structure in the correction dropdown.** With PHI-dominant kinds added, the 8 FHIR-backed groups from Sprint 1.3 need extending. A new "Patient Identity" group seems natural. Total groups grows to ~9-10.

## 12. Relationship to other design docs

- `PLUMBING_FIX.md` — sibling architectural debt (source_regions duplication). Both issues arise from the same pattern: data that represents related concepts stored in unrelated places. Fixing them together would be sensible but not required.
- `CLINICAL_SHAPE_DESIGN.md` — defines current atom schema. This document's proposal would extend that schema rather than replace it.
- `TRAINING_MEDIA_DESIGN.md` — consumer of the unified schema. §6 training record shape simplifies when the two streams become one.
- `PHASE_1_DESIGN.md` — current sprint work unaffected. Phase 1 drill-down operates on the current atom shape; it will work transparently when the atom shape gains PHI attributes.

---

**End of v0.1. Shape-not-spec. Promote to detail design when scope is committed.**
