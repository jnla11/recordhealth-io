# CLINICAL_SHAPE_DESIGN.md — GT-1.6 Clinical Shape Extension

**Status:** Design phase. Implementation deferred to GT-1.6a–e sprints.
**Authored:** 2026-04-15 (GT-1.6 design session)
**Supersedes:** The minimal annotation schema deployed in GT-1.

---

## 1. Purpose

Extend the grading tool's annotation schema from a single-row "annotation"
shape into a clinically rich, FHIR-aligned, longitudinally-queryable
data model that supports:

- Multi-region evidence per clinical fact (one fact, many bounding boxes)
- FHIR-shaped clinical metadata per entity kind (status, category, dates, codes)
- Multi-system canonical coding (SNOMED, ICD-10-CM, RxNorm, LOINC, CPT, HCPCS, CVX, NPI, UCUM)
- Resolution workflow distinguishing complete vs in-progress annotations
- Knowledge gap detection as a first-class clinical observation
- Future recursive enrichment as more patient context becomes available
- BioMistral fine-tuning corpus generation

This design is the schema and conceptual model. Implementation is
deferred to GT-1.6a–e and is bounded by the audit findings of GT-1.6b.

---

## 2. Design Principles

**Verbatim is sacred.** The `verbatim_value` field on every data atom
is the exact text from the document, never modified, never normalized.
All clinical interpretation lives in separate fields. This is the
Provenance Doctrine applied to clinical extraction.

**FHIR is the container; terminologies are the contents.** FHIR
defines the resource shapes (Condition, MedicationStatement, etc.).
SNOMED, ICD, RxNorm, LOINC, CPT, HCPCS, CVX, UCUM are the actual
codes that fill those shapes. Both layers are required.

**Append-only canonical codes.** Codes are never modified or removed.
Future enrichment passes add codes; they don't replace them. Each
code carries its own provenance and timestamp.

**Resolution status is orthogonal to confidence.** Confidence is
"how sure am I about what the document says." Resolution status is
"have I done the work to fully tag this." A high-confidence
extraction can still be `needs_lookup` until codes are resolved.

**Many-to-many between atoms and source regions.** One clinical
fact can have many bounding box mentions. One bounding box can be
evidence for multiple clinical facts. The link is a join table.

**Schema supports gaps that the data has, not gaps the system
imposes.** Resolution gaps (incomplete data) are represented by
nullable fields, not entities. Knowledge gaps (clinically meaningful
documentation inconsistencies) are first-class entities.

---

## 3. Three Categories of "Gap"

The design distinguishes three concepts that are sometimes conflated:

**Resolution gaps** — the architectural ground state. Every patient
record is built from fragments. Missing reference ranges, undated
medications, conditions mentioned once with no follow-up — these are
the normal incomplete state of medical records. **Not surfaced as
entities.** Represented by nullable schema fields and empty
canonical_codes arrays.

**Documentation gaps** (knowledge_gap entities, in scope) — internal
inconsistencies in the records that a clinician would want surfaced
during patient interaction. "Patient was on warfarin in 2023, no
current evidence of continuation or discontinuation." Actionable
inside an appointment window. The next reasonable step is "ask the
patient" or "look for the missing document." First-class entities,
lifecycle-tracked.

**Care gaps** (out of scope for GT-1.6) — recommendations against
external clinical guidelines. "Patient is 58, no colonoscopy in 12
years, recommend screening." Crosses from observation into medical
opinion. Requires external knowledge layer (USPSTF, AHA, ADA), risk
calculators, and likely regulatory framing (SaMD territory).
Explicitly excluded from GT-1.6 to preserve the liability boundary.

---

## 4. Entity Kinds

20 entity kinds, grouped by complexity tier. Each kind maps to one
or more FHIR resources, with a defined subset of fields captured for
v1 of the grading tool.

### Tier 1: Simple Identification (5 kinds)

#### `provider`
- **FHIR resource:** Practitioner
- **Fields:**
  - `name_verbatim` — exact text from document
  - `name_normalized` — canonical format: "Last, First MI."
  - `role` — treating | ordering | referring | consulting | performing | primary_care
  - `specialty` — when stated
  - `organization_atom_id` — FK to organization atom when linkable
  - `phi_token` — the {{PHI:PROVIDER:drN}} token used in this document
- **Canonical codes:** NPI (resolved via NPPES API)

#### `organization`
- **FHIR resource:** Organization
- **Fields:**
  - `name_verbatim`
  - `type` — hospital | clinic | urgent_care | lab | imaging_center | pharmacy | insurance | practice | system
- **Canonical codes:** NPI (org-level), via NPPES API

