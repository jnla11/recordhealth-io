# Seed Corpus Regimen and Confusion Class Taxonomy
## ADI Supplement — Record Health

**Document version:** 1.2
**Status:** Pre-implementation spec
**Supplements:** ADAPTIVE_DOCUMENT_INTELLIGENCE.md sections 2.3, 11
**Governs:** Seed corpus construction strategy, Domain 1/2 failure taxonomy, extraction pipeline stage routing, train/validation/test split protocol, baseline benchmarking

---

## 1. The Two-Domain Model

Medical document extraction fails at two structurally distinct pipeline stages. Conflating them in training produces a corpus that teaches the wrong layer the wrong lesson.

```
Domain 1 — Scan / Artifact Degradation
└── Root cause: physical capture process corrupting a correct document
    Pipeline stage: preprocessing (before OCR)
    Fix: optical normalization — deskew, denoise, contrast correction
    Training need: degraded synthetic documents, artifact variation
    Asset value: moderate — general OCR research partially covers this

Domain 2 — Layout and Terminology Chaos
└── Root cause: medical industry non-standardization on a perfect capture
    Pipeline stage: layout understanding and semantic parsing (after OCR)
    Fix: provider fingerprint learning, terminology normalization
    Training need: real provider layout diversity, terminology variant coverage
    Asset value: high — specific to medical documents, no existing solution
```

The seed corpus and taxonomy are designed around this distinction. Domain 1 coverage is sufficient but not over-invested. Domain 2 coverage is deep, systematic, and the primary source of long-term PatternLibrary value.

---

## 2. Revised Confusion Class Taxonomy

### 2.1 Design Principles

- Each class maps to exactly one pipeline stage (preprocessing or semantic parsing)
- Each class is non-PHI by construction — it describes structural/optical failure patterns, not content
- New cases require an app update — the initial set is intentionally broad to minimize future MAJOR version bumps
- Domain 2 classes outnumber Domain 1 classes approximately 3:1

### 2.2 Domain 1 — Optical / Artifact Classes

These map to the **preprocessing pipeline stage**. Remediation is optical normalization before OCR runs.

```swift
enum ConfusionClass: String, Codable {

    // ── DOMAIN 1: OPTICAL / ARTIFACT ─────────────────────────────────────

    // Character-level optical confusion
    case d1_alphanumericSubstitution
    // O↔0, l↔1, I↔1, S↔5, Z↔2
    // Most common OCR confusion class. High volume, well-characterized.

    case d1_ligatureCollapse
    // rn↔m, cl↔d, fi/fl ligature misread, vv↔w
    // Font-dependent. More common in serif and older print.

    case d1_punctuationDropout
    // Missing or misread period, comma, slash, hyphen, decimal point
    // Critical for numeric values — 1400 vs 140.0 vs 14.00

    case d1_diacriticStrip
    // café→cafe, naïve→naive
    // Low frequency in English medical docs, higher in multilingual contexts

    // Document-level optical failure
    case d1_lowContrastDropout
    // Faint print, faded ink, poor toner, light-colored text on light background
    // Common in older documents, thermal fax paper, carbon copies

    case d1_skewDistortion
    // Document rotation — handheld capture angle, scanner feed skew
    // Disrupts line detection and column boundary identification

    case d1_motionBlur
    // Handheld camera shake during capture
    // Distinct from skew — characters present but unresolvable

    case d1_shadowIntrusion
    // Lighting shadow across page, common in phone capture of bound documents
    // Creates false contrast gradients that confuse region segmentation

    case d1_compressionArtifact
    // JPEG blocking artifacts destroying fine character detail
    // Particularly damaging to small fonts and thin strokes

    case d1_faxHalftone
    // Fax transmission halftoning noise
    // Produces systematic dot pattern over characters

    case d1_generationLoss
    // Copy of a copy degradation — cumulative character edge erosion
    // Each photocopy generation reduces character sharpness

    case d1_stampOverlay
    // Rubber stamp, watermark, or annotation obscuring underlying text
    // CONFIDENTIAL, VOID, RECEIVED stamps common in medical records

    case d1_paperDamage
    // Hole punch through text, tear, fold crease, moisture damage
    // Physical document damage creating irrecoverable character loss

    case d1_backgroundTexture
    // Letterhead patterns, security paper micro-printing, watermarks
    // Background noise interfering with character segmentation
```

### 2.3 Domain 2 — Layout and Terminology Classes

These map to the **semantic parsing pipeline stage**. Remediation is layout fingerprint learning and terminology normalization after OCR produces text.

