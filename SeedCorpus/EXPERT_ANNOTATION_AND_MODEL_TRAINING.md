# Expert Annotation and Model Training
## Record Health — Stage Progression Specification

**Document version:** 1.3
**Status:** Strategic + pre-implementation spec
**Supplements:** ADAPTIVE_DOCUMENT_INTELLIGENCE.md, SEED_CORPUS_AND_TAXONOMY.md
**Governs:** Expert annotation operation, proficiency ladder, fine-tuning strategy, document comprehension model, clinical reasoning layer, Stage 4 private instance three-role architecture, LLM-powered PHI tokenization, MIMIC-IV as jumpstart, Tier 3 research consent framework, Stage 4b consented corpus training, business stage progression, regulatory milestones
**Companion documents:** ADAPTIVE_DOCUMENT_INTELLIGENCE.md v2.2, SERVER_INFRASTRUCTURE.md v1.1, SEED_CORPUS_AND_TAXONOMY.md v1.2, SEED_CORPUS_STARTER_KIT.md v1.4, FUNCTION_DISTINCTION.md v1.0
**CRITICAL OVERRIDE:** FUNCTION_DISTINCTION.md supersedes the assumption in sections 1.1 and 2.1 of this document that user corrections are a meaningful cross-user training signal. User corrections feed on-device personal calibration (Layer 3 MLUpdateTask) and anomaly detection review only. The expert annotation operation described in sections 3–5 is the sole source of cross-user training data. See FUNCTION_DISTINCTION.md sections 1–3 before implementing any component in this document.

---

## 1. Strategic Framing

### 1.1 The Core Reframe

**UPDATED:** The original framing of this section described user corrections as a training
signal that feeds the cross-user learning system. That model is superseded.
See FUNCTION_DISTINCTION.md section 1 for the authoritative statement.

The corrected model in one paragraph: The training loop is entirely offline and
expert-driven. Expert annotations are the sole source of cross-user training data.
User corrections feed on-device personal calibration (personal MLUpdateTask, Layer 3)
and anomaly detection review only. What lands on device is pre-validated intelligence
produced by the offline loop — rules and model weights that were benchmarked against
expert-annotated ground truth before any user saw them.

The ADI architecture was designed assuming users could act as reliable correction agents
for cross-user training. That assumption fails for the failure modes with the highest
clinical stakes — structural failures invisible to the reading eye, semantic failures
requiring medical domain knowledge, and silent non-recognition. The correction quality
problem is not a UI problem. It is a comprehension problem.

This document addresses that gap through a permanent expert annotation operation and
a four-stage model training progression that builds from the rule engine the app
launches with toward clinical reasoning capability that interrogates the medical
establishment with patient data as evidence.

**What users do and don't do:**

```
Users DO:
├── Upload documents → on-device extraction runs
├── Read their extracted health data
├── Flag something that looks wrong → anomaly_flags table
└── Benefit from the system getting smarter (invisibly, in background)

Users DO NOT:
├── Correct extractions that feed cross-user training
├── Interact with correction class forms (admin tool only)
├── Train the PatternLibrary through their corrections
└── Need to do anything for the system to improve
```

**The personal calibration exception:**
User corrections do feed one learning system — the on-device personal MLUpdateTask
(Layer 3). This is purely personal: learns the user's specific providers, their
scan quality, their document sources. These weights never leave the device and
never contribute to cross-user intelligence. This layer improves the experience
for that specific user only.

### 1.2 Stages 1–3 Are a Capital and Corpus Engine

Stages 1 through 3 are not a slower version of Stage 4. They are a deliberate accumulation operation that makes Stage 4 possible without burning the company down getting there.

```
Stage 1   Data vacuum + rule refinement + user trust + subscription revenue
Stage 2   Corpus depth + fine-tuned model + institutional conversations open
Stage 3   Document-level comprehension + API surface + partnership revenue
Stage 4   Clinical reasoning + evidence-based interrogation + category shift
```

Every user who subscribes funds annotation hours. Every correction is a training example. Every PatternLibrary promotion is a proof point for the partnership conversation. Every institutional pilot at Stage 3 is the revenue line that funds the L5 researcher at Stage 4.

The arms race framing — competitors spending tens of millions on clinical LLMs from the top down — is a false frame for Stages 1–3. They are solving a different problem. You are not competing with a research-grade clinical model at Stage 1. The race doesn't start until Stage 4, and by then the corpus built from real patient document chaos is the asset no competitor can acquire by any means other than time.

### 1.3 The Stage 4 Thesis

Stage 4 is a category shift, not a feature upgrade. Every stage prior is patient-side: helping users understand what their documents say. Stage 4 flips the direction of interrogation — using accumulated patient data, clinically validated extraction, and evidence-based medical knowledge to interrogate what should have been done versus what was done.

That is a different company at a different valuation with a different acquirer profile. It requires regulatory engagement, institutional partnership, and a corpus that took years to build. None of those things are available at launch. All of them are earned through Stages 1–3.

---

## 2. The Annotation Problem in Full

### 2.1 What Users Can Actually Correct

Stratified by reliability, not by frequency:

```
High user reliability — binary, surface-legible failures
├── d1_alphanumericSubstitution    "this says 14O, it should be 140"
├── d1_punctuationDropout          "missing decimal — 1400 should be 140.0"
├── d2_numericFormatVariant        "this value is wrong"
├── d2_dateFormatVariant           "wrong date"
└── Simple value mismatches where the error is visually obvious

Medium user reliability — requires recognition of own data
├── d2_terminologyVariant          "Gluc means Glucose"
├── d2_brandToGenericFailure       "Glucophage is metformin"
└── — Most patients know their medications; fewer know lab codes

Low user reliability — structurally invisible or domain-gated
├── d2_columnMisattribution        user cannot see the column structure
├── d2_referenceRangeCollision     most users don't know reference ranges exist
├── d2_labelValueInversion         invisible in the review surface
├── d2_sectionBoundaryFailure      no surface manifestation
├── d2_impliedUnitContext          requires knowing the unit should be there
├── d2_negationMisparse            "no evidence of X" → X present — invisible
├── d2_qualifierDropout            "borderline" stripped — subtle, invisible
└── d2_contextualAbbreviationCollision  requires clinical disambiguation

Zero user reliability — silent non-recognition
└── The atom was never extracted. The user sees a complete-looking extraction.
    There is no empty chair at the table. No UI surface addresses this.
    Only a human with the source document AND extraction output, comparing both,
    can detect what is missing. This is the most dangerous failure class.
```

### 2.2 The "Yes But" Correction Classes

Beyond binary corrections, medical documents require structured multi-part corrections that users cannot reliably produce and the current correction schema cannot capture:

**Class A — Correct value, wrong label**
"Glucose is correctly extracted as 140, but it's been associated with the Sodium field."
Requires: understanding that value and label are a semantic unit, not independent atoms.

