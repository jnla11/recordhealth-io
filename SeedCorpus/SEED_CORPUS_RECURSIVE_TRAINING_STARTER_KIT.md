# Seed Corpus Recursive Training Starter Kit
## Implementation Guide — Stage 1 / Stage 2 ADI Bootstrap

**Document version:** 1.7
**Status:** Implementation guide with sprint prompts
**Supplements:** EXPERT_ANNOTATION_AND_MODEL_TRAINING.md, SEED_CORPUS_AND_TAXONOMY.md, ADAPTIVE_DOCUMENT_INTELLIGENCE.md, FUNCTION_DISTINCTION.md
**Governs:** MIMIC-IV local processing, document rendering pipeline, SEED annotation interface, programmatic sampling engine, PatternLibrary promotion from seed corpus, Bedrock inference role and PHI boundary, Stage 4 three-layer model stack, Claude.ai planning prompts for each build step

---

## 1. Overview

This document is the operational companion to the spec documents. Where those documents describe what to build and why, this document describes exactly how to build it — with copyable Claude Code sprint prompts for each component.

The seed corpus starter kit has nine components built in dependency order. No component should be started before its dependencies are in place. The sequence matters because the annotation schema must exist before pipeline output is written, and the pipeline must be running before the annotation interface has anything to show.

**On Bedrock's role:** Bedrock is used in this kit as a stateless inference service — a smart consultant you query with structured, anonymized input. It is never trained by anything you send it. Every call is independent. The learning accumulates entirely in your Neon database and your own model weights. See section 1.3 for the full Bedrock role clarification and section 12.2 for the compliance boundary.

### 1.1 MIMIC-IV Constraints

Everything involving MIMIC-IV data runs locally. No MIMIC content is transmitted to any external API, including Bedrock, OpenAI, or Anthropic. Per PhysioNet's LLM policy, MIMIC data may not be processed through third-party APIs.

Practically this means:
- Steps 1–2 (MIMIC extraction and rendering) run on your local machine
- The rendered document images that leave local processing have had PHI tokenized out before any network call
- The raw MIMIC CSVs and rendered images with real clinical text stay on disk, never uploaded

### 1.2 What MIMIC-IV Actually Contains

MIMIC-IV has two relevant modules for Stage 1/2 seed corpus:

**mimic-iv-note:** Free-text clinical notes including discharge summaries, radiology reports, and nursing notes. De-identified but realistic clinical language. Useful for: Domain 2 terminology variant coverage, section structure training, negation and qualifier examples.

**mimic-iv (core):** Structured lab results, medications, vital signs. Useful for: Rendering realistic lab report documents with known ground truth values, unit variant coverage, reference range examples.

**What MIMIC is NOT:** Rendered document images. MIMIC is text and structured data. Steps 1–2 convert that into rendered PDFs that simulate how these records would actually appear as printed documents — which is what your OCR pipeline actually processes.

**MIMIC is the jumpstart, not the destination.** MIMIC-IV is one hospital system, one patient population, a fixed historical snapshot. It is the best publicly available clinical training signal, which is why it is the Stage 4a bootstrap. Stage 4b is when consented patient records from your own user base supersede MIMIC as the primary training source — see EXPERT_ANNOTATION_AND_MODEL_TRAINING.md section 5.6 and 5.7 for the full Stage 4b architecture and Tier 3 consent framework.

The MIMIC pipeline in this kit (Steps 1–2) serves three roles:
- **Seed corpus (Stage 1/2):** Rendered documents for OCR pipeline training and annotation
- **Stage 4a bootstrap:** Clinical reasoning model initial training before consented corpus reaches scale
- **Ongoing validation baseline:** After Stage 4b transition, MIMIC remains the held-out validation set that confirms the consented-corpus-trained model hasn't regressed on known clinical patterns

### 1.3 Bedrock's Role in This Architecture — Not Training

Bedrock is an inference service throughout this entire kit. You are never training Bedrock. When you call Bedrock in Step 9, the underlying model is unchanged by your input. Every call is stateless — when it ends, nothing persists on Bedrock's side. What changes is your database.

```
You call Bedrock with:       Bedrock returns:
A prompt + structured data   A classification or suggestion

Your Neon database updates.
Bedrock does not update.
The learning is yours, not Bedrock's.
```

**Where actual training happens in this architecture:**

Stage 1 — Nothing is trained in the ML sense. PatternLibrary rules are promoted (logic, not weights). MLUpdateTask trains a small CoreML classifier on-device from personal corrections — that model lives on the user's device.

Stage 2 — You fine-tune a small base model on your expert-annotated corpus. This runs on cloud GPU infrastructure you control (AWS SageMaker, not Bedrock Training). The weights are yours. You export to CoreML and ship in the app.

Stage 4a — You train a clinical reasoning model on your private infrastructure against local MIMIC-IV data. Weights are yours. MIMIC is the jumpstart. This introduces a three-layer model stack:

Stage 4b — Consented patient records from your own user base (Tier 3 opt-in) supersede MIMIC as the primary training source. LoRA adapter fine-tuning on the consented corpus runs continuously as the corpus grows. MIMIC transitions to validation baseline. The consented corpus is trained through a separate ingestion path on the private instance — not through the Steps 1–2 MIMIC pipeline.

```
Layer 1 — On device (Stage 2/3 CoreML extraction models)
└── Always on device. PHI never leaves. Unchanged at Stage 4.

Layer 2 — Your private server (MIMIC-trained reasoning model)
└── Clinical coherence validation against known clinical patterns.
    Structured JSON input only — not raw documents.
    Your infrastructure, your rules, your weights.

Layer 3 — Bedrock (stateless large model reasoning)
└── Open-ended reasoning on cases Layer 2 flagged.
    Receives structured extraction output + coherence flags only.
    Never receives raw documents, MIMIC content, or raw PHI.
    Fires only on escalated cases — not every document.
    Stateless — nothing persists after each call.
```

Layer 3 only fires on cases Layer 2 couldn't resolve with high confidence. Well-trained extraction models at Stage 2/3 mean fewer Layer 2 flags, which means fewer Bedrock calls. Getting Stages 1–3 right is what makes Stage 4 cost-controlled.

---

## 2. Step 1 — Local MIMIC Environment and Data Extraction

### 2.1 What This Does

Python scripts that read MIMIC-IV data files locally and extract structured content by document type. Output is JSON files on disk, organized by document category. These JSON files are the input to the document renderer in Step 2.

### 2.2 Prerequisites

- MIMIC-IV data files downloaded locally (requires PhysioNet credentialed access)
- Python 3.11+
- Files expected at: `~/mimic-iv/` and `~/mimic-iv-note/`

### 2.3 Sprint Prompt — Step 1

```
Reference: SEED_CORPUS_AND_TAXONOMY.md section 4.3 (Track B sources), EXPERT_ANNOTATION_AND_MODEL_TRAINING.md section 2.1

Create a Python script at scripts/mimic_extractor.py that runs entirely locally and never makes any network calls.

The script reads MIMIC-IV data from ~/mimic-iv/ and ~/mimic-iv-note/ and produces structured JSON extraction files organized by document category.

Implement these four extractors:

1. DischargeNoteExtractor
   - Source: mimic-iv-note/discharge.csv.gz
   - Fields to extract: subject_id (hashed), hadm_id (hashed), charttime, text
   - Parse text into sections using regex: Chief Complaint, History of Present Illness, 
     Medications on Admission, Discharge Medications, Discharge Diagnosis, 
     Pertinent Results, Physical Exam
   - Output: data/mimic/discharge/{hadm_id_hash}.json per note
   - Limit: first 500 notes for seed corpus

2. RadiologyNoteExtractor  
   - Source: mimic-iv-note/radiology.csv.gz
   - Fields: subject_id (hashed), hadm_id (hashed), charttime, text
   - Parse into sections: Examination, Indication, Technique, Findings, Impression
   - Output: data/mimic/radiology/{note_id_hash}.json
   - Limit: first 300 notes

3. LabResultExtractor
   - Source: mimic-iv/hosp/labevents.csv.gz + d_labitems.csv.gz
   - Join labevents with d_labitems on itemid to get label, fluid, category
   - Group by hadm_id — one file = one patient encounter lab panel
   - Fields per result: label, value, valuenum, valueuom, ref_range_lower, 
     ref_range_upper, flag (abnormal/normal)
   - Output: data/mimic/labs/{hadm_id_hash}.json
   - Limit: 400 encounters with at least 5 lab results each

4. MedicationExtractor
   - Source: mimic-iv/hosp/prescriptions.csv.gz
   - Fields: drug, drug_type, formulary_drug_cd, gsn, ndc, prod_strength, 
     dose_val_rx, dose_unit_rx, route
   - Group by hadm_id — one file = one encounter medication list
   - Output: data/mimic/medications/{hadm_id_hash}.json
   - Limit: 300 encounters

All subject_id and hadm_id values must be hashed (SHA-256 truncated to 12 chars) before writing to output files. No real patient identifiers in any output file.

Include a manifest.json at data/mimic/manifest.json listing all output files with their document category, section count, and hash.

Add a validation function that confirms no output file contains patterns matching: dates in MM/DD/YYYY format, names (Firstname Lastname pattern), phone numbers, or SSN patterns. Raise ValueError if any validation fails.

Run with: python scripts/mimic_extractor.py --limit-per-type 500 --validate
```

---

## 3. Step 2 — Document Renderer

### 3.1 What This Does

Takes the structured JSON output from Step 1 and renders it into realistic PDF documents that simulate how these records would appear as printed provider documents. The rendered PDFs are what the OCR pipeline actually processes — which means the ground truth extraction is known because you generated the content.

Renders four layout families: LabCorp-style lab report, Quest-style lab report, hospital discharge summary, and radiology report. Each layout family has controlled variation in font, column spacing, and formatting to generate Domain 2 layout diversity.

### 3.2 Sprint Prompt — Step 2

```
Reference: SEED_CORPUS_AND_TAXONOMY.md section 4.3 (Track B), section 4.4.3 (Track C)

Create a Python document rendering pipeline at scripts/document_renderer.py using ReportLab (pip install reportlab).

Implement four layout renderers. Each renderer takes a JSON file from data/mimic/ and produces a PDF at data/rendered/{layout_type}/{source_hash}.pdf alongside a ground_truth JSON at data/ground_truth/{layout_type}/{source_hash}.json.

Layout 1: LabCorpStyle
- Page: Letter, 1-inch margins
- Header: "Laboratory Report" in 10pt bold, patient info block (use hashed IDs only, no real names), 
  specimen info block, ordering provider (use "Provider [hash]")
- Lab results table: 5 columns — Test Name | Result | Units | Reference Range | Flag
- Column widths: 200px | 80px | 80px | 120px | 40px
- Alternating row shading (white / very light gray)
- Abnormal values in bold
- Footer: page number, report ID (hashed)
- Variation parameters (randomize per document):
  font_size: choice([9, 10, 11])
  column_spacing: choice(['tight', 'normal', 'wide'])
  header_style: choice(['full', 'compact'])

Layout 2: QuestStyle  
- Similar to LabCorpStyle but: 2-column layout for results (test+result left, units+range right),
  different header typography, result flags as symbols (H/L/C) not words
- Same variation parameters

Layout 3: DischargeSummaryStyle
- Section-based layout, each section has bold header + body text
- Sections: Chief Complaint, HPI, Medications, Diagnoses, Lab Results (summary table), Plan
- Body text: 10pt, 1.4 line height
- Medications section: numbered list with drug name, dose, route, frequency
- Diagnosis section: ICD-style numbered list
- Variation: font_family: choice(['Helvetica', 'Times-Roman']), line_height: choice([1.3, 1.4, 1.5])

Layout 4: RadiologyStyle
- Header with exam type, date (use relative "Day 0" not real dates), ordering info
- Body: FINDINGS section in justified text, IMPRESSION section with numbered conclusions
- Watermark-style "FINAL REPORT" diagonal text (light gray, 45 degrees)
- Variation: column_width: choice([0.7, 0.8, 0.9]) * page_width

Ground truth JSON format per rendered document:
{
  "sourceFile": "data/mimic/labs/abc123.json",
  "layoutType": "LabCorpStyle",
  "layoutVariant": { "font_size": 10, "column_spacing": "tight", ... },
  "providerLayoutHash": "sha256_of_layout_params_truncated_16_chars",
  "groundTruth": [
    {
      "fieldType": "numericLabValue",
      "label": "Glucose",
      "value": "140",
      "unit": "mg/dL",
      "referenceRange": "70-100",
      "flag": "H",
      "canonicalId": "LOINC:2345-7",
      "pageIndex": 0,
      "approximateBoundingBox": { "x": 0.35, "y": 0.42, "w": 0.12, "h": 0.02 }
    }
  ]
}

The approximateBoundingBox values should be computed from ReportLab's coordinate system converted to normalized 0-1 space.

Also implement DegradationPipeline that post-processes rendered PDFs:
- gaussian_blur(radius: uniform(0.5, 2.5))
- jpeg_compression(quality: choice([50, 60, 70, 80]))
- rotation(degrees: uniform(-3, 3))
- brightness(delta: uniform(-0.15, 0.15))
Apply 0, 1, or 2 degradations randomly per document. Record which degradations were applied in the ground truth JSON under "degradations".

Run with: python scripts/document_renderer.py --source data/mimic/ --output data/rendered/ --ground-truth data/ground_truth/ --count 200
```

---

## 3b. Step 2b — Confusion-Class-Aware Augmentation Engine

### 3b.1 What This Does

Takes each base rendered PDF and produces N targeted variant documents, each perturbed along the specific confusion class axis the annotation identified as a failure. One annotated document becomes 5–8 distinct training examples. Effective training corpus size grows 5–8x without sourcing additional real documents.

The augmentation engine sits between the renderer (Step 2) and the extraction runner (Step 4). It runs after annotation sessions identify which confusion classes are active in the corpus, and before training runs to maximize example diversity per class.

**Why this matters statistically:** Without augmentation, 600 annotated documents yield ~50 examples per confusion class — borderline stable. With 5–8x augmentation, the same 600 documents yield 250–400 examples per class — well into saturation. The bottleneck shifts entirely to the test silo (300 real PDFs in Silo B), not training volume.

**Hard limits:**
- Augmented documents enter training split only — never validation or test silo
- Never augment augmented documents (augmentation_generation max = 1)
- Test silo is real, unaugmented, human-annotated only — no exceptions

### 3b.2 Augmentation Strategies by Confusion Class

