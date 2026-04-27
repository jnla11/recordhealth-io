# ATOM_UNIFICATION_DESIGN — Unified Atom Model with PHI as Attribute

**Status:** v1.0 — shape-not-spec, ready for sprint commitment
**Supersedes:** v0.1 (2026-04-22)
**Last revised:** 2026-04-24
**Location at rest:** `SeedCorpus/ATOM_UNIFICATION_DESIGN.md`

**Implementation status (2026-04-27):** v1.0 design committed.
Sprints U.1a–U.2b.3.c complete on iOS (db_unification branch).
Worker schema migration U.1b/U.1c/U.1d/U.1e complete on staging.
Remaining: U.3 (data migration), U.4 (ADI console), U.5 (cleanup),
U.F (FHIR import). v1.0 decisions are not under debate; execution
continues per ATOM_UNIFICATION_SPRINT_ARC.md.

**Related:**
- `PLUMBING_FIX.md` — sibling architectural debt (source_regions duplication)
- `CLINICAL_SHAPE_DESIGN.md` — current atom/PHI schema
- `TRAINING_MEDIA_DESIGN.md` — consumer of unified training data
- `RecordHealth_App/docs/ARCHITECTURE.md` — iOS architecture
- `RecordHealth_App/docs/DATABASE_LAYOUT.md` — Neon project topology

---

## 1. Framing — training signal is the north star

The Record Health ingest pipeline produces data. Reviewers correct that data in the ADI. **The delta between pipeline output and reviewer-corrected output is the training signal that improves the pipeline.** Every architectural decision in this document flows from that principle.

Today the pipeline treats PHI detections and clinical atoms as two separate data streams. They live in separate tables, grade through separate UI surfaces, and produce two parallel training streams that downstream tooling must reconcile by coordinate matching. This document unifies them: every meaningful span in a document is an atom, PHI-ness is a flag on the atom, reviewer corrections land as superseding atom versions, and the delta is preserved at every stage.

The unification is not primarily about schema cleanup. It is about making the training signal legible end-to-end. Schema consequences follow from that goal.

### Scope of v1.0

This document defines the target architecture, the migration arc, and the sprint decomposition. It is shape-not-spec: detail design happens per sprint at execution time. When a future sprint commits to part of this arc, this document provides enough context to plan against rather than rediscover.

---

## 2. Architectural principles

These principles govern every decision below. When downstream choices feel ambiguous, return to them.

**Every span is an atom.** No document ever produces both "an atom" and "a PHI detection" for the same span. An atom either is or is not PHI; if it is, it carries the tokenization metadata.

**Pipeline truth is immutable.** Every atom produced by any pipeline (AI extraction, FHIR import, regex hints) is preserved verbatim from the moment of creation. Reviewer corrections, classification changes, and PHI promotions/demotions produce new superseding atom versions. The original is never overwritten.

**PHI boundary is structural, not conventional.** Whether an atom is PHI-sensitive is not decided at call sites. The atom carries an `is_phi` flag, a `phi_type`, and an `access_tier`. Code that handles atoms reads those fields; it does not re-derive PHI-ness.

**Trust boundary is tokenization, not tier.** The 1st level AI pass sees raw document text and produces atoms with PHI flags set. Everything downstream of tokenization sees only tokens. This line is the trust boundary. It is crossed once, in one direction, by one process.

**Two stores, one canonical vocabulary.** iOS FactStore is the patient's source of truth. ADI `data_atoms` is the training corpus. They evolve independently. Both speak the same atom vocabulary, pinned to a shared schema version.

**Append-only where it matters.** FactStore is append-only (already). `data_atoms` on the Worker becomes append-only (new). `grading_submissions` is already append-only. These three append-only stores together preserve the full training signal.

**User data stays on device unless the user submits it.** FHIR imports stay on iOS. Patient-edit atoms stay on iOS. Atoms only reach the Worker via explicit superuser submission for ADI review.

**Raw FHIR is never discarded.** Apple Health delivers more data than the current import path consumes. All raw FHIR resources are preserved encrypted on device, whether or not the current mapper handles their resource type. Future expansion reads from the preserved raw data.

---

## 3. Unified atom model

Every atom carries the following fields. Nullability reflects what may be absent at creation time but becomes populated through pipeline stages or reviewer corrections.

### 3.1 Core fields

```
id                       : UUID                (required, assigned at creation)
document_id              : UUID                (required, the source document)
patient_id               : UUID                (required)
kind                     : AtomKind enum       (required, FHIR-aligned parent)
subtype                  : string              (nullable, granular classification)
classification_certainty : enum                (required: specific | parent_only | low_confidence)
verbatim_value           : string              (required, the literal text from source)
source_region            : SourceRegion        (required, coordinates + char offsets)
confidence               : float 0..1          (required, producer's confidence)

is_phi                   : bool                (required, false by default)
phi_type                 : PHIType enum        (nullable, required when is_phi=true)
phi_token_uid            : string              (nullable, required when is_phi=true)
access_tier              : enum                (nullable: standard | restricted)

codings                  : Coding[]            (required, empty array by default)
structured_payload       : JSONB               (nullable, kind-specific structured data)
regex_hints              : RegexHint[]         (nullable, pattern-detection metadata)

produced_by              : string              (required, e.g. "pipeline.ingest_pass.v1")
produced_at              : timestamp           (required, UTC)
schema_version           : string              (required, pins canonical vocabulary version)
supersedes               : UUID                (nullable, references prior atom version on ADI side only)

resolution_status        : enum                (required: awaiting_review | confirmed | corrected | rejected)
reviewer_id              : string              (nullable)
reviewed_at              : timestamp           (nullable)
```

### 3.2 Field semantics

**`kind`** is the FHIR-aligned parent category. Required on every atom. ~15 values. Maps 1:1 to a FHIR resource type or composition.