**Class B — Correct atoms, wrong association**
"Creatinine 1.4 and eGFR 45 are both correctly extracted but shouldn't be linked — they're from different encounters."
Requires: clinical context about what co-occurrence means.

**Class C — Correct extraction, missing qualifier**
"Glucose 140 is correct, but the extraction dropped 'fasting' from 'Fasting glucose 140.'"
Requires: understanding that the qualifier changes clinical interpretation.

**Class D — Locally correct, globally incoherent**
"Every field is individually correct but the document section is a differential diagnosis, not a confirmed diagnosis list."
Requires: document-level comprehension of clinical document structure.

**Class E — Silent absence**
"Creatinine appears on page 2 and was never extracted. There is no extraction record to flag."
Requires: a human comparing source and output explicitly looking for gaps.

These correction classes define the annotation schema. The structured output format for expert annotations must capture all five — not just the correction value but the correction class, the clinical rationale, and the document context that informs the judgment.

---

## 3. Proficiency Ladder

Six levels, each with distinct capability, cost, and stage applicability. The lean startup path begins at L0 and earns each level as the business generates the capital and corpus quality to justify it.

### L0 — Founder (You)

**Role in the operation:** Manual seed corpus review. False positive flagging. Miscategorized atom identification. Pipeline smoke testing. Architectural coherence review.

**Why L0 is high signal:** You hold the full context of every pipeline decision — the provenance doctrine, the PHI stripping logic, the confusion class taxonomy, the reasons specific architectural choices were made. An L1 annotator following a checklist can flag "this value looks wrong." You can flag "this extraction violated the column attribution rule we built for lab reports because the provider layout hash doesn't match any known LabCorp fingerprint." That is categorically different signal.

**Stage applicability:** Stage 1 (primary), Stage 2 (senior review, edge case escalation)

**Cost:** $0 cash. High founder time — front-load this before launch, not after.

---

### L1 — Trained Annotator

**Role in the operation:** Binary and structured corrections at volume. Follows annotation guidelines written by L0/L2. Does not require medical domain knowledge. Reviews extraction output against source document for obvious mismatches.

**What they can do:** Flag wrong values, mismatched labels, obvious format errors, missing fields that are visually present in the source document.

**What they cannot do:** Detect clinically incoherent associations, interpret negation in clinical narrative, distinguish differential from confirmed diagnosis sections, notice that a "correct" value has the wrong unit implied by column context.

**Sourcing:** Scale AI, Surge AI, direct contractor platforms. For medical document annotation, a brief training protocol (2–4 hours) on document structure and annotation guidelines is required before they produce usable output. First 50 annotations from any new L1 annotator are reviewed by L0/L2 before entering the corpus.

**Stage applicability:** Stage 1, Stage 2 (volume work), Stage 3 (simple field corrections only)

**Cost:** $15–25/hour. At 10 hours/week that's $600–1,000/month for meaningful annotation velocity.

---

### L2 — Data Scientist

**Role in the operation:** Pattern anomaly detection across the corpus. Identifies systematic failure modes the rule engine isn't catching — clusters of similar errors that haven't surfaced in user corrections. Drives the fine-tuning process: dataset formatting, training runs, evaluation metrics, model behavior analysis.

**What they add:** The bridge between annotation data and model behavior. Can identify that 23% of lab report extractions from a specific layout cluster are consistently miscategorizing reference ranges as result values — a pattern invisible to L0/L1 because individual corrections don't cluster visibly. Designs the fine-tuning dataset structure, runs training experiments, interprets evaluation results.

**Medical credential requirement:** None. Requires strong ML/NLP experience and willingness to learn medical document domain specifics on the job. A generalist ML contractor who has worked on document processing or information extraction is the right profile.

**Engagement model:** Contractor, 10–20 hours/week at Stage 2. Likely moves to part-time hire at Stage 3 if budget allows.

**Stage applicability:** Stage 2 (primary), Stage 3 (primary), Stage 4 (supporting L5)

**Cost:** $80–150/hour. At 15 hours/week, $5,000–9,000/month.

---

### L3 — Medical Practitioner

**Role in the operation:** Clinical context the annotation guidelines can't anticipate. Reviews edge cases flagged by L2 as anomalous. Answers "is this clinically coherent?" for association errors and complex "yes but" corrections. Validates that the extraction captures the clinical meaning, not just the surface value.

**What they add:** The clinical reading of a document. A physician looking at a lab report reads it differently than a data scientist — they see what should be present, what the values imply in combination, what the section structure means clinically. They catch Class B (association errors) and Class D (global incoherence) corrections that L2 cannot.

**Engagement model:** Medical advisor at equity (preferred at Stage 2 — aligns incentives, minimizes cash) or hourly contractor for specific annotation sessions. Does not need to be a data scientist. Needs to read medical documents the way a clinician reads them. Primary care physician, hospitalist, or internist with broad document exposure is ideal.

**Time commitment:** 4–8 hours/month at Stage 2. Increases to 10–20 hours/month at Stage 3.

**Stage applicability:** Stage 2, Stage 3, Stage 4

**Cost:** $100–300/hour cash, or equity equivalent. Physician advisor arrangements typically 0.1–0.5% equity at seed stage.

---

### L4 — Medical Informaticist

**Role in the operation:** Rare combination of clinical knowledge and health data systems expertise. Understands LOINC, RxNorm, SNOMED-CT, ICD-10, and HL7/FHIR at depth. Can design annotation schemas for complex clinical document structures. Validates terminology normalization at scale. Evaluates whether extracted data is correctly mapped to public ontologies.

**What they add:** The linchpin of Tier A annotation quality for Stages 3–4. Can evaluate whether an extraction is not just locally correct but correctly situated within the broader clinical knowledge landscape. Designs the cross-page context annotation schema for Stage 3. Validates that the fine-tuned model's terminology normalization is clinically defensible.

**Engagement model:** Specialist contractor at Stage 3. Academic partnership or fractional hire at Stage 4. Not available on equity terms at seed stage — this profile has too many options.

**Stage applicability:** Stage 3 (primary), Stage 4 (supporting L5)

**Cost:** $150–250/hour. Engaged for specific annotation design sprints and model evaluation sessions, not continuous.

---

### L5 — Clinical LLM Researcher

**Role in the operation:** PhD-level. Designs the clinical reasoning layer training regimen. Validates model outputs against clinical outcomes in MIMIC-IV. Understands failure modes of large language models on medical text. Publishes findings — academic credibility is a business asset at Stage 4.

**What they add:** The research rigor required for Stage 4 clinical claims. Designs the evaluation framework against MIMIC-IV outcomes. Identifies when the model is confidently wrong in ways that L3/L4 wouldn't catch. Positions the company's clinical intelligence capability in the research literature — which matters for regulatory submissions and institutional partnerships.

**Engagement model:** Academic partnership (researcher at a university medical center brings institutional credibility and may come with grant funding), significant equity stake, or post-Series A hire. Not a bootstrap operation. This is the Stage 4 milestone, not a pre-launch resource.