```
DOMAIN 1 — Optical (renderer-level perturbations)
Ground truth: unchanged — content is identical, only rendering varies

d1_alphanumericSubstitution:
  → Vary DPI (72 / 96 / 120 / 150)
  → Vary JPEG compression quality (40% / 60% / 80%)
  → Vary Gaussian blur sigma (0.5 / 1.0 / 1.5 / 2.0)
  → Vary contrast ratio of target field region
  → Vary character pair (O/0, l/1, I/1, S/5, B/8)
  Variants per document: 5–15

d1_lowContrastDropout:
  → Vary background lightness under text (95% / 90% / 85% white)
  → Vary ink darkness of specific field regions
  → Simulate faded cartridge on specific columns
  Variants per document: 3–6

d1_skewDistortion:
  → Vary rotation angle (0.5° / 1.0° / 2.0° / 3.0°)
  → Vary perspective distortion (handheld scan simulation)
  → Combine with blur (compound degradation)
  Variants per document: 3–8

d1_shadowIntrusion:
  → Vary shadow position and gradient across page
  → Vary shadow intensity (20% / 40% / 60% opacity)
  → Apply to different page regions
  Variants per document: 4–8

DOMAIN 2 LAYOUT — Structural (layout-level perturbations)
Ground truth: updated bounding boxes recomputed from new layout geometry

d2_columnMisattribution:
  → Vary column gap (-4px to +4px in 2px steps)
  → Vary tab stop positions (±3px jitter)
  → Vary whitespace between label and value (0px / 2px / 4px / 8px)
  → Shift value columns left/right by 2–8 pixels
  Variants per document: 3–8

d2_lineBreakIntrusion:
  → Vary field width to force break at different character positions
  → Vary font size slightly to change wrap behavior
  → Break same field at 3–5 different positions
  Variants per document: 3–5

d2_referenceRangeCollision:
  → Vary visual separation between result and reference range columns
  → Move reference range column closer to result column
  → Use different delimiter styles (space / dash / pipe / parentheses)
  Variants per document: 3–6

DOMAIN 2 TERMINOLOGY — Syntactic (surface form perturbations)
Ground truth: same canonical ID, different surface form (or converted value)

d2_terminologyVariant:
  → Swap between known variant forms of the same term
    ("Gluc" / "Glucose" / "GLU" / "BG" — all LOINC:2345-7)
  → Mix abbreviation styles within the same document
  Variants per document: 2–5

d2_unitVariant:
  → Render same value in different unit representations
  → Apply conversion formula — ground truth value AND unit must update
    (mg/dL ↔ mmol/L requires numeric conversion, not just label swap)
  Variants per document: 2–4

d2_dateFormatVariant:
  → Render same date in multiple formats across variants
    (MM/DD/YYYY / DD-MON-YYYY / YYYY-MM-DD / Month DD YYYY)
  Variants per document: 3–5
```

### 3b.3 Ground Truth Update Rules

```
Domain 1 perturbations (optical only):
  Ground truth JSON: unchanged
  Bounding boxes: unchanged (same layout, same positions)
  Values: unchanged (content identical, only rendering degraded)

Domain 2 layout perturbations:
  Ground truth JSON: recompute bounding boxes from new layout geometry
  Values: unchanged
  Association: revalidated against new column positions

Domain 2 terminology (surface form only):
  Ground truth JSON: surface form changes, canonical ID unchanged
  "Gluc" → LOINC:2345-7 same as "Glucose" → LOINC:2345-7

Domain 2 unit variant (value AND unit change):
  Ground truth JSON: converted value + new unit — BOTH must update
  This is the only augmentation class where ground truth math is required
  Apply the conversion formula before writing ground truth
  Flag for L0 review — unit conversions must be verified
```

### 3b.4 Sprint Prompt — Step 2b

```
Reference: SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §3.2 (renderer output),
SEED_CORPUS_AND_TAXONOMY.md §3 (confusion class taxonomy),
FUNCTION_DISTINCTION.md §8.1 (storage boundaries)

Build an augmentation engine that takes base rendered PDFs from Step 2
and produces targeted variant documents perturbed along specific
confusion class axes.

Input:
  base_pdf_path         path to rendered PDF from Step 2
  ground_truth_path     path to corresponding ground truth JSON
  confusion_class       which class to perturb along
  n_variants            how many variants to generate (default 5)
  augmentation_strategy specific perturbation type within the class

Output per variant:
  variant_pdf           rendered PDF with perturbation applied
  variant_ground_truth  updated ground truth JSON
  augmentation_manifest records params used for reproducibility
                        stored in augmentation_params JSONB column

Directory structure:
  data/augmented/{base_document_hash}/{strategy}_{variant_n}.pdf
  data/augmented/{base_document_hash}/{strategy}_{variant_n}_ground_truth.json
  data/augmented/{base_document_hash}/manifest.json

Implement these strategies first (highest expected annotation coverage):

  d1_alphanumericSubstitution:
    Parameters: dpi in [72, 96, 120, 150], jpeg_quality in [40, 60, 80],
    blur_sigma in [0.5, 1.0, 1.5, 2.0], char_pair in ['O0','l1','I1','S5','B8']
    Ground truth: unchanged

  d2_columnMisattribution:
    Parameters: column_gap_delta in [-4, -2, 0, +2, +4] pixels,
    tab_stop_jitter in [-3, -1, +1, +3] pixels,
    label_value_whitespace in [0, 2, 4, 8] pixels
    Ground truth: recompute bounding boxes from new layout geometry

  d2_lineBreakIntrusion:
    Parameters: field_width_delta in [-20, -10, +10, +20] pixels
    Ground truth: recompute bounding boxes from new line positions

  d2_unitVariant:
    Parameters: target_unit, conversion_factor, conversion_offset
    Ground truth: apply conversion formula to value AND update unit string
    Flag all unit variant augmentations for L0 review in manifest

Ground truth update contract:
  Domain 1: copy ground truth JSON unchanged
  Domain 2 layout: recompute all bounding boxes
  Domain 2 terminology/unit: update surface form and/or value+unit

Write all augmented documents to seed_documents table with:
  is_augmented: true
  augmentation_source_id: UUID of base seed_document
  augmentation_class: confusion class targeted
  augmentation_strategy: specific strategy applied
  augmentation_params: JSONB of exact parameters used
  augmentation_generation: 1 (never augment an augmentation)
  corpus_split: 'training' (hardcoded — augmented docs never enter test silo)
  provider_layout_hash: inherited from base document

Add augmentation_generation check at write time:
  If source document is_augmented = true → raise error, do not write
  This enforces the generation = 1 hard limit at the database layer

Provide a CLI entry point:
  python scripts/augment.py
    --base-doc-id {seed_document_uuid}
    --confusion-class d1_alphanumericSubstitution
    --strategy dpi_variation
    --n-variants 5
    --output-dir data/augmented/

And a batch mode:
  python scripts/augment_batch.py
    --annotation-summary data/annotation_summary.json
    --n-variants 5
    --output-dir data/augmented/
    (reads which confusion classes are active in current corpus,
     generates variants for all base documents tagged with those classes)

Device test: generate 5 variants of one base lab report PDF.
Verify ground truth JSON is valid for each variant.
Confirm all 5 write to seed_documents with is_augmented=true,
corpus_split='training', correct augmentation_params JSONB.
Confirm source document is_augmented=false (not an augmented base).
```

### 3b.5 Augmentation Multiplier and Training Impact

```
Without augmentation:
  600 annotated docs → ~600 training examples
  ~50 examples per confusion class (borderline stable)

With augmentation (5–8x):
  600 annotated docs → 3,000–4,800 training examples
  ~250–400 examples per confusion class (saturation zone)

Promotion gate is unchanged — Silo B (300 real PDFs) is the gate
Augmentation affects training volume only, not benchmark validity

Effective annotation rate with augmentation:
  1 annotation session (160–180 docs) → 800–1,440 training examples
  Reaches training saturation in 3–4 annotation sessions
  instead of 15–20 sessions without augmentation
```

### 3b.6 Schema Additions

Add to the `src/migrations/003_seed_corpus.sql` migration:

```sql
-- Add augmentation columns to seed_documents
ALTER TABLE seed_documents ADD COLUMN is_augmented BOOLEAN DEFAULT FALSE;
ALTER TABLE seed_documents ADD COLUMN augmentation_source_id UUID REFERENCES seed_documents(id);
ALTER TABLE seed_documents ADD COLUMN augmentation_class TEXT;
ALTER TABLE seed_documents ADD COLUMN augmentation_strategy TEXT;
ALTER TABLE seed_documents ADD COLUMN augmentation_params JSONB;
ALTER TABLE seed_documents ADD COLUMN augmentation_generation INT DEFAULT 0;

-- Enforce generation hard limit at database layer
ALTER TABLE seed_documents ADD CONSTRAINT augmentation_generation_max
  CHECK (augmentation_generation <= 1);

-- Enforce augmented docs stay in training split
ALTER TABLE seed_documents ADD CONSTRAINT augmented_training_only
  CHECK (NOT is_augmented OR corpus_split = 'training');

-- Track augmentation run history
CREATE TABLE augmentation_runs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at                  TIMESTAMPTZ DEFAULT now(),
    base_document_id        UUID REFERENCES seed_documents(id),
    confusion_class         TEXT,
    strategy                TEXT,
    n_variants_requested    INT,
    n_variants_produced     INT,
    params_used             JSONB,
    unit_conversion_flagged BOOLEAN DEFAULT FALSE,
    l0_review_required      BOOLEAN DEFAULT FALSE,
    notes                   TEXT
);
```

---

### 4.1 What This Does

Adds the annotation operation tables to the existing Neon database. This must run before any pipeline output is written. Uses the existing Worker migration pattern.

### 4.2 Sprint Prompt — Step 3

```
Reference: EXPERT_ANNOTATION_AND_MODEL_TRAINING.md section 9.3, SERVER_INFRASTRUCTURE.md section 4.3

Add a database migration to the recordhealth-api Worker project that creates the seed corpus and annotation tables in Neon Postgres.

Create a new file src/migrations/003_seed_corpus.sql with these tables:

CREATE TABLE IF NOT EXISTS seed_documents (
    id                      TEXT PRIMARY KEY,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    source_file             TEXT NOT NULL,
    layout_type             TEXT NOT NULL,
    layout_variant          JSONB,
    provider_layout_hash    TEXT NOT NULL,
    document_category       TEXT NOT NULL,
    corpus_split            TEXT NOT NULL DEFAULT 'training',
    render_path             TEXT,
    ground_truth            JSONB NOT NULL,
    degradations            JSONB,
    annotation_status       TEXT DEFAULT 'pending',
    annotated_at            TIMESTAMPTZ,
    annotator_level         TEXT
);

CREATE TABLE IF NOT EXISTS expert_annotations (
    id                      TEXT PRIMARY KEY,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    seed_document_id        TEXT REFERENCES seed_documents(id),
    annotator_level         TEXT NOT NULL,
    annotator_id            TEXT NOT NULL,
    correction_class        TEXT,
    source_region           JSONB,
    extraction_output       JSONB,
    correction_detail       JSONB,
    clinical_rationale      TEXT,
    negative_space_flags    JSONB DEFAULT '[]',
    requires_escalation     BOOLEAN DEFAULT FALSE,
    escalated_to_level      TEXT,
    corpus_split            TEXT NOT NULL DEFAULT 'training',
    quality_flags           JSONB DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS negative_space_annotations (
    id                      TEXT PRIMARY KEY,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    seed_document_id        TEXT REFERENCES seed_documents(id),
    annotator_level         TEXT NOT NULL,
    missing_field_type      TEXT NOT NULL,
    missing_canonical_id    TEXT,
    expected_region         JSONB,
    visually_present        BOOLEAN DEFAULT TRUE,
    clinical_significance   TEXT,
    clinical_rationale      TEXT,
    corpus_split            TEXT NOT NULL DEFAULT 'training'
);

CREATE TABLE IF NOT EXISTS extraction_runs (
    id                      TEXT PRIMARY KEY,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    seed_document_id        TEXT REFERENCES seed_documents(id),
    pipeline_version        TEXT NOT NULL,
    pattern_library_version TEXT NOT NULL,
    extractions             JSONB NOT NULL,
    extraction_errors       JSONB DEFAULT '[]',
    run_duration_ms         INT,
    ocr_engine              TEXT DEFAULT 'VisionKit'
);

CREATE TABLE IF NOT EXISTS benchmark_runs (
    id                      TEXT PRIMARY KEY,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    corpus_split            TEXT NOT NULL,
    pattern_library_version TEXT NOT NULL,
    sample_size             INT NOT NULL,
    results_by_field_type   JSONB NOT NULL,
    results_by_category     JSONB NOT NULL,
    results_by_class        JSONB NOT NULL,
    overall_accuracy        FLOAT,
    false_positive_rate     FLOAT,
    false_negative_rate     FLOAT,
    silent_miss_rate        FLOAT,
    gate_result             TEXT,
    notes                   TEXT
);

CREATE INDEX idx_seed_docs_status ON seed_documents(annotation_status);
CREATE INDEX idx_seed_docs_split ON seed_documents(corpus_split);
CREATE INDEX idx_seed_docs_category ON seed_documents(document_category);
CREATE INDEX idx_annotations_doc ON expert_annotations(seed_document_id);
CREATE INDEX idx_extraction_runs_doc ON extraction_runs(seed_document_id);
CREATE INDEX idx_benchmark_split ON benchmark_runs(corpus_split);

Add a POST /admin/migrate endpoint to index.js that runs this migration. Protect it with a static ADMIN_KEY env var checked against an Authorization header. The endpoint should be idempotent — CREATE TABLE IF NOT EXISTS means it is safe to run multiple times.

Test by hitting POST /admin/migrate with the correct Authorization header and confirming all tables exist via /health/db.
```

---

## 5. Step 4 — Extraction Pipeline Runner

### 5.1 What This Does

A Swift command-line tool that takes a rendered document path, runs it through the existing iOS extraction pipeline (VisionKit OCR + layout rules + semantic parsing), and writes results to Neon via the Worker API. This is the existing pipeline exposed as a batch tool — not new extraction logic, just a new entry point.

### 5.2 Sprint Prompt — Step 4