**`subtype`** is the granular distinction within `kind`. Nullable — flat clinical atoms (condition, medication, labValue) don't need it. Required for atoms where the parent category has multiple meaningful subtypes (patientIdentifier.ssn vs patientIdentifier.mrn).

**`classification_certainty`** — the AI or producer's confidence in the *classification*, distinct from `confidence` which is the extraction confidence.
- `specific` — producer is confident in both `kind` and `subtype`.
- `parent_only` — producer is confident in `kind` but cannot reliably determine `subtype`. Holding pen state. Atom lands with `subtype = null`.
- `low_confidence` — producer is uncertain even at parent level. Lands in an `uncategorized` or best-guess `kind` with this flag for reviewer triage.

**`is_phi` / `phi_type` / `phi_token_uid`** — PHI state. `phi_type` is the HIPAA-aligned identifier category (~25 values, see §5). `phi_token_uid` is the stable token identifier that maps to the reverse token map for detokenization.

**`access_tier`** — two tiers.
- `standard` — normal PHI (patient name, DOB, MRN, phone, provider name). Detokenizes automatically for display.
- `restricted` — ultra-sensitive PHI (full SSN, account numbers tied to financial access). Requires biometric unlock or explicit tap-to-reveal. Every detokenization logged to audit.

**`codings[]`** — array of clinical codes attached to the atom. Each entry:
```
{
  system: string        // e.g. "http://hl7.org/fhir/sid/icd-10-cm"
  code: string          // e.g. "E11.9"
  display: string       // e.g. "Type 2 diabetes mellitus without complications"
  source: enum          // "fhir_import" | "adi_reviewer" | "cross_record_inference"
  added_at: timestamp
  confidence: float 0..1
}
```
Append-only within the atom. FHIR import populates on ingest. ADI reviewer lookups add via the existing `POST /v1/admin/lookup` path, now wired to write `canonical_codes_append`. Cross-record inference is future scope.

**`structured_payload`** — kind-specific structured data. Nullable. Populated when the source (FHIR, trained AI) produces it. Left null for plain PDF extractions where only `verbatim_value` is available. See §4.3 for per-kind payload shapes.

**`regex_hints[]`** — metadata only, never identity. Captures what regex patterns matched this span during ingest, for training-signal purposes. AI decides classification; regex hints travel alongside.
```
{
  pattern: string       // e.g. "ssn_format" | "phone_us" | "date_iso"
  span_in_atom: [start, end]
  confidence: float
  checksum_valid: bool?
}
```

**`produced_by`** — provenance tag. Versioned string identifying which pipeline stage produced this atom version. Allows training export to filter by source and weight by reliability.

**`supersedes`** — on the ADI side only. Nullable UUID pointing to the prior atom version this row replaces. On iOS, FactStore handles supersession via its own mechanism (FactInterpretation versioning); the iOS `HealthFact` model does not need this field.

### 3.3 The atom kind hierarchy

`kind` is FHIR-aligned parent. `subtype` is granular child. FHIR export maps `kind` to a resource type; `subtype` becomes a `system` URI or `use` code on the FHIR field.

Full taxonomy in §4.

---

## 4. Canonical atom vocabulary

The `AtomKind` enum is shared between iOS and Worker, pinned to `schema_version`. Changing it requires schema version bump.

### 4.1 Clinical kinds (flat, no subtype)

| `kind` | PHI? | FHIR target |
|---|---|---|
| `condition` | No | `Condition` |
| `diagnosis` | No | `Condition` with `verificationStatus: confirmed` |
| `symptom` | No | `Condition` with category |
| `allergy` | No | `AllergyIntolerance` |
| `medication` | No | `MedicationStatement` / `MedicationRequest` |
| `procedure` | No | `Procedure` |
| `immunization` | No | `Immunization` |
| `vitalSign` | No | `Observation` (category: vital-signs) |
| `labValue` | No | `Observation` (category: laboratory) |
| `finding` | No | `Observation` (category: exam) |
| `device` | No | `DeviceUseStatement` |
| `referral` | No | `ServiceRequest` |
| `carePlan` | No | `CarePlan` |
| `familyHistory` | No | `FamilyMemberHistory` |
| `socialHistory` | No | `Observation` (category: social-history) |
| `encounter` | No | `Encounter` |
| `uncategorized` | No | — (fallback) |

### 4.2 Identity / PHI-adjacent kinds (hierarchical, subtype required)

| `kind` | `subtype` | Default PHI | Access tier | FHIR target |
|---|---|---|---|---|
| `patientDemographic` | `name` | Yes | standard | `Patient.name` |
| `patientDemographic` | `dateOfBirth` | Yes | standard | `Patient.birthDate` |
| `patientDemographic` | `sex` | No | — | `Patient.gender` |
| `patientDemographic` | `bloodType` | No | — | `Observation` |
| `patientDemographic` | `pronouns` | No | — | `Patient.extension` |
| `patientDemographic` | `age` | No (when standalone) | — | derived |
| `patientDemographic` | `race` | No | — | `Patient.extension` |
| `patientDemographic` | `ethnicity` | No | — | `Patient.extension` |
| `patientIdentifier` | `mrn` | Yes | standard | `Patient.identifier` |
| `patientIdentifier` | `ssn` | Yes | **restricted** | `Patient.identifier` |
| `patientIdentifier` | `ssnLastFour` | Yes | standard | `Patient.identifier` |
| `patientIdentifier` | `billingAccountNumber` | Yes | **restricted** | `Account.identifier` |
| `patientIdentifier` | `memberNumber` | Yes | **restricted** | `Coverage.identifier` |
| `patientIdentifier` | `subscriberNumber` | Yes | **restricted** | `Coverage.subscriberId` |
| `patientIdentifier` | `encounterNumber` | Yes | standard | `Encounter.identifier` |
| `patientIdentifier` | `unspecifiedIdentifier` | Yes | standard | holding pen |
| `patientContact` | `phone` | Yes | standard | `Patient.telecom` |
| `patientContact` | `email` | Yes | standard | `Patient.telecom` |
| `patientContact` | `fax` | Yes | standard | `Patient.telecom` |
| `patientContact` | `unspecifiedContact` | Yes | standard | holding pen |
| `patientAddress` | — | Yes | standard | `Patient.address` |
| `guardianInfo` | `name` | Yes | standard | `Patient.contact` |
| `guardianInfo` | `relationship` | No | — | `Patient.contact.relationship` |
| `guardianInfo` | `phone` | Yes | standard | `Patient.contact.telecom` |
| `emergencyContact` | `name` | Yes | standard | `Patient.contact` |
| `emergencyContact` | `relationship` | No | — | `Patient.contact.relationship` |
| `emergencyContact` | `phone` | Yes | standard | `Patient.contact.telecom` |
| `emergencyContact` | `address` | Yes | standard | `Patient.contact.address` |