**Stage applicability:** Stage 4

**Cost:** $200–400/hour cash, or 0.5–2% equity pre-Series A, or funded through academic partnership grant.

---

## 4. Annotation Operation by Stage

### 4.1 Annotation Mix

Each stage uses a different blend of proficiency levels. The mix shifts from self-directed toward specialist-heavy as capabilities rise and revenue funds escalation.

```
Stage 1:  L0 50% / L1 40% / L2 10% (spot anomaly review)
Stage 2:  L0 10% / L1 30% / L2 30% / L3 25% / L4 5%
Stage 3:  L1 10% / L2 30% / L3 30% / L4 30%
Stage 4:  L3 25% / L4 35% / L5 40%
```

### 4.2 Annotation Output Format

The structured annotation format captures all five correction classes. This format is the fine-tuning dataset record — not just a correction log.

```json
{
  "annotationId": "uuid",
  "documentId": "uuid",
  "annotatorLevel": "L3",
  "annotatorId": "hashed",
  "annotationDate": "ISO-8601",
  "sourceRegion": {
    "pageIndex": 2,
    "boundingBox": { "x": 0.12, "y": 0.34, "w": 0.45, "h": 0.08 },
    "regionType": "labTableValueColumn"
  },
  "extractionOutput": {
    "fieldType": "numericLabValue",
    "extractedValue": "140",
    "associatedLabel": "Sodium",
    "unit": "mEq/L",
    "confidence": 0.71
  },
  "correctionClass": "A",
  "correctionDetail": {
    "isExtractedValueCorrect": true,
    "correctLabel": "Glucose",
    "correctCanonicalId": "LOINC:2345-7",
    "correctUnit": "mg/dL",
    "unitConversionRequired": false
  },
  "clinicalRationale": "Value position in column 3 maps to Glucose per document layout fingerprint. Sodium appears in column 1. Column misattribution due to crowded tab stop layout.",
  "negativeSpaceFlags": [],
  "documentContextNotes": "Multi-panel chemistry report. Section header 'Basic Metabolic Panel' on page 1 applies to this page 2 table — cross-page context required.",
  "annotationQualityFlags": [],
  "requiresL4Review": false
}
```

**Negative space annotation** (Class E — silent absence) uses a separate record format:

```json
{
  "annotationId": "uuid",
  "annotationType": "negativeSpace",
  "documentId": "uuid",
  "annotatorLevel": "L3",
  "missingField": {
    "fieldType": "numericLabValue",
    "canonicalId": "LOINC:2160-0",
    "canonicalName": "Creatinine",
    "expectedRegion": { "pageIndex": 2, "approximateBoundingBox": {...} },
    "visuallyPresent": true,
    "extractionRecord": null
  },
  "clinicalSignificance": "high",
  "clinicalRationale": "Creatinine present at page 2, line 14. No extraction record exists. Value 1.4 mg/dL with reference range 0.7–1.3. Abnormal — clinically significant absence."
}
```

### 4.3 Annotation Volume Targets by Stage

These are milestones, not fixed thresholds. The transition gates open when quality and diversity are sufficient, not when a number is hit. Numbers are benchmarks for planning annotation operation pace.

```
Stage 1 → Stage 2 gate:
├── 1,000 annotated documents minimum
├── At least 500 Tier A (L3 reviewed) records
├── Coverage across 5 document categories
├── At least 10 distinct providerLayoutHash values
└── Negative space annotation pass completed on 20% of corpus

Stage 2 → Stage 3 gate:
├── 3,000 annotated documents
├── At least 1,500 Tier A records
├── Fine-tuned extraction model outperforms rule engine on test silo
├── "Yes but" correction class distribution across all 5 classes
└── L4 informaticist has reviewed and approved annotation schema

Stage 3 → Stage 4 gate:
├── 7,000+ annotated documents
├── Majority Tier A
├── Document-level model validated on multi-page test silo documents
├── PhysioNet MIMIC-IV credentialed access active
├── Local inference infrastructure operational
└── Institutional partnership or funding secured for Stage 4 operation
```

### 4.4 Estimated Annotation Costs

These are operational cost estimates, not projections. Actual costs depend on annotation velocity and proficiency mix decisions.

```
Pre-launch seed corpus build (Stage 1 foundation):
├── L0 time (founder): uncosted — high value, front-load before launch
├── L1 contractors: 200–400 hours at $15–25 = $3,000–10,000
└── L2 spot review: 20–40 hours at $80–150 = $1,600–6,000
Total pre-launch: $5,000–16,000

Stage 2 annotation operation (monthly, ongoing):
├── L1 volume: 40 hrs/month at $20 = $800/month
├── L2 data scientist: 60 hrs/month at $100 = $6,000/month
├── L3 practitioner: 8 hrs/month at $200 = $1,600/month (or equity)
└── L4 informaticist: 8 hrs/month at $200 = $1,600/month (periodic)
Steady-state monthly: $8,000–12,000

Stage 3 annotation operation (monthly):
├── L2 data scientist: 80 hrs/month at $100 = $8,000/month
├── L3 practitioner: 20 hrs/month at $200 = $4,000/month
├── L4 informaticist: 30 hrs/month at $200 = $6,000/month
└── L1 supporting: 20 hrs/month at $20 = $400/month
Steady-state monthly: $18,000–25,000

Stage 4 annotation operation (monthly):
├── L3 practitioner: 40 hrs/month at $200 = $8,000/month
├── L4 informaticist: 60 hrs/month at $200 = $12,000/month
├── L5 researcher: 60 hrs/month at $300 = $18,000/month (or equity/grant)
Steady-state monthly: $35,000–50,000+
Note: Stage 4 is not a bootstrap operation. Revenue from Stage 3 API
licensing or institutional partnership funding is the prerequisite.
```

---

## 5. Model Training Progression

### 5.1 Stage 1 — Rule-Based Extraction with ADI Feedback

**What it is:** The launch architecture. Preprocessing pipeline, VisionKit OCR, layout understanding rules, semantic parsing rules, FactStore ingest. ADI consensus engine promotes user corrections to PatternLibrary. On-device MLUpdateTask for personal calibration.

**Ceiling:** The rule engine ceiling. Cannot generalize beyond its training distribution. Cannot detect silent non-recognition. Cannot reason about clinical meaning. Cannot handle correction Classes B, C, D, E.

**Training input:** Seed corpus (manually built pre-launch). User corrections via ADI pipeline. No model fine-tuning at this stage.

**What improves over time:** PatternLibrary version. Optical failure coverage (Domain 1). Terminology normalization for known variants (Domain 2). Provider layout fingerprint coverage.

**What does not improve:** Structural and semantic failure modes requiring medical domain knowledge. Silent non-recognition. Clinical coherence.

**Infrastructure:** Existing iOS app + Cloudflare Worker + Neon Postgres. No new model infrastructure required.

---