```
Reference: ARCHITECTURE.md (existing extraction pipeline), SERVER_INFRASTRUCTURE.md section 5.3 (ADI routes)

Create a Swift command-line target in the Xcode project named SeedCorpusRunner.

This target imports the existing extraction pipeline services (DocumentReadService, AIExtractionService, or equivalents) and runs them against local rendered documents.

Implement ExtractionPipelineRunner with this interface:

struct ExtractionPipelineRunner {
    func runDocument(
        pdfPath: URL,
        seedDocumentId: String,
        groundTruthPath: URL,
        workerBaseURL: URL,
        authToken: String
    ) async throws -> ExtractionRunResult
}

struct ExtractionRunResult {
    let seedDocumentId: String
    let extractions: [ExtractedField]
    let errors: [ExtractionError]
    let durationMs: Int
    let patternLibraryVersion: String
}

struct ExtractedField {
    let fieldType: String
    let label: String?
    let value: String
    let unit: String?
    let confidence: Float
    let pageIndex: Int
    let boundingBox: CGRect
    let confusionClassPredicted: String?
}

The runner should:
1. Load the PDF from pdfPath using PDFKit
2. Run VisionKit OCR on each page using the existing OCRResultStore pipeline
3. Run layout understanding rules against OCR output using existing LayoutUnderstandingService
4. Run semantic parsing using existing SemanticParsingService
5. Collect all ExtractedField results and ExtractionErrors
6. POST results to {workerBaseURL}/v1/seed/extraction-run with the authToken

The POST payload:
{
  "seedDocumentId": "...",
  "pipelineVersion": "1.0.0",
  "patternLibraryVersion": "...",
  "extractions": [...],
  "errors": [...],
  "durationMs": 1234,
  "ocrEngine": "VisionKit"
}

Add a Worker endpoint POST /v1/seed/extraction-run (protected, Bearer JWT) that writes the payload to the extraction_runs table and updates seed_documents.annotation_status to 'extracted' if it was 'pending'.

Add a CLI entry point main.swift that accepts:
--pdf-dir path/to/rendered/documents/
--ground-truth-dir path/to/ground_truth/
--worker-url https://api.recordhealth.workers.dev
--token {jwt}
--limit 50

Run all PDFs in the pdf-dir up to limit, posting each result to the Worker. Log progress to stdout. Log errors to stderr. Exit 0 on completion, non-zero on fatal error.

Device test: run against 5 rendered PDFs from Step 2, confirm extraction_runs rows appear in Neon.
```

---

## 6. Step 5 — SEED Annotation Interface

### 6.1 What This Does

The primary L0 annotation tool. A web application that shows the source document alongside the extraction pipeline output, allowing you to review each extraction, flag errors, select correction class, add rationale, and flag negative space (missing extractions). Saves completed annotations to Neon.

Built as a Cloudflare Pages app with Worker API backend. No framework required — vanilla React is sufficient. This is an internal tool, not a consumer product.

### 6.2 Sprint Prompt — Step 5 (Worker API)

```
Reference: EXPERT_ANNOTATION_AND_MODEL_TRAINING.md section 4.2 (annotation output format), SERVER_INFRASTRUCTURE.md section 5.3

Add these SEED annotation API endpoints to the recordhealth-api Worker (index.js). All routes are protected with Bearer JWT. Add an ANNOTATOR_KEY env var that provides a separate auth path for the annotation interface without requiring an Apple Sign In account.

GET /v1/seed/queue
Returns pending annotation work:
{
  "pending": [
    {
      "id": "seed_doc_id",
      "documentCategory": "labReport",
      "layoutType": "LabCorpStyle",
      "annotationStatus": "extracted",
      "extractionCount": 12,
      "groundTruthCount": 14,
      "createdAt": "..."
    }
  ],
  "stats": {
    "pending": 120,
    "inProgress": 3,
    "complete": 47,
    "total": 170
  }
}

GET /v1/seed/document/:id
Returns full document data for annotation:
{
  "document": { ...seed_documents row... },
  "extractions": { ...extraction_runs row with full extractions array... },
  "groundTruth": { ...parsed ground truth JSON... },
  "existingAnnotations": [ ...any existing expert_annotations rows... ]
}

Also returns a presigned URL or base64 encoded rendered PDF for display.
Store rendered PDFs in Neon as base64 in seed_documents.render_data TEXT column (add this column in the migration). Size limit 5MB per document — enforce this.

POST /v1/seed/annotate
Accepts a complete annotation payload:
{
  "seedDocumentId": "...",
  "annotatorId": "...",
  "annotatorLevel": "L0",
  "annotations": [
    {
      "id": "uuid",
      "correctionClass": "A",
      "sourceRegion": { "pageIndex": 0, "boundingBox": {...} },
      "extractionOutput": { ...the extracted field being annotated... },
      "correctionDetail": {
        "isExtractedValueCorrect": false,
        "correctLabel": "Glucose",
        "correctCanonicalId": "LOINC:2345-7",
        "correctValue": "140",
        "correctUnit": "mg/dL"
      },
      "clinicalRationale": "...",
      "requiresEscalation": false
    }
  ],
  "negativeSpaceFlags": [
    {
      "id": "uuid",
      "missingFieldType": "numericLabValue",
      "missingCanonicalId": "LOINC:2160-0",
      "visuallyPresent": true,
      "clinicalSignificance": "high",
      "clinicalRationale": "Creatinine visible at page 1 line 14, not extracted"
    }
  ],
  "sessionComplete": true
}

Writes to expert_annotations and negative_space_annotations tables.
Updates seed_documents.annotation_status to 'annotated' if sessionComplete is true.
Returns { "saved": true, "annotationCount": N, "negativeSpaceCount": M }

POST /v1/seed/ingest-document
Accepts: { "seedDocumentId": "...", "groundTruth": {...}, "layoutType": "...", "documentCategory": "...", "corpusSplit": "training", "renderDataBase64": "..." }
Writes to seed_documents table.
Used by the Step 2 renderer to ingest documents after rendering.

All endpoints log to audit_log table on error.
```

### 6.3 Sprint Prompt — Step 5 (Annotation UI)

```
Reference: EXPERT_ANNOTATION_AND_MODEL_TRAINING.md sections 2.2, 4.2

Create a single-page web annotation interface as a standalone HTML file at tools/seed-annotator/index.html. No build step required — vanilla JS, no dependencies except the Worker API.

The interface has three panels:

LEFT PANEL (40% width): Document viewer
- Renders the base64 PDF from the API using PDF.js (load from cdnjs)
- Page navigation controls (prev/next page)
- Highlights bounding boxes for each extraction overlaid on the PDF
  - Green box: extraction matches ground truth
  - Amber box: extraction present but unreviewed
  - Red box: extraction flagged as incorrect
  - Blue dashed box: ground truth field with no matching extraction (potential negative space)
- Click a highlighted box to load that extraction in the center panel

CENTER PANEL (35% width): Annotation form
Shows the currently selected extraction with:

Field: [fieldType label]
Extracted value: [value] [unit]
Ground truth value: [value] [unit] (from ground_truth JSON)
Match: [green checkmark if values match / red X if mismatch]

Correction class selector (radio buttons):
○ No correction needed
○ A — Correct value, wrong label
○ B — Correct atoms, wrong association  
○ C — Correct extraction, missing qualifier
○ D — Locally correct, globally incoherent
○ E — Silent absence (use for negative space panel)

Correction fields (shown based on selected class):
- Correct label (text input, class A)
- Correct canonical ID (text input with LOINC/RxNorm lookup hint, classes A/C)
- Correct value (text input, classes A/B)
- Correct unit (text input, classes A/C)
- Clinical rationale (textarea, all classes)
- Requires L3 review (checkbox)

Save button: POSTs to /v1/seed/annotate for this single extraction

RIGHT PANEL (25% width): Session controls
- Document info (category, layout type, extraction count)
- Progress: N of M extractions reviewed
- Negative space section:
  Add missing field button → shows inline form:
    Field type (dropdown: numericLabValue, medicationName, date, etc.)
    Canonical ID (text)
    Visually present (yes/no toggle)
    Clinical significance (low/medium/high/critical)
    Rationale (textarea)
    Save negative space flag button
  List of flagged negative space items for this document
- Complete session button (marks document as annotated)
- Skip document button (returns to queue)
- Queue stats: X pending, Y complete

On load:
- Prompt for ANNOTATOR_KEY (stored in sessionStorage)
- Fetch queue from /v1/seed/queue
- Load first pending document
- Load PDF.js and render document

Keyboard shortcuts:
1-5: select correction class
Enter: save current annotation and advance to next extraction
N: add negative space flag
C: complete session
S: skip document

Style: clean, functional, high contrast. Dark mode preferred since this is an extended annotation session tool. No decorative elements.

Save as a single self-contained HTML file. Test by opening locally with a CORS-permissive browser flag and hitting the staging Worker API.
```

---

## 6b. Step 5b — SEED Master Control (Full Ops Dashboard)

### 6b.1 What This Does

A standalone desktop web application deployed to Cloudflare Pages that serves as the complete operational interface for the seed corpus annotation operation and ADI system management. It is not part of the Record Health iOS app — it is an internal tool, separate URL, separate deployment.

The annotation interface from Step 5 (the three-panel annotator) becomes one of four screens in this tool. The other three screens cover system state, corpus silo management, and PatternLibrary review. Together they give you everything you need to run the annotation operation, monitor accuracy progress, manage the corpus splits, and approve or reject rule promotions — all in one place without writing queries against Neon manually.

**Why standalone, not superuser mode in Record Health:**

- Annotation requires desktop screen real estate — a three-panel side-by-side layout is not practical on mobile
- The tool iterates independently of the iOS app — no App Store review cycle for operational changes
- App Store guidelines are skeptical of superuser functionality in consumer health apps
- The ops dashboard (benchmark scores, PatternLibrary state, Bedrock suggestions, corpus version) belongs on a desktop management interface

**Who uses it:**

- L0 (you): all four screens, full admin access
- L1 annotators: annotation queue screen only, simplified correction form
- L2 data scientist: all screens, no approval authority on PatternLibrary
- L3 medical practitioner: annotation queue screen with full correction class support

Role gating is done via the `ANNOTATOR_KEY` env var with a simple role suffix: `{key}:L0`, `{key}:L1`, etc. The interface reads the role from the key and shows/hides screens accordingly.

### 6b.2 Screen Architecture

```
SEED Master Control
├── Dashboard        System state at a glance
│   ├── Accuracy metrics by field type (bar chart, delta vs prior run)
│   ├── System maturity phase + promotion gate status
│   ├── Corpus split document counts
│   ├── Pending review counts (seed candidates + Bedrock suggestions)
│   └── Silent miss rate trend
│
├── Annotation queue  Document review and tagging (L0/L1/L2/L3)
│   ├── LEFT: Document viewer (PDF.js rendering with bounding box overlays)
│   │   ├── Red box: extraction flagged as incorrect
│   │   ├── Amber box: extraction unreviewed
│   │   ├── Green box: extraction confirmed correct
│   │   └── Blue dashed box: ground truth field with no extraction (negative space)
│   ├── CENTER: Correction form
│   │   ├── Selected extraction display (field type, value, unit, confidence)
│   │   ├── Ground truth comparison (match/mismatch indicator)
│   │   ├── Correction class selector (A–E radio buttons)
│   │   ├── Class-conditional correction fields (label, canonical ID, unit, rationale)
│   │   └── Requires L3 review checkbox
│   └── RIGHT: Session controls
│       ├── Progress (N of M reviewed, flagged count, negative space count)
│       ├── Negative space panel (add missing field form)
│       ├── Keyboard shortcuts reference
│       ├── Save annotation / Complete session / Skip document buttons
│       └── Queue stats (pending, in progress, complete)
│
├── Corpus manager    Silo versioning and benchmark history (L0/L2)
│   ├── Three silo cards (Training / Validation / Test)
│   │   ├── Version badge, document count, annotated count
│   │   ├── Layout hash count, status badge (Active/Shadow/Locked)
│   │   └── Last modified timestamp
│   ├── Benchmark history table (run date, F1 score, delta, gate result)
│   └── Run benchmark button (triggers POST /v1/seed/benchmark)
│
└── PatternLibrary    Candidate review and promotion management (L0 only)
    ├── Pending approval queue (seed corpus candidates)
    │   ├── Rule per row: class, category, field type, observation count, diversity
    │   ├── Sample atoms expandable view
    │   └── Approve / Reject buttons (fires POST /v1/admin/seed/approve or reject)
    ├── Bedrock suggestions queue
    │   ├── Terminology suggestions with confidence scores
    │   ├── Rule suggestions with impact/complexity ratings
    │   └── Classification disagreements requiring annotation review
    └── Promoted rules table (version history, confidence scores, source)
```

### 6b.3 Sprint Prompt — Step 5b