#### `visitDate`
- **FHIR resource:** Encounter (period.start)
- **Fields:**
  - `date` (ISO 8601)
  - `date_type` — service | admission | discharge | follow_up | scheduled
  - `encounter_type` — office_visit | emergency | inpatient | telehealth | procedure | lab_draw

#### `reportDate`
- **FHIR resource:** DiagnosticReport (effectiveDateTime)
- **Fields:**
  - `date` (ISO 8601)
  - `date_type` — authored | issued | received | resulted
  - `report_type` — lab | imaging | pathology | operative | discharge_summary | consultation

#### `coverage`
- **FHIR resource:** Coverage
- **Fields:**
  - `plan_name`
  - `type` — commercial | medicare | medicaid | tricare | workers_comp | self_pay | other
  - `member_id` (PHI token)
  - `group_number`
  - `status` — active | inactive | unknown

### Tier 2: Clinical Observations (4 kinds)

#### `labValue`
- **FHIR resource:** Observation
- **Fields:**
  - `test_name`
  - `value` (numeric or string)
  - `unit` (UCUM)
  - `reference_range`
  - `interpretation` — normal | abnormal | high | low | critical_high | critical_low | indeterminate
  - `specimen_type` — blood | urine | csf | tissue | other
- **Canonical codes:** LOINC (test), UCUM (unit)

#### `vitalSign`
- **FHIR resource:** Observation
- **Fields:**
  - `vital_type` — blood_pressure | heart_rate | respiratory_rate | temperature | oxygen_saturation | weight | height | bmi | pain_scale
  - `value` (numeric)
  - `unit` (UCUM)
  - `interpretation` — normal | abnormal | high | low
  - `body_site` — for BP: left_arm, right_arm, etc.
- **Canonical codes:** LOINC, UCUM

#### `socialHistory`
- **FHIR resource:** Observation (LOINC-coded)
- **Fields:**
  - `category` — smoking | alcohol | drug_use | occupation | exercise | sexual_activity | housing | education | diet
  - `status` — current | former | never | unknown
  - `detail` (verbatim — "1 pack/day x 20 years")
  - `quantity` (when parseable)
  - `duration` (when parseable)
- **Canonical codes:** LOINC (e.g. 72166-2 for smoking status), SNOMED for findings

#### `immunization`
- **FHIR resource:** Immunization
- **Fields:**
  - `vaccine_name`
  - `date_administered`
  - `site` — left_arm | right_arm | left_thigh | right_thigh | oral | intranasal | other
  - `lot_number`
  - `manufacturer`
  - `dose_number`
  - `series` — complete | incomplete | unknown
- **Canonical codes:** CVX (vaccine), RxNorm (product)

### Tier 3: Core Clinical Entities (6 kinds)

#### `symptom`
- **FHIR resource:** Observation (acute) or Condition (chronic-as-problem)
- **Fields:**
  - `clinical_status` — active | recurrence | resolved | unknown
  - `acuity` — acute | chronic | subacute | unknown
  - `severity` — mild | moderate | severe | null
  - `body_site`
  - `onset_date`
  - `duration`
  - `associated_context`
- **Canonical codes:** SNOMED

#### `condition`
- **FHIR resource:** Condition
- **Fields:**
  - `clinical_status` — active | recurrence | relapse | inactive | remission | resolved | unknown
  - `category` — problem_list | encounter_diagnosis | health_concern | historical
  - `severity` — mild | moderate | severe | null
  - `onset_date`
  - `abatement_date`
  - `body_site`
  - `stage` (cancer staging, kidney disease staging, etc.)
- **Canonical codes:** SNOMED, ICD-10-CM

#### `diagnosis`
- **FHIR resource:** Condition (with category=encounter-diagnosis)
- **Fields:**
  - `clinical_status` — active | provisional | differential | confirmed | refuted | ruled_out
  - `category` — encounter_diagnosis | discharge_diagnosis | admitting_diagnosis | principal_diagnosis
  - `severity` — mild | moderate | severe | null
  - `onset_date` (of the underlying condition)
  - `body_site`
- **Canonical codes:** SNOMED, ICD-10-CM

#### `medication`
- **FHIR resource:** MedicationStatement / MedicationRequest
- **Fields:**
  - `status` — active | completed | stopped | on_hold | intended | entered_in_error | unknown
  - `intent` — proposal | plan | order | original_order | documented_history
  - `ingredient` (normalized name)
  - `strength`
  - `dose_form` — tablet | capsule | inhaler | injection | topical | liquid | patch | suppository | other
  - `route` — oral | inhalation | intravenous | intramuscular | subcutaneous | topical | rectal | ophthalmic | other
  - `frequency` (verbatim — "BID," "Q6H PRN")
  - `prn` — true | false
  - `duration` — episodic | short_course | ongoing | unknown
  - `start_date`
  - `end_date`
  - `prescriber_atom_id`