### 5.2 Stage 2 — Fine-Tuned Extraction Model

**What it is:** A small language model fine-tuned specifically for medical document field extraction, replacing the rule engine for document categories it covers. Trained on expert-annotated examples with structured output including correction class, clinical rationale, and negative space flags.

**Architecture:** Task-specific extraction model. Input: document region image + surrounding context + document category + provider layout fingerprint. Output: structured extraction with field type, value, canonical ID, unit, confidence, and correction class prediction. Separate model heads per document category (lab reports, discharge summaries, prescriptions, EOBs) for efficiency.

**Training dataset:** Expert-annotated corpus from the annotation operation. 1,000–3,000 training examples minimum per document category before fine-tuning produces reliable improvement. All training examples are Tier A (L3 reviewed) or Tier B (L2 reviewed with L3 spot check). Tier C (L1 only) examples are excluded from fine-tuning data — they're used for rule engine improvement only.

**Fine-tuning approach:** Start from a capable base model with strong document understanding. LoRA or QLoRA for parameter-efficient fine-tuning — minimizes compute cost while preserving base model capabilities. Evaluate against held-out validation silo. Gate against test silo before deployment.

**New failure modes addressed:**
- d2_columnMisattribution (with sufficient annotated examples)
- d2_referenceRangeCollision
- d2_labelValueInversion
- d2_negationMisparse
- d2_qualifierDropout
- Silent non-recognition (negative space prediction)

**Infrastructure additions:** Fine-tuning pipeline (cloud GPU, periodic runs, not continuous). Model versioning alongside PatternLibrary versioning. Model evaluation harness against corpus test silo. On-device CoreML export for inference (model runs on device — PHI never sent to inference endpoint).

**MIMIC dependency:** MIMIC-IV text content useful for terminology coverage at Stage 2. PhysioNet DUA signed (already in progress under Tenavet LLC). MIMIC data processed locally — never transmitted to third-party APIs per PhysioNet LLM policy.

---

### 5.3 Stage 3 — Document-Level Comprehension Model

**What it is:** The extraction model expands from region-level to document-level context. It reads the full document before extracting any field — understanding section structure, page continuity, and implicit context across pages. Multi-page context loss, section boundary failures, and implied unit context become addressable because the model sees the whole before extracting the parts.

**Architecture:** Document encoder + field extractor. The document encoder processes the full document (all pages) and produces a document-level representation capturing section hierarchy, page relationships, and running context. The field extractor uses this representation alongside region-level features to produce extractions informed by whole-document understanding.

**Training dataset:** Documents annotated at the document level — not just field level. Annotation captures section relationships, cross-page dependencies, and document structure. Requires L4 medical informaticist to design annotation schema and validate that document-level annotations correctly capture clinical document structure. 3,000–7,000 training examples.

**New failure modes addressed:**
- d2_multiPageContextLoss
- d2_sectionBoundaryFailure
- d2_nestedTableFailure
- d2_reflowArtifact (with document context)
- d2_impliedUnitContext (inferred from document-level column headers)
- Correction Class D (global incoherence — model reads the whole document before judging any field)

**Infrastructure additions:** Document-level inference pipeline. Increased context window requirement. Model chunking strategy for very long documents. API packaging for institutional licensing.

**Business inflection:** Stage 3 capability opens the institutional market. The API surface becomes a real revenue line. Health system archival digitization, legal medical record review, insurance document processing, EHR import tools — none of these buyers care about the consumer app. They care about document-level extraction accuracy at scale. Stage 3 is the product they will pay for.

---

### 5.4 Stage 4 — Clinical Reasoning Layer

**What it is:** A second model pass that evaluates the Stage 3 extraction output for clinical coherence. It does not re-extract — it reasons. Does this creatinine value make sense alongside this eGFR? Does this medication dosage make sense for the patient context in this document? Does this diagnosis appear in a differential section or a confirmed diagnosis list? Are these two atoms from the same encounter or different ones?

**The category shift:** Every stage prior is patient-side interpretation — helping users understand what their documents say. Stage 4 enables the interrogation to run in the other direction. A corpus of patient records, extracted with clinical precision, annotated with expert ground truth, and validated against MIMIC-IV outcomes, becomes a tool for asking: what should have been done, and was it done?

That is evidence-based medicine applied to individual patient records at scale. It is the foundation of a clinical decision support product, a quality-of-care analysis tool, a population health intelligence platform. It is a different company.

**Architecture:** Clinical reasoning model trained on MIMIC-IV outcomes. Input: structured extraction output from Stage 3 model + patient context from FactStore (longitudinal, across documents). Output: coherence scores per extracted field, association validity flags, clinical plausibility ratings, anomaly signals where extracted data contradicts expected clinical patterns.

**Training requirement:** MIMIC-IV clinical datasets (PhysioNet credentialed access, already in progress) are the Stage 4a bootstrap — the best available public training signal for clinical reasoning. MIMIC is the jumpstart, not the destination. See section 5.6 for Stage 4b, where consented patient records from your own user base supersede MIMIC as the primary training source. Locally deployed inference throughout — PhysioNet LLM policy explicitly prohibits sending MIMIC data through third-party APIs. Requires private VPC inference infrastructure.

**L5 researcher role:** Designs training regimen. Validates against MIMIC-IV outcomes. Identifies failure modes of the reasoning model — cases where it is confidently wrong in clinically significant ways. Publishes findings in medical informatics literature — academic credibility is a regulatory and partnership asset.

**New capability class:**
- Cross-atom coherence validation
- Association error detection (Correction Class B at scale)
- Clinical plausibility scoring
- Longitudinal pattern analysis across encounters
- Differential vs confirmed diagnosis distinction
- Outcome-referenced extraction validation

**Regulatory milestone:** At Stage 4 capability, FDA Software as a Medical Device (SaMD) classification is no longer a future consideration — it is an active requirement if clinical decision support claims are made. Engage regulatory counsel at Stage 3, not Stage 4, so the regulatory strategy is in place before the product crosses the line.

**Infrastructure additions:** Private VPC or on-premises GPU infrastructure for MIMIC training and inference. Clinical reasoning model versioning separate from extraction model versioning. Regulatory documentation pipeline (software development lifecycle artifacts required for FDA submission). HIPAA Business Associate Agreements with institutional partners. See section 5.5 for the full three-role private instance architecture.

---

### 5.5 Stage 4 — Private Instance Architecture: Three Roles

The Stage 4 private AWS instance is not solely a clinical reasoning server. It serves three distinct roles that together constitute the full PHI boundary and reasoning stack. All three run on the same private infrastructure. Nothing raw crosses any external boundary.

```
PRIVATE AWS INSTANCE
────────────────────────────────────────────────────────────
Role 1   PHI Gateway          ← new framing, replaces on-device only
Role 2   Clinical Reasoning   ← original Stage 4 capability
Role 3   Escalation Handler   ← Bedrock orchestration with clean boundary
────────────────────────────────────────────────────────────
```