```swift
    // ── DOMAIN 2: LAYOUT STRUCTURE ───────────────────────────────────────

    case d2_columnMisattribution
    // Value assigned to wrong label due to ambiguous column layout
    // Lab reports with crowded columns, misaligned tab stops
    // Example: Glucose value read as Sodium value due to column shift
    // HIGH PRIORITY — produces factually wrong extractions silently

    case d2_referenceRangeCollision
    // Reference range parsed as result value, or vice versa
    // Example: "3.5-5.0" (reference range) read as the patient value
    // Extremely common in lab reports — reference range is adjacent to result

    case d2_labelValueInversion
    // Label and value positions swapped due to non-standard layout
    // Some providers print value first, label second
    // Example: "140 Sodium" instead of "Sodium 140"

    case d2_headerValueCollision
    // Column header misread as a data value or vice versa
    // Particularly common in multi-section lab reports

    case d2_multiPageContextLoss
    // Value on page N requires context (units, label, reference range)
    // from page N-1 that is not captured in the current page region
    // Example: units defined in page 1 header, values appear on page 3

    case d2_sectionBoundaryFailure
    // Extraction bleeds across logical document sections
    // Chemistry panel values mixing with hematology values
    // Common when section dividers are visual-only (no semantic marker)

    case d2_nestedTableFailure
    // Table within a table — inner table rows misread as outer table rows
    // Common in complex lab panels with sub-groupings

    case d2_reflowArtifact
    // EHR print driver reflow breaking field boundaries at page edge
    // Value split across line or page due to print margin calculation
    // Produces partial values that look complete to the OCR engine

    case d2_impliedUnitContext
    // Value present, unit absent — must be inferred from document context
    // Example: all values in a column share a unit stated only in the header
    // OCR sees "140" with no unit — correct unit is "mEq/L" from column header

    case d2_lineBreakIntrusion
    // Multi-word field split across detected lines, parsed as two fields
    // "Basic Metabolic" on line 1, "Panel" on line 2 — read as two entries

    case d2_whitespaceDelimiterAmbiguity
    // Column boundary inferred from whitespace — fails when values contain spaces
    // Example: "< 0.5" read as two tokens, breaking the value field

    // ── DOMAIN 2: TERMINOLOGY / SEMANTIC ─────────────────────────────────

    case d2_terminologyVariant
    // Same concept expressed with non-standard or provider-specific abbreviation
    // Gluc → Glucose, BMP → Basic Metabolic Panel, CBC w/diff → CBC with Differential
    // HIGHEST PRIORITY — affects nearly every document from every provider

    case d2_brandToGenericFailure
    // Medication listed by brand name not resolving to RxNorm generic concept
    // Tylenol → acetaminophen, Glucophage → metformin
    // Brand names change, go off-patent, get reformulated — dynamic problem

    case d2_formularyCodeUnresolved
    // Internal hospital or insurance formulary code not in public ontology
    // NDC codes, internal drug IDs, regional formulary identifiers
    // Example: "MET500" → metformin 500mg (only decipherable with provider context)

    case d2_compoundTermFailure
    // Multi-component medication or test name parsed as separate entities
    // "Amoxicillin-Clavulanate" split into two unresolved terms
    // "T4 Free" vs "Free T4" vs "FT4" — same concept, multiple surface forms

    case d2_unitVariant
    // Correct value, non-standard unit expression
    // mg/dL vs mg/100mL vs mmol/L (requires conversion, not just normalization)
    // mEq/L vs mmol/L for electrolytes
    // IU/L vs U/L vs units/L for enzymes
    // CRITICAL for numeric values — wrong unit means wrong interpretation

    case d2_numericFormatVariant
    // Same numeric value in non-standard notation
    // 1.40 x 10³ vs 1400 vs 1.4K vs 1,400
    // <0.5 vs < 0.5 vs LO vs LOW vs below detection limit
    // >1000 vs >1,000 vs HIGH vs H vs above range

    case d2_dateFormatVariant
    // Date present in non-standard format
    // PHI-tokenized at the CorrectionRecord level — pattern atom carries
    // only the format class, not the date value
    // MM/DD/YYYY vs DD-MON-YYYY vs ISO 8601 vs "Jan 3, 2024"

    case d2_negationMisparse
    // Negative finding parsed as positive
    // "No evidence of pneumonia" → pneumonia present
    // "Denied chest pain" → chest pain present
    // Critical for clinical narrative sections, less common in structured labs

    case d2_qualifierDropout
    // Clinical qualifier stripped from value during extraction
    // "Borderline high glucose" → glucose value without borderline qualifier
    // "Trace protein" → protein present without trace qualifier
    // Changes clinical interpretation significantly

    case d2_contextualAbbreviationCollision
    // Abbreviation with multiple valid expansions in medical context
    // MS → Multiple Sclerosis / Mitral Stenosis / Morphine Sulfate
    // PE → Pulmonary Embolism / Physical Exam / Pleural Effusion
    // Resolution requires document-level context, not local lookup

    case d2_providerSpecificNomenclature
    // Test or medication name specific to a single provider or regional network
    // Not in any public ontology — requires provider layout fingerprint context
    // The long tail of terminology variation — high volume, low individual frequency

    // ── SHARED / AMBIGUOUS ───────────────────────────────────────────────

    case unknown
    // Failure class not determinable from available features
    // Accumulated unknowns are reviewed periodically for new class candidates
}
```

### 2.4 Class Distribution Target

The taxonomy contains 14 Domain 1 classes and 22 Domain 2 classes. Seed corpus coverage targets and consensus promotion priority reflect this weighting:

| Domain | Classes | Seed corpus target | Promotion priority |
|---|---|---|---|
| Domain 1 — Optical | 14 | 30% of seed atoms | Standard |
| Domain 2 — Layout | 8 | 35% of seed atoms | Elevated |
| Domain 2 — Terminology | 13 | 35% of seed atoms | Elevated |
| Unknown | 1 | Emergent | Review queue |

---

## 3. Pipeline Stage Routing

The confusion class determines which pipeline stage is responsible for remediation. This prevents the common error of trying to fix Domain 2 failures with better preprocessing or Domain 1 failures with terminology normalization.

```
Raw document image
        │
        ▼
┌───────────────────────────────┐
│   PREPROCESSING STAGE         │  ← Domain 1 remediation lives here
│                               │
│   Deskew (d1_skewDistortion)  │
│   Denoise (d1_faxHalftone,    │
│     d1_compressionArtifact,   │
│     d1_backgroundTexture)     │
│   Contrast normalize          │
│     (d1_lowContrastDropout,   │
│     d1_shadowIntrusion)       │
│   Blur correction             │
│     (d1_motionBlur)           │
│   Damage masking              │
│     (d1_paperDamage,          │
│     d1_stampOverlay)          │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│   OCR ENGINE (VisionKit)      │
│                               │
│   Character-level classes     │
│   resolved here:              │
│   d1_alphanumericSubstitution │
│   d1_ligatureCollapse         │
│   d1_punctuationDropout       │
│   d1_diacriticStrip           │
│   d1_generationLoss           │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│   LAYOUT UNDERSTANDING STAGE  │  ← Domain 2 layout remediation
│                               │
│   Region classification       │
│   Column boundary detection   │
│   Provider fingerprint match  │
│   Reference range isolation   │
│   Section boundary detection  │
│   Multi-page context assembly │
│                               │
│   Resolves:                   │
│   d2_columnMisattribution     │
│   d2_referenceRangeCollision  │
│   d2_labelValueInversion      │
│   d2_headerValueCollision     │
│   d2_multiPageContextLoss     │
│   d2_sectionBoundaryFailure   │
│   d2_nestedTableFailure       │
│   d2_reflowArtifact           │
│   d2_impliedUnitContext       │
│   d2_lineBreakIntrusion       │
│   d2_whitespaceDelimiterAmbiguity │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│   SEMANTIC PARSING STAGE      │  ← Domain 2 terminology remediation
│                               │
│   Terminology normalization   │
│   Ontology resolution         │
│   Unit canonicalization       │
│   Negation detection          │
│   Qualifier preservation      │
│   Abbreviation disambiguation │
│                               │
│   Resolves:                   │
│   d2_terminologyVariant       │
│   d2_brandToGenericFailure    │
│   d2_formularyCodeUnresolved  │
│   d2_compoundTermFailure      │
│   d2_unitVariant              │
│   d2_numericFormatVariant     │
│   d2_dateFormatVariant        │
│   d2_negationMisparse         │
│   d2_qualifierDropout         │
│   d2_contextualAbbreviationCollision │
│   d2_providerSpecificNomenclature    │
└───────────────────────────────┘
        │
        ▼
   Structured extraction
   → FactStore ingest
```