- **Canonical codes:** RxNorm (ingredient + SCD), NDC if visible
- **Critical disambiguation rule:** Same medication name in different
  clinical contexts (history vs current vs prescribed) = different
  data atoms. See §6.

#### `allergy`
- **FHIR resource:** AllergyIntolerance
- **Fields:**
  - `clinical_status` — active | inactive | resolved
  - `type` — allergy | intolerance | sensitivity
  - `category` — food | medication | environment | biologic
  - `criticality` — low | high | unable_to_assess
  - `reaction` (verbatim)
  - `reaction_severity` — mild | moderate | severe
  - `onset_date`
- **Canonical codes:** SNOMED (allergen), RxNorm (medication allergies)

#### `procedure`
- **FHIR resource:** Procedure
- **Fields:**
  - `status` — completed | in_progress | not_done | preparation | on_hold
  - `category` — surgical | diagnostic | therapeutic | counseling | imaging
  - `performed_date`
  - `performed_period_start` / `performed_period_end`
  - `body_site`
  - `laterality` — left | right | bilateral | not_applicable
  - `outcome`
  - `performer_atom_id`
  - `reason_atom_id` (FK to condition/diagnosis)
- **Canonical codes:** SNOMED, CPT

### Tier 4: Relational Entities (4 kinds)

#### `familyHistory`
- **FHIR resource:** FamilyMemberHistory
- **Fields:**
  - `relationship` — mother | father | sister | brother | maternal_grandmother | etc.
  - `condition` (verbatim)
  - `condition_codes` (SNOMED, ICD-10-CM)
  - `onset_age`
  - `deceased` — true | false | unknown
  - `cause_of_death`

#### `device`
- **FHIR resource:** DeviceUseStatement
- **Fields:**
  - `device_name`
  - `type` — implant | external | monitoring | therapeutic | prosthetic
  - `status` — active | completed | removed | entered_in_error
  - `implant_date`
  - `removal_date`
  - `body_site`
  - `laterality`
  - `manufacturer`
  - `model`
- **Canonical codes:** SNOMED, UDI if visible

#### `referral`
- **FHIR resource:** ServiceRequest
- **Fields:**
  - `status` — draft | active | completed | cancelled | entered_in_error
  - `intent` — proposal | plan | order | original_order
  - `priority` — routine | urgent | stat | asap
  - `service_requested`
  - `reason_atom_id`
  - `requester_atom_id`
  - `target_specialty`
  - `target_provider_atom_id`
  - `occurrence_date`
- **Canonical codes:** SNOMED (service), CPT (procedure)

#### `carePlan`
- **FHIR resource:** CarePlan / Goal
- **Fields:**
  - `status` — active | completed | revoked | on_hold | draft | unknown
  - `intent` — proposal | plan | order
  - `category` — treatment | follow_up | monitoring | prevention | education
  - `description`
  - `target_date`
  - `target_value` (e.g. "A1C < 7%," "BP < 130/80")
  - `related_condition_atom_id`
- **Canonical codes:** SNOMED

### Catch-All

#### `uncategorized`
- For document content that has no FHIR home (administrative noise,
  out-of-scope observations, clinically unclear references)
- Only `verbatim_value` and source regions populated
- Reviewer can recategorize to a real entity_kind later

---

## 5. Schema

Postgres syntax. Targets the staging Worker (Neon).

### 5.1 Enums

```sql
CREATE TYPE entity_kind_enum AS ENUM (
  'provider', 'organization', 'visitDate', 'reportDate', 'coverage',
  'labValue', 'vitalSign', 'socialHistory', 'immunization',
  'symptom', 'condition', 'diagnosis', 'medication', 'allergy', 'procedure',
  'familyHistory', 'device', 'referral', 'carePlan',
  'uncategorized'
);

CREATE TYPE resolution_status_enum AS ENUM (
  'confirmed', 'needs_lookup', 'awaiting_review', 'unresolvable'
);

CREATE TYPE region_role_enum AS ENUM (
  'primary_mention', 'restatement', 'tabular_value',
  'cross_reference', 'supporting_evidence', 'co_mention'
);

CREATE TYPE gap_type_enum AS ENUM (
  'discontinuity', 'missing_expected', 'unresolved_reference',
  'temporal_inconsistency', 'other'
);
```

### 5.2 data_atoms