#### Role 1 — PHI Gateway (LLM-Powered Deep Tokenization)

The current on-device tokenizer is rule-based — it catches what the rules know about. It misses what it doesn't: novel PHI formats, contextually implicit identifiers, and combinations of individually benign fields that become identifying together.

At Stage 4 the private instance becomes the authoritative PHI boundary. Documents arrive from the device, pass through a two-pass tokenization pipeline, and only the tokenized output proceeds downstream.

**Pass 1 — Structural validation (fast, pattern-based):**

The existing on-device tokenizer output is validated. All rule-based tokens are confirmed correctly applied. Any structural tokens the device missed are added. This pass is pattern matching — fast, deterministic.

**Pass 2 — Semantic PHI detection (LLM inference):**

The partially-tokenized document passes through the private LLM. The model identifies residual PHI that rules cannot catch:

```
What rule-based tokenization misses:
├── "The patient presented on the Tuesday after Thanksgiving"
│   — Temporal reference with no standard date format
│
├── "Dr. Smith at the Palo Alto clinic"
│   — Provider name + location = re-identification risk
│
├── "She works as a firefighter in Station 12"
│   — Occupation + specific unit = quasi-identifier
│
├── "Her daughter, who is also a patient here"
│   — Family relationship = indirect identifier
│
├── Combination quasi-identifiers
│   "45-year-old male, rare metabolic condition, rural Montana"
│   — No single field is PHI, but the combination is
│
└── Implicit temporal references
    "Three weeks after the hurricane"
    — Timeframe without explicit date
```

After Pass 2, every identifiable element is tokenized. The raw document content stays within the private instance perimeter. The tokenized output is what flows to Neon, the PatternAtom pipeline, and all downstream services.

**Audit trail:**

Every document processed by the gateway is logged:

```sql
-- Add to private instance schema
phi_gateway_log (
    id                      UUID PRIMARY KEY,
    processed_at            TIMESTAMPTZ,
    document_hash           TEXT,       -- SHA-256 of raw input
    tokenized_hash          TEXT,       -- SHA-256 of tokenized output
    tokens_applied          JSONB,      -- what was detected and tokenized
    pass1_token_count       INT,
    pass2_token_count       INT,        -- additional tokens found by LLM pass
    pass2_detections        JSONB,      -- what the LLM found that rules missed
    processing_ms           INT,
    document_category       TEXT
)
```

This log is the HIPAA compliance audit trail. It proves at any point in a compliance review what PHI entered the system and what was released downstream. The difference between asserting HIPAA compliance and demonstrating it.

#### Role 2 — Clinical Reasoning Layer

Unchanged from the original Stage 4 specification. Receives structured extraction output from FactStore (already tokenized, produced by the Stage 2/3 on-device models). Runs MIMIC-trained coherence validation. Returns flags and plausibility scores.

Input is structured JSON — never raw documents. The gateway ensures raw content never reaches this layer.

```
Input:  { fieldType, canonicalId, value, unit, confidence, associations[] }
Output: { coherenceScore, plausibilityRating, associationFlags[], anomalySignals[] }
```

#### Role 3 — Escalation Handler (Bedrock Orchestration)

Cases that Role 2 could not resolve with high confidence are escalated to Bedrock for large model reasoning. Role 3 constructs the Bedrock prompt from tokenized, structured input — raw PHI never reaches Bedrock under any circumstances.

```
Role 2 flags a low-confidence case
        ↓
Role 3 receives: structured extraction + coherence flags + anomaly signals
        ↓
Role 3 constructs prompt using tokenized content only:
  "Extracted fields: [FIELD_TYPE_1] = [TOKEN_1] [TOKEN_UNIT_1]
   Coherence flag: association between [TOKEN_1] and [TOKEN_2]
   is clinically implausible. Reason?"
        ↓
Bedrock call (stateless, no PHI)
        ↓
Role 3 receives Bedrock reasoning
        ↓
Role 3 de-tokenizes for display to authorized user
  (substitutes real values back from token map, within private instance only)
        ↓
Structured response returned to device
```

Bedrock fires only on escalated cases — not every document. Well-trained Stage 2/3 models that rarely produce coherence flags mean Bedrock calls are rare and cost-controlled. Weak extraction models that produce frequent flags are expensive to escalate. Getting Stages 1–3 right directly controls Stage 4 operating cost.

#### Full Stage 4 Data Flow

```
User's iPhone
└── Document captured
└── Stage 2/3 CoreML extraction (on device, PHI contained)
└── Structured extraction JSON → FactStore (on device)
        ↓ (encrypted transmission)
PRIVATE AWS INSTANCE
└── Role 1: PHI Gateway
    └── Pass 1: structural token validation
    └── Pass 2: LLM semantic PHI detection
    └── Fully tokenized output produced
    └── Audit log written
        ↓
└── Role 2: Clinical Reasoning
    └── MIMIC-trained model evaluates coherence
    └── High-confidence results returned immediately
    └── Low-confidence cases escalated to Role 3
        ↓ (escalated cases only)
└── Role 3: Escalation Handler
    └── Constructs tokenized Bedrock prompt
    └── Calls Bedrock (stateless, no PHI)
    └── De-tokenizes response within private instance
    └── Returns structured reasoning to device
        ↓
User's iPhone
└── Coherence scores, plausibility ratings, anomaly flags
└── Bedrock reasoning on escalated cases
└── Everything presented in context of the user's FactStore
    (real values displayed to user from local FactStore,
     not from anything transmitted)
```

#### Infrastructure Specification

```
Private AWS instance:
├── EC2 GPU instance (g4dn.xlarge or equivalent for inference)
│   Scales to g4dn.12xlarge for MIMIC training runs
│
├── VPC with no public internet access
│   Outbound: Bedrock endpoint only (Role 3)
│   Inbound: App traffic (authenticated, encrypted)
│
├── EBS encrypted storage for MIMIC training data
│   Never mounted outside the VPC
│
├── IAM roles:
│   inference-role: read model weights, write phi_gateway_log
│   training-role: read MIMIC data, write model checkpoints
│   No cross-role access
│
├── Model storage: S3 bucket in same VPC, no public access
│   phi_gateway_model/        — Role 1 LLM weights
│   clinical_reasoning_model/ — Role 2 MIMIC-trained weights
│   (Role 3 has no stored weights — calls Bedrock externally)
│
└── Compliance:
    HIPAA BAA with AWS (required before PHI touches AWS infrastructure)
    CloudTrail logging on all API calls
    GuardDuty enabled
    phi_gateway_log retained per HIPAA retention requirements
```

---

### 5.6 Stage 4b — Consented Corpus Supersedes MIMIC

MIMIC-IV is one hospital system, one patient population, a fixed historical snapshot. It is the best publicly available clinical training data, which is why it is the Stage 4a starting point. It is not the endpoint.

Consent-given real patient records from your own user base are superior in every dimension that matters for training a clinical reasoning model:

```
MIMIC-IV                              Consented user records
──────────────────────────────────────────────────────────────────────
One hospital system (BIDMC)           Every provider your users visit
Fixed historical snapshot             Living, continuously updated
Beth Israel patient population        National demographic + geo spread
Pre-EHR-modernization artifacts       Current document formats and layouts
De-identified (lossy process)         Consented (no information loss)
No feedback loop                      ADI flywheel feeds training continuously
Research access barrier               Your own user base
Outcome data: historical only         Outcome data: prospective if IRB permits
```

The transition from Stage 4a to Stage 4b is the moment the moat becomes absolute. A competitor with capital can license MIMIC and replicate your Stage 4a training. They cannot access your consented patient corpus. It does not exist anywhere else. It was earned through years of user trust, product quality, and explicit consent.

**Stage 4b transition criteria:**

```
├── Tier 3 consent framework legally reviewed and approved
├── IRB submission completed (if prospective outcome data involved)
├── Consented corpus reaches 10,000+ documents
│   across at least 50 distinct provider layout types
├── MIMIC-trained Stage 4a model establishes baseline benchmark
├── Consented corpus fine-tune outperforms MIMIC baseline
│   on held-out test silo by statistically significant margin
└── MIMIC transitions to validation baseline role —
    still used to verify the consented model hasn't regressed
    on known clinical patterns, but no longer the training source
```

**The LoRA adapter path for Stage 4b:**

Rather than retraining from scratch, Stage 4b fine-tunes a new LoRA adapter on the consented corpus, layered on top of the Stage 4a base. This preserves the MIMIC-learned clinical patterns while specializing the model on your actual user population. Incremental fine-tuning runs as the consented corpus grows — the model improves continuously, not just at discrete version releases.

---

### 5.7 Tier 3 Research Consent Framework

Tier 3 is a new opt-in tier that enables consented patient records to feed the clinical reasoning model training pipeline. It is a different legal instrument from the Tier 1/2 HIPAA Safe Harbor de-identification — it requires explicit informed consent under a research data use framework.

**The four consent tiers:**

```
Tier 0 — Opted out
└── No pattern atoms transmitted. On-device learning only.
    PatternLibrary updates still received (free rider — acceptable).

Tier 1 — Default
└── Anonymous pattern atoms transmitted.
    PHI never leaves device in raw form.
    HIPAA Safe Harbor de-identification.
    User receives PatternLibrary improvements.

Tier 2 — Active
└── Same as Tier 1.
    User sees contribution metrics.
    Elevated trust signal — active opt-in weighted 1.1x in consensus.
    Eligible for extended token allocation or early feature access.

Tier 3 — Research consent (new)
└── User explicitly consents to de-identified health record data
    being used for clinical reasoning model training.
    Different legal instrument from Tier 1/2 — see below.
    Full opt-out preserved at any time with data deletion.
    Governed by a formal research data use agreement.
    IRB review required before activation if prospective
    outcome data is included.
```

**Why Tier 3 is a different legal instrument:**

Tier 1/2 operate under HIPAA Safe Harbor — the 18 enumerated identifiers are removed and the pattern atoms are de-identified by construction. This is a data minimization approach: nothing identifiable is ever transmitted.

Tier 3 involves transmitting richer data — de-identified document content, structured extraction, longitudinal health patterns — to train a model. This is research use of health information, which triggers different legal requirements:

- **HIPAA Authorization** (45 CFR §164.508): explicit written authorization from the patient for research use of their PHI, even de-identified PHI used in research that could re-identify
- **IRB oversight** (45 CFR 46, the Common Rule): if the research constitutes human subjects research, IRB review is required
- **Research data use agreement**: a formal legal instrument governing how the data is used, stored, retained, and destroyed