### 3.1 Stage Assignment in CorrectionRecord

Each `CorrectionRecord` carries a `pipelineStage` field derived from the confusion class at extraction time:

```swift
enum PipelineStage: String, Codable {
    case preprocessing      // Domain 1 optical
    case ocrEngine          // Domain 1 character
    case layoutUnderstanding // Domain 2 structural
    case semanticParsing    // Domain 2 terminology
    case unknown
}

// Derived automatically from ConfusionClass
extension ConfusionClass {
    var pipelineStage: PipelineStage {
        switch self {
        case .d1_skewDistortion, .d1_motionBlur, .d1_shadowIntrusion,
             .d1_lowContrastDropout, .d1_compressionArtifact,
             .d1_faxHalftone, .d1_backgroundTexture,
             .d1_stampOverlay, .d1_paperDamage:
            return .preprocessing

        case .d1_alphanumericSubstitution, .d1_ligatureCollapse,
             .d1_punctuationDropout, .d1_diacriticStrip,
             .d1_generationLoss:
            return .ocrEngine

        case .d2_columnMisattribution, .d2_referenceRangeCollision,
             .d2_labelValueInversion, .d2_headerValueCollision,
             .d2_multiPageContextLoss, .d2_sectionBoundaryFailure,
             .d2_nestedTableFailure, .d2_reflowArtifact,
             .d2_impliedUnitContext, .d2_lineBreakIntrusion,
             .d2_whitespaceDelimiterAmbiguity:
            return .layoutUnderstanding

        case .d2_terminologyVariant, .d2_brandToGenericFailure,
             .d2_formularyCodeUnresolved, .d2_compoundTermFailure,
             .d2_unitVariant, .d2_numericFormatVariant,
             .d2_dateFormatVariant, .d2_negationMisparse,
             .d2_qualifierDropout, .d2_contextualAbbreviationCollision,
             .d2_providerSpecificNomenclature:
            return .semanticParsing

        case .unknown:
            return .unknown
        }
    }
}
```

The `pipelineStage` field is included in the `PatternAtom`. The consensus engine tracks promotion rates and failure frequencies separately per stage — this prevents Domain 1 failure volume from burying Domain 2 signal in aggregate metrics.

---

## 4. Seed Corpus Regimen

### 4.1 Architecture Overview

The seed corpus is built across three parallel tracks, each targeting a distinct failure domain and document source type. They run concurrently during the pre-launch period and are merged into a single pre-populated PatternLibrary before launch.

```
Track A — Synthetic Degradation      → Domain 1 coverage
Track B — Real Layout Diversity      → Domain 2 layout coverage
Track C — Terminology Normalization  → Domain 2 terminology coverage
```

### 4.2 Track A — Synthetic Degradation (Domain 1)

**Goal:** Broad coverage of optical failure modes across font classes, DPI levels, and document categories. Ground truth is known because you control the input.

**Process:**

1. Source clean document templates (CMS public forms, HL7 reference implementations, provider-agnostic layouts)
2. Populate with synthetic but realistic content using Synthea-generated values
3. Render at target DPI (72, 96, 150, 300) using CoreGraphics
4. Apply degradation filters in isolation and combination:

```swift
struct DegradationMatrix {
    // Applied independently and in combinations
    let degradations: [DegradationType] = [
        .gaussianBlur(radius: 0.5...3.0),
        .jpegCompression(quality: 0.3...0.7),
        .rotation(degrees: -5...5),
        .perspectiveSkew(magnitude: 0.02...0.08),
        .brightnessShift(delta: -0.3...0.3),
        .contrastReduction(factor: 0.4...0.8),
        .shadowGradient(angle: 0...360, opacity: 0.2...0.6),
        .halftonePattern(frequency: 30...80),
        .motionBlur(angle: 0...180, radius: 1...4),
        .paperTexture(grain: 0.05...0.2)
    ]
    // Generate N combinations per base document
    // Label each with the degradation types applied → ground truth confusion classes
}
```

5. Run degraded documents through VisionKit OCR
6. Capture all failure events as CorrectionRecords with `correctionSource: .synthetic`
7. Ground truth label is derived from the degradation parameters — no manual correction needed

**Volume target:** 200 seed atoms per Domain 1 confusion class = ~2,800 atoms total for Track A

**Key sources:**
- CMS Medicare specimen EOBs
- HL7 FHIR reference document templates
- State immunization form PDFs
- Insurance company public specimen forms

---

### 4.3 Track B — Real Layout Diversity (Domain 2 Layout)

**Goal:** Provider fingerprint coverage across the major document sources users will actually scan. Ground truth requires manual correction — this is the highest-effort track and the highest-value one.

**The core problem:** Synthea generates structurally realistic documents with normalized terminology. It will not produce the column layout quirks of a LabCorp report, the specific reflow behavior of an Epic EHR printout, or the reference range positioning in a Quest Diagnostics panel. You need real provider layout variation.

**Sources, prioritized:**

```
Priority 1 — High volume, high variability, widely used
├── LabCorp report layouts (multiple panel types)
├── Quest Diagnostics report layouts (multiple panel types)
├── Epic EHR printed discharge summaries
├── Medicare EOB (CMS standard + carrier variants)
└── Standard hospital lab report (multiple institution styles)

Priority 2 — Significant but narrower distribution
├── Cerner EHR printed documents
├── MEDITECH output formats
├── Athenahealth report layouts
├── Private insurance EOB variants (Aetna, BCBS, United)
└── Imaging report formats (radiology, pathology)

Priority 3 — Long tail, high value when encountered
├── Regional hospital proprietary formats
├── Specialty lab reports (genetic testing, toxicology)
├── Pre-2000 legacy formats (paper-native, pre-EHR)
└── Non-English medical documents (Spanish, Portuguese)
```