### 4.3 Provider and organization kinds

| `kind` | `subtype` | Default PHI | FHIR target |
|---|---|---|---|
| `provider` | `name` | Yes (standard) | `Practitioner.name` |
| `provider` | `npi` | Yes (standard) | `Practitioner.identifier` |
| `provider` | `role` | No | `PractitionerRole.code` |
| `provider` | `specialty` | No | `PractitionerRole.specialty` |
| `provider` | `credentials` | No | `Practitioner.qualification` |
| `providerContact` | `phone` | Yes (standard) | `Practitioner.telecom` |
| `providerContact` | `fax` | Yes (standard) | `Practitioner.telecom` |
| `providerContact` | `address` | Yes (standard) | `Practitioner.address` |
| `organization` | `facilityName` | Yes (standard) | `Organization.name` |
| `organization` | `departmentName` | Yes (standard) | `Organization.partOf` |
| `organization` | `phone` | Yes (standard) | `Organization.telecom` |
| `organization` | `fax` | Yes (standard) | `Organization.telecom` |
| `organization` | `address` | Yes (standard) | `Organization.address` |

### 4.4 Administrative and document metadata

| `kind` | `subtype` | Default PHI | FHIR target |
|---|---|---|---|
| `coverage` | `payerName` | No | `Coverage.payor` |
| `coverage` | `planType` | No | `Coverage.class` |
| `coverage` | `effectiveDate` | Yes (standard) | `Coverage.period` |
| `coverage` | `groupNumber` | Yes | **restricted** | `Coverage.class` |
| `documentReference` | `accessionNumber` | Yes (standard) | `DocumentReference.identifier` |
| `documentReference` | `orderNumber` | Yes (standard) | `ServiceRequest.identifier` |
| `documentReference` | `formCode` | No | `DocumentReference.type` |
| `documentReference` | `documentType` | No | `DocumentReference.type` |
| `documentReference` | `barcode` | Yes (conservative) | `DocumentReference.identifier` |
| `visitDate` | — | Yes (standard) | `Encounter.period` |
| `reportDate` | — | Yes (standard) when patient-linked | `DocumentReference.date` |

### 4.5 Structured payload shapes per kind

Path 1 from design conversation: richer data lives in `structured_payload`, kind stays at parent level.

**`labValue.structured_payload`:**
```
{
  value: number,
  unit: string,
  reference_range: { low: number, high: number, unit: string },
  interpretation: enum,  // high | low | normal | abnormal | critical
  method: string,
  specimen: string,
  body_site: string
}
```

**`medication.structured_payload`:**
```
{
  dose: { value: number, unit: string },
  route: string,
  frequency: string,
  duration: string,
  prn: bool,
  timing: string,
  dispensing_context: enum  // administered | prescribed | documented
}
```

**`immunization.structured_payload`:**
```
{
  lot_number: string,
  manufacturer: string,
  site: string,
  route: string,
  dose_quantity: { value: number, unit: string },
  status: string
}
```

**`vitalSign.structured_payload`:**
```
{
  value: number,
  unit: string,
  component: [ { type: string, value: number, unit: string } ],  // for blood pressure
  body_site: string,
  position: string
}
```

**`allergy.structured_payload`:**
```
{
  criticality: enum,
  reactions: [ { manifestation: string, severity: string } ],
  substance_code: string,
  verification_status: string
}
```

**`encounter.structured_payload`:**
```
{
  class: enum,  // inpatient | outpatient | emergency | virtual | etc.
  type: string,
  participants: [ { name: string, role: string } ],
  period: { start: timestamp, end: timestamp },
  reason_codes: [ string ]
}
```

Other kinds may not need structured payload in v1; added later as sources become available.

---

## 5. PHI taxonomy (expanded)

Current `PHITokenType` has 9 values. Expanded per HIPAA's 18 identifier categories and the granularity the atom model needs:

### Identifier category
- `mrn`
- `ssn`
- `ssnLastFour`
- `accountNumber`
- `accessionNumber`
- `licenseNumber`
- `deviceIdentifier`
- `memberNumber`

### Name category
- `patientName`
- `providerName`
- `guardianName`
- `emergencyContactName`
- `staffName`

### Location / Contact category
- `patientAddress`
- `patientPhone`
- `patientEmail`
- `providerPhone`
- `providerFax`
- `providerAddress`
- `facilityName`
- `facilityAddress`

### Temporal category
- `dob`
- `dateOfService`
- `dateOfReport`
- `dateOfAdmission`
- `dateOfDischarge`
- `dateSigned`

### Other
- `urlOrHandle`
- `ipAddress`
- `photograph`
- `biometric`
- `otherIdentifier`

Token format on device stays `{{PHI:TYPE:id}}` where TYPE is one of the expanded values. Token map on iOS stores real value with expanded type label.

**Relationship to atom kind:** `phi_type` is the HIPAA classification. `kind` + `subtype` is the FHIR-aligned atom classification. They overlap but serve different purposes — `phi_type` drives tokenization and compliance; `kind`+`subtype` drives semantics and export.

---

## 6. Three stores, one vocabulary