The specific triggers for IRB requirement depend on whether the research involves prospective outcome data (does the clinical reasoning model's output affect patient care decisions, and are those outcomes tracked). Training a model on consented historical records: probably not regulated research. Using that model to study clinical outcomes prospectively: probably is.

**Consent language (plain language requirement):**

Tier 3 consent must be genuinely informed — not a checkbox buried in a settings flow. The consent moment should:

- Explain in plain language what data will be used (de-identified health records, extraction output, correction history)
- Explain what it will be used for (training a model that improves health record reading for everyone)
- Explain what will not be shared (no raw PHI, no identifiable information, no data sold to third parties)
- Provide a plain-language summary of the data use agreement
- Make opt-out prominent and immediate (not buried in settings)
- Confirm data deletion on opt-out (corpus contributions removed within 30 days)

**Draft consent language:**

*"You can help make Record Health smarter for everyone — including yourself. If you choose, we can use your de-identified health record data to train the AI that reads medical documents. No personal information is included. Your records are stripped of all identifying details before they're used. You can withdraw at any time and your data will be deleted from our training systems within 30 days. This is completely optional — Record Health works the same either way."*

**Tier 3 data flow:**

```
User grants Tier 3 consent
        ↓
Documents processed normally (on-device extraction, PHI tokenization)
        ↓
Tokenized extraction output + document structure
flagged as tier3_consented in FactStore
        ↓
Private AWS instance PHI gateway
        ↓
LLM deep tokenization pass (Role 1)
Produces fully tokenized, research-ready document representation
        ↓
Written to consented_training_corpus table (private instance only)
        ↓
Periodic fine-tuning runs against accumulated consented corpus
        ↓
LoRA adapter update → clinical reasoning model improves
        ↓
Improved model returns to all users
(including opted-out users — they benefit from the improvement
without contributing to it)
```

**Schema additions for Tier 3:**

```sql
-- On private AWS instance (never in Neon)
consented_training_corpus (
    id                      UUID PRIMARY KEY,
    consented_at            TIMESTAMPTZ,
    user_consent_version    TEXT,           -- version of consent language shown
    document_hash           TEXT,           -- one-way hash of source document
    tokenized_content       JSONB,          -- fully tokenized document representation
    extraction_output       JSONB,          -- structured extraction atoms
    correction_history      JSONB,          -- user corrections on this document
    document_category       TEXT,
    provider_layout_hash    TEXT,
    corpus_split            TEXT,           -- training/validation/test
    withdrawal_requested    BOOLEAN DEFAULT FALSE,
    withdrawn_at            TIMESTAMPTZ
)

-- In Neon (flags consent status, no PHI)
user_consent_tier (
    user_id                 TEXT PRIMARY KEY,
    tier                    INT,            -- 0,1,2,3
    tier3_consented_at      TIMESTAMPTZ,
    tier3_consent_version   TEXT,
    tier3_withdrawn_at      TIMESTAMPTZ,
    tier3_deletion_completed BOOLEAN DEFAULT FALSE
)
```

**Withdrawal and deletion:**

On opt-out from Tier 3, all `consented_training_corpus` rows for that user are deleted within 30 days. Models trained before the withdrawal are not retrained — removing individual records from trained model weights is not technically feasible with current methodology. Consent language should disclose this limitation explicitly. Any future training runs exclude withdrawn users.

### 6.1 Stage 1 — Consumer Traction

**Value proposition:** Meaningfully better than a manila folder. Health records organized, searchable, and "pretty good" at extraction. The bar is not clinical perfection — it is friction reduction versus the current state of health record management.

**Subscription trigger:** The subscription question resolves around UX and trust, not extraction accuracy. A user who understands that the app is improving will tolerate a correctable error. A user who catches an error without context will lose trust. Onboarding framing matters — set expectations that this is an intelligent system that improves with use, not an infallible one.

**Target cohort:** Chronic condition patients. Diabetes, hypertension, autoimmune conditions, cancer survivors. These users generate 5–20 documents per year, have strong motivation to track their own data, and already understand that their records matter. They are the power users who generate the most correction signal and have the highest willingness to pay.

**Revenue model:** Free / Pro ($6.99/month) / Family ($11.99/month) / Boost Pack ($1.99 consumable). Conversion rate experiment runs at launch — the business case for Stage 2 annotation investment is justified when MRR covers annotation operating costs.

**Moat building:** PatternLibrary accumulates. Every user correction is an asset even if individually imperfect. The corpus build begins. The test silo is locked. The baseline benchmark is established.

**Risk:** Extraction quality ceiling is the rule engine ceiling. Do not make clinical accuracy claims at Stage 1. Position as an organizational and extraction tool, not a clinical decision support tool.

### 6.2 Stage 2 — Retention and Referral Inflection

**Value proposition:** The app is visibly getting smarter. Users who tolerated Stage 1 imperfection see it resolving. Extraction accuracy on their specific document sources improves as their provider layout fingerprints accumulate corrections. "It actually reads my records" becomes a defensible claim.

**Retention dynamic:** Chronic condition users who have been correcting extractions for 6–12 months have a personalized, improving experience that cannot be replicated by switching apps. Their corrections are embedded in the PatternLibrary. Their documents have been re-scored as the library improved. Switching cost is real.

**Referral dynamic:** Health records are shared — between family members, with caregivers, with patient advocates. A user who trusts Record Health refers their spouse, their parent, their support group. Word of mouth in chronic condition communities is high-velocity and high-trust.

**Institutional conversations open:** Stage 2 fine-tuning accuracy, paired with the PatternLibrary provenance story and the corpus audit trail, is sufficient to have early conversations with EHR vendors and insurance document processors. Not a sales process yet — a relationship-building process that positions Stage 3 as the product they will eventually buy.

**Revenue target:** Stage 2 annotation costs ($8,000–12,000/month) require approximately 1,200–1,700 Pro subscribers at $6.99/month to cover. This is not a large number. 10,000 downloads at 15% conversion covers it with margin.

### 6.3 Stage 3 — Institutional Market Opens

**Value proposition:** Document-level extraction accuracy at scale. Multi-page context. Provider-agnostic. Provenance-tracked. A held-out test set benchmark that can be audited. This is the product institutional buyers will pay for.

**B2B surface:**
- Health system archival digitization — converting decades of paper records to structured data
- Legal medical record review — malpractice, personal injury, disability claims
- Insurance prior authorization and claims document processing
- EHR document import — structured extraction at point of ingestion
- Life insurance underwriting — medical history document review

**API/licensing model:** PatternLibrary + document-level extraction model packaged as a callable API. Per-document pricing or volume license. Revenue line independent of consumer app subscription. This is the funding mechanism for Stage 4.

**Regulatory engagement:** Begin FDA SaMD regulatory strategy at Stage 3. Engage regulatory counsel before the product makes clinical decision support claims. Understand the 510(k) vs De Novo pathway options. Build the software development lifecycle documentation that FDA will require. This is not a blocker to Stage 3 — it is preparation for Stage 4.

**Partnership milestone:** The institutional pilot that funds Stage 4 is earned by demonstrating Stage 3 capability — document-level accuracy on a held-out test set, provenance story, audit trail. You do not walk into a health system with a Stage 1 app and ask for Stage 4 money. You walk in with Stage 3 traction and a clear roadmap.

### 6.4 Stage 4 — Category Shift

**The flip:** Every stage prior helps patients understand what their documents say. Stage 4 enables the interrogation to run in the other direction — using accumulated, clinically validated patient data to interrogate what should have happened against what did happen.

Evidence-based medicine has always existed at the population level. Clinical guidelines are written for average patients. Stage 4 applies that evidence at the individual level — this patient, these records, this clinical history, against what the evidence says should have been done.

That is not a health records app. That is a clinical intelligence platform.

**Acquirer profile:** Health systems seeking quality-of-care analytics. Payers seeking prior authorization automation and fraud detection. Life sciences companies seeking real-world evidence from patient-reported data. EHR vendors seeking intelligent document import. Research institutions seeking structured patient data pipelines.

**Valuation dynamic:** The PatternLibrary + expert-annotated corpus + clinical reasoning model is the acquisition target, not the consumer app. The consumer app is the data collection mechanism and the proof of concept. The underlying intelligence is the asset.

**Regulatory path:** FDA SaMD classification is required for clinical decision support claims. 510(k) or De Novo depending on intended use and risk classification. Plan for 12–24 months regulatory process. Academic publication of clinical reasoning model validation is a regulatory asset — L5 researcher's role extends into the regulatory submission.

**The competitive moat at Stage 4:** Years of expert annotation. A PatternLibrary built from the bottom of real patient document chaos. A fine-tuned extraction model trained on the most diverse real-world medical document corpus in the consumer health space. A clinical reasoning layer validated against MIMIC-IV outcomes. None of this is available for purchase. It is earned through Stages 1–3.

---

## 7. Competitive Landscape

### 7.1 The Arms Race Is a False Frame for Stages 1–3

Well-capitalized medical AI companies are building clinical LLMs from the top down — hire L5 researchers on day one, train on licensed clinical datasets, pursue hospital partnerships. They understand clinical language. They do not understand the chaos of real-world patient document formats.

Their weakness is your foundation. The PatternLibrary is built from the bottom of that chaos — from the specific way LabCorp prints a potassium result, the specific way Epic's print driver reflows a discharge summary, the specific OCR failure modes of a faxed prescription from 2003. No amount of clinical training data produces that knowledge. It requires real patient documents and real corrections at scale.

### 7.2 Competitor Map

**Well-funded medical AI startups:** Top-down approach. Strong on clinical language, weak on document format diversity. Not competing with a Stage 1 consumer app. Potential partners or acquirers at Stage 4, not competitors at Stage 1–2.

**EHR vendors (Epic, Cerner, Oracle Health):** Control structured data inside the hospital. Do not control what leaves — the printout, the patient portal PDF, the fax. Your surface area is exactly what they cannot touch. Architecturally incapable of building patient-first tools. Most likely acquirer category at Stage 3–4.

**General document AI (AWS Textract, Google Document AI, Azure Form Recognizer):** Excellent at general documents, weak at medical-specific layout and terminology. No PatternLibrary equivalent for medical documents. You run on top of their OCR engines and add the layer they don't have. Not competitors — infrastructure.

**Consumer health apps (Apple Health, MyChart, generic organizers):** Store documents, don't extract them. The gap between "file this PDF" and "read this PDF and understand what it says" is your entire product surface. At Stage 1 you are already past where they are.

**The actual competitive risk:** A well-funded startup that decides to build the PatternLibrary approach from the consumption side, with meaningful capital behind it. This risk is real at Stage 3–4. It is not real at Stage 1–2 because the corpus cannot be purchased — only earned. An 18-month head start on correction consensus is not catchable in 6 months with more money.

---

## 8. Regulatory Milestone Map

```
Stage 1   No regulatory action required.
          Do not make clinical decision support claims.
          Position as organizational and extraction tool.

Stage 2   Begin monitoring FDA SaMD guidance for digital health tools.
          No regulatory action required.
          Document development processes in preparation for future needs.

Stage 3   Engage regulatory counsel.
          Assess SaMD risk classification for intended use.
          Begin software development lifecycle documentation (IEC 62304).
          Do not make clinical decision support claims yet.
          Academic publication of extraction model validation — regulatory asset.

Stage 4a  FDA SaMD pathway required for clinical decision support claims.
          510(k) or De Novo depending on risk classification.
          L5 researcher's clinical reasoning validation study is part of
          regulatory submission evidence.
          HIPAA BAAs required with institutional partners AND with AWS.
          IRB consideration for any prospective clinical study design.
          Target: 12–24 month regulatory process concurrent with build.
          Private instance phi_gateway_log is the HIPAA audit trail artifact.
          Tier 3 consent framework legally reviewed — activate only after
          regulatory counsel sign-off.

Stage 4b  IRB submission if consented corpus involves prospective outcomes.
          Research data use agreement (DUA) governing consented corpus.
          Tier 3 consent language reviewed by regulatory counsel and IRB.
          HIPAA Authorization language validated for research use.
          Ongoing IRB reporting if prospective outcome data is collected.
          Model trained on consented corpus requires updated SaMD submission
          if intended use expands beyond Stage 4a claims.
```

---

## 9. Integration with Existing Spec Documents

### 9.1 Document Relationships

This document supplements but does not supersede the existing spec documents. The relationship is additive:

- **ADAPTIVE_DOCUMENT_INTELLIGENCE.md v2.0** governs the ADI pipeline, consensus engine, trust ladder, and PatternLibrary versioning. Stage 1 of this document operates entirely within that architecture.
- **SEED_CORPUS_AND_TAXONOMY.md v1.2** governs the seed corpus construction, confusion class taxonomy, train/validation/test split, and production gate. The annotation operation in this document feeds the training silo of that corpus.
- **SERVER_INFRASTRUCTURE.md** governs the Cloudflare Worker and Neon Postgres infrastructure. Stage 2 model infrastructure (fine-tuning pipeline, model versioning) extends but does not replace the existing server infrastructure.

### 9.2 New Infrastructure Requirements by Stage

**Stage 2:**
- Fine-tuning pipeline (cloud GPU, periodic runs — AWS SageMaker or equivalent)
- Model registry alongside PatternLibrary versioning
- CoreML model export pipeline (on-device inference)
- Model evaluation harness against corpus test silo
- MIMIC-IV local processing environment (never cloud-transmitted)

**Stage 3:**
- Document-level inference pipeline
- API gateway for institutional licensing
- Expanded Neon schema for document-level extraction records
- API authentication and rate limiting for B2B clients

**Stage 4:**
- Private VPC or on-premises GPU infrastructure (see section 5.5)
- Clinical reasoning model versioning (separate from extraction model)
- MIMIC-IV local training environment (Stage 4a)
- Consented training corpus storage on private instance (Stage 4b)
- LoRA adapter versioning for consented corpus fine-tuning iterations
- Regulatory documentation pipeline (IEC 62304 artifacts)
- HIPAA BAA with AWS
- Research data use agreement infrastructure (Stage 4b)
- User consent tier tracking in Neon (user_consent_tier table)
- Withdrawal and deletion pipeline for Tier 3 opt-outs

### 9.3 Schema Additions Required

The annotation operation produces records that need a home in Neon Postgres. The following tables are added alongside the ADI tables:

```sql
-- Expert annotation records
expert_annotations (
    id                      UUID PRIMARY KEY,
    created_at              TIMESTAMPTZ,
    document_id             UUID,
    annotator_level         TEXT,           -- 'L0','L1','L2','L3','L4','L5'
    annotator_id            TEXT,           -- hashed
    correction_class        TEXT,           -- 'A','B','C','D','E'
    source_region           JSONB,
    extraction_output       JSONB,
    correction_detail       JSONB,
    clinical_rationale      TEXT,
    negative_space_flags    JSONB,
    requires_escalation     BOOLEAN DEFAULT FALSE,
    escalated_to_level      TEXT,
    corpus_split            TEXT            -- 'training','validation','test'
)

-- Negative space (silent non-recognition) records
negative_space_annotations (
    id                      UUID PRIMARY KEY,
    created_at              TIMESTAMPTZ,
    document_id             UUID,
    annotator_level         TEXT,
    missing_field_type      TEXT,
    missing_canonical_id    TEXT,
    expected_region         JSONB,
    visually_present        BOOLEAN,
    clinical_significance   TEXT,           -- 'low','medium','high','critical'
    clinical_rationale      TEXT,
    corpus_split            TEXT
)

-- Model version registry
model_versions (
    id                      UUID PRIMARY KEY,
    created_at              TIMESTAMPTZ,
    stage                   INT,            -- 1,2,3,4
    model_version           TEXT,           -- semver
    base_model              TEXT,
    training_corpus_version TEXT,           -- corpus manifest version used
    test_silo_version       TEXT,
    benchmark_results       JSONB,
    production_gate_result  TEXT,
    deployed_at             TIMESTAMPTZ,
    superseded_by           UUID
)
```

---

*End of document.*

*This document governs the expert annotation operation and model training progression for Record Health. Document version 1.3 updates section 1.1 to reflect the corrected training model and adds the FUNCTION_DISTINCTION.md reference as the authoritative override. Version 1.2 added sections 5.6 and 5.7. Version 1.1 added section 5.5. FUNCTION_DISTINCTION.md v1.0 supersedes any assumption in this document that user corrections feed cross-user training — they do not. Expert annotation is the sole source of cross-user training data. MIMIC-IV is the Stage 4a training jumpstart. Stage 4b is the moment the moat becomes absolute. Tier 3 consent must be legally reviewed before activation. Stage transitions are manual decisions requiring explicit sign-off. The road is long and intensive. Until Stage 4, the operation is data vacuum, corpus refinement, and capital accumulation. Every stage is the prerequisite for the next.*