**Sourcing strategy:**

Real provider layouts are obtained from:

- **MIMIC-IV** — de-identified clinical notes from Beth Israel. Real provider-originated documents. Requires PhysioNet DUA. Gives you authentic clinical structure and terminology variation, though not always as rendered PDF/images.
- **i2b2 NLP datasets** — de-identified clinical notes from multiple institutions. Real layout diversity.
- **Your own records and willing contributors** — highest fidelity because they're real scan artifacts. PHI stripped before corpus entry. Ask family, friends, any willing participant. Even 5-10 people with diverse providers gives you significant layout coverage.
- **Patient advocacy communities** — some patients publicly share anonymized document examples for educational purposes. Treat as supplemental, not primary.
- **Render MIMIC text into provider-accurate templates** — take MIMIC clinical text content and render it into known provider layout templates using CoreGraphics. Bridges the gap between having real terminology and needing real rendered documents.

**Process:**

1. Acquire documents through above sources
2. Run through full extraction pipeline — capture all failures as CorrectionRecords
3. Manually review and correct failures — this is the high-effort step
4. Generate `providerLayoutHash` fingerprints for each distinct layout encountered
5. Tag each correction with the layout source for diversity tracking
6. Export as CorrectionRecords with `correctionSource: .seedCorpus`

**Volume target:** 150 seed atoms per Domain 2 layout confusion class = ~1,200 atoms for 8 layout classes, distributed across at least 15 distinct `providerLayoutHash` values

**Quality gate:** no layout class graduates into the seed library unless it has atoms from at least 5 distinct provider layout fingerprints. Single-provider layout rules are not generalizable.

---

### 4.4 Track C — Terminology Normalization (Domain 2 Terminology)

**Goal:** Comprehensive coverage of the terminology variant space — the gap between how providers write things and what public ontologies understand. This track is the most systematic and the most directly tied to canonical ID resolution quality.

**The core asset:** A terminology variant table mapping surface forms to canonical IDs. This is built before app launch and expanded continuously by user corrections thereafter. It is the single most high-value artifact in the seed corpus.

#### 4.4.1 Terminology Variant Table Construction

**Lab test terminology** (LOINC resolution target):

```
Canonical LOINC term          Known surface variant forms
─────────────────────────────────────────────────────────────────
Glucose [Mass/volume] in      Gluc, Glucose, Blood Glucose, BG,
Serum or Plasma               Fasting Glucose, GLU, GLUCOSE
LOINC: 2345-7

Sodium [Moles/volume] in      Na, Sodium, Na+, SODIUM, Serum Na
Serum or Plasma
LOINC: 2951-2

Potassium [Moles/volume] in   K, Potassium, K+, POTASSIUM, Serum K
Serum or Plasma
LOINC: 2823-3

Creatinine [Mass/volume] in   Creat, Creatinine, Cr, CREAT, SCr
Serum or Plasma
LOINC: 2160-0

Hemoglobin A1c                HbA1c, A1C, Hemoglobin A1c, HgbA1c,
LOINC: 4548-4                 Glycated Hgb, GHb, %HbA1c

Estimated Glomerular          eGFR, GFR, EGFR, Estimated GFR,
Filtration Rate               CKD-EPI GFR, MDRD GFR
LOINC: 33914-3

... (continued for top 200 lab tests by encounter frequency)
```

**Medication terminology** (RxNorm resolution target):

```
RxNorm canonical              Brand names + common variants
─────────────────────────────────────────────────────────────────
metformin                     Glucophage, Fortamet, Glumetza,
RxNorm: 6809                  Riomet, metformin HCl, Met, MET

lisinopril                    Prinivil, Zestril, lisinopril HCl
RxNorm: 29046

atorvastatin                  Lipitor, atorvastatin calcium
RxNorm: 83367

levothyroxine                 Synthroid, Levoxyl, Unithroid,
RxNorm: 10582                 T4, LT4, L-thyroxine

amlodipine                    Norvasc, amlodipine besylate
RxNorm: 17767

... (continued for top 200 medications by prescription frequency)
```

**Panel / test bundle terminology:**

```
Standard name                 Provider variant names
─────────────────────────────────────────────────────────────────
Basic Metabolic Panel         BMP, CHEM-7, SMA-7, Basic Met Panel,
                              Electrolytes + BUN/Creat

Comprehensive Metabolic Panel CMP, CHEM-14, SMA-14, Comp Met Panel

Complete Blood Count          CBC, CBC w/diff, CBC with differential,
                              Hemogram, Full Blood Count, FBC

Lipid Panel                   Lipid Profile, Cholesterol Panel,
                              Fasting Lipids, Cardiovascular Risk Panel

Thyroid Panel                 TFT, Thyroid Function Tests, TSH + Free T4,
                              Thyroid Profile
```

**Unit variant table** (canonicalization + conversion flags):

```
Concept                  Variants requiring normalization only    Variants requiring conversion
───────────────────────────────────────────────────────────────────────────────────────────────
Glucose                  mg/dL, mg/100mL, mg%                    mmol/L (÷ 18.0182)
Electrolytes             mEq/L, mmol/L, meq/l                    — (numerically equivalent)
Enzyme activity          U/L, IU/L, units/L, mIU/L               — (note mIU vs IU)
Hemoglobin               g/dL, g/100mL, g%                       mmol/L (÷ 1.6113)
Creatinine               mg/dL                                   µmol/L (× 88.42)
```

#### 4.4.2 Building the Variant Table

Sources for systematic variant enumeration:

**LOINC database** — downloadable, free. The LOINC `RELATEDNAMES2` field contains known synonyms and abbreviations for each term. This is the most systematic source for lab test variants and covers several thousand commonly ordered tests.

**RxNorm API** — free, provides brand-to-generic mappings, ingredient relationships, and dose form variants for all FDA-approved medications. Query the `getAllRelatedInfo` endpoint for each top-200 medication to enumerate known surface forms.

**SNOMED-CT** — diagnosis and procedure terminology. Less critical for v1 (lab values and medications are higher volume) but important for clinical narrative sections.

**MIMIC-IV clinical notes** — run NLP entity extraction against de-identified notes to enumerate real-world surface forms that don't appear in the official ontology databases. This catches the informal abbreviations (`SCr` for serum creatinine, `lytes` for electrolytes) that providers use but ontologies don't list.