```sql
CREATE TABLE data_atoms (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- Client-supplied IDs accepted on INSERT; default fires only
  -- when caller omits id. iOS HealthFact.id passes through as
  -- data_atoms.id so reviewer corrections in the grading tool
  -- can round-trip to the iOS atom by ID match.
  document_id     UUID NOT NULL,
  patient_id      UUID NOT NULL,
  entity_kind     entity_kind_enum NOT NULL,
  verbatim_value  TEXT NOT NULL,
  clinical_fields JSONB NOT NULL DEFAULT '{}',
  canonical_codes JSONB NOT NULL DEFAULT '[]',
  resolution_status resolution_status_enum NOT NULL DEFAULT 'awaiting_review',
  resolution_notes  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by  TEXT NOT NULL,
  reviewed_at TIMESTAMPTZ,
  reviewer_id TEXT,
  CONSTRAINT data_atoms_resolution_check CHECK (
    (resolution_status = 'confirmed' AND reviewed_at IS NOT NULL AND reviewer_id IS NOT NULL)
    OR resolution_status != 'confirmed'
  )
);

CREATE INDEX idx_data_atoms_document ON data_atoms(document_id);
CREATE INDEX idx_data_atoms_patient ON data_atoms(patient_id);
CREATE INDEX idx_data_atoms_kind ON data_atoms(entity_kind);
CREATE INDEX idx_data_atoms_status ON data_atoms(resolution_status);
CREATE INDEX idx_data_atoms_canonical_codes ON data_atoms USING gin(canonical_codes);
CREATE INDEX idx_data_atoms_clinical_fields ON data_atoms USING gin(clinical_fields);
```

### 5.3 source_regions

```sql
CREATE TABLE source_regions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id   UUID NOT NULL,
  page          INTEGER NOT NULL,
  bbox_x        NUMERIC(8,6) NOT NULL,
  bbox_y        NUMERIC(8,6) NOT NULL,
  bbox_width    NUMERIC(8,6) NOT NULL,
  bbox_height   NUMERIC(8,6) NOT NULL,
  verbatim_text TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by    TEXT NOT NULL
);

CREATE INDEX idx_source_regions_document ON source_regions(document_id);
CREATE INDEX idx_source_regions_doc_page ON source_regions(document_id, page);
```

### 5.4 atom_region_links

```sql
CREATE TABLE atom_region_links (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  data_atom_id     UUID NOT NULL REFERENCES data_atoms(id) ON DELETE CASCADE,
  source_region_id UUID NOT NULL REFERENCES source_regions(id) ON DELETE CASCADE,
  region_role      region_role_enum NOT NULL DEFAULT 'primary_mention',
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by       TEXT NOT NULL,
  UNIQUE (data_atom_id, source_region_id)
);

CREATE INDEX idx_atom_region_links_atom ON atom_region_links(data_atom_id);
CREATE INDEX idx_atom_region_links_region ON atom_region_links(source_region_id);
```

### 5.5 knowledge_gaps

```sql
CREATE TABLE knowledge_gaps (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id  UUID NOT NULL,
  document_id UUID NOT NULL,
  gap_type    gap_type_enum NOT NULL,
  related_atom_ids UUID[] NOT NULL DEFAULT '{}',
  related_concept JSONB,
  question    TEXT NOT NULL,
  suggested_resolution_action TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by  TEXT NOT NULL,
  resolved_at TIMESTAMPTZ,
  resolved_by TEXT,
  resolution_notes TEXT,
  resolution_atom_ids UUID[] NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'open'
);

CREATE INDEX idx_knowledge_gaps_patient ON knowledge_gaps(patient_id);
CREATE INDEX idx_knowledge_gaps_document ON knowledge_gaps(document_id);
CREATE INDEX idx_knowledge_gaps_status ON knowledge_gaps(status);
CREATE INDEX idx_knowledge_gaps_related_atoms ON knowledge_gaps USING gin(related_atom_ids);
```

### 5.6 canonical_codes JSONB shape

Each entry in the `canonical_codes` array on `data_atoms`
represents a terminology code associated with this clinical
fact. Codes are artifacts with provenance, not assertions of
truth. The system holds multiple attestations from different
sources and lets downstream consumers (reviewers, providers,
billing specialists, patients) make informed decisions based
on the full evidence chain.

**Core fields:**

```json
{
  "system": "SNOMED-CT",
  "code": "19030005",
  "display": "Recurrent otitis media",
  "specificity": "exact",
  "derivation": "api_match_with_selection",
  "attestation": "ai_suggested",
  "confidence": 0.88,
  "confidence_basis": "initial_ai_assignment",
  "reasoning": "NLM Clinical Tables returned 3 SNOMED candidates for 'otitis media recurrent'. Selected 19030005 (Recurrent otitis media) over parent concept 65363002 (Otitis media) because the document explicitly states 'recurrent'.",
  "caveats": [
    "Laterality not specified — if bilateral, a more specific SNOMED qualifier applies",
    "Recurrence count not documented — if >=4 episodes/12mo, additional specificity available"
  ]
}
```