### 6.1 iOS FactStore — patient source of truth

- Location: on-device, encrypted at rest
- Retention: as long as the user keeps the record
- Append-only (already is)
- Carries all atoms produced by iOS pipeline: PDF ingest, FHIR import, manual entry
- PHI atoms carry `phi_token_uid` pointing to iOS PHITokenStore
- Reviewer corrections from ADI do NOT flow back in v1 (deferred — see §13)

### 6.2 ADI `data_atoms` — training corpus

- Location: `RecordHealth-ADI / staging` Neon project
- Retention: long-term (training data)
- Append-only (becomes new in this unification)
- Populated by superuser submission of documents from iOS
- Reviewer corrections produce superseding atom rows (`supersedes` FK)
- Training export reads supersession chains to reconstruct pipeline-vs-reviewer delta
- PHI tokens received as JSONB `phi_reverse_map` on `review_documents`; ADI console detokenizes for display

### 6.3 iOS on-device audit log — compliance record

- Location: on-device, encrypted at rest
- Retention: 30-90 days TTL (not training data)
- Mirrors atom schema for consistency
- Logs every atom creation, correction, deletion, access
- Syncs to Worker `audit_*` tables with matching TTL (if cloud audit sync lands — see §13)

### 6.4 Schema version pinning

Every transit payload carries `atom_schema_version: "2.0"`. Worker validates on ingest. Mismatches reject with clear error. Canonical vocabulary changes bump the version; both sides update together.

### 6.5 Database layout

Per `RecordHealth_App/docs/DATABASE_LAYOUT.md`:
- Unification schema work targets `RecordHealth-ADI / staging` exclusively
- `RecordHealth / production` contains user-flow tables only; no ADI tables
- Seed corpus on `RecordHealth / staging-seed-corpus` may eventually consume unified atom shape (future scope)

---

## 7. Ingest architecture

Three-tier framing. Today's pipeline runs on Bedrock; the architecture is designed to accept BioMistral as a drop-in replacement for the 1st level AI without structural changes.

### 7.1 1st level AI pass (atom extraction + PHI identification)

**One AI call per document. One job. One structured output.**

Input: raw document text. OCR-derived or native-text-extracted. Accompanied by regex hints as metadata.

Output: unified atom list. Every atom has:
- `kind`, `subtype`, `classification_certainty`
- `verbatim_value`, `source_region`, `confidence`
- `is_phi`, `phi_type` (if PHI), `phi_token_uid` (to be assigned post-AI)
- `structured_payload` (if AI is trained to produce structure)

Output is fully classified. Tokenization is a deterministic post-processing step that walks the atoms, assigns stable token IDs via the iOS PHITokenStore, and writes `phi_token_uid` into atom records.

**Trust boundary:** this AI sees raw PHI. Runs on AWS BAA-covered infrastructure. Today that's Bedrock; future that's BioMistral on sandboxed AWS. The atoms produced by this pass are the only artifact that crosses to the next tier.

**Breakdown Pass not split out in v1.** Structural decomposition (sections, subsections, roles) is folded into the single call. Splits out in a future sprint when extraction quality demands it. See §13.

### 7.2 Regex hints (metadata only)

Regex runs on raw document text during ingest. Produces hints, not atoms. Travels alongside document text into the AI prompt as additional context.

**Regex does well:**
- SSN format, phone format, email format, date format, MRN format
- Checksum validation (Luhn credit cards, valid SSN structure)
- Document structure hints (section headers, table boundaries)