**Manual enumeration** — for provider-specific nomenclature that appears nowhere in public databases. This is the long tail and grows continuously with user corrections. The seed corpus captures the most common 20% that covers 80% of encounters.

#### 4.4.3 Terminology Seed Atom Generation

With the variant table constructed, seed atom generation for Domain 2 terminology is systematic:

1. For each canonical term, enumerate all known surface variants
2. Generate synthetic document fragments containing each variant in context
3. Run through the semantic parsing stage
4. Capture failures where the variant does not resolve to the canonical ID
5. Correct each failure manually — ground truth is the canonical ID
6. Export as pattern atoms with `confusionClass: .d2_terminologyVariant` (or more specific subclass) and `resolvedCanonicalId` populated

**Volume target:** 100 seed atoms per Domain 2 terminology class = ~1,300 atoms for 13 terminology classes. Terminology variant table should cover at minimum:
- Top 200 lab tests by encounter frequency
- Top 200 medications by prescription frequency
- Top 50 panel/bundle names
- Top 100 unit variant pairs

---

### 4.5 Train / Validation / Test Split

Training against all corpus documents without a held-out baseline is a critical evaluation error. It measures whether the system fits training data, not whether it improves on unseen documents. The outcome delta validation in the consensus engine becomes circular — rules derived from documents are evaluated against the same documents. That is not a delta, it is a tautology.

The split is defined and locked **before any annotation work begins**. Once labeling starts, the test set is physically isolated and never touched during training or tuning.

#### 4.5.1 Split Structure

```
All source documents (pre-annotation)
        │
        ├── Training set (60%)
        │   └── Used to generate seed atoms and derive initial rules
        │       Active input to PatternLibrary construction
        │       Tracks A, B, C annotation runs against this set only
        │
        ├── Validation set (20%)
        │   └── Used during shadow testing to tune promotion thresholds
        │       The outcome delta window runs against this set
        │       Held out from rule derivation but used iteratively
        │       Results inform threshold calibration, not rule content
        │
        └── Test set (20%)
                └── Locked before annotation begins — never touched
                    during training, tuning, or threshold calibration
                    Used only at defined benchmark checkpoints
                    Produces the honest accuracy number
```

#### 4.5.2 Stratified Sampling

A random split is insufficient. A naive 60/20/20 split on 100 documents might accidentally put all LabCorp examples in training and leave the test set with only Quest layouts — then the test score measures Quest accuracy, not general accuracy.

Stratify across all three dimensions before splitting:

```
Stratification dimensions:
├── Document category (lab, imaging, discharge, prescription, EOB)
├── Provider layout type (by providerLayoutHash cluster)
└── Domain (Domain 1 artifact-heavy vs Domain 2 layout/terminology-heavy)

Process:
1. Enumerate all source documents
2. Assign each to a stratum (category × layout type × domain)
3. Within each stratum, randomly assign 60/20/20
4. Verify all three splits have representation across all strata
   before proceeding — resample if any stratum is missing from test set
5. Lock test set: tag all test documents with corpus_split: test
   in the corpus manifest
6. Physically isolate test set files — separate directory,
   not accessible to annotation tooling
```

The `corpus_split` tag is stored in the seed corpus manifest alongside the `providerLayoutHash`. The PatternAtomExtractor checks this tag at ingest time (see section 4.5.4).

#### 4.5.3 Baseline Benchmark and Checkpoint Scoring

The test set produces a baseline accuracy score before any user corrections enter the system, and is re-scored at defined checkpoints thereafter.

**Baseline measurement (pre-launch):**

```
1. Run test set through full pipeline under seed library only
2. Record per-field extraction accuracy by:
   ├── Confusion class
   ├── Document category
   ├── Pipeline stage (preprocessing / OCR / layout / semantic)
   └── Field type
3. Store as PatternLibrary v0.0.0 benchmark in consensus_log
```

**Checkpoint schedule:**

```
Checkpoint 1   Pre-launch baseline        PatternLibrary v0.0.0
Checkpoint 2   Phase 2 opens              First real promotions applied
Checkpoint 3   10 promotions              Early flywheel validation
Checkpoint 4   50 promotions              Mid-scale validation
Checkpoint 5+  Quarterly thereafter       Ongoing performance tracking
```

Each checkpoint run produces a delta table against the baseline:

```
Field type          v0.0.0    v1.2.0    delta
──────────────────────────────────────────────
Numeric lab value   71%       89%       +18%
Medication name     64%       81%       +17%
Unit resolution     58%       79%       +21%
Column attribution  52%       74%       +22%
Reference range     61%       83%       +22%
```

A monotonically improving delta across checkpoints confirms the system is working. A drop in any category — even if the overall score improves — is a signal to investigate. A poisoned rule that slipped through consensus will show up here as a category-level regression even if the consensus engine did not flag it.

**The defensible accuracy number:**

*"On a held-out test set of N documents spanning M provider layout types and 5 document categories — never seen during training or threshold calibration — Record Health achieves X% field-level extraction accuracy under PatternLibrary v1.2, compared to Y% baseline at launch."*

That number is auditable and meaningful because it was measured against documents the system never trained on.

#### 4.5.4 Test Set Contamination Protection

As user corrections accumulate post-launch, users may organically scan documents that share layout fingerprints with test set documents. Without protection, the test set gradually stops being genuinely unseen.

**Provenance isolation at ingest:**

The PatternAtomExtractor checks each incoming atom's `providerLayoutHash` against the test set fingerprint registry before routing:

```swift
enum AtomRoutingDestination {
    case trainingPool       // normal — enters consensus pipeline
    case benchmarkPool      // layout matches test set fingerprint — routed to
                            // benchmark tracking only, excluded from training
}

// In PatternAtomExtractor:
func route(_ atom: PatternAtom) -> AtomRoutingDestination {
    if TestSetFingerprintRegistry.shared.contains(atom.providerLayoutHash) {
        return .benchmarkPool
    }
    return .trainingPool
}
```

Atoms routed to `benchmarkPool` are stored in Neon but excluded from the `candidate_rules` pipeline. They accumulate as an ongoing source of independent validation signal — effectively extending the test set with real-world documents that share its layout characteristics, without contaminating training.

**Annual test set rotation:**

Every 12 months:

```
1. Retire 50% of test set documents → move to training pool
   (these become additional training signal)
2. Replace with fresh documents from providers or layouts
   not yet represented in the corpus
3. Re-run baseline measurement against new test set composition
4. Reset baseline in consensus_log with new version tag
5. Update TestSetFingerprintRegistry on all clients
```

Rotation maintains the genuinely unseen quality of the test set as the training corpus grows. Retired test documents don't go to waste — they become high-quality labeled training examples.

---

### 4.6 Seed Corpus Merge and Quality Gate

Before any seed rule enters the PatternLibrary, it passes a quality gate. Rules from the training set only — never from validation or test sets.

```
For each candidate seed rule:
├── Domain 1: represented by atoms from at least 3 distinct degradation
│   parameter combinations (not just one severity level)
├── Domain 2 layout: represented by atoms from at least 5 distinct
│   providerLayoutHash values (not just one provider's layout)
├── Domain 2 terminology: resolvedCanonicalId confirmed present in
│   public ontology (RxNorm, LOINC, SNOMED-CT, ICD-10)
├── All domains: corpus_split tag is training — no validation or test
│   set atoms contribute to seed rule derivation
└── All domains: manual review of at least 10 representative atoms
    before promotion to seed library
```

Rules that pass become seed library entries. Rules that don't accumulate further without entering the live library.

**Minimum viable seed library at launch:**

| Category | Rule count | Atom count |
|---|---|---|
| Domain 1 optical | 14 classes, ~3 rules each | ~2,800 atoms |
| Domain 2 layout | 8 classes, ~5 rules each | ~1,200 atoms |
| Domain 2 terminology | Top 200 lab + top 200 med variants | ~1,300 atoms |
| **Total** | **~500 rules** | **~5,300 atoms** |

---

### 4.7 Ongoing Corpus Expansion

The seed corpus is a living artifact, not a one-time construction. It expands through:

**User correction graduation:** When a user correction accumulates sufficient consensus and passes outcome delta validation, it promotes to the PatternLibrary and implicitly expands the effective corpus. The seed corpus is the floor — user-sourced rules are the ceiling.

**Periodic LOINC/RxNorm refresh:** Both ontologies release quarterly updates. New terms, deprecated terms, and updated synonyms should trigger a seed corpus review pass. Automated: query the change delta, flag any affected rules for review, generate new atoms for new variants.

**Unknown class review:** The `unknown` confusion class accumulates failures that don't fit existing categories. Monthly review of `unknown` atoms identifies candidates for new taxonomy classes — which require an app update but may be warranted as volume grows.

**Provider fingerprint expansion:** Each new `providerLayoutHash` that appears in user corrections with sufficient frequency is a candidate for a new layout rule. The system learns new providers organically — the seed corpus covers the most common ones at launch.

**Annual test set rotation:** As described in section 4.5.4. Retired test set documents graduate to the training pool as high-quality labeled examples. Replacement documents maintain the unseen quality of the held-out set. Baseline resets at each rotation.

**Benchmark pool promotion:** Atoms accumulating in `benchmarkPool` (section 4.5.4) are reviewed annually. If a `providerLayoutHash` in the benchmark pool has accumulated sufficient volume and the associated test set documents have been rotated out, those atoms can be reclassified to `trainingPool` and enter the consensus pipeline.

---

### 4.8 Corpus Manifest and Silo Versioning

The three corpus splits are managed as independent versioned silos from the moment the initial split is made. They are never a single commingled pool that gets logically partitioned — they are separate artifacts that evolve on separate version tracks and rejoin only at defined, logged merge points.

#### 4.8.1 Silo Structure

```
Corpus Manifest (master registry — versioned in repo)
        │
        ├── Silo A: Training Pool
        │   ├── Version: train_v1.0
        │   ├── Documents tagged corpus_split: training
        │   ├── Fully annotated — atoms actively generated
        │   └── Active input to PatternLibrary construction
        │
        ├── Silo B: Validation Pool
        │   ├── Version: val_v1.0
        │   ├── Documents tagged corpus_split: validation
        │   ├── Ground truth labels only — no atom generation
        │   └── Used only for shadow testing threshold calibration
        │
        └── Silo C: Test Pool
                ├── Version: test_v1.0
                ├── Documents tagged corpus_split: test
                ├── Ground truth labels only — read-only between benchmarks
                └── Accessed only at defined benchmark checkpoints
```

Each silo carries its own `providerLayoutHash` fingerprint registry. The `TestSetFingerprintRegistry` loaded by `PatternAtomExtractor` is derived from the test silo's fingerprint registry at its current version — it updates only when `test_vN` increments.

#### 4.8.2 Silo Version Semantics

```
Silo version increments when:
├── Training (train_vN):   New documents added, validation documents graduated,
│                          retired test documents absorbed
├── Validation (val_vN):   New documents added, documents graduated to training
└── Test (test_vN):        Annual rotation — old documents retired to training,
                           new unseen documents added, baseline resets
```

Silo versions never decrement. Moves between silos are one-directional:

```
test → training     (annual rotation — retired documents)
validation → training  (graduation after sufficient calibration cycles)
training → validation  PROHIBITED
training → test        PROHIBITED
validation → test      PROHIBITED
```

The prohibited directions are enforced in the corpus manifest tooling, not just by convention. An attempt to move a document toward a more held-out silo is rejected with an error requiring manual override with explicit rationale logged.

#### 4.8.3 Corpus Manifest Schema

The manifest is a JSON file versioned in the repo alongside the spec documents. It is the single source of truth for corpus composition.