**Allowed `system` values:** SNOMED-CT, ICD-10-CM, RxNorm,
RxNorm-IN, LOINC, CPT, HCPCS, CVX, NPI, NDC, UDI, UCUM.

**Allowed `specificity` values:** exact, class_level,
category_level.

**Allowed `derivation` values:**

- `verbatim_from_source` — code was present in the source
  document (FHIR import, printed on PDF)
- `deterministic_api_match` — API returned exact match, no
  interpretation needed
- `api_match_with_selection` — API returned multiple candidates,
  AI or reviewer selected best fit
- `ai_inferred_from_context` — AI derived this from clinical
  reasoning, not direct textual evidence
- `human_assigned` — reviewer typed the code manually

**Allowed `attestation` values:**

- `source_document` — this code appeared in the source artifact
  (FHIR coding, printed on the PDF)
- `provider_documented` — a provider explicitly assigned this
  code in the clinical record
- `api_resolved` — deterministic API match from verbatim text
- `ai_suggested` — AI proposed this based on extraction + context
- `reviewer_assessed` — reviewer evaluated and accepted/modified
- `patient_reported` — patient stated this
- `fhir_import` — code preserved verbatim from a FHIR resource
  at import time (e.g. Apple Health). Deterministic,
  high-confidence, bypasses the ontology lookup service.
- `amended` — a prior attestation was questioned; this entry
  represents the amendment (see amendments array)

**Allowed `confidence_basis` values:**

- `initial_ai_assignment` — confidence is the AI's initial
  score, not yet updated by any subsequent evidence
- `reviewer_assigned` — confidence was set by a human reviewer
- `bayesian_composite` — confidence was computed from the
  attestation_history (future capability; schema supports it
  now, computation deferred)
- `cross_source_corroborated` — confidence was boosted by
  independent corroboration from a different source type

**`reasoning`** (string) — human-readable explanation of how
this code was derived. Powers the "i" button in the reviewer
UI. Stored permanently alongside the code for long-term
explainability. The AI lookup prompt produces this; reviewers
can also add reasoning when manually assigning codes.

**`caveats`** (string array) — explicit uncertainty flags.
Things the AI (or reviewer) identified as unresolved or
potentially incorrect about this code assignment. Surfaced
alongside reasoning in the "i" button. Empty array when no
caveats apply.

**Attestation history and amendments:**

For codes that accumulate evidence over time (cross-source
corroboration, reviewer assessment on top of AI suggestion,
later amendment), the canonical_codes entry carries two
additional arrays:

```json
{
  "attestation_history": [
    {
      "attestation": "ai_suggested",
      "confidence": 0.88,
      "by": "ontology_resolution_v1",
      "by_authority": "ai_pipeline",
      "at": "2026-04-16T22:30:00Z",
      "source_document_id": "abc-123"
    },
    {
      "attestation": "reviewer_assessed",
      "confidence": 0.95,
      "by": "reviewer-jason",
      "by_authority": "domain_informed_non_clinical",
      "at": "2026-04-16T23:00:00Z",
      "action": "confirmed"
    },
    {
      "attestation": "source_corroboration",
      "confidence": 0.97,
      "by": "fhir_import",
      "by_authority": "ehr_system",
      "at": "2026-04-17T10:00:00Z",
      "source_document_id": "def-456",
      "note": "Apple Health FHIR MedicationStatement carried identical coding"
    }
  ],
  "amendments": [
    {
      "prior_code": "H66.90",
      "amended_to": "H66.93",
      "amended_by": "reviewer-jason",
      "amended_by_authority": "domain_informed_non_clinical",
      "amended_at": "2026-04-17T14:00:00Z",
      "reason": "Bilateral documented on page 3. H66.93 is more specific than H66.90."
    }
  ]
}
```

**Allowed `by_authority` values** (for attestation_history
entries and amendments):

- `ai_pipeline` — AI system (lowest initial weight)
- `mechanical_annotator` — basic QA annotator
- `domain_informed_non_clinical` — trained power user without
  medical credentials
- `clinical_data_specialist` — medical degree + data science
- `licensed_clinician` — practicing MD/DO/NP
- `ehr_system` — Epic/Cerner/Athena or similar EHR FHIR export
- `certified_lab` — CLIA-certified laboratory result
- `patient_self_report` — patient-stated information