**Regex does not:**
- Identify PHI (category 2 / identification is AI's job)
- Classify atoms
- Distinguish contextual meaning

Hints travel as `regex_hints[]` on atoms where patterns matched, after AI produces the atom list. Never affect classification. Used as training signal: when AI and regex agree, high-confidence signal. When they disagree, reviewer-grading opportunity.

### 7.3 Tokenization (deterministic post-processing)

After AI produces atoms with `is_phi` flags set, deterministic bookkeeping:

- For each atom with `is_phi = true`: look up real value in iOS PHITokenStore
- If existing token: use it. Cross-document consistency.
- If new: assign next token ID. Store in PHITokenStore with `phi_type`.
- Write `phi_token_uid` into atom record.

Not an AI call. Not subject to the trust boundary. The token map is authoritative.

### 7.4 FHIR import pass

Parallel ingest path for Apple Health FHIR data. Never crosses trust boundary (data is already on-device from user's own Apple Health, trusted by definition).

**Flow:**
1. Raw FHIR resource received via HealthKit
2. **Raw preservation:** persist verbatim to `Documents/profiles/{patientUUID}.fhir_raw.enc`. Encrypted. Never thrown away, even for resource types the current mapper doesn't handle.
3. **Mapper:** `FHIRRecordMapper` converts FHIR → `FHIRImportCandidate`. Adds Patient, Practitioner, Organization resource branches (missing today).
4. **Bridge:** new `FHIRImportCandidate → PendingInterpretation` path. Each candidate produces one or more atoms with:
   - `kind` from resource type (Patient → patientDemographic/patientIdentifier/patientContact/patientAddress per subtype)
   - `codings[]` populated from `FHIRSourceCode` triples (finally wired through)
   - `structured_payload` populated from structured FHIR fields (reference ranges, dosage, immunization detail)
   - `confidence: 1.0` (FHIR is ground truth)
   - `classification_certainty: specific`
   - `produced_by: "pipeline.fhir_import.v1"`
5. **Write to FactStore:** FHIR atoms skip review queue and write directly to FactStore (they're ground truth, not AI predictions)
6. **Unmapped-field logging:** every dropped FHIR path logged to diagnostic view for future mapper expansion

**Worker transit:** optional for v1. If enabled, a new endpoint `POST /v1/admin/atoms/fhir-import` accepts FHIR-sourced atoms without PDF precondition. Passes `codings[]` into `data_atoms.canonical_codes`. This is how FHIR ground-truth (verbatim, canonical_code) pairs feed the training corpus.

### 7.5 Document scanner

Follows PDF path. Document scanner produces image or PDF; inherits entire 1st level AI pass pipeline. No separate scope.

### 7.6 Voice / transcript — deferred to future scope

See §13.

### 7.7 2nd level AI pass (user-invoked reasoning)

Separate call, separate prompt, separate job. User asks a question; AI sees tokenized atoms + the question; produces an answer with tokens; detokenized at display time.

Downstream of trust boundary. Never sees raw PHI.

No changes in v1 — existing Query Pass already implements this. Documented here for architectural completeness.

---

## 8. ADI grading surface

### 8.1 Unified atom list, PHI as filter

PHI tab collapses. One atom list with filters:
- By `kind` (existing filter)
- By `is_phi` (new: all / PHI only / non-PHI only)
- By `phi_type` (new, when PHI-only active)
- By `verdict` (existing)

### 8.2 Hybrid interaction — inline quick-verdict + drill-down

Preserves reviewer throughput while allowing depth when needed.

**Inline quick-verdict:** PHI-flagged atoms get per-row Confirm/Correct/Reject buttons in list view. Reviewer can scan-and-verdict without entering drill-down. This preserves the PHI tab's current throughput.

**Drill-down:** any atom (PHI or clinical) can enter drill-down via click. Drill-down provides richer correction form, bbox edits, full rationale, Prev/Next nav.

### 8.3 Overlay color semantics — red = PHI, mandatory

PHI-flagged atoms render red on the overlay regardless of kind color.
Non-PHI atoms use kind color (`KIND_COLORS` palette).

**Breaking change:** `region-rejected` currently uses a red variant. U.4 picks a new color for rejected atoms (gray/strikethrough proposed) to preserve red-exclusively-for-PHI. Reviewers have internalized "red = PHI" as the primary visual signal; protecting this signal is a U.4 requirement.

### 8.4 Reviewer corrections and token lifecycle

Reviewer corrections produce superseding atom rows. PHI flag flips and token reassignments follow these rules:

**Atom promoted to PHI** (was `is_phi: false`, reviewer says it's PHI):
- New atom row inserted with `supersedes` → original atom ID
- New row has `is_phi: true`, `phi_type: <reviewer-assigned>`, `phi_token_uid: null`
- Token assignment happens server-side at write time, writing into the document's reverse map
- Original atom row preserved unchanged

**Atom demoted from PHI** (was `is_phi: true`, reviewer says it's not PHI):
- New atom row with `supersedes` → original, `is_phi: false`, `phi_token_uid: null`
- The token in the reverse map is NOT deleted — it's marked superseded (append-only applies to the reverse map too)
- `verbatim_value` remains the real value (audit trail)

**PHI type corrected** (was `phi_type: providerName`, reviewer says `patientName`):
- New atom row with `supersedes` → original, updated `phi_type`, same or new `phi_token_uid`
- Token identity is orthogonal to type correction — the real value didn't change, its classification did

**Token map never mutates tokens.** Tokens are stable IDs. Atom versions point to different tokens when values or types change; old tokens remain valid for historical detokenization.

### 8.5 Grading submission payload — unified

`POST /v1/admin/grading/submit` accepts a unified `verdicts[]` array. Each verdict carries `is_phi` flag; server partitions for per-stream F1 computation.

- `verdicts[]` — single array (was `verdicts[]` + `phi_verdicts[]`)
- `discoveries[]` — single array (was `discoveries[]` + `phi_discoveries[]`)
- `bbox_edit_history` — unchanged, atom-id-keyed
- `summary` — both clinical F1 and PHI F1 via partitioned computeMetrics

`validateRejectReasons` branches per-entry on `is_phi` flag. `REJECT_REASONS_PHI` and `REJECT_REASONS_CLINICAL` allowlists both preserved in v1. Merging the allowlists is follow-on work.

### 8.6 ENTITY_KIND_GROUPS expansion

Sprint 1.3's 8 groups expand to ~10 with a new "Patient Identity" group containing the new `patientDemographic.*`, `patientIdentifier.*`, `patientContact.*`, `patientAddress` kinds. Invariant (union = `ENTITY_KINDS`) maintained. Kind Assignment Wizard (PHASE_ROADMAP §3.8) remains future scope — the expanded grouped dropdown handles v1.

---

## 9. iOS changes

FactStore stays as-is structurally. Adding fields to atom model, not restructuring.

### 9.1 Schema additions on HealthFact / FactInterpretation / PendingInterpretation

New optional fields on each model per §3.1:
- `subtype`, `classificationCertainty`, `isPhi`, `phiType`, `phiTokenUid`, `accessTier`
- `codings: [Coding]`
- `structuredPayload: Codable?` (kind-specific)
- `producedBy`, `producedAt`, `schemaVersion`

Back-compat: optional fields default to nil/empty; old encrypted data decodes cleanly.

### 9.2 DocumentTransitService

Build unified `atoms[]` payload per §8.5. Transition-compatible: Worker accepts both old and new shapes during U.2 window.

Version string `atom_schema_version: "2.0"` on every transit payload. Worker validates.

### 9.3 FHIR import path

Per §7.4:
- Add raw FHIR preservation sidecar
- Add Patient, Practitioner, Organization resource-type branches
- Add FHIR → PendingInterpretation bridge
- Wire codings[] through to atoms
- Unmapped-field logging
- (Optional) Worker transit endpoint for FHIR-sourced atoms

### 9.4 RecordTokenizer

Role shrinks. Today it does PHI identification + tokenization. Post-unification:
- PHI identification moves to AI
- Tokenizer becomes token-map bookkeeping utility
- Called after AI produces atoms with `is_phi` set
- Assigns stable token IDs, updates PHITokenStore
- Deterministic, no AI involvement

Legacy tokenizer paths (the three `switch resourceType` branches in FHIR mapper and synthesis engine, the regex-based patient/provider tokenization) deprecate. Cleanup sprint at end of arc.

### 9.5 Access-tier UI

Restricted-tier PHI atoms render masked by default. Tap-to-reveal triggers biometric unlock; reveal logged to audit. Builds on existing PHIVault concept.

---

## 10. Worker changes

### 10.1 Schema migration (ADI tables only)

**`data_atoms` table additions:**
- `is_phi` BOOLEAN NOT NULL DEFAULT FALSE
- `phi_type` TEXT (nullable)
- `phi_token_uid` TEXT (nullable)
- `access_tier` TEXT (nullable, values: standard | restricted)
- `subtype` TEXT (nullable)
- `classification_certainty` TEXT NOT NULL DEFAULT 'specific'
- `codings` JSONB NOT NULL DEFAULT '[]' (already exists, now actually populated)
- `structured_payload` JSONB (nullable)
- `regex_hints` JSONB NOT NULL DEFAULT '[]'
- `supersedes` UUID (nullable, self-FK to data_atoms.id)
- `produced_by` TEXT NOT NULL
- `produced_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- `schema_version` TEXT NOT NULL DEFAULT '2.0'

**`entity_kind_enum` migration:**
- Add all new values per §4 via `ALTER TYPE ... ADD VALUE` (serialized per Postgres constraints)
- Includes `finding`, `encounter` (resolves current drift)
- Includes new patient identity, provider, organization, documentReference, and holding-pen kinds

**Append-only conversion:**
- All `UPDATE data_atoms SET ...` paths change to `INSERT ... (supersedes) VALUES (...)` pattern
- Current mutation points: resolution_status changes, reviewer assignment, reviewed_at writes
- Latest-in-chain queries replace current-state queries (window function or view)

### 10.2 `review_phi_detections` migration

Table deprecates but retains during transition. Data migration:
- Each row matched to a `data_atoms` row by coordinate overlap + shared `document_id`
- Match found: attributes merge into atom (new superseding row with PHI flag set)
- Orphan PHI detection: new atom row created with patient-identity kind inferred from `token_type`

Dev data only today, so migration is lightweight. Production cutover follows standard App Store release cycle. Table drop in U.5.

### 10.3 Ingest handler changes

`POST /v1/admin/documents/upload`:
- Accept unified `atoms[]` alongside legacy `extractions[]` + `detected_phi[]` (backward compat during U.1/U.2)
- Validate `atom_schema_version` header
- Route unified atoms to `data_atoms` with full field set
- After U.2, deprecate legacy shape; after U.5, remove

New endpoint `POST /v1/admin/atoms/fhir-import` (optional v1):
- No PDF precondition
- Accepts FHIR-sourced atom batch
- Populates `codings[]` from FHIR source codes
- Tags `produced_by: "pipeline.fhir_import.v1"`

### 10.4 Grading submit handler

`POST /v1/admin/grading/submit`:
- Accept unified `verdicts[]` with per-entry `is_phi` flag
- Backward compat: accept legacy split shape during transition
- `validateRejectReasons` branches per-entry
- `computeGradingSummary` partitions by `is_phi` for two F1 blocks (client sees both)
- Persist to `grading_submissions` — either unified `verdicts` column or keep split columns populated from unified input during transition

### 10.5 Ontology lookup — wire to canonical_codes

`POST /v1/admin/lookup` currently writes to `ontology_traces` only. Extend to also `PATCH` atom with `canonical_codes_append` so reviewer-resolved codes persist on the atom. Fulfills the dead-lettered `canonical_codes` path.

---

## 11. Sprint arc

Six core sprints. Each independently shippable with rollback possible at sprint boundaries.

### Sprint U.1 — Schema preparation

**Scope:** ADI schema migration + iOS model additions + transit version string.

**Worker:**
- ALTER `data_atoms` with new columns (§10.1)
- ALTER `entity_kind_enum` for canonical vocabulary
- Change UPDATE paths to append-only INSERT pattern
- Accept both old and new transit payload shapes
- Schema version validation

**iOS:**
- Add new fields to `HealthFact`, `FactInterpretation`, `PendingInterpretation`
- `DocumentTransitService` emits unified `atoms[]` with version string
- Old payload shape still supported (dual-emit during U.2 window)

**Pre-sprint audit:** none beyond Audits 1, 3, 4 already completed.

**Smoke test:** round-trip test document through both old and new paths. Verify both produce valid data. Verify Worker rejects mismatched schema versions.

### Sprint U.2 — iOS unification

**Scope:** iOS produces only unified atoms; legacy paths deprecated.

**Worker:** no changes (U.1 already accepts unified shape).

**iOS:**
- Switch `DocumentTransitService` to unified-only output
- `RecordTokenizer` shrinks to bookkeeping utility
- Legacy dual-switch FHIR mapper consolidation begins
- AI extraction prompt updated to produce full unified atom fields (no separate extraction + PHI passes)

**Pre-sprint audit:** confirm U.1 landed cleanly, version validation working.

**Smoke test:** ingest a real document set. Compare unified atom output to pre-unification baseline. No atoms lost, no atoms invented, PHI flags correctly assigned.

### Sprint U.F — FHIR import unification

**Runs parallel to U.2 after U.1 lands. Can ship independently.**

**Scope:** FHIR import produces unified atoms; raw FHIR preserved.

**iOS:**
- Add raw FHIR preservation sidecar (`fhir_raw.enc`)
- Add Patient, Practitioner, Organization resource-type branches to `FHIRRecordMapper`
- Add `FHIRImportCandidate → PendingInterpretation` bridge
- Wire `FHIRSourceCode` through to `codings[]`
- Populate `structured_payload` from structured FHIR fields
- Unmapped-field logging
- FHIR atoms skip review queue, write directly to FactStore

**Worker:**
- (Optional) New endpoint `POST /v1/admin/atoms/fhir-import` accepting FHIR-sourced atoms without PDF

**Pre-sprint audit:** re-verify `FHIRRecordMapper` after U.2 cleanup; confirm no new drift.

**Smoke test:** import a synthetic Apple Health FHIR bundle. Verify every resource type lands as unified atoms with correct codings. Verify raw sidecar contains verbatim copies.

### Sprint U.3 — Data migration

**Scope:** existing `review_phi_detections` rows collapse into `data_atoms`.

**Worker:**
- Migration script: for each `review_phi_detections` row, match to `data_atoms` by coordinates + `document_id`
- Match hit: insert new atom version with PHI attributes, supersedes chain from original
- Orphan: insert new atom row with patient-identity kind inferred from `token_type`
- Data integrity checks before and after

**iOS:** no changes.

**Pre-sprint audit:** snapshot `review_phi_detections` state. Count rows, distribution by token_type, overlap rate with data_atoms.

**Smoke test:** verify every former PHI detection accounted for. No dangling tokens. No broken supersedes chains.

### Sprint U.4 — ADI console unification

**Scope:** PHI tab collapse, unified grading surface.

**Worker:**
- `validateRejectReasons` branches per-entry
- `computeGradingSummary` partitions by `is_phi`
- `GET /v1/admin/grading/submissions` handles unified shape

**ADI console:**
- Delete PHI tab, unify into Atoms tab
- Add `is_phi` / `phi_type` filters
- Preserve inline quick-verdict for PHI atoms
- Drill-down available for all atoms
- Red overlay = PHI only; rejected atoms use new non-red color
- ENTITY_KIND_GROUPS expanded with Patient Identity group
- Collapse `selectPhi` / `selectedPhiIndex` / `phiVerdicts` into atom state
- Drawing discriminator moves from activeTab to explicit affordance (modal picker or toolbar toggle)

**iOS:** no changes.

**Pre-sprint audit:** Audit 4 already covers (see `/tmp/adi_console_audit.md`).

**Smoke test:** manual reviewer workflow on test document. Verify unified grading flow. Verify backward-compat with pre-U.4 submissions (historical grading_submissions still renders).

### Sprint U.5 — Cleanup

**Scope:** drop deprecated paths and tables.

**Worker:**
- Drop `review_phi_detections` table
- Drop legacy payload shape handlers
- Drop `phi_verdicts` / `phi_discoveries` columns on `grading_submissions` (or keep for historical rows)

**iOS:**
- Remove legacy tokenizer paths
- Remove dual-switch FHIR mapper code

**Pre-sprint audit:** verify no callers of deprecated paths remain.

**Smoke test:** build passes with legacy removed. Historical grading_submissions still queryable.

---

## 12. Open questions for sprint execution

Real decisions that can wait until the relevant sprint starts:

1. **Data migration policy for orphan PHI detections** (U.3) — precise matching tolerance, handling of PHI detections without coordinate overlap.
2. **Drawing-mode affordance in ADI console** (U.4) — modal picker vs sticky toolbar vs keyboard modifier for "draw PHI discovery" post-tab-collapse.
3. **Structured payload validation** (U.1/U.2) — strict JSONB schema vs permissive. How to handle FHIR data that doesn't fit the payload shape.
4. **Reject color replacement** (U.4) — gray, strikethrough, amber, other. Requires reviewer UX check.
5. **Historical grading_submissions migration** (U.5) — keep split columns for old rows vs backfill to unified shape.
6. **FHIR transit endpoint scope** (U.F) — whether v1 ships the endpoint or defers to a later sprint.
7. **Token map schema on reverse map** (U.1) — whether reverse map on `review_documents` needs supersession tracking or stays flat.

---

## 13. Future scope — handoff to subsequent conversations

Everything deferred from v1 with enough context to pick up later:

### 13.1 Breakdown Pass as separate AI call
**Shape:** structural decomposition of documents (sections, subsections, roles) as dedicated 1st-level AI pass, running before Atom Pass. Outputs hierarchical region structure; Atom Pass consumes as context.
**Trigger:** extraction quality demands section-scoped reasoning, or downstream (FHIR DocumentReference, scoped re-extraction) needs structural output.
**Blocking:** none architectural; prompt engineering work.
**Open questions:** granularity, how to handle malformed documents.

### 13.2 Tokenization as separate AI pass
**Shape:** promote tokenization from deterministic bookkeeping to its own AI pass if cross-document consistency requires semantic reasoning ("is this Dr. Smith the same as in doc X?").
**Trigger:** token-map lookup-by-hash produces false negatives (same person, slightly different rendering); cross-document linking quality suffers.
**Blocking:** requires training data showing where lookup fails.
**Open questions:** how to bound the pass's scope, whether it runs at ingest or as background reconciliation.

### 13.3 Patient profile synthesis
**Shape:** deterministic aggregation over all of a patient's atoms to produce canonical patient facts, flagged inconsistencies, merged duplicates.
**Trigger:** user-facing profile view needs a coherent single-source representation.
**Blocking:** requires stable atom vocabulary (v1 provides).
**Open questions:** conflict resolution rules (which atom wins when DOB disagrees), whether profile is cached derived view or separate store.

### 13.4 Rosetta / patient context priming
**Shape:** pass known facts from FactStore as prompt context to Atom Pass. AI validates rather than re-discovers. Flags inconsistencies (new document says X, known facts say Y).
**Trigger:** patient has on-device corpus large enough to benefit from priming.
**Blocking:** profile synthesis (§13.3) for stable priming source.
**Open questions:** prompt token budget for priming, how to weight known facts vs new document.

### 13.5 Feedback loop ADI → iOS
**Shape:** reviewer corrections flow back to user's device. User's FactStore gains the corrected atom.
**Trigger:** users report bad atoms persisting after ADI correction; trust issue.
**Blocking:** atom versioning on iOS (already supports), sync protocol design.
**Open questions:** conflict resolution when user edited locally and reviewer also corrected, how to surface corrections to user without alarming them.

### 13.6 Audit pipeline unification
**Shape:** `audit_documents` / `audit_phi_detections` / `audit_*` tables mirror the unified atom schema. Same structural model, different retention (30-day TTL).
**Trigger:** drift between review pipeline and audit pipeline creates inconsistent compliance records.
**Blocking:** U.1 through U.5 of main unification.
**Open questions:** whether audit atoms need the full field set or a reduced shape.

### 13.7 BioMistral migration
**Shape:** replace Bedrock as 1st level AI with BioMistral on AWS BAA-covered infrastructure. Schema stays; producer changes.
**Trigger:** BioMistral training produces better extraction quality than Bedrock; cost model favors swap.
**Blocking:** BioMistral training corpus readiness; deployment infrastructure.
**Open questions:** cutover strategy (parallel runs? flag-gated? hard cutover?), training corpus coverage targets.

### 13.8 Cross-record inference for codings
**Shape:** as patient accumulates documents, infer missing codings on existing atoms from context in newer documents. Write with `source: "cross_record_inference"`.
**Trigger:** atoms from PDF ingest have empty codings that could be resolved from FHIR-sourced atoms on same patient.
**Blocking:** stable atom vocabulary, FHIR import populating codings (U.F).
**Open questions:** confidence thresholds for inference, how to surface inferred codings to reviewer for validation.

### 13.9 Voice / transcript ingest
**Shape:** audio capture, on-device transcription, transcript-to-atom extraction. Handling of voice biometric data as PHI.
**Trigger:** user demand for spoken note capture; clinical encounters recorded.
**Blocking:** all of v1 atom unification.
**Open questions:** transcription accuracy requirements, audio file retention policy, voice biometric tier (restricted?).

### 13.10 Recursive refinement pass for holding-pen atoms
**Shape:** periodic background pass over atoms with `classification_certainty = parent_only` or `low_confidence`. Attempts re-classification with benefit of fuller corpus context. New atom version if confident; stays in holding pen otherwise.
**Trigger:** patient corpus grows; holding-pen atom count grows; user value in retroactively resolving.
**Blocking:** stable atom vocabulary, enough corpus to draw context from.
**Open questions:** scheduling (on-demand? background? after each new ingest?), how to surface refinements to user.

### 13.11 Production sync schema
**Shape:** patient atoms sync to cloud for cross-device or backup. New schema on `RecordHealth / production` (not ADI staging).
**Trigger:** user demand for cross-device continuity; backup/restore requirements.
**Blocking:** production-readiness review, HIPAA-aligned sync protocol.
**Open questions:** sync architecture (per-atom, per-record, batched), encryption model, authentication.

### 13.12 PHI type vocabulary further expansion
**Shape:** beyond §5's expanded ~25 types, any PHI categories that emerge from corpus experience.
**Trigger:** reviewer grading surfaces PHI types not covered; HIPAA reinterpretation.
**Blocking:** none structural.
**Open questions:** registration process for new PHI types, backward compat.

### 13.13 On-device audit log cloud sync
**Shape:** iOS audit log mirrors to Worker `audit_*` tables with matching TTL. Compliance record at the cloud level.
**Trigger:** compliance requirement, user transparency feature.
**Blocking:** audit pipeline unification (§13.6).
**Open questions:** sync frequency, failure handling, audit log encryption.

### 13.14 Kind Assignment Wizard
**Shape:** decision-tree UI replacing flat/grouped dropdown for `corrected_kind`. Per PHASE_ROADMAP §3.8.
**Trigger:** kind taxonomy grows large enough that dropdowns become unusable.
**Blocking:** stable atom vocabulary.
**Open questions:** tree design, how to handle PHI-vs-clinical branching.

### 13.15 Submitted Documents Review Flow
**Shape:** reviewer surface for revisiting locked submissions, amendments, training media export implications. Per PHASE_ROADMAP §3.9.
**Trigger:** Phase 2 ADI work.
**Blocking:** v1 unification.

---

## 14. Relationship to other design docs

- **`PLUMBING_FIX.md`** — sibling architectural debt (source_regions duplication). Both issues stem from data representing related concepts in unrelated places. Fixing together sensible but not required.
- **`CLINICAL_SHAPE_DESIGN.md`** — current atom schema. This document extends, not replaces.
- **`TRAINING_MEDIA_DESIGN.md`** — consumer of unified schema. §6 training record shape simplifies when streams unify.
- **`PHASE_1_DESIGN.md`** — current drill-down work unaffected; operates on current atom shape; gains PHI attributes transparently.
- **`RecordHealth_App/docs/ARCHITECTURE.md`** — iOS target architecture. Unification aligns with the ExtractionReviewGateway invariant (all AI output flows through gateway before persistence). Unified atom model is what flows through.
- **`RecordHealth_App/docs/DATABASE_LAYOUT.md`** — authoritative for Neon project topology. Unification work targets `RecordHealth-ADI / staging` exclusively; production untouched.

---

## 15. Acceptance — what "v1 unification complete" means

When U.1 through U.5 (plus U.F) land:

- One atom vocabulary, canonically defined, version-pinned across iOS and Worker
- Every meaningful span is an atom; PHI is a flag, not a parallel record type
- FHIR import produces unified atoms with codings preserved
- PDF ingest produces unified atoms via one AI call per document
- ADI grading operates on a unified surface; reviewer corrections produce superseding atom versions
- Training signal (pipeline-vs-reviewer delta) preserved end-to-end via append-only ADI storage and full producer tagging
- Raw FHIR never discarded; unmapped fields logged for future expansion
- `canonical_codes` wired end-to-end; no more dead-lettered coding column
- PHI token map stays on iOS; Worker sees tokens and per-document reverse maps only
- Red overlay semantic preserved; reviewer muscle memory intact
- Production database untouched; all schema work scoped to ADI staging
- Schema version validation at Worker boundary catches drift early

Everything in §13 is deferred with enough context for the next conversation to plan against.

---

**End of v1.0. Shape-not-spec. Ready for sprint commitment.**