```
Reference: SEED_CORPUS_STARTER_KIT.md sections 6.2 (Step 5 Worker API endpoints),
12.4 (Step 9 Bedrock analysis endpoints), SERVER_INFRASTRUCTURE.md sections 5.4, 5.5, 5.6

Build the SEED Master Control as a Cloudflare Pages deployment. The app is a
single HTML file at tools/seed-master-control/index.html. No build step, no
framework, no dependencies except PDF.js (from cdnjs) and Chart.js (from cdnjs).
All styling uses CSS variables matching the Record Health design system.

The app has four screens navigated by a left sidebar. Role-gating controls
which screens are accessible based on the ANNOTATOR_KEY role suffix.

─── SHELL AND NAVIGATION ────────────────────────────────────────────

Overall layout: CSS grid, two columns — 180px sidebar + 1fr main.
Min-height: 100vh. No outer padding. Border between sidebar and main: 0.5px.

Sidebar:
- Tool name "SEED Control" at top in 11px uppercase muted text
- Four nav items: Dashboard / Annotation queue / Corpus manager / PatternLibrary
- Each nav item has a 7px colored dot (gray/teal/purple/amber per screen)
- Active state: white background, 2px right border, font-weight 500
- Sidebar background: var(--color-background-secondary)

Auth on load:
- Prompt for ANNOTATOR_KEY via a centered modal overlay (not browser prompt)
- Parse role from key suffix: key ending ':L0' → role L0, ':L1' → L1, etc.
  If no suffix, default to L1
- Store key and role in sessionStorage
- L0: all four nav items visible
- L1: Annotation queue only
- L2: Dashboard + Annotation queue + Corpus manager
- L3: Annotation queue only (same as L1 but full correction class support)
- Show role badge in sidebar footer: "L0 — admin"

─── SCREEN 1: DASHBOARD ─────────────────────────────────────────────

On load, fetch:
  GET /v1/seed/benchmark/history (last run)
  GET /v1/seed/queue (stats block only)
  GET /v1/admin/seed/candidates (count only)
  GET /v1/admin/seed/analysis-review (counts only)

Top metric row — four cards in a 4-column grid:
  "Documents annotated" — from queue stats.complete
  "Overall F1" — from latest benchmark_run.overall_accuracy, formatted as percent
  "PatternLibrary version" — from GET /v1/pattern-library/latest
  "Pending review" — sum of candidates + Bedrock suggestions

Accuracy by field type — horizontal bar chart using Chart.js:
  One bar per field type (numericLabValue, medicationName, unitResolution,
  columnAttribution, referenceRange, terminologyNormalization)
  Bar color: green if >= threshold (0.78), amber if 0.65-0.78, red if < 0.65
  Each bar shows current F1 and delta vs prior benchmark run
  Use Chart.js horizontal bar chart, x-axis 0-1, labels on left

System maturity card — right column alongside the chart:
  Phase badge (seed/early/scaling/steady mapped to amber/blue/teal/green)
  Promotion gate status (Open/Closed)
  Trust ladder progress (N users of 500 threshold)
  Silent miss rate
  Corpus split versions
  Bedrock suggestions pending count

─── SCREEN 2: ANNOTATION QUEUE ──────────────────────────────────────

On load: GET /v1/seed/queue → load first pending document
On document load: GET /v1/seed/document/:id → load extractions + ground truth + PDF

Three-panel CSS grid layout: 2fr 1.4fr 1fr, height calc(100vh - 120px)

LEFT PANEL — Document viewer:
  Load PDF using PDF.js from cdnjs
  Render current page to a canvas element
  Page navigation: prev/next buttons, "Page N of M" display
  After rendering each page, draw bounding box overlays as absolutely-positioned
  divs on top of the canvas:
    - Red border + red tint: extractions where annotation.correction_class != null
    - Amber border + amber tint: extractions where no annotation exists yet
    - Green border + green tint: extractions annotated as 'no correction needed'
    - Blue dashed border + blue tint: ground_truth fields with no matching extraction
  On click of a bounding box: load that extraction into the center panel
  Legend below canvas: colored squares + labels for each box type

CENTER PANEL — Correction form:
  Selected extraction section (always visible):
    Field type badge, extracted label → value + unit
    Confidence score as a small progress bar (0-1)
    Ground truth comparison row:
      Show ground truth label → value + unit
      Match indicator: green checkmark if values match, red X if mismatch
      "No ground truth" in gray if ground truth field is absent

  Correction class radio group (6 options):
    No correction needed
    A — correct value, wrong label
    B — correct atoms, wrong association
    C — correct extraction, missing qualifier
    D — locally correct, globally incoherent
    E — silent absence (redirects to negative space panel)
  Selected option highlighted with font-weight 500 and filled dot

  Class-conditional correction fields (show/hide based on selected class):
    Class A: Correct label (text input), Canonical ID (text input with
             "LOINC:XXXXX or RxNorm:XXXXX" placeholder), Correct unit (text input)
    Class B: Association description (textarea)
    Class C: Missing qualifier (text input), Corrected canonical ID (text input)
    Class D: Global context issue (textarea)
    Class E: Redirect to negative space panel — show inline "Use the negative
             space form in the right panel for silent absences"

  Clinical rationale textarea (all classes except 'no correction needed')
  Requires L3 review checkbox (shown for L0/L2 only)

  Save annotation button:
    POST /v1/seed/annotate with current extraction annotation
    On success: advance to next unreviewed extraction in document
    On error: show inline error, do not advance

RIGHT PANEL — Session controls:
  Progress card:
    "N of M reviewed" with progress bar
    "N flagged · N negative space" in muted text

  Negative space card:
    List of existing negative space flags for this document
    Add missing field button → expands inline form:
      Field type dropdown (numericLabValue, medicationName, date, etc.)
      Canonical ID text input
      Visually present toggle (yes/no)
      Clinical significance select (low/medium/high/critical)
      Clinical rationale textarea
      Save button → POST /v1/seed/annotate with negativeSpaceFlags array

  Keyboard shortcuts card:
    Static reference — 1-5 for correction class, Enter to save + next,
    N for negative space, S to skip, C to complete session

  Action buttons:
    Save annotation (primary style)
    Complete session (marks document annotated, loads next from queue)
    Skip document (returns to queue without marking complete)

  Queue stats footer: X pending, Y complete, Z in progress

Keyboard event handler on document:
  Keys 1-5: select correction class (1=none, 2=A, 3=B, 4=C, 5=D)
  Enter: save current annotation and advance to next extraction
  N: focus negative space form
  S: skip document
  C: complete session (with confirmation prompt)

─── SCREEN 3: CORPUS MANAGER ────────────────────────────────────────

On load: GET /v1/seed/queue (for corpus stats per split)
         GET /v1/seed/benchmark/history (last 10 runs)

Three silo cards in a 3-column grid:
  Each card: silo name, version badge, document count, annotated count,
  layout hash count, atoms generated count, status badge
  Status badges: Active (green) / Shadow testing (blue) / Locked (gray)
  Training and Validation cards show a small "Last modified" timestamp
  Test card shows "Last benchmark" timestamp

Run benchmark button:
  POST /v1/seed/benchmark { corpusSplit: 'training', sampleSize: 30 }
  Show loading state on button during request
  On completion: refresh benchmark history table + metric cards

Benchmark history table:
  Columns: Run date · Test silo version · F1 · Delta · Gate result
  Color-code gate result: Baseline (amber) / Approved (green) / Blocked (red)
  Clicking a row expands to show per-field-type breakdown for that run
  Last 10 runs, newest first

─── SCREEN 4: PATTERNLIBRARY ────────────────────────────────────────

On load: GET /v1/admin/seed/candidates
         GET /v1/admin/seed/analysis-review
         GET /v1/admin/seed/promoted

Pending approval section:
  One row per candidate rule:
    Confusion class (font-weight 500), document category, field type
    Observation count badge, diversity score
    Status badge: seed_pending_review (amber)
    Expandable: click row to show sample atoms (first 3) as a sub-table
    Approve button → POST /v1/admin/seed/approve { candidateRuleId, approvedBy: role }
      On success: remove row, show "Approved — promotes at next 2AM CRON"
    Reject button → POST /v1/admin/seed/reject { candidateRuleId, rejectedBy: role }
      On success: remove row, show "Rejected"

Bedrock suggestions section (three sub-lists):
  1. Terminology suggestions:
     Surface form → suggested canonical term + ID
     Confidence score (color-coded: green >= 0.85, amber 0.70-0.85, red < 0.70)
     Provider-specific flag if true (show warning badge)
     Approve → POST /v1/admin/seed/analysis-approve { type: 'terminology', id, decision: 'approved' }
     Skip → POST /v1/admin/seed/analysis-approve { type: 'terminology', id, decision: 'rejected' }

  2. Rule suggestions:
     Rule name + pipeline stage badge
     Impact/complexity badges
     Expandable: click to show full implementation approach + test case
     Approve → POST /v1/admin/seed/analysis-approve { type: 'rule', id, decision: 'approved' }
     Skip → dismiss

  3. Classification disagreements:
     Your classification vs Bedrock classification
     Bedrock reasoning (truncated to 80 chars, expand on click)
     Update annotation → opens annotation queue to the specific document/extraction
     Skip → dismiss

Promoted rules table:
  Version · Confusion class · Category · Field type · Confidence · Source
  Rows in newest-first order
  Source badge: seedCorpus (teal) / bedrockSuggested (blue) / userCorrection (green)
  Click row → expandable rule definition JSON view

─── DEPLOYMENT ──────────────────────────────────────────────────────

Create wrangler.toml for the Pages project at tools/seed-master-control/wrangler.toml:

name = "seed-master-control"
pages_build_output_dir = "."

The single HTML file is the entire deployment.
Deploy with: cd tools/seed-master-control && wrangler pages deploy .

The app reads the Worker API base URL from a config block at the top of the HTML:
const CONFIG = {
  workerUrl: 'https://api.recordhealth.workers.dev',
  // Override for local dev:
  // workerUrl: 'http://localhost:8787'
}

All fetch calls use CONFIG.workerUrl as the base, append the ANNOTATOR_KEY as
Authorization: Bearer {key} header (before the role suffix is stripped).

─── QUALITY REQUIREMENTS ────────────────────────────────────────────

Dark mode default: prefers-color-scheme: dark is the primary mode.
All colors use CSS variables — nothing hardcoded.
Responsive to viewport width >= 1200px. No mobile layout required.
All async operations show a loading state on the triggering element.
All errors show inline — never silent failures, never browser alerts.
Keyboard shortcuts work when focus is not in a text input.
PDF.js renders asynchronously — show a skeleton placeholder while loading.
Bounding box overlays recompute on page navigation and PDF scale changes.
Chart.js renders after the benchmark data loads — not a static chart.

Save the complete app as tools/seed-master-control/index.html.
Test by deploying to Cloudflare Pages staging environment and running
the full annotation workflow against at least 3 seed documents.
```

---

## 7. Step 6 — PatternAtom Generator

### 7.1 What This Does

### 7.2 Sprint Prompt — Step 6

```
Reference: ADAPTIVE_DOCUMENT_INTELLIGENCE.md sections 4.2, 4.3 (PatternAtom schema and PHI strip verifier), section 8.4 (seed corpus quality anchor)

Add a Worker endpoint and a scheduled job that converts completed expert_annotations into PatternAtoms.

POST /v1/seed/generate-atoms (protected, admin key)
Accepts: { "seedDocumentIds": ["id1", "id2"] } or { "all": true } for all annotated docs

For each expert_annotation record:
1. Map correction fields to PatternAtom schema:
   - confusionClass: derive from correctionClass using this mapping:
     A → d2_columnMisattribution or d2_labelValueInversion (based on correctionDetail)
     B → d2_sectionBoundaryFailure
     C → d2_qualifierDropout  
     D → d2_sectionBoundaryFailure
     E → log as negative_space, do not produce PatternAtom (handled separately)
   - fieldType: from extraction_output.fieldType
   - documentCategory: from seed_documents.document_category
   - providerLayoutHash: from seed_documents.provider_layout_hash
   - ocrConfidencePre: from extraction_output.confidence
   - ocrConfidencePost: 0.95 (annotated corrections are high confidence by definition)
   - resolvedCanonicalId: from correctionDetail.correctCanonicalId
   - correctionSource: 'seedCorpus'
   - seedAgreementScore: null (seed corpus atoms don't self-reference)

2. Run PHI strip verifier against the produced atom:
   - No string field contains date patterns (MM/DD/YYYY, YYYY-MM-DD, Month DD YYYY)
   - No string field contains name patterns (Title Firstname Lastname)
   - No string field contains SSN pattern (XXX-XX-XXXX)
   - resolvedCanonicalId if present matches LOINC:XXXXXXX or RxNorm:XXXXXX or SNOMED:XXXXXX
   - providerLayoutHash is exactly 16 hex characters
   If any check fails: log error, skip this annotation, do not produce atom

3. Write to pattern_atoms table with:
   - corpus_split: same as the annotation's corpus_split
   - processed: false
   - All PatternAtom fields from the schema

4. For negative_space_annotations: write to a separate seed_negative_space_atoms table
   (structure: document_category, missing_field_type, missing_canonical_id, 
   clinical_significance, corpus_split, processed)

Return:
{
  "atomsGenerated": N,
  "annotationsSkipped": M,
  "skipReasons": ["phi_detected: annotation abc123", ...],
  "negativeSpaceAtoms": K
}

Also add this logic to the existing daily consensus CRON job:
After step 1 (update system maturity metrics), run:
  - Count unprocessed seed corpus atoms in pattern_atoms where corpus_split = 'training' 
    and correction_source = 'seedCorpus' and processed = false
  - For seed atoms: apply 1.5x threshold multiplier (as per ADI spec section 11.5)
  - Seed atoms bypass the validation window — they go directly to 'passed' status
    after manual review flag is set (requires requires_manual_signoff field in candidate_rules)
  - Add requires_manual_signoff BOOLEAN DEFAULT TRUE to candidate_rules for seed-sourced candidates
  - Promotion only fires when requires_manual_signoff is set to false via:
    POST /v1/seed/approve-candidate { "candidateRuleId": "..." }  (admin key protected)
```

---

## 8. Step 7 — Programmatic Sampling Engine

### 8.1 What This Does

A Worker cron job and on-demand endpoint that randomly samples documents from the training silo, runs them through a scoring comparison against annotated ground truth, and computes per-class accuracy metrics. This is what tells you whether the seed corpus is producing real signal — the internal benchmark before the formal test silo gate.

### 8.2 Sprint Prompt — Step 7

```
Reference: SEED_CORPUS_AND_TAXONOMY.md sections 4.5.3 (baseline benchmark), 4.9 (production gate thresholds)

Add a sampling and scoring engine to the Worker.

POST /v1/seed/benchmark (protected, admin key)
Accepts:
{
  "corpusSplit": "training",    // or "validation"
  "sampleSize": 50,             // number of documents to sample
  "patternLibraryVersion": "current",
  "notes": "post-first-100-annotations baseline"
}

The endpoint:
1. Randomly samples sampleSize seed_documents from the specified corpus_split
   where annotation_status = 'annotated'
2. For each sampled document, loads:
   - The most recent extraction_runs row for that document
   - All expert_annotations rows for that document
   - The ground_truth JSON from seed_documents
3. Scores each extraction against ground truth and annotations:

   For each extraction in extraction_runs.extractions:
   a. Find the matching ground truth field (match by approximate bounding box overlap > 50%)
   b. If matched: compare extracted value against ground truth value
      - exact_match: extracted value == ground truth value (case insensitive, trimmed)
      - canonical_match: resolved canonical IDs match (stronger signal)
      - unit_match: extracted unit matches ground truth unit
   c. Check expert_annotations for this extraction:
      - If annotation exists and correctionClass != null: this was a failure
      - correctionClass tells you what kind of failure
   
   Compute per-document scores:
   - true_positives: extractions with no annotation (pipeline got it right)
   - false_positives: extractions with annotation (pipeline got it wrong)
   - false_negatives: negative_space_annotations for this document (silent misses)
   - precision = TP / (TP + FP)
   - recall = TP / (TP + FN)
   - f1 = 2 * precision * recall / (precision + recall)

4. Aggregate across all sampled documents:
   - results_by_field_type: { numericLabValue: {precision, recall, f1, n}, ... }
   - results_by_category: { labReport: {precision, recall, f1, n}, ... }
   - results_by_class: { A: N, B: N, C: N, D: N, E: N }  (failure class distribution)
   - overall_accuracy: mean F1 across all field types
   - false_positive_rate: total FP / (total FP + total TP)
   - false_negative_rate: total FN / (total FN + total TP)
   - silent_miss_rate: negative space annotations / total expected extractions

5. Evaluate against production gate thresholds (from ADI spec section 4.9.2):
   numericLabValue: 0.82, medicationName: 0.78, unitResolution: 0.75,
   columnAttribution: 0.72, referenceRange: 0.78, overall: 0.78
   Set gate_result: 'approved' | 'blockedFloor' | 'blockedRegression' | 'baselineEstablished'

6. Write to benchmark_runs table, return full results JSON

GET /v1/seed/benchmark/history
Returns last 20 benchmark_runs ordered by created_at desc.
Include delta from previous run for each metric (null for first run).

GET /v1/seed/benchmark/failures
Returns the top 20 most common failure patterns across all annotated documents:
- Grouped by confusionClass + documentCategory + fieldType
- Ordered by frequency desc
- This tells you which failure modes to prioritize in the next annotation pass

Add to wrangler.toml cron triggers: "0 6 * * 1" (weekly Monday 6AM UTC)
Weekly benchmark auto-runs against training split, sample size 30, writes to benchmark_runs.
Does not trigger promotion — benchmark is observational unless manually reviewed.
```