**Design notes on attestation and amendments:**

- Everything is an artifact with provenance. There is no
  binary "true/false" gate on codes. Healthcare records
  contain what was documented, not what is objectively true.
  The system holds all attestations and lets downstream
  consumers make informed decisions.
- Amendments are append-only. The original code stays in the
  record permanently. An amendment says "here is what we
  believe is more accurate, and here is why." Neither
  overwrites the other. Both are first-class artifacts.
- The top-level `confidence` starts as the AI's initial
  assignment. Future sprints may implement Bayesian composite
  scoring from `attestation_history`, where each new
  attestation updates the score weighted by the attester's
  authority. Until then, `confidence` is either the initial
  AI score or the most recent reviewer's assessment.
  `confidence_basis` indicates which.
- `attestation_history` captures the raw evidence chain.
  The grading tool's scoring logic (GT-5, future) uses
  attestation to determine scoring eligibility: only codes
  where `attestation` is `reviewer_assessed`,
  `source_document`, or `fhir_import` enter the scoring
  corpus. AI suggestions that haven't been reviewed exist
  in the data for workflow and training capture but do not
  count as ground truth for F1 scoring.
- The `amendments` chain is itself high-value training data.
  When a reviewer amends an AI suggestion, the (original,
  amended, reason) triple teaches the future model why its
  suggestion was wrong in this context.

**Fields preserved from prior design (GT-1.5a):**

- `ai_suggested_code` and `ai_suggested_display` — populated
  when a reviewer overrides an AI suggestion (now captured
  more richly in amendments, but preserved for backwards
  compatibility with existing GT-1.5a registrations)
- `resolved_at` and `resolved_by` — still valid as shorthand
  for "when and who last touched this code." The full chain
  lives in attestation_history.

### 5.7 Migration from GT-1 annotations table

The GT-1 annotations table is not auto-migrated. GT-1.6c will deprecate
it via comment, and it will be dropped after GT-2 validates the new
four-table structure. No production data exists in the old table.

```sql
COMMENT ON TABLE annotations IS
  'DEPRECATED in GT-1.6. Use data_atoms + source_regions + '
  'atom_region_links instead. Drop after GT-2 validation.';
```

---

## 6. Clinical Disambiguation: Same Text, Different Atoms

A medication name appearing three times in one document does not mean
one atom with three source regions. Three clinical contexts:

- "Past meds: Albuterol 2018-2020" → atom A: medication,
  status=stopped, intent=documented_history
- "Current meds: (Albuterol absent)" → no atom, but informs that A
  is not currently active
- "Plan: Restart Albuterol 90mcg/inh" → atom B: medication,
  status=intended, intent=plan

**Two distinct data_atoms.** Same `verbatim_value` text patterns,
different `clinical_fields.status` and `clinical_fields.intent`.

The clustering decision in the grading tool is **clinically
conditional, not textual.** A reviewer must distinguish atoms by
clinical meaning, not just by string match. This is part of why
ground truth annotation is expensive — and what makes it ground truth.

---

## 7. Ontology Lookup Service

The grading tool needs a service that takes a verbatim string +
clinical context and returns ranked canonical code candidates.

### 7.1 Two implementation paths, used together

**API path (deterministic, preferred when available):**
- **NPPES** for NPI lookup (providers, organizations) — free, no auth
- **RxNav** for RxNorm — NLM-operated, free, no auth
- **UMLS Metathesaurus** for cross-terminology lookup — free with registration
- **NLM Clinical Tables Search** for ICD-10-CM, LOINC, SNOMED browsing

**AI path (interpretive, for fuzzy or context-dependent matches):**
- Registered prompt: `ontology_resolution_v1` (or similar)
- Inputs: verbatim_value, entity_kind, surrounding source_text,
  sibling atoms in the same document for context
- Output: ranked array of candidate codes with reasoning and
  confidence scores
- Same prompt registry pattern as everything else from GT-1.5a

### 7.2 The lookup is ALSO the BioMistral training target

The ontology_resolution prompt is functionally what the future
locally-deployed BioMistral model will do automatically at extraction
time. The (verbatim, context, reviewer-confirmed-codes) tuples
generated by the grading tool ARE the fine-tuning corpus.

This means:
- The lookup output schema = the future model output schema
- Reviewer overrides on AI suggestions are the highest-signal training data
- The schema captures both AI suggestion and human override (per §5.6)

### 7.3 Reviewer flow

1. AI runs lookup, populates `canonical_codes` with
   `attestation: ai_suggested`, `derivation` per lookup path,
   `reasoning` explaining the resolution chain, and `caveats`
   flagging uncertainty.