```json
{
  "manifestVersion": "1.3",
  "lastUpdated": "2026-03-15",

  "silos": {
    "training": {
      "version": "train_v1.2",
      "documentCount": 312,
      "providerLayoutHashes": ["hash_a1", "hash_b2", "..."],
      "changeLog": [
        {
          "version": "train_v1.1",
          "date": "2026-01-10",
          "change": "Graduated 18 documents from val_v1.0",
          "documentIds": ["..."]
        },
        {
          "version": "train_v1.2",
          "date": "2026-03-15",
          "change": "Absorbed 40 retired documents from test_v1.0 rotation",
          "documentIds": ["..."]
        }
      ]
    },
    "validation": {
      "version": "val_v1.0",
      "documentCount": 84,
      "providerLayoutHashes": ["hash_c3", "hash_d4", "..."],
      "changeLog": []
    },
    "test": {
      "version": "test_v2.0",
      "documentCount": 86,
      "providerLayoutHashes": ["hash_e5", "hash_f6", "..."],
      "baselinePatternLibraryVersion": "v1.8.0",
      "changeLog": [
        {
          "version": "test_v2.0",
          "date": "2026-03-15",
          "change": "Annual rotation — retired 40 to training, added 42 new layouts",
          "baselineReset": true,
          "retiredDocumentIds": ["..."],
          "addedDocumentIds": ["..."]
        }
      ]
    }
  },

  "benchmarkHistory": [
    {
      "checkpoint": 1,
      "date": "2025-09-01",
      "label": "Pre-launch baseline",
      "patternLibraryVersion": "v0.0.0",
      "testSiloVersion": "test_v1.0",
      "productionGateResult": "baseline_established",
      "results": {
        "numericLabValue": 0.71,
        "medicationName": 0.64,
        "unitResolution": 0.58,
        "columnAttribution": 0.52,
        "referenceRange": 0.61,
        "overall": 0.61
      }
    }
  ]
}
```

The benchmark history is append-only. No entry is modified after the checkpoint run completes. The pairing of `patternLibraryVersion` × `testSiloVersion` is what makes any checkpoint result reproducible and auditable — both numbers are required to reconstruct the exact conditions of a benchmark run.

#### 4.8.4 Permitted Rejoin Points

**Rejoin Type 1 — Validation → Training graduation:**

```
Criteria before a validation document graduates to training:
├── Participated in at least 3 shadow test cycles
├── All rules it contributed to calibrating are promoted or rejected
├── No active shadow tests currently reference this document
├── providerLayoutHash does not appear in test silo fingerprint registry
└── Manual review sign-off logged in manifest changeLog
```

**Rejoin Type 2 — Test → Training annual rotation:**

```
Annual rotation process:
1. Select 50% of test silo documents for retirement (oldest by ingest date)
2. Verify none are referenced by active benchmark runs
3. Move to training silo — append to train_vN+1
4. Source replacement documents from provider layouts not in any silo
5. Stratify replacements across document categories (maintain coverage)
6. Add to test silo — increment to test_vN+1
7. Update TestSetFingerprintRegistry — distribute to all clients
8. Re-run baseline benchmark against test_vN+1
9. Record new baseline in benchmarkHistory with baselineReset: true
10. Log full rotation in manifest changeLog
```

---

### 4.9 Threshold-Gated Production Promotion

The silo versioning and benchmark checkpoints establish what the system knows about its own accuracy. Section 4.9 closes the loop: a PatternLibrary version does not graduate to production distribution until it clears defined accuracy thresholds against the held-out test silo. This is the recursion-to-production gate.

Without this gate, the consensus engine can promote rules and distribute them to production clients based solely on internal signal quality metrics — outcome delta against the validation pool, diversity scores, contradiction rates. Those metrics are necessary but not sufficient. The test silo provides the independent external confirmation that promoted rules actually improve extraction on documents the system has never seen.

#### 4.9.1 The Production Gate

Every proposed PatternLibrary version runs against the test silo before distribution is authorized. The gate is evaluated per document category and per pipeline stage — a version that improves lab report accuracy while degrading prescription accuracy does not pass.

```
PatternLibrary vX.Y.Z proposed for production distribution
        │
        ▼
Run full extraction pipeline against test silo (current version)
        │
        ▼
Compute accuracy scores per field type, category, pipeline stage
        │
        ▼
Evaluate against gate thresholds (section 4.9.2)
        │
        ├── All gates pass → APPROVED for production distribution
        │   └── Log to benchmarkHistory, distribute via CDN
        │
        ├── Any gate fails → BLOCKED
        │   └── Log failure to consensus_log
        │       Flag affected rules for investigation
        │       Revert PatternLibrary to last approved version
        │       Do not distribute
        │
        └── Regression detected (any category score drops vs prior approved)
            → BLOCKED regardless of overall score improvement
            └── Category regression is investigated before any distribution
                A score improvement in one category never offsets a regression
                in another — they are evaluated independently
```

#### 4.9.2 Gate Thresholds

Production gate thresholds are stored in `consensus_config` and tunable without a code deploy. These are v1 defaults calibrated against the seed corpus baseline.

**Absolute floor thresholds** — score must be at or above this value:

| Field type | Minimum score |
|---|---|
| Numeric lab value | 0.82 |
| Medication name | 0.78 |
| Unit resolution | 0.75 |
| Column attribution | 0.72 |
| Reference range isolation | 0.78 |
| Terminology normalization | 0.76 |
| Overall (weighted mean) | 0.78 |

**Regression thresholds** — score must not drop more than this amount vs prior approved version:

| Scope | Maximum allowed regression |
|---|---|
| Any individual field type | 0.02 (2 percentage points) |
| Any document category | 0.02 |
| Any pipeline stage | 0.03 |
| Overall weighted mean | 0.01 |

A drop exceeding any regression threshold blocks distribution regardless of whether absolute floors are met. A version that is 95% accurate overall but has regressed 3 points in medication name resolution does not ship until the regression is diagnosed and resolved.

#### 4.9.3 Gate Result States

```swift
enum ProductionGateResult: String {
    case approved
        // All absolute floors met, no regressions detected
        // Distribution authorized

    case blockedFloor
        // One or more absolute floor thresholds not met
        // Affected rules flagged, version held

    case blockedRegression
        // Regression detected in one or more categories vs prior approved
        // Even if overall score improved — regression always blocks

    case blockedBothFailures
        // Both floor and regression failures present

    case baselineEstablished
        // First run — no prior version to compare against
        // Scores recorded as baseline, distribution authorized
        // (Seed library ships at whatever accuracy the seed corpus achieves)

    case investigationRequired
        // Ambiguous result — regression is borderline, manual review needed
        // Distribution held pending explicit sign-off
}
```

Gate results are recorded in `benchmarkHistory` alongside the checkpoint scores. The `productionGateResult` field is append-only and never modified after the run completes.

#### 4.9.4 Gate in the CRON Pipeline

The production gate runs as the final step of the consensus CRON job, after candidate promotion and library diff computation but before CDN distribution is triggered:

```
Consensus CRON (daily, 2AM UTC)
        │
        ├── [existing] Update system maturity metrics
        ├── [existing] Evaluate candidate rules
        ├── [existing] Promote passing candidates to pattern_library
        ├── [existing] Compute library diff
        │
        ▼  ← NEW
Run production gate against test silo
        │
        ├── APPROVED → trigger CDN distribution, log checkpoint
        │
        └── BLOCKED / INVESTIGATION_REQUIRED
                → do not distribute
                → log gate result with full diagnostic breakdown
                → notify via Worker alert (email or webhook)
                → PatternLibrary version remains at last approved
```

The notification on a blocked gate is important. The CRON runs at 2AM — you need to know by morning that a promotion was held and why, not discover it in the next manual review cycle.

#### 4.9.5 Threshold Evolution

Gate thresholds are not static. They tighten as the system matures:

```
Phase 2 (scaling):   Thresholds set at v1 defaults (section 4.9.2)
                     System proving itself — floors are achievable but not trivial

Phase 3 (steady state, after 10 clean promotions):
                     Absolute floors increase by 3-5 percentage points
                     Regression allowance tightens from 2% to 1%
                     System is now expected to hold its gains

Annual review:       Thresholds reviewed against trailing 12-month benchmark history
                     If the system is consistently clearing floors by >10 points,
                     floors are raised to maintain meaningful gate pressure
                     If any floor has never been cleared, investigate whether
                     the rule class is working or the threshold is miscalibrated
```

Threshold changes are logged in `consensus_config` with rationale and the benchmark data that informed the change. A threshold increase that causes a previously-approved version to fail retroactively is not applied retroactively — it applies to the next proposed version only.

#### 4.9.6 The Full Recursion Loop — Closed

With sections 4.5 through 4.9 in place, the complete recursion-to-production loop is:

```
User corrections arrive
        ↓
PatternAtoms extracted, PHI stripped
        ↓
Routed to trainingPool or benchmarkPool (section 4.5.4)
        ↓
Training atoms enter candidate_rules (consensus engine)
        ↓
Candidates evaluated: observation threshold, diversity, burst detection,
contradiction rate, power user caps (ADI v2.0 section 8)
        ↓
Passing candidates enter shadow validation against validation silo
        ↓
Outcome delta confirmed positive (ADI v2.0 section 8.6)
        ↓
Candidate promoted to PatternLibrary vX.Y.Z (proposed)
        ↓
Production gate: full pipeline run against test silo (section 4.9.1)
        ↓
Gate thresholds evaluated per field type, category, pipeline stage (section 4.9.2)
        ↓
        ├── APPROVED → distribute to all clients via CDN
        │             → retroactive re-scoring triggered on client devices
        │             → benchmarkHistory updated
        │
        └── BLOCKED → held, flagged, investigated
                    → prior approved version remains in production
                    → no client impact
```

Every arrow in this loop is logged, versioned, and auditable. The test silo is the external ground truth that the system cannot game — the final check before learned intelligence reaches users.

---

## 5. Integration with ADI Spec

### 5.1 Updates to ADAPTIVE_DOCUMENT_INTELLIGENCE.md

This document supersedes the following sections of ADI v2.0:

- **Section 2.3** (ConfusionClass Taxonomy) — replaced by sections 2.2-2.3 of this document
- **Section 11** (Seed Corpus Strategy) — replaced by sections 4.1-4.7 of this document

The following sections are entirely new with no ADI v2.0 counterpart:

- **Section 4.5** — Train/validation/test split protocol and stratified sampling
- **Section 4.5.3** — Baseline benchmark and checkpoint scoring schedule
- **Section 4.5.4** — Test set contamination protection and `benchmarkPool` atom routing
- **Section 4.8** — Corpus manifest and silo versioning
- **Section 4.9** — Threshold-gated production promotion and the full recursion loop

Implementation requirements flowing from these sections:
- `corpus_split` field added to Neon `pattern_atoms` table
- `TestSetFingerprintRegistry` implemented in `PatternAtomExtractor`
- `AtomRoutingDestination` enum and routing logic in `PatternAtomExtractor`
- `ProductionGateResult` enum and gate evaluation added to consensus CRON job
- `productionGateResult` field added to `benchmarkHistory` in corpus manifest
- Gate threshold values added to `consensus_config` table
- CRON alert/notification mechanism for blocked gate results
- Corpus manifest JSON file created and versioned in repo

All other ADI v2.0 sections remain in effect.

### 5.2 PatternAtom Schema Addition

The `PatternAtom` struct gains one field to support stage-aware consensus routing:

```swift
// Add to PatternAtom
let pipelineStage: PipelineStage   // derived from confusionClass, see section 3.1
```

The consensus engine tracks candidate rule counts, promotion rates, and outcome delta scores separately per `pipelineStage`. This prevents Domain 1 failure volume (higher frequency, more mechanical) from distorting promotion metrics for Domain 2 failures (lower frequency, higher value).

### 5.3 Consensus Config Additions

```sql
-- Add to consensus_config
adi_d2_promotion_priority_multiplier   -- Default: 1.3
    -- Domain 2 candidates advance through the pipeline with reduced observation
    -- requirements relative to Domain 1. Reflects their higher strategic value
    -- and lower natural frequency in the correction stream.

adi_terminology_canonical_gate_required -- Default: true for d2_terminologyVariant
    -- Tier 1 canonical ID gate is mandatory for all terminology class promotions.
    -- A terminology rule that cannot resolve to a public ontology ID does not promote.

adi_layout_provider_spread_minimum     -- Default: 5
    -- Domain 2 layout rules require observations from at least N distinct
    -- providerLayoutHash values before entering shadow validation.
    -- Prevents a single-provider layout quirk from graduating as a general rule.
```

---

*End of document.*

*This document supplements ADAPTIVE_DOCUMENT_INTELLIGENCE.md. It governs seed corpus construction, confusion class taxonomy definition, evaluation protocol, silo versioning, and threshold-gated production promotion. Document version 1.2 adds corpus manifest and silo versioning (section 4.8) and the threshold-gated production promotion gate with the full closed recursion loop (section 4.9). The taxonomy defined in section 2 is the authoritative source for ConfusionClass enum values in the iOS codebase. Any new class additions require both an app update (MAJOR library version bump) and an update to this document before implementation begins. The test set defined in section 4.5 must be locked before annotation work begins on any corpus track — this ordering cannot be reversed. The production gate defined in section 4.9 must be implemented before any PatternLibrary version is distributed to production clients.*