---

## 9. Step 8 — Promotion Evaluation and PatternLibrary Writer

### 9.1 What This Does

Extends the existing ADI consensus CRON job to handle seed corpus atoms through the promotion pipeline, with the manual sign-off gate that prevents automatic promotion without your review. Adds a simple admin endpoint to approve candidates after review.

### 9.2 Sprint Prompt — Step 8

```
Reference: ADAPTIVE_DOCUMENT_INTELLIGENCE.md section 8.7 (consensus CRON job), section 11.5 (seed corpus weighting), SEED_CORPUS_AND_TAXONOMY.md section 4.9 (production gate)

Extend the existing adiConsensusHandler in index.js to include seed corpus promotion.

Add to the consensus CRON pipeline, after step 2 (evaluate candidate rules), a new step 2b:

STEP 2b: Seed corpus candidate evaluation

Query pattern_atoms where correction_source = 'seedCorpus' and processed = false.
Group by (confusion_class, document_category, field_type, ocr_engine).
For each group:
  a. Count atoms: observation_count
  b. Check provider_layout_hash diversity: count distinct hashes = diversity_count
  c. Apply seed thresholds (1.5x multiplier on standard thresholds from consensus_config):
     - min_observations_seed = floor(min_observations * 1.5)
     - min_diversity_seed = min_diversity (same, not multiplied)
  d. If observation_count >= min_observations_seed AND diversity_count >= 5:
     - Check if candidate_rule already exists for this combination
     - If not: INSERT into candidate_rules with:
         status: 'seed_pending_review'
         requires_manual_signoff: true
         observation_count: from atoms
         diversity_score: diversity_count / 10.0 (normalized)
         validation_status: 'pending'
         source: 'seedCorpus'
     - If exists and status = 'seed_pending_review': update counts
  e. Mark contributing atoms as processed = true

STEP 2c: Approved seed candidate promotion

Query candidate_rules where status = 'seed_pending_review' and requires_manual_signoff = false.
For each:
  a. Assign new PatternLibrary version (PATCH increment)
  b. Write to pattern_library:
     - All rule fields
     - source_candidate_id = candidate_rules.id
     - confidence_score = observation_count / (observation_count + 5) * diversity_score
       (shrinkage formula — seed rules start with conservative confidence)
  c. Compute library diff from previous version
  d. Write diff to distribution
  e. Update candidate_rules.status = 'promoted'
  f. Log to consensus_log with decision = 'promoted', decision_reason = 'seed_corpus_manual_review'

Add these admin endpoints (ADMIN_KEY protected):

GET /v1/admin/seed/candidates
Returns all candidate_rules where source = 'seedCorpus' and status = 'seed_pending_review':
{
  "candidates": [
    {
      "id": "...",
      "confusionClass": "d2_columnMisattribution",
      "documentCategory": "labReport",
      "fieldType": "numericLabValue",
      "observationCount": 12,
      "diversityScore": 0.7,
      "sampleAtoms": [ first 3 atoms for review ],
      "representativeAnnotations": [ first 3 annotations that contributed ]
    }
  ]
}

POST /v1/admin/seed/approve
Body: { "candidateRuleId": "...", "approvedBy": "L0", "approvalNotes": "..." }
Sets requires_manual_signoff = false on the candidate.
Promotion fires on the next CRON run (next 2AM UTC).
Returns { "approved": true, "willPromoteAt": "next cron run" }

POST /v1/admin/seed/reject
Body: { "candidateRuleId": "...", "rejectedBy": "L0", "rejectionReason": "..." }
Sets status = 'rejected' on the candidate.
Logs to consensus_log with decision = 'rejected'.

GET /v1/admin/seed/promoted
Returns all pattern_library entries with source_candidate_id referencing a seed corpus candidate.
Includes current confidence scores and observation counts.
This is the live view of what the seed corpus has actually contributed to the PatternLibrary.
```

---

## 11. Operating Procedure

With all eight components in place, the annotation operation runs as follows:

### 10.1 Daily Workflow (Stage 1)

```
1. Run document renderer to ingest new rendered documents
   python scripts/document_renderer.py --count 20

2. Run extraction pipeline runner against new documents  
   SeedCorpusRunner --pdf-dir data/rendered/ --limit 20

3. Open SEED annotation interface
   tools/seed-annotator/index.html
   
4. Work through annotation queue
   Target: 10–20 documents per annotation session
   Apply correction classes A–E
   Flag negative space where present
   Complete each session

5. Generate atoms from completed annotations
   POST /v1/seed/generate-atoms { "all": true }

6. Review pending candidates
   GET /v1/admin/seed/candidates
   Review sample atoms and representative annotations
   Approve or reject each candidate

7. Approved candidates promote at next 2AM CRON run
```

### 10.2 Weekly Workflow

```
Monday 6AM UTC: Automated benchmark runs against training split (30 documents)
Review benchmark_runs via GET /v1/seed/benchmark/history
Compare delta from prior week
Check GET /v1/seed/benchmark/failures for failure class distribution
Adjust annotation focus based on failure distribution
  — If d2_columnMisattribution is high: prioritize lab report annotation this week
  — If false_negative_rate rising: do a negative space annotation pass
```

### 10.3 Pre-Launch Milestone Check

Before launch, the seed corpus should pass:

```
Benchmark run against validation split:
├── overall_accuracy >= 0.61 (matches the example baseline in spec)
├── All document categories represented with N >= 20 documents
├── At least 5 distinct providerLayoutHash values per category
├── negative_space_annotations exist for at least 20% of documents
├── All 5 correction classes (A–E) represented in annotations
└── gate_result: 'baselineEstablished'

PatternLibrary state:
├── At least 500 promoted rules (GET /v1/admin/seed/promoted count)
├── Coverage across all 8 Domain 2 layout confusion classes
├── Coverage across top 20 lab test terminology variants
├── Coverage across top 20 medication brand→generic mappings
└── pattern_library version >= 0.1.0
```

---

## 12. Step 9 — Bedrock Failure Analysis Layer

### 12.1 What This Does

After each benchmark run, this layer sends the failure distribution and extraction output pairs to AWS Bedrock for three distinct analysis passes: failure classification validation, terminology variant discovery, and rule suggestion generation. No MIMIC source content is transmitted — only your pipeline's structured output and your ground truth labels.

This is the feedback accelerator. Instead of waiting for annotation sessions to surface every failure pattern manually, Bedrock reads your benchmark output and tells you where the pipeline is falling short, what terminology gaps exist, and what rules would close them. You review the suggestions before anything is promoted — Bedrock proposes, you dispose.

### 12.2 PhysioNet Compliance Boundary

The constraint is narrow and the architecture respects it cleanly:

```
STAYS LOCAL — never sent to Bedrock
├── Raw MIMIC CSV files
├── Rendered PDFs containing MIMIC clinical text
├── VisionKit OCR output from MIMIC-rendered documents
└── Any string containing MIMIC patient record content

BEDROCK ELIGIBLE — your pipeline output, not MIMIC content
├── Structured extraction JSON { fieldType, label, value, unit, confidence }
├── Ground truth labels { label, canonicalId, value, unit }
├── Failure class distributions from benchmark_runs table
├── Anonymized extraction pairs (extracted vs ground truth, no source text)
└── PatternAtoms (PHI-stripped, non-MIMIC content by construction)
```

The Bedrock calls never see clinical note text, radiology report prose, or any MIMIC narrative content. They see your pipeline's structured output compared against your ground truth labels — both of which are artifacts you produced, not MIMIC data.

### 12.3 Three Analysis Passes

**Pass 1 — Failure classification validation**

Sends extraction/ground-truth pairs to Bedrock and asks it to classify each failure using your confusion class taxonomy. Compare against your L0 manual classifications. Divergences surface taxonomy gaps and annotation guideline ambiguities.

**Pass 2 — Terminology variant discovery**

Sends unresolved terminology surface forms to Bedrock and asks for enumeration of additional variants not yet in your variant table. Expands terminology coverage without manual enumeration.

**Pass 3 — Rule suggestion generation**

Sends the benchmark failure distribution to Bedrock and asks for specific rule additions per failure cluster, including pipeline stage, implementation approach, and test case.

### 12.4 Sprint Prompt — Step 9 (Worker Endpoints)