2. Reviewer sees suggestions ranked by confidence in the ADI
   tool. Each suggestion has an "i" button that surfaces the
   reasoning and caveats.
3. Reviewer either:
   - Confirms top suggestion → new attestation_history entry
     with `attestation: reviewer_assessed`, `action: confirmed`
   - Amends to a different code → amendment entry with
     prior_code, amended_to, and reason. Original code
     preserved.
   - Types a code manually → new code entry with
     `attestation: reviewer_assessed`,
     `derivation: human_assigned`
   - Marks as unresolvable → attestation stays `ai_suggested`,
     a caveat is added noting the reviewer could not resolve
4. The lookup prompt's self-questioning (caveats and reviewer
   questions) guides the reviewer to the specific decision
   points that need human judgment, reducing the medical
   expertise required for effective review.

### 7.4 FHIR-sourced atoms bypass the lookup

Atoms originating from FHIR imports (Apple Health, EHR portal
syncs, CCDA attachments) come pre-coded by the source system.
Their `coding[]` arrays carry SNOMED, ICD-10-CM, RxNorm, LOINC,
CVX, UCUM, and other terminology codes that are authoritative.

These atoms bypass the AI ontology lookup entirely. At import,
each `coding[]` entry becomes a canonical_codes entry with
`source: fhir_import`, full system + code + display preserved
verbatim from the FHIR resource.

This has two important implications:

1. **Deterministic shortcut.** FHIR-sourced facts skip the
   AI lookup cost and arrive fully coded. Only PDF-extracted
   facts (or other unstructured sources) need the AI lookup.

2. **Free training corpus.** FHIR-sourced (verbatim, code) pairs
   are reviewer-grade training data with zero annotation effort.
   When the BioMistral fine-tuning corpus is assembled, these
   pairs contribute alongside reviewer-confirmed pairs from the
   grading tool.

The iOS FHIR import path (FHIRRecordMapper.swift in the iOS
repo) currently discards `coding[].code` and `coding[].system`,
keeping only `display`. This is a known gap (GT-1.6b finding #2)
and is addressed in GT-1.6c.

---

## 8. Six Grading Dimensions

The schema supports six independent quality dimensions when grading
AI extraction against reviewer ground truth:

1. **Region recall** — did AI find all the source regions?
2. **Region clustering** — did AI correctly group regions onto atoms?
3. **Clinical disambiguation** — did AI distinguish same-text-different-clinical-meaning?
4. **Status accuracy** — did AI assign correct FHIR clinical status?
5. **Code accuracy** — did AI assign correct canonical codes at each terminology level?
6. **Gap detection** — did AI surface knowledge gaps that a reviewer also flagged?

Dimensions 1–5 are extraction quality. Dimension 6 is clinical
noticing — scored by precision (AI-flagged gaps that match
reviewer-flagged) and recall (reviewer-flagged gaps that AI also
flagged), likely recall-weighted.

---

## 9. Future Recursive Enrichment

The schema is designed for the eventual case where new patient
context (new documents, new atoms, new resolved gaps) enriches
existing atoms.

**Code-fill-in-later.** A condition extracted in 2018 with only a
SNOMED code can have an ICD-10-CM code added years later by an
enrichment pass. The `canonical_codes` array is append-only; new
codes carry their own `resolved_at` timestamp. No data is lost.

**Cross-document fact reconciliation.** Multiple atoms across many
documents about the same clinical fact (recurrent OM mentioned in 5
visit notes) should eventually link to a single longitudinal patient
condition record. That higher-level entity is **out of scope for
GT-1.6** but the data_atoms it would be built from must have stable
IDs and richly-coded canonical codes for the linkage to work. This
schema provides both.

---

## 10. Out of Scope (explicitly)

- **Care gaps** (clinical guideline-based recommendations) — see §3
- **Patient-level reconciled fact records** — atoms are document-level;
  patient-level rollups are a future architectural layer
- **Cross-patient cohort analysis schema** — future work
- **Real-time clinical decision support** — Record Health surfaces
  observations, doesn't make medical recommendations
- **Specialized FHIR resources beyond the 19 entity kinds** — Consent,
  AdverseEvent, ResearchStudy, etc. can be added in future sprints
  if document content warrants

---

## 11. Implementation Sprint Decomposition

GT-1.6 design (this document) → execution sprints, in order:

1. **GT-1.6b — Pre-design FactStore audit.** Verify stable atom IDs,
   JSONB query patterns, document-vs-patient fact separation in current
   iOS code. Findings only, no changes. Runs FIRST so findings can
   inform schema deployment. **Status: complete (2026-04-15).**

2. **GT-1.6a — Schema deployment + Worker endpoints + auth.**
   Run CREATE TYPE / CREATE TABLE statements on staging Worker
   (data_atoms, source_regions, atom_region_links, knowledge_gaps).
   Build Worker endpoints for atom + region + link CRUD, with auth
   model supporting both isADIAdminAuthorized (for grading tool
   reviewer writes) and a separate iOS-write auth (for ingest
   pipeline writes). Smoke test with manual insert/query.
   **Status: Complete (2026-04-16).** Schema deployed, 12 CRUD
   endpoints live, smoke tests passing.

3. **GT-1.6c — Pass 2 prompt v2 + FactKind expansion + FHIR coding capture.**
   Three coordinated changes:
   - Add familyHistory, immunization, socialHistory, device, referral,
     carePlan, coverage to the entity_kind enum in the Pass 2 prompt.
     Update extraction rules. Bump pass2_extraction to v2 in the
     prompt registry.
   - Expand iOS FactKind enum with the same seven new cases.
   - Update FHIRRecordMapper to capture `coding[].code` and
     `coding[].system` (not just display). Persist as a structured
     codes field on FHIRImportCandidate that propagates to FactStore.
   The three are bundled because AI output, iOS types, and FHIR
   imports must all agree on the expanded entity kind set.
   **Status: Complete (2026-04-16).** v2 prompt registered, FactKind
   expanded, FHIR coding capture live through FHIRBackgroundObservation.
   FactStore threading deferred to GT-1.6e.

4. **GT-1.6d — Ontology lookup service.** Worker endpoint +
   ontology_resolution_v1 prompt registration + API integrations
   (NPPES, RxNav, UMLS, NLM Clinical Tables Search). MUST land
   before GT-2 — the non-medical reviewer cannot annotate without
   lookup support. FHIR-sourced atoms bypass this service entirely
   per §7.4.
   **Status: Complete (2026-04-16).** Lookup endpoint live,
   agent traces captured, all smoke tests passing.

5. **GT-2 — PDF annotation drawing in ADI console.** Builds
   against GT-1.6a/c/d. First user-visible grading tool feature.

6. **GT-1.6e — iOS data model + SourceRegion persistence.** Update
   FactStore types to match the new schema. Update DeduplicationEngine
   (currently EntityReconciliationService) to handle the many-to-many
   atom/region relationship. **Mandatory:** persist `sourceRegion`
   from PendingInterpretation through `writeToFactStore` into a new
   field on FactProvenance (or HealthFact). The data is already
   extracted today but discarded at acceptance — closing this gap is
   the most important iOS refactor in GT-1.6 (per GT-1.6b finding #7).
   Can run in parallel with GT-2 once GT-1.6a lands.

---

## 12. Open Questions

These are intentionally unresolved and will be addressed in
implementation sprints:

- **NPI confidence threshold for auto-confirmation.** What confidence
  level is high enough to mark `source: api_lookup` rather than
  `source: ai_suggested`? Likely 0.95+ for exact name + specialty +
  state matches.

- **AI ontology lookup model selection.** Bedrock Claude Sonnet (same
  as Pass 2) or a cheaper model? Lookup happens many times per
  document; cost vs accuracy tradeoff worth measuring.

- **Reviewer UX for many-to-many atom/region linking.** How does the
  ADI tool let a reviewer say "these 5 boxes are evidence for this
  one atom" efficiently? Likely a click-to-attach pattern after the
  atom is created, but exact UX is GT-2 scope.

- **Knowledge gap detection prompt.** Separate from extraction or
  combined? Initial assumption: separate prompt that runs after
  extraction completes, sees all atoms, surfaces gaps. To be
  designed in GT-1.6d or a follow-on sprint.

- **Migration path for atoms whose entity_kind is later determined
  to be wrong.** If an atom is created as `condition` and later
  reclassified as `diagnosis`, do we mutate the row or create a
  new atom and deprecate the old? Provenance favors the latter but
  doubles row count for what's conceptually a correction.

- **Existing PDF text layers vs Vision re-OCR.** When a PDF arrives
  via FHIR import (e.g. CCDA attachments, DiagnosticReport
  presentedForm) it may already contain a high-quality text layer
  from the source EHR. The current PageCodex architecture may be
  Vision-OCRing all PDFs unconditionally, discarding existing text
  layers and introducing OCR errors that didn't exist in the
  original. A separate audit is needed to confirm whether this is
  happening and, if so, to design a "use existing text layer when
  present, fall back to Vision OCR otherwise" pattern. Out of
  GT-1.6 scope but flagged here for follow-up.