```
Reference: SERVER_INFRASTRUCTURE.md section 9 (Bedrock integration via aws4fetch),
SEED_CORPUS_AND_TAXONOMY.md section 2.2-2.3 (confusion class taxonomy),
EXPERT_ANNOTATION_AND_MODEL_TRAINING.md section 2.2 (correction classes A-E)

Add a Bedrock failure analysis layer to the recordhealth-api Worker. 
Uses the existing aws4fetch SigV4 Bedrock integration already in index.js.
All three endpoints are admin-key protected.

─── SHARED BEDROCK HELPER ───────────────────────────────────────────

Extract the existing Bedrock call logic into a shared helper function
callBedrock(prompt, maxTokens = 1500) that:
- Constructs the SigV4 signed request using existing aws4fetch pattern
- Uses env.BEDROCK_MODEL_ID (existing env var)
- Parses and returns the text response content
- Throws on non-200 response with the error body

─── ENDPOINT 1: POST /v1/seed/analyze/classify-failures ─────────────

Purpose: Validate your L0 failure classifications against Bedrock's
independent classification. Surfaces taxonomy gaps.

Request body:
{
  "pairs": [
    {
      "pairId": "uuid",
      "documentCategory": "labReport",
      "layoutType": "LabCorpStyle",
      "extracted": {
        "fieldType": "numericLabValue",
        "label": "Sodium",
        "value": "140",
        "unit": "mEq/L",
        "confidence": 0.71
      },
      "groundTruth": {
        "label": "Glucose",
        "value": "140",
        "unit": "mg/dL",
        "canonicalId": "LOINC:2345-7"
      },
      "yourClassification": "d2_columnMisattribution"
    }
  ]
}
Max 20 pairs per request. Validate this limit and return 400 if exceeded.

Build this system prompt:
"You are an expert in medical document OCR pipeline failure analysis.
You classify extraction failures using a defined taxonomy.
You always respond with valid JSON only, no prose, no markdown."

Build this user prompt per pair (concatenate all pairs into one prompt):
"Classify this extraction failure:
Document type: {documentCategory}, layout: {layoutType}
Extracted: label={label}, value={value}, unit={unit}, confidence={confidence}
Ground truth: label={gtLabel}, value={gtValue}, unit={gtUnit}, canonicalId={canonicalId}

Confusion class taxonomy (use exact enum values):
d1_alphanumericSubstitution, d1_ligatureCollapse, d1_punctuationDropout,
d1_lowContrastDropout, d1_skewDistortion, d1_motionBlur, d1_shadowIntrusion,
d1_compressionArtifact, d1_faxHalftone, d1_generationLoss, d1_stampOverlay,
d2_columnMisattribution, d2_referenceRangeCollision, d2_labelValueInversion,
d2_headerValueCollision, d2_multiPageContextLoss, d2_sectionBoundaryFailure,
d2_reflowArtifact, d2_impliedUnitContext, d2_lineBreakIntrusion,
d2_terminologyVariant, d2_brandToGenericFailure, d2_formularyCodeUnresolved,
d2_unitVariant, d2_numericFormatVariant, d2_negationMisparse,
d2_qualifierDropout, d2_contextualAbbreviationCollision, unknown

Pipeline stages: preprocessing, ocrEngine, layoutUnderstanding, semanticParsing

For pair {pairId} return JSON:
{
  \"pairId\": \"{pairId}\",
  \"confusionClass\": \"enum_value\",
  \"pipelineStage\": \"stage_name\",
  \"confidence\": 0.0-1.0,
  \"reasoning\": \"one sentence\",
  \"taxonomyGapDetected\": true/false,
  \"taxonomyGapDescription\": \"if gap detected, describe it\"
}"

Wrap all pairs in one prompt, request JSON array response.
Parse Bedrock response as JSON array.

For each pair, compute:
- agreement: yourClassification === bedrock.confusionClass
- disagreement: different classifications

Write results to a new table bedrock_analysis_runs:
CREATE TABLE IF NOT EXISTS bedrock_analysis_runs (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    analysis_type TEXT NOT NULL,
    input_count INT,
    results JSONB NOT NULL,
    agreement_rate FLOAT,
    taxonomy_gaps_detected INT,
    bedrock_model TEXT,
    prompt_tokens_approx INT,
    notes TEXT
);

Return:
{
  "runId": "uuid",
  "pairsAnalyzed": N,
  "agreementRate": 0.82,
  "disagreements": [
    {
      "pairId": "...",
      "yourClassification": "d2_columnMisattribution",
      "bedrockClassification": "d2_labelValueInversion",
      "bedrockReasoning": "...",
      "reviewRecommended": true
    }
  ],
  "taxonomyGaps": [
    { "pairId": "...", "description": "..." }
  ]
}

─── ENDPOINT 2: POST /v1/seed/analyze/terminology-gaps ──────────────

Purpose: Discover terminology surface forms not in your variant table.
Expands terminology coverage without manual enumeration.

Request body:
{
  "unresolved": [
    {
      "surfaceForm": "BMP",
      "documentContext": "lab report section header",
      "documentCategory": "labReport",
      "fieldType": "panelName",
      "attemptedCanonicalId": null
    }
  ]
}
Max 30 surface forms per request.

System prompt:
"You are a medical terminology expert with deep knowledge of LOINC, RxNorm,
SNOMED-CT, and clinical abbreviation conventions.
You always respond with valid JSON only."

User prompt per surface form (batch all into one prompt):
"Analyze this unresolved medical terminology surface form:
Surface form: \"{surfaceForm}\"
Context: {documentContext}
Document type: {documentCategory}
Field type: {fieldType}

Provide:
1. The canonical term this likely refers to
2. The canonical ID (LOINC:XXXXX, RxNorm:XXXXX, SNOMED:XXXXX, or ICD10:XXXXX)
3. All known surface variant forms that should resolve to this canonical term
4. Confidence that this is the correct canonical mapping (0-1)
5. Whether this appears to be provider-specific nomenclature unlikely to appear broadly

Return JSON:
{
  \"surfaceForm\": \"{surfaceForm}\",
  \"canonicalTerm\": \"...\",
  \"canonicalId\": \"...\",
  \"canonicalSystem\": \"LOINC|RxNorm|SNOMED|ICD10|unknown\",
  \"variants\": [\"list\", \"of\", \"surface\", \"forms\"],
  \"mappingConfidence\": 0.0-1.0,
  \"isProviderSpecific\": true/false,
  \"notes\": \"any caveats\"
}"

Parse JSON array response from Bedrock.

Write results to bedrock_analysis_runs.
Also write high-confidence results (mappingConfidence >= 0.85, isProviderSpecific = false)
to a terminology_suggestions table:
CREATE TABLE IF NOT EXISTS terminology_suggestions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    surface_form TEXT NOT NULL,
    canonical_term TEXT,
    canonical_id TEXT,
    canonical_system TEXT,
    variants JSONB,
    mapping_confidence FLOAT,
    is_provider_specific BOOLEAN,
    bedrock_notes TEXT,
    review_status TEXT DEFAULT 'pending',
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    approved BOOLEAN
);

Return:
{
  "runId": "uuid",
  "surfaceFormsAnalyzed": N,
  "suggestionsGenerated": M,
  "highConfidenceSuggestions": K,
  "suggestions": [ ...full results array... ]
}

─── ENDPOINT 3: POST /v1/seed/analyze/suggest-rules ─────────────────

Purpose: Given the benchmark failure distribution, generate specific
rule additions that would reduce the highest-frequency failure clusters.

Request body:
{
  "benchmarkRunId": "uuid",
  "topN": 5
}

Fetch the benchmark_run row for benchmarkRunId.
Extract top N failure types from results_by_field_type and results_by_class
sorted by (1 - f1_score) descending — worst performers first.

System prompt:
"You are an expert in building medical document extraction pipelines.
You design specific, implementable extraction rules to fix identified failure patterns.
You always respond with valid JSON only."

User prompt:
"This medical document extraction pipeline has the following failure distribution
from a benchmark run against {sampleSize} annotated documents:

Top failure patterns:
{topFailures formatted as: rank. confusionClass in documentCategory (fieldType): precision=X recall=X f1=X count=N}

Overall pipeline accuracy: {overallAccuracy}
Silent miss rate (unextracted fields): {silentMissRate}

For each failure pattern, provide a specific extraction rule that would reduce it.

Return JSON array, one entry per failure pattern:
{
  \"failurePattern\": \"d2_columnMisattribution in labReport\",
  \"currentF1\": 0.52,
  \"suggestedRuleType\": \"layout|terminology|preprocessing|semantic\",
  \"pipelineStage\": \"layoutUnderstanding\",
  \"ruleName\": \"short descriptive name\",
  \"ruleDescription\": \"what the rule does in plain language\",
  \"implementationApproach\": \"how to implement — specific and actionable\",
  \"testCase\": {
    \"input\": \"describe the document region that triggers this rule\",
    \"expectedOutput\": \"what correct extraction looks like\",
    \"failureSignature\": \"what the pipeline currently produces wrong\"
  },
  \"estimatedImpact\": \"low|medium|high\",
  \"implementationComplexity\": \"low|medium|high\",
  \"caveats\": \"any risks or edge cases to watch for\"
}"

Parse JSON array from Bedrock.
Write to a rule_suggestions table:
CREATE TABLE IF NOT EXISTS rule_suggestions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    benchmark_run_id TEXT REFERENCES benchmark_runs(id),
    failure_pattern TEXT NOT NULL,
    current_f1 FLOAT,
    suggested_rule_type TEXT,
    pipeline_stage TEXT,
    rule_name TEXT,
    rule_description TEXT,
    implementation_approach TEXT,
    test_case JSONB,
    estimated_impact TEXT,
    implementation_complexity TEXT,
    caveats TEXT,
    review_status TEXT DEFAULT 'pending',
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    promoted_to_rule BOOLEAN DEFAULT FALSE
);

Return:
{
  "runId": "uuid",
  "benchmarkRunId": "...",
  "failurePatternsAnalyzed": N,
  "suggestionsGenerated": M,
  "suggestions": [ ...full results array... ]
}

─── ENDPOINT 4: GET /v1/admin/seed/analysis-review ──────────────────

Purpose: Single dashboard endpoint for reviewing all pending
Bedrock analysis output before any suggestion is acted on.

Returns:
{
  "pendingClassificationDisagreements": [
    { disagreement records where reviewRecommended: true, not yet reviewed }
  ],
  "pendingTerminologySuggestions": [
    { terminology_suggestions where review_status = 'pending' }
  ],
  "pendingRuleSuggestions": [
    { rule_suggestions where review_status = 'pending' }
  ],
  "counts": {
    "classificationDisagreements": N,
    "terminologySuggestions": M,
    "ruleSuggestions": K
  }
}

─── ENDPOINT 5: POST /v1/admin/seed/analysis-approve ────────────────

Purpose: Approve or reject individual Bedrock suggestions after review.

Request body:
{
  "type": "terminology|rule|classification",
  "id": "suggestion_id",
  "decision": "approved|rejected",
  "reviewedBy": "L0",
  "notes": "optional review notes"
}

For approved terminology suggestions:
- Write to pattern_atoms as a seed corpus atom with correctionSource: 'bedrockSuggested'
- Set corpus_split: 'training'
- Mark as requires_manual_signoff: false (already reviewed)

For approved rule suggestions:
- Write to a pending_rules table for implementation tracking
- Does not auto-implement — creates a tracked work item

For approved classification disagreements:
- Update the expert_annotation record with the reviewed classification
- Flag the taxonomy entry for potential spec update

For rejections: mark rejected, log reason, no further action.

Return { "processed": true, "type": "...", "id": "..." }

─── MIGRATION ───────────────────────────────────────────────────────

Add the three new tables (bedrock_analysis_runs, terminology_suggestions,
rule_suggestions) to src/migrations/004_bedrock_analysis.sql.

Run via the existing POST /admin/migrate endpoint.
```

### 12.5 Sprint Prompt — Step 9 (Weekly Integration)

```
Reference: SEED_CORPUS_STARTER_KIT.md section 10.2 (weekly workflow),
Step 7 benchmark endpoint

Extend the weekly benchmark CRON job (currently "0 6 * * 1" in wrangler.toml)
to automatically trigger Bedrock analysis after the benchmark run completes.

In the scheduledHandler in index.js, after the weekly benchmark run writes
to benchmark_runs, chain these calls automatically:

1. Fetch the 10 worst-performing extraction pairs from the completed
   benchmark run (lowest F1 per field type, one pair per failure type):
   - Join extraction_runs with expert_annotations on seed_document_id
   - Select pairs where annotation.correction_class IS NOT NULL
   - Order by annotation confidence DESC, limit 10
   - Format as pairs array for the classify-failures endpoint

2. POST internally to /v1/seed/analyze/classify-failures with the pairs
   (internal call — use fetch with the same Worker URL and admin key)

3. Fetch unresolved surface forms: query expert_annotations where
   correctionDetail->>'correctCanonicalId' IS NULL
   AND correction_class IN ('A','C') — these are the cases where
   you flagged a correction but couldn't resolve to a canonical ID
   Limit 20, order by created_at DESC

4. POST internally to /v1/seed/analyze/terminology-gaps with those forms

5. POST internally to /v1/seed/analyze/suggest-rules with the
   completed benchmarkRunId and topN: 5

Log each internal call result to audit_log:
{
  "event": "weekly_bedrock_analysis",
  "classificationDisagreements": N,
  "terminologySuggestions": M,
  "ruleSuggestions": K,
  "benchmarkRunId": "..."
}

The full weekly automated sequence is now:
  6:00 AM Monday  → benchmark run (30 documents, training split)
  ~6:05 AM        → Bedrock classification validation (10 pairs)
  ~6:07 AM        → Bedrock terminology gap discovery (up to 20 forms)
  ~6:10 AM        → Bedrock rule suggestions (top 5 failure patterns)
  ~6:12 AM        → audit_log entry with full summary

Your Monday morning review:
  GET /v1/admin/seed/analysis-review
  → shows all pending suggestions from the automated run
  → you approve/reject each before anything is promoted
  → approved terminology → feeds pattern_atoms as bedrockSuggested atoms
  → approved rules → feeds pending_rules work item queue
```

### 12.6 Updated Weekly Workflow

With Step 9 in place, the Monday review session gains a third input alongside the benchmark delta and failure distribution:

```
Monday morning (automated, ran overnight):
├── Benchmark run: 30 documents, training split, delta from prior week
├── Bedrock classification analysis: disagreements flagged for review
├── Bedrock terminology gaps: new variant suggestions pending approval
└── Bedrock rule suggestions: implementation candidates per failure cluster

Your review (GET /v1/admin/seed/analysis-review):
├── Review classification disagreements
│   Agree with Bedrock → update annotation classification
│   Disagree → reject, note taxonomy ambiguity for spec review
│
├── Review terminology suggestions
│   High confidence, non-provider-specific → approve → feeds pattern_atoms
│   Provider-specific or uncertain → reject or flag for L3 review
│
└── Review rule suggestions
    High impact + low complexity → approve → adds to pending_rules queue
    Approve into annotation focus for this week's sessions
    Reject if the suggested rule is too narrow or risky

Annotation session focus this week:
└── Prioritize documents matching the approved rule suggestions
    Bedrock told you what to look for — go find more examples of it
```

### 12.7 Compliance Confirmation Checklist

Before running any Bedrock analysis call, confirm:

```
□ Input to Bedrock contains no MIMIC CSV content
□ Input to Bedrock contains no clinical note prose from MIMIC
□ Input to Bedrock contains no radiology report text from MIMIC
□ All values in extraction pairs are pipeline output, not MIMIC source values
  (they may coincidentally be the same number, but they come from your pipeline)
□ providerLayoutHash values are one-way hashes — no provider names in payload
□ No dates from MIMIC patient records appear in any prompt
□ All canonical IDs are public ontology references (LOINC:X, RxNorm:X, etc.)
```

The Worker endpoint can enforce the first four checks programmatically by
rejecting any input payload that contains strings matching MIMIC file paths
(`/home/*/mimic-iv/`) or known MIMIC column names (`subject_id`, `hadm_id`,
`stay_id`) in any string field. Add this as a preflight check in each
/v1/seed/analyze/* endpoint before the Bedrock call fires.

---

## 13. Step 10 — Sampled Bedrock Recursion Pass + Context Expectation Engine

### 13.1 What This Does

Two distinct self-improving mechanisms that run after the system reaches corpus maturity. Neither replaces expert annotation. Both reduce how much expert annotation is needed by generating lower-weight training signal automatically.

**Important:** Step 10 should not be built until the system has at minimum 200 real annotated documents in the training corpus and the benchmark engine (Step 7) is producing stable scores. Running these mechanisms on a thin corpus produces noise, not signal.

---

### 13.2 Factor 1 — Sampled Bedrock Recursion Pass

Not a full recursion. A statistically sampled pass targeting uncertain extractions. Running Bedrock on every document would be prohibitively expensive and mostly redundant — the signal is in the uncertain cases, not the confident ones.

**Sampling criteria:**

```
Include in sample:
  Local model confidence < 0.75 (uncertain extractions)
  Field types with historically high error rates this week
    (from benchmark_runs results_by_field_type, bottom quartile)
  Document layouts with < 50 training examples in corpus
    (novel layouts where model has least experience)
  FactStore coherence score < 0.30
    (extractions that contradict patient history)
  Random 5% of high-confidence extractions
    (control group — detects model drift vs Bedrock baseline)

Exclude from sample:
  Extractions already in expert_annotations queue
  Document types with corpus coverage > 200 examples per layout
  Documents sampled in prior 4 weeks (avoid repetition)
  Extractions from test silo documents (never)
```

**Bedrock model version tracking:**

When the Bedrock model version changes (e.g. claude-sonnet-4-6 → next version), trigger a targeted re-sampling pass on prior agreed cases with `local_confidence < 0.80`. The new model may catch failures the old model missed — free corpus enrichment from Anthropic's research investment.

```sql
provisional_training_candidates (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at                  TIMESTAMPTZ DEFAULT now(),
    document_id                 UUID REFERENCES seed_documents(id),
    extraction_id               UUID,
    local_model_output          JSONB,
    local_model_confidence      FLOAT,
    bedrock_correction          JSONB,
    bedrock_confidence          FLOAT,
    bedrock_model_version       TEXT,      -- track Bedrock version explicitly
    canonical_id_resolved       BOOLEAN,
    factstore_coherent          BOOLEAN,
    sampling_reason             TEXT,      -- why this extraction was sampled
    batch_id                    UUID,      -- groups candidates from same run
    batch_review_status         TEXT DEFAULT 'pending',
                                           -- 'pending','approved','rejected'
    batch_rejection_reason      TEXT,
    promoted_at                 TIMESTAMPTZ,
    training_weight             FLOAT DEFAULT 0.7,
    -- Lower than L0/L3 annotations (1.0) — Bedrock is probabilistic,
    -- not a ground truth authority
    promoted_to_annotation_id   UUID REFERENCES expert_annotations(id)
)
```

**Promotion gate — batch review, not individual:**

Bedrock-sampled corrections are reviewed and promoted as a batch, not individually. If a batch has internal inconsistencies (Bedrock correcting the same pattern in opposing directions), reject the whole batch and investigate before promoting anything.

```
Batch passes if:
  Internal consistency rate > 0.85
    (Bedrock corrections within batch agree with each other)
  Canonical ID resolution rate > 0.80
    (most corrections resolve to a known LOINC/RxNorm/SNOMED ID)
  FactStore coherence rate > 0.75
    (corrections are consistent with patient history)
  No single confusion class dominates > 60% of the batch
    (diversity check — a dominated batch suggests sampling bias)

Batch fails if any condition is not met:
  → Rejected, rejection_reason logged
  → L0 investigates before next sampling run
```

**Promoted candidates enter expert_annotations with:**
- `annotator_level: 'bedrock_sampled'`
- `training_weight: 0.7` (lower than human annotation)
- `requires_l0_review: false` (already batch-reviewed)
- `source: 'sampled_recursion_pass'`

---

### 13.3 Factor 2 — Context Expectation Engine

Learns what each document type should contain based on observed co-occurrence patterns across the corpus. Uses that knowledge to tighten the ingest pass — making the system proactive about what it expects to find, not just reactive to what it found.

**Two levels of expectation:**

```
Level 1 — Corpus-level (document category → expected atoms)
  P(atom_type | document_category) computed across all documents
  Example: P(medicationList | dischargeSummary) = 0.94
  → Discharge summaries are expected to contain medication lists
  → Absence is a negative space signal, not just a miss

Level 2 — Patient-level (known conditions → expected atoms)
  P(atom_type | condition) computed across patient FactStores
  Example: P(HbA1c | Type2Diabetes) = 0.83
  → A patient with T2D is expected to have HbA1c in lab reports
  → Missing HbA1c in a lab report for this patient is flagged
```

**Conservative early, tighter over time:**

The engine is deliberately conservative at low sample sizes. Expectations only activate when the corpus is deep enough to be statistically meaningful.

```
Expectation activation thresholds:

Corpus-level:
  sample_size < 30:   no expectation set (insufficient data)
  sample_size 30–50:  expectation threshold 0.90 (very high bar)
  sample_size 50–100: expectation threshold 0.85
  sample_size > 100:  expectation threshold 0.80 (standard threshold)
  sample_size > 200:  layout-specific expectations emerge
                      (separate P per providerLayoutHash)

Patient-level:
  condition must have ICD-10 canonical ID confirmed
  co_occurrence_rate must be based on ≥ 20 patients with this condition
  before patient-level expectations activate
```

**The ingest pass integration:**

```
Document arrives for ingest
        ↓
Context Expectation Engine assembles expectation set:
  Query document_type_atom_expectations for this document_category
  Query patient_atom_expectations for this patient (from FactStore)
  Merge: document-level expectations + patient-level expectations
        ↓
Extraction pipeline runs with expectation context:
  For each expected atom: heightened sensitivity in that field region
  After extraction: check which expected atoms are absent
        ↓
Absent expected atoms → negative_space_candidates table
  source: 'context_expectation'
  co_occurrence_rate: the rate that set the expectation
  expectation_level: 'corpus' or 'patient'
  clinical_significance: derived from condition context if patient-level
        ↓
High clinical significance missing atoms → elevated in L0 review queue
Low significance → logged for corpus coverage analysis
```

**Schema:**

```sql
document_type_atom_expectations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_category       TEXT NOT NULL,
    provider_layout_hash    TEXT,          -- NULL = all layouts, specific = layout-specific
    field_type              TEXT NOT NULL,
    canonical_id            TEXT,
    co_occurrence_rate      FLOAT NOT NULL,
    sample_size             INT NOT NULL,
    expectation_threshold   FLOAT,         -- NULL = below activation threshold
    expectation_active      BOOLEAN DEFAULT FALSE,
    last_computed_at        TIMESTAMPTZ,
    corpus_version          TEXT           -- which corpus produced this rate
)

patient_atom_expectations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id_hash         TEXT NOT NULL,
    condition_canonical_id  TEXT NOT NULL,  -- ICD-10 of the driving condition
    expected_field_type     TEXT NOT NULL,
    expected_canonical_id   TEXT,
    co_occurrence_rate      FLOAT NOT NULL,
    patient_sample_size     INT NOT NULL,   -- how many patients with this condition
    expectation_active      BOOLEAN DEFAULT FALSE,
    last_updated            TIMESTAMPTZ
)

negative_space_candidates (
    -- extends existing negative_space_annotations
    -- adds context_expectation as a source type
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at              TIMESTAMPTZ DEFAULT now(),
    document_id             UUID REFERENCES seed_documents(id),
    patient_id_hash         TEXT,
    field_type              TEXT,
    canonical_id            TEXT,
    source                  TEXT,          -- 'human_annotated','context_expectation'
    co_occurrence_rate      FLOAT,         -- if context_expectation
    expectation_level       TEXT,          -- 'corpus' or 'patient'
    clinical_significance   TEXT,          -- 'low','medium','high','critical'
    review_status           TEXT DEFAULT 'pending',
    reviewed_at             TIMESTAMPTZ,
    reviewed_by             TEXT,
    confirmed_missing       BOOLEAN        -- human confirms it's genuinely absent
)
```

**Weekly CRON job for expectation mining:**

```
Schedule: 0 3 * * 1  (Monday 3AM UTC — after benchmark, before your review)

1. For each document_category:
   Compute P(field_type | document_category) across all extraction_runs
   where annotation exists and correction_class IS NULL (confirmed correct)
   Update document_type_atom_expectations
   Set expectation_active based on sample_size thresholds above

2. For each document_category + providerLayoutHash pair with sample_size > 20:
   Compute layout-specific co_occurrence_rate
   Write separate row with provider_layout_hash set

3. For each known condition in patient FactStores:
   Compute P(field_type | condition) across patients with that condition
   Only activate if ≥ 20 distinct patients with this condition in corpus
   Update patient_atom_expectations

4. Log expectation changes:
   New expectations activated this week
   Expectations that crossed layout-specific threshold
   Expectations that refined significantly (rate changed > 0.05)
   Surface in SEED Master Control dashboard as 'new expectations'
```

---

### 13.4 Sprint Prompt — Step 10

```
Reference: SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §13,
FUNCTION_DISTINCTION.md §5.3, §8.1

Build two components for the recursive self-improvement layer.
Do not build Step 10 until benchmark_runs has at least 10 runs
and the corpus has > 200 annotated documents in the training split.

─── COMPONENT A: Sampled Bedrock Recursion Pass ─────────────────────

New Worker endpoint: POST /v1/seed/recursion/sample
Protected by ADMIN_KEY.

Sampling logic:
  Query extraction_runs for this week's documents
  Apply sampling criteria (see §13.2) — uncertain, novel, coherence-failed
  Add 5% random sample of high-confidence extractions as control group
  Cap sample at 50 documents per run (cost control)
  Exclude documents sampled in prior 28 days (check recursion_sample_log)

For each sampled extraction:
  Call Bedrock with: local model output + document region context
  Prompt: "Review this medical document extraction. If correct, confirm.
           If incorrect, provide the corrected extraction with your
           confidence score and reasoning."
  Parse response: agreement/correction + bedrock_confidence

Write disagreements where bedrock_confidence > 0.90 to
provisional_training_candidates with:
  bedrock_model_version from env.BEDROCK_MODEL_ID
  sampling_reason from the criteria that selected it
  batch_id from this run's UUID

New Worker endpoint: GET /v1/admin/seed/recursion/pending
Returns all provisional_training_candidates where batch_review_status = 'pending'
Grouped by batch_id with batch statistics:
  internal_consistency_rate, canonical_resolution_rate,
  factstore_coherence_rate, dominant_class_pct

New Worker endpoint: POST /v1/admin/seed/recursion/approve-batch
Input: { batchId, decision: 'approved'|'rejected', rejectionReason? }
If approved and batch passes all gates:
  Write each candidate to expert_annotations with annotator_level 'bedrock_sampled'
  training_weight: 0.7
  Set batch_review_status: 'approved'
If rejected:
  Set batch_review_status: 'rejected', log rejection_reason

New table: recursion_sample_log
  Tracks which documents were sampled and when
  Prevents re-sampling the same document within 28 days

On Bedrock model version change (env.BEDROCK_MODEL_ID updated):
  Trigger re-sampling of prior agreed cases with local_confidence < 0.80
  Flag these in batch metadata as 'model_version_recheck'

─── COMPONENT B: Context Expectation Engine ─────────────────────────

New weekly CRON job: runs Monday 3AM UTC (add to wrangler.toml triggers)
Add handler: contextExpectationHandler() in index.js

Job runs in three passes:

Pass 1 — Corpus-level co-occurrence:
  For each document_category:
    Count total annotated documents in training split
    For each field_type found in extraction_runs for this category:
      Compute co_occurrence_rate = docs_with_this_field / total_docs
      Apply sample_size thresholds to determine expectation_active
      Upsert into document_type_atom_expectations

Pass 2 — Layout-specific co-occurrence:
  For each (document_category, provider_layout_hash) pair
  where sample_size > 20:
    Same computation as Pass 1
    Write with provider_layout_hash set (non-null)

Pass 3 — Patient-level co-occurrence:
  For each ICD-10 condition with ≥ 20 distinct patients in corpus:
    Find all patients with this condition confirmed in FactStore
    For each field_type: compute P(field_type | condition)
    Only activate if co_occurrence_rate > 0.75 AND sample_size ≥ 20
    Upsert into patient_atom_expectations

Ingest pass integration:
  In POST /v1/seed/ingest-document:
  After document is written, before returning:
    1. Query document_type_atom_expectations for this document_category
       and providerLayoutHash (prefer layout-specific over general)
    2. Query patient_atom_expectations for this patient
    3. Merge into expectation_set[]
    4. Compare against extraction_run results for this document
    5. Missing expected atoms → write to negative_space_candidates
       with source: 'context_expectation'
       co_occurrence_rate from the expectation row
       clinical_significance: 'high' if patient-level condition-driven,
                               'medium' if corpus-level rate > 0.90,
                               'low' otherwise

New Worker endpoint: GET /v1/admin/seed/expectations
Returns:
  active_corpus_expectations: count and top 10 by co_occurrence_rate
  active_patient_expectations: count by condition
  new_this_week: expectations activated since last Monday
  pending_negative_space: count of unreviewed context_expectation candidates

─── SEED MASTER CONTROL ADDITIONS ───────────────────────────────────

Dashboard screen additions:
  Recursion panel: pending batches count, last sample run date,
                   Bedrock model version in use
  Expectations panel: active expectations count, new this week,
                       pending negative space candidates from expectations

PatternLibrary screen additions:
  New tab: Recursion batches — list pending batches with batch statistics
           Approve batch / Reject batch buttons
           Batch detail view showing individual candidates

─── COMPLIANCE ──────────────────────────────────────────────────────

Sampled Bedrock calls follow same PHI compliance as Step 9:
  No MIMIC source content
  No raw PHI — tokenized extraction output only
  preflight check: reject if payload contains subject_id, hadm_id, stay_id

Context Expectation Engine reads only:
  extraction_runs (pipeline output — no PHI)
  expert_annotations (correction metadata — no PHI)
  FactStore condition atoms (canonical IDs only — no PHI)

─── DEVICE TEST ─────────────────────────────────────────────────────

Recursion pass:
  Trigger POST /v1/seed/recursion/sample manually
  Confirm provisional_training_candidates rows written with correct batch_id
  Confirm recursion_sample_log prevents re-sampling same document
  Approve one batch via POST /v1/admin/seed/recursion/approve-batch
  Confirm expert_annotations rows written with annotator_level 'bedrock_sampled'

Context expectation:
  Trigger contextExpectationHandler() manually
  Confirm document_type_atom_expectations populated for at least one category
  Ingest one discharge summary for a patient with a known condition
  Confirm patient_atom_expectations queried during ingest
  Confirm negative_space_candidates written for any missing expected atoms
  with source: 'context_expectation'
```

---

When ingesting seed documents (Step 4 / POST /v1/seed/ingest-document), assign corpus_split using stratified random assignment before any annotation begins:

```javascript
// In the document ingestion endpoint
function assignCorpusSplit(documentCategory, providerLayoutHash) {
  // Deterministic assignment based on hash — same document always gets same split
  // This ensures reproducibility across pipeline runs
  const hashInt = parseInt(providerLayoutHash.slice(0, 8), 16);
  const remainder = hashInt % 100;
  
  if (remainder < 60) return 'training';
  if (remainder < 80) return 'validation';
  return 'test';
}
```

Deterministic assignment means the same document always lands in the same split regardless of when it's ingested. This prevents accidental re-assignment if documents are re-ingested.

Once assigned, splits are locked. The test silo documents are tagged in Neon and the `TestSetFingerprintRegistry` is populated from all `providerLayoutHash` values where `corpus_split = 'test'`. This registry is what the PatternAtomExtractor checks at runtime to route live user corrections away from the training pipeline.

---

## 15. Claude.ai Planning Prompts

These prompts are for the Claude.ai chat interface — not Claude Code. Use them to plan each build step, resolve architectural decisions, and produce the Claude Code sprint prompt you'll take to the terminal. The workflow for every step:

1. Paste the planning prompt into Claude.ai → get back a resolved sprint prompt + any issues flagged
2. Take that sprint prompt to Claude Code → implementation
3. Verify on device before proceeding to the next step

### 15.1 The Meta-Prompt

Use this any time you're unsure which step you're on or what to build next.

```
I'm working on Record Health, a consumer iOS health records app with an
AI-powered extraction pipeline and recursive training system.

Core spec documents in my repo:
- FUNCTION_DISTINCTION.md v1.0 (authoritative override — read this first)
- ADAPTIVE_DOCUMENT_INTELLIGENCE.md v2.2
- SERVER_INFRASTRUCTURE.md v1.1
- SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md v1.5
- EXPERT_ANNOTATION_AND_MODEL_TRAINING.md v1.3

Current state: [describe where you are]
What I'm trying to do next: [describe the component]

Before producing a Claude Code sprint prompt:
1. Identify which spec document section governs this component
2. Flag any conflicts with existing code I should audit first
3. Confirm the write permission boundaries from FUNCTION_DISTINCTION.md §8.2
4. Produce the sprint prompt with: Reference, Audit first, Implementation, Device test
```

---

### 15.2 Step 1 — Setup

```
I'm starting the Record Health ADI build.

Reference: SERVER_INFRASTRUCTURE.md §6.2, §8, SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §4.2

Before I touch any code, produce:
1. The exact wrangler.toml change to add the daily 2AM UTC consensus CRON
   alongside the existing monthly token drip
2. The full list of env bindings to add via wrangler secret put, with
   placeholder values and a one-line description of each
3. The Neon staging branch setup — what to add to wrangler.toml and how to
   point the staging env at the branch DATABASE_URL
4. A Claude Code sprint prompt for the Neon schema migration that creates all
   ADI and seed corpus tables in dependency order

I will run this against the staging branch first. Flag anything that could
conflict with the existing index.js before I start.
```

---

### 15.3 Step 2 — Seed Corpus

```
I'm building the seed corpus pipeline for Record Health.

Reference: SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §2.3, §3.2, §5.2,
SEED_CORPUS_AND_TAXONOMY.md §4.5

Produce three Claude Code sprint prompts in sequence:

Sprint A — MIMIC extractor (local Python)
Target: reads MIMIC-IV CSVs from a local directory, outputs structured JSON
by document type. Stays local, no network calls, no external dependencies
beyond standard Python libs. Include the exact directory structure expected.

Sprint B — Document renderer (local Python + ReportLab)
Target: takes MIMIC JSON output from Sprint A, renders into realistic PDFs
using four layout families: LabCorpStyle, QuestStyle, DischargeSummaryStyle,
RadiologyStyle. Produces ground_truth JSON alongside each PDF. Applies
degradation filters (blur, JPEG compression, rotation, brightness).

Sprint C — Corpus split assignment
Target: stratified 60/20/20 split by providerLayoutHash assigned before any
annotation. Deterministic — same document always gets same split. Outputs
a split manifest JSON. Test silo output directory is isolated with a README
that says DO NOT ANNOTATE.

Before writing the prompts, tell me if there are any MIMIC DUA compliance
issues I need to address in the renderer output.
```

---

### 15.4 Step 2b — Augmentation Engine

```
I'm building the confusion-class-aware augmentation engine for Record Health.

Reference: SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §3b,
SEED_CORPUS_AND_TAXONOMY.md §3 (confusion class taxonomy)

Before producing the Claude Code sprint prompt, answer:
1. Which augmentation strategies produce the highest training value
   per compute hour given my current annotation distribution?
2. For unit variant augmentation — what are the correct conversion
   formulas for the unit pairs most likely to appear in lab reports
   (mg/dL ↔ mmol/L, mEq/L ↔ mmol/L, µg/dL ↔ nmol/L)?
3. What is the correct approach for recomputing bounding boxes
   after a column gap delta perturbation in a ReportLab-rendered PDF?

Then produce a Claude Code sprint prompt for augment.py and augment_batch.py
covering:
- CLI single-document mode and batch mode
- All three priority strategies: d1_alphanumericSubstitution,
  d2_columnMisattribution, d2_lineBreakIntrusion
- Ground truth update logic per domain
- seed_documents write with full augmentation tagging
- Hard limits enforced at write time:
  augmentation_generation check (max 1)
  corpus_split hardcoded to 'training'

Also produce the schema migration additions for the augmentation columns
and augmentation_runs table as a standalone SQL snippet I can add to
003_seed_corpus.sql before running it.
```

---

```
I'm building the annotation interface for Record Health.

Reference: SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §6.2, §6b.3,
FUNCTION_DISTINCTION.md §3, §8.2

Produce two Claude Code sprint prompts:

Sprint A — Annotation Worker API (Cloudflare Worker, src/index.js)
Six endpoints: GET /v1/seed/queue, GET /v1/seed/document/:id,
POST /v1/seed/annotate, POST /v1/seed/ingest-document,
POST /v1/seed/extraction-run, POST /v1/seed/generate-atoms
Include the full request/response shape for each endpoint.
PHI strip verifier must run on generate-atoms before any atom is written.
User flags write to anomaly_flags table — NOT pattern_atoms directly.

Sprint B — SEED Master Control (Cloudflare Pages, single HTML file)
Four screens: Dashboard, Annotation queue, Corpus manager, PatternLibrary.
Role-gating via ANNOTATOR_KEY:L0/L1/L2/L3 suffix.
Annotation queue must include:
- PDF.js document rendering with bounding box overlays
- Bedrock pre-annotation call on document load (forms pre-filled)
- Keyboard shortcuts (1–5 correction class, Enter save+advance, N negative space)
- Batch annotation mode for same-class failures across documents
Deploy target: Cloudflare Pages, wrangler pages deploy

Before writing the prompts, audit whether the existing index.js has any
route naming conflicts with the /v1/seed/* namespace.
```

---

### 15.5 Step 3 — Annotate (Worker API + Master Control)

```
I'm building the annotation interface for Record Health.

Reference: SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §6.2, §6b.3,
FUNCTION_DISTINCTION.md §3, §8.2

Produce two Claude Code sprint prompts:

Sprint A — Annotation Worker API (Cloudflare Worker, src/index.js)
Six endpoints: GET /v1/seed/queue, GET /v1/seed/document/:id,
POST /v1/seed/annotate, POST /v1/seed/ingest-document,
POST /v1/seed/extraction-run, POST /v1/seed/generate-atoms
Include the full request/response shape for each endpoint.
PHI strip verifier must run on generate-atoms before any atom is written.
User flags write to anomaly_flags table — NOT pattern_atoms directly.

Sprint B — SEED Master Control (Cloudflare Pages, single HTML file)
Four screens: Dashboard, Annotation queue, Corpus manager, PatternLibrary.
Role-gating via ANNOTATOR_KEY:L0/L1/L2/L3 suffix.
Annotation queue must include:
- PDF.js document rendering with bounding box overlays
- Bedrock pre-annotation call on document load (forms pre-filled)
- Keyboard shortcuts (1–5 correction class, Enter save+advance, N negative space)
- Batch annotation mode for same-class failures across documents
Deploy target: Cloudflare Pages, wrangler pages deploy

Before writing the prompts, audit whether the existing index.js has any
route naming conflicts with the /v1/seed/* namespace.
```

---

### 15.6 Step 4 — Train

```
I'm setting up the async training loop for Record Health.

Reference: FUNCTION_DISTINCTION.md §5.1, §5.2,
EXPERT_ANNOTATION_AND_MODEL_TRAINING.md §5.2

Produce three Claude Code sprint prompts:

Sprint A — export_corpus.py
Reads from expert_annotations table in Neon (not CorrectionStore).
Outputs training.jsonl and validation.jsonl.
Each record: input = document region context + extraction task description,
output = structured extraction JSON.
PHI strip verification pass before any record is written to JSONL.
Tags each record with corpus_split, document_category, correction_class.

Sprint B — train.py
Hugging Face Trainer + PEFT LoRA fine-tuning.
Base model: microsoft/Phi-3-mini-4k-instruct (Stage 2 start).
LoRA config: r=16, lora_alpha=32, target_modules q_proj/v_proj.
Reads training.jsonl, outputs adapter to /output/lora_adapter/.
Weights and Biases integration for loss curve monitoring.
Designed to run on AWS g4dn.2xlarge spot instance or local GPU box.

Sprint C — distill.py
Post-training analysis: runs new model vs rule engine on validation corpus.
Finds cases where model wins, rule engine loses.
For each: attempts to express the pattern as an explicit PatternLibrary rule.
Outputs candidate_distilled_rules.json for manual review.

Also give me the exact AWS CLI commands to launch and terminate a
g4dn.2xlarge spot instance for a training run.
```

---

### 15.7 Step 5 — Promote

```
I'm building the promotion pipeline for Record Health.

Reference: FUNCTION_DISTINCTION.md §4, SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §9.2, §12.4

Produce two Claude Code sprint prompts:

Sprint A — Promotion evaluation + PatternLibrary writer
Extends the existing ADI consensus CRON (daily 2AM UTC) to handle seed
corpus artifacts. Adds manual sign-off gate — candidates sit in
gate_status 'pending_approval' until approved via admin endpoint.
Admin endpoints: GET /v1/admin/seed/candidates, POST /v1/admin/seed/approve,
POST /v1/admin/seed/reject, GET /v1/admin/seed/promoted.
Writes training_artifacts rows for model candidates.
Routes each artifact to A/B/C/D per FUNCTION_DISTINCTION.md §4.1.

Sprint B — Bedrock failure analysis layer (Step 9)
Three Bedrock passes: failure classification validation, terminology
variant discovery, rule suggestion generation.
Endpoints: POST /v1/seed/analyze/classify-failures,
POST /v1/seed/analyze/terminology-gaps,
POST /v1/seed/analyze/suggest-rules.
Weekly automation: fires after Monday 6AM benchmark CRON completes.
All suggestions queue in /v1/admin/seed/analysis-review for manual approval.
MIMIC content never transmitted to Bedrock — pipeline output and labels only.

Before writing the prompts, check the existing consensus CRON handler
in index.js and tell me the exact insertion point for the seed corpus
artifact routing logic.
```

---

### 15.8 Step 6 — Ship to Device

```
I'm building the device delivery layer for Record Health.

Reference: ADAPTIVE_DOCUMENT_INTELLIGENCE.md §10.3, §10.4,
FUNCTION_DISTINCTION.md §4.2

Produce two Claude Code sprint prompts:

Sprint A — PatternLibrary delta sync (iOS, Route A)
Client polls GET /v1/pattern-library/delta?from_version={current} on app open.
Response: delta JSON with additions and modifications since from_version.
Apply atomically to local PatternLibrary store.
Trigger retroactive re-scoring: query FactStore for extractions under prior
version, re-run against new rules, auto-accept high-confidence improvements.
Rollback: prior version retained in local store.

Sprint B — CoreML model download (iOS, Route B)
Poll GET /v1/model/latest on app open alongside PatternLibrary check.
If new version available and device eligible: background download of
.mlmodelc from CloudFront.
Hot-swap via MLModel(contentsOf:) once download completes.
Staged rollout flag in response: {eligible: true/false} — server controls
the 10/50/100% rollout, client obeys the flag.
Prior model retained on device for 14 days for rollback.
Monitor anomaly_flag rate during rollout, surface delta in SEED Master
Control dashboard.

Also give me the exact CoreML model export command from a Hugging Face
LoRA adapter to a compiled .mlmodelc, including coremltools version and
any known compatibility issues with Phi-3 Mini.
```

---

### 15.9 Swift Runner Audit Prompt (Step 4 pre-work)

Run this before the Step 2 Swift sprint prompt — establishes what's safe to import into a CLI target.

```
I'm about to build a Swift CLI target (SeedCorpusRunner) that imports the
existing Record Health extraction services and runs them against local PDFs.

Reference: SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §5.2

Audit only — do not implement anything.

Read DocumentReadService, LayoutUnderstandingService, SemanticParsingService
and any services they depend on. Report:

1. Which UIKit or SwiftUI types do these services import or depend on?
2. Which depend on app lifecycle (AppDelegate, SceneDelegate, @main)?
3. Which use @EnvironmentObject, @StateObject, or other SwiftUI property wrappers?
4. Which access Keychain or UserDefaults with an app bundle requirement?
5. What would need to be refactored or dependency-injected to run these
   services in a macOS CLI context without an app?

Return a plain assessment only. No code.
```

---

### 15.10 Step 10 — Sampled Bedrock Recursion + Context Expectation Engine

```
I'm building the recursive self-improvement layer for Record Health.

Reference: SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §13,
FUNCTION_DISTINCTION.md §5.3

Before producing Claude Code sprint prompts, answer:

1. For the sampled Bedrock recursion pass:
   What is the right sample cap per weekly run given Bedrock API costs?
   At current token pricing, what does 50 sampled documents cost
   at an average of 800 tokens per extraction review call?

2. For the context expectation engine:
   At what corpus size does the Monday 3AM CRON job become slow enough
   to need query optimization? What indexes should be on
   extraction_runs to support the co-occurrence computation efficiently?

3. For the Bedrock model version re-sampling trigger:
   What is the cleanest way to detect that env.BEDROCK_MODEL_ID
   has changed since the last sampling run — should this be stored
   in a system config table or detected by comparing the model version
   on the most recent recursion_sample_log rows?

Then produce two Claude Code sprint prompts:

Sprint A — Sampled Bedrock recursion pass
  POST /v1/seed/recursion/sample (admin key)
  GET /v1/admin/seed/recursion/pending
  POST /v1/admin/seed/recursion/approve-batch
  recursion_sample_log table
  provisional_training_candidates table
  Batch gate logic (consistency, canonical resolution, coherence, diversity)
  Bedrock model version change re-sampling trigger

Sprint B — Context Expectation Engine
  Monday 3AM CRON handler (contextExpectationHandler)
  Three passes: corpus-level, layout-specific, patient-level
  Ingest pass integration in POST /v1/seed/ingest-document
  negative_space_candidates extension
  GET /v1/admin/seed/expectations dashboard endpoint
  SEED Master Control dashboard additions

Confirm both components follow the PHI compliance boundary from
FUNCTION_DISTINCTION.md §5.3 — no raw PHI, no MIMIC content,
tokenized extraction output only.
```

---

### 15.11 Benchmark Debugging Prompt

When a training run produces unexpected scores, use this to diagnose before adjusting.

```
My Record Health benchmark run returned unexpected results.

Reference: SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md §8.2,
SEED_CORPUS_AND_TAXONOMY.md §4.9

Results: [paste benchmark_runs row or F1 scores here]
Expected: [what you expected to see]
Prior run for comparison: [prior scores if available]

Before suggesting any changes to the training setup:
1. Identify which field types drove the delta (positive or negative)
2. Check whether the delta is within normal variance for this corpus size
3. Identify whether this looks like overfitting, underfitting, or a data issue
4. Tell me which confusion classes to focus annotation effort on this week
   to move the lowest-scoring field types

Do not suggest changing model architecture or hyperparameters until the
annotation corpus gap is ruled out as the cause.
```

---

*This document is the operational implementation guide for the Seed Corpus Recursive Training Starter Kit. Document version 1.7 adds section 13 — Step 10, the recursive self-improvement layer: the statistically sampled Bedrock recursion pass (Factor 1 — sampled, not full, cost-controlled, batch-reviewed at 0.7x training weight) and the Context Expectation Engine (Factor 2 — corpus and patient-level co-occurrence mining, conservative activation thresholds, proactive negative space detection). Also adds section 15.10 Claude.ai planning prompt for Step 10 and renumbers benchmark debugging to 15.11. Version 1.6 added Step 2b (augmentation engine). Version 1.5 renamed the kit and added section 15. Version 1.4 added Step 5b. Sprint prompts are designed for Claude Code single-prompt implementation. Test each component against staging Neon branch before running against production. Step 10 should not be built until the corpus has > 200 annotated documents and benchmark_runs has > 10 stable runs.*
