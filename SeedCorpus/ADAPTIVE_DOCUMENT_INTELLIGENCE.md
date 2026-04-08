# Adaptive Document Intelligence
## System Design Specification — Record Health

**Document version:** 2.2
**Status:** Pre-implementation spec
**Governs:** CorrectionStore, PatternAtom pipeline, federated learning layer, consensus engine, PatternLibrary versioning, seed corpus, opt-in tier structure including Tier 3 research consent
**Depends on:** OCRResultStore, PHITokenStore, FactStore (append-only doctrine), Cloudflare Worker gateway, AWS Bedrock inference layer
**Infrastructure:** See SERVER_INFRASTRUCTURE.md — D1/R2 references in v1.0 are superseded. All server-side storage runs on Neon Postgres.
**CRITICAL OVERRIDE:** FUNCTION_DISTINCTION.md supersedes section 8.2 of this document. Phase gates are now driven by offline benchmark scores, not user correction volume. User corrections feed anomaly detection only — not the consensus engine. See FUNCTION_DISTINCTION.md sections 1–3 before implementing any component that touches user corrections, phase transitions, or PatternAtom generation.

---

## 1. Overview and Design Philosophy

Adaptive Document Intelligence (ADI) is a continuously learning extraction layer that compounds OCR and document pattern accuracy over time across the entire Record Health user base — without transmitting, storing, or processing protected health information at any system boundary outside the device.

The core architectural insight is that a correction event contains two separable components:

- **PHI layer** — the actual health content, patient identifiers, values, provider names. This never leaves the device.
- **Pattern atom** — an optical and structural failure signature describing *why* the extraction failed, containing zero health information. This is the unit of shared learning.

The system compounds across three distinct learning layers, each operating on different data and at different scopes:

| Layer | Data Used | Scope | PHI Risk |
|---|---|---|---|
| On-device personalization | Full crops, full PHI context | Single user | None (contained) |
| Rule consensus engine | Pattern atoms, visual feature vectors | System-wide | None (non-PHI by construction) |
| Federated visual model | Gradient deltas only | System-wide | Negligible (differential privacy) |

Every design decision in this document flows from one invariant: **the server layer must be architecturally incapable of reconstructing PHI, not merely policy-prohibited from doing so.**

A second invariant governs the consensus engine: **promotion requires evidence of positive outcome delta, not merely observation count.** Threshold-based promotion alone is gameable. Quality-of-outcome validation is not.

---

## 2. CorrectionStore

### 2.1 Purpose

CorrectionStore is the append-only, on-device ledger of every extraction correction made by the user. It is the raw signal from which all derived learning artifacts are produced. It is PHI-containing and encrypted at rest.

### 2.2 Schema

```swift
struct CorrectionRecord: Codable, Identifiable {

    // Identity
    let id: UUID
    let createdAt: Date
    let appVersion: String
    let patternLibraryVersion: String

    // Provenance linkage (ties back to OCRResultStore and FactStore)
    let documentId: UUID
    let ocrResultId: UUID           // FK → OCRResultStore bounding box record
    let factId: UUID?               // FK → FactStore observation if applicable
    let pageIndex: Int
    let boundingBox: CGRect         // normalized 0-1 coordinate space

    // Pixel capture (PHI-containing, never transmitted)
    let pixelCropPath: String       // encrypted local path to raw image crop
    let cropDPI: Float
    let cropColorSpace: String      // grayscale, rgb, cmyk

    // OCR failure detail
    let ocrEngine: String           // "VisionKit", "Tesseract", etc.
    let ocrRawOutput: String        // tokenized — PHI replaced with tokens
    let ocrConfidencePre: Float     // engine-reported confidence before correction
    let fieldType: FieldType        // .numericLabValue, .medicationName, .date, .providerName, etc.
    let confusionClass: ConfusionClass  // see 2.3

    // Correction detail
    let correctedValueTokenized: String  // PHI-tokenized corrected value
    let correctedCanonicalId: String?    // RxNorm, LOINC, SNOMED-CT, ICD-10 ID if applicable
    let ocrConfidencePost: Float         // estimated post-correction confidence
    let correctionSource: CorrectionSource  // .userManual, .userAccepted, .autoPromoted

    // Document structure
    let documentCategory: DocumentCategory  // .labReport, .imaging, .discharge, .prescription, etc.
    let providerLayoutHash: String          // one-way SHA-256 of structural fingerprint, NOT provider identity
    let layoutRegionType: LayoutRegionType  // .header, .labTable, .valueColumn, .footerSignature, etc.

    // Batch tracking
    var batchId: UUID?          // populated when atom is bundled for upload
    var uploadedAt: Date?       // nil until confirmed uploaded
}
```

### 2.3 ConfusionClass Taxonomy

```swift
enum ConfusionClass: String, Codable {
    case alphanumericSubstitution   // O↔0, l↔1, I↔1
    case ligatureCollapse           // rn↔m, cl↔d, fi ligature
    case wordBoundaryFailure        // merged or split tokens
    case punctuationDropout         // missing period, comma, slash
    case numericFormatMismatch      // 140mg vs 140 mg vs 140mg/dL
    case diacriticStrip             // café → cafe
    case lineBreakIntrusion         // value split across detected lines
    case lowContrastDropout         // faint print, faded ink
    case skewDistortion             // rotated text misread
    case handwritingMisclass        // printed region classified as handwritten
    case stampOverlay               // rubber stamp obscuring text
    case faxArtifact                // halftone noise on fax-origin documents
    case unknown
}
```

The initial taxonomy is deliberately conservative. New cases require an app update (MAJOR library version bump). A well-defined initial set buys a long runway before the schema needs to change — resist the urge to over-enumerate at launch.

### 2.4 Append-Only Enforcement

Consistent with FactStore doctrine. No updates, no deletes. Corrections to corrections produce new CorrectionRecord entries referencing the prior `id`. The full chain is preserved.

Atomic writes only. No `try?`. Failure surfaces to the caller — never silently swallowed.

### 2.5 Encryption

CorrectionStore records are encrypted using the same keying strategy as the PHI vault. The `pixelCropPath` references a separately encrypted binary blob in the local document store. The crop is never written in plaintext at any point.

---

## 3. VisualFeatureExtractor

### 3.1 Purpose

VisualFeatureExtractor runs entirely on-device against the raw pixel crop to produce a `VisualFeatureVector` — an optical description of the conditions that produced the OCR failure. This vector is transmittable because it describes visual *conditions*, not visual *content*. A human or model cannot reconstruct legible text from it.

### 3.2 VisualFeatureVector Schema

```swift
struct VisualFeatureVector: Codable {

    // Typography
    let estimatedFontClass: FontClass        // .serif, .sansSerif, .monospace, .handwritten
    let estimatedFontSizePt: Float           // approximate, derived from pixel metrics
    let strokeWeightClass: StrokeWeightClass // .hairline, .light, .regular, .bold
    let characterSpacingClass: SpacingClass  // .tight, .normal, .wide, .proportional

    // Rendering conditions
    let effectiveDPI: Float
    let contrastRatio: Float                 // Weber contrast of character vs background
    let backgroundTextureScore: Float        // 0-1, paper grain / noise floor
    let compressionArtifactScore: Float      // 0-1, JPEG/scan degradation level
    let baselineSkewDegrees: Float           // document rotation in region
    let renderingMode: RenderingMode         // .printed, .handwritten, .stamped, .faxed, .digital

    // Region geometry
    let regionWidthPx: Int
    let regionHeightPx: Int
    let characterCountEstimate: Int          // from bounding box density, not text content
    let lineCountEstimate: Int

    // Contextual
    let adjacentRegionTypes: [LayoutRegionType]  // what surrounds this region structurally
    let isMultiColumn: Bool
    let columnPositionEstimate: Float        // 0-1 left-to-right in column layout
}
```

### 3.3 What Is Deliberately Not Captured

- No pixel data
- No character shapes
- No glyph embeddings
- No text content in any form
- No feature that could serve as input to a character recognition model externally

The vector describes the *environment* of the failure, not the failure itself in legible form.

---

## 4. PatternAtomExtractor

### 4.1 Purpose

PatternAtomExtractor takes a `CorrectionRecord` and produces a `PatternAtom` — the complete transmittable unit of learning signal. This is where PHI stripping is formally enforced as a processing step, not a policy.

### 4.2 PatternAtom Schema

```swift
struct PatternAtom: Codable, Identifiable {

    // Identity
    let id: UUID
    let createdAt: Date
    let appVersion: String
    let patternLibraryVersion: String
    let sourceCorrectionId: UUID    // local reference only, never transmitted

    // Document classification (no PHI)
    let documentCategory: DocumentCategory
    let providerLayoutHash: String      // one-way, non-reversible
    let layoutRegionType: LayoutRegionType
    let fieldType: FieldType

    // Failure signature
    let confusionClass: ConfusionClass
    let ocrEngine: String
    let ocrConfidencePre: Float
    let ocrConfidencePost: Float

    // Visual conditions
    let visualFeatures: VisualFeatureVector

    // Canonical resolution (public ontology IDs only — never raw text)
    let resolvedCanonicalId: String?    // RxNorm, LOINC, SNOMED-CT, ICD-10
    let canonicalSystem: String?        // "RxNorm", "LOINC", etc.

    // Signal quality metadata
    let correctionSource: CorrectionSource
    let userOptInLevel: OptInLevel      // .default, .active — affects consensus weighting

    // Seed corpus agreement (computed on-device before transmission)
    let seedAgreementScore: Float?      // 0-1 if atom matches a seed rule; nil if novel territory

    // EXPLICITLY ABSENT:
    // - ocrRawOutput
    // - correctedValue (raw)
    // - documentId
    // - patientId
    // - providerName
    // - any date from the document
    // - any pixel data
    // - any text content
}
```

### 4.3 PHI Strip Verification

Before any atom is queued for transmission, `PatternAtomExtractor` runs a `PHIStripVerifier` that asserts:

- No token matching PHI token format present in any string field
- `resolvedCanonicalId` if present exists in the public ontology whitelist
- `providerLayoutHash` is a valid SHA-256 hex string (not a name)
- No field contains a date string in any common format

If verification fails, the atom is discarded and logged locally. It never enters the upload buffer. The correction is still stored locally and still feeds on-device learning.

---

## 5. On-Device Learning Layer

### 5.1 MLUpdateTask Integration

The on-device model is a CoreML classifier that takes a `VisualFeatureVector` plus structural context and predicts the optimal extraction strategy for a document region. It is trained and updated entirely on-device using `MLUpdateTask`.

Training inputs: full resolution pixel crop + `CorrectionRecord` metadata
Training label: the corrected extraction strategy that succeeded
Training trigger: when `CorrectionStore` accumulates 10 new records since last update, or on weekly timer, whichever comes first

Model weights never leave the device. This layer is purely personal calibration — it learns the user's specific document sources, scanner quality, and provider layout patterns.

### 5.2 Confidence Router

The on-device model produces a per-region confidence score that feeds directly into TierAssignment:

```swift
struct RegionExtractionPlan {
    let regionId: UUID
    let recommendedStrategy: ExtractionStrategy
    let confidenceScore: Float          // 0-1
    let suggestedTier: ReviewTier       // derived from confidence + field sensitivity
    let basisPatternLibraryVersion: String
    let basisModelVersion: String
}
```

High confidence regions from well-represented document categories route to Tier 1 (auto-accept eligible). Low confidence or novel regions route to Tier 2 (user review). The routing threshold is tunable and itself informed by historical accuracy per confidence band.

---

## 6. Batch Upload Service

### 6.1 Design Principles

- **Lazy**: atoms accumulate locally and upload in batches. Real-time ingestion is waste.
- **Threshold-triggered**: upload fires when buffer hits 50 atoms OR 7 days have elapsed since last upload, whichever comes first.
- **Compression**: batch payload is gzip-compressed. Average atom is ~800 bytes; 50 atoms compress to under 10KB.
- **Idempotent**: each atom carries a stable `id`. Server deduplicates on ingest. Safe to retry.
- **Non-blocking**: upload runs in a background URLSession task. Never on the main thread. Never blocks document processing.

### 6.2 Upload Payload

```json
{
  "batchId": "uuid",
  "clientId": "hashed-device-id",
  "appVersion": "1.4.2",
  "patternLibraryVersion": "0.7.1",
  "atomCount": 47,
  "optInLevel": "active",
  "atoms": [ ... ]
}
```

`clientId` is a one-way hash of the device identifier. It is used only for burst detection and diversity weighting in the consensus engine. It is not stored after consensus processing completes.

### 6.3 Retry Logic

Exponential backoff: 1min → 5min → 30min → 6hr → 24hr. After 5 failures the batch is held and retried on next app open. Atoms are never discarded from the local buffer due to upload failure — they accumulate until successful transmission is confirmed.

### 6.4 Opt-Out Enforcement

If the user is opted out, `BatchUploadService` is never instantiated. The upload pathway does not exist at runtime, not merely disabled by a flag. On-device learning (Layer 1) continues normally for opted-out users.

---

## 7. Network Layer

### 7.1 Endpoint

```
POST https://api.recordhealth.workers.dev/v1/pattern-atoms
Authorization: Bearer {worker-issued JWT}
Content-Type: application/json
Content-Encoding: gzip
```

The Worker validates the JWT (same HS256 scheme as the existing auth layer), decompresses the payload, runs PHI strip verification independently on the server side (defense in depth), and writes to Neon Postgres.

### 7.2 Server-Side PHI Strip Verification

The Worker runs its own assertion layer on every received atom:

- Scans all string fields against a PHI pattern detector (date formats, name-like strings, numeric sequences matching SSN/DOB patterns)
- If any field triggers a PHI signal, the entire batch is rejected with a 422, logged for investigation, and the client is flagged for audit review
- Clean batches are written atomically and acknowledged with 202

This is defense in depth. The client-side `PHIStripVerifier` should catch everything. The server-side check ensures that a bug in the client extractor cannot result in PHI reaching the server.

### 7.3 What the Server Is Architecturally Incapable Of Receiving

The endpoint accepts `application/json` with a defined schema. Fields not in the schema are stripped. The schema contains no field that could hold a document image, pixel data, raw OCR text, or patient identifier. The server cannot receive PHI because the wire format does not have a container for it.

---

## 8. Server-Side Repository and Consensus Engine

### 8.1 Storage Architecture (Neon Postgres)

All ADI server-side state lives in the existing Neon Postgres database. No D1 or R2 is required or provisioned. See SERVER_INFRASTRUCTURE.md section 4.3 for the complete table schema.

Tables:
- `pattern_atoms` — queryable atom index, no raw content
- `candidate_rules` — accumulating candidates with full validation state
- `pattern_library` — versioned promoted rules
- `consensus_log` — full promotion audit trail
- `client_metadata` — clientId hashes for burst detection, nulled post-consensus
- `consensus_config` — tunable parameters, no code deploy required
- `system_maturity` — current trust ladder phase and transition history

### 8.2 Trust Ladder — System Maturity Phases

**SUPERSEDED:** This section is superseded by FUNCTION_DISTINCTION.md sections 2.1–2.3.
The phase gate model defined below tied transitions to user correction volume.
That model is incorrect. Phase transitions are now driven by offline benchmark scores
and expert annotation corpus milestones. User counts do not gate intelligence improvement.

The corrected phase definitions, system_maturity table schema, and transition criteria
are in FUNCTION_DISTINCTION.md section 2. Reference that document for all implementation
work touching system_maturity, phase transitions, or consensus gate behavior.

The content below is retained for historical reference only.
Do not implement from this section — implement from FUNCTION_DISTINCTION.md section 2.

```
[HISTORICAL — DO NOT IMPLEMENT]
Phase 0 — Seed Only
Population:       0 users
Promotion:        Seed corpus rules only
Transition to Phase 1: Manual, after first 50 real users with corrections
[SUPERSEDED — user correction count is no longer a transition gate]

Phase 1 — Early Adopters
Population:       1–499 users with corrections
[SUPERSEDED — population count is no longer a transition gate]

Phase 2 — Scaling
Population:       500–1,999 users with corrections
[SUPERSEDED — population count is no longer a transition gate]

Phase 3 — Steady State
Population:       2,000+ users with corrections
[SUPERSEDED — population count is no longer a transition gate]
```

**Corrected transition gates (from FUNCTION_DISTINCTION.md section 2.2):**
```
Phase 0 → Phase 1:  Expert annotation corpus hits 500 Tier A documents
                    AND benchmark overall F1 > 0.61 on test silo

Phase 1 → Phase 2:  Benchmark overall F1 > 0.78 on test silo
                    AND Tier 1 auto-accept rate > 82% on validation silo

Phase 2 → Phase 3:  No discrete transition — continuous offline improvement
```

### 8.3 Promotion Thresholds by Phase

| Gate | Phase 0 | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|---|
| Min observations | Manual | Accumulating | 50 | 25–40 |
| Min unique users | N/A | N/A | 40 | 20 |
| Max top contributor % | N/A | N/A | 15% | 20% |
| Min diversity score | N/A | N/A | 0.70 | 0.60 |
| Contradiction halt | N/A | N/A | 10% | 15% |
| Validation window | 3 days | N/A | 21 days | 7–14 days |
| Canonical ID gate | Encouraged | N/A | Mandatory | Mandatory for Tier 1 |
| Outcome delta required | N/A | N/A | Positive + significant | Positive + significant |

Threshold values are stored in `consensus_config` and tunable without a code deploy. The table above represents v1 defaults.

### 8.4 Seed Corpus as Quality Anchor

During Phase 0 and Phase 1, the seed corpus acts as a quality anchor — incoming user corrections are evaluated against seed rules and weighted accordingly. This gives the consensus engine meaningful signal quality differentiation during the period when user spread is insufficient for outcome delta to be statistically valid.

```
Correction arrives during Phase 0/1:
→ Does it agree with an existing seed corpus rule?
    Yes → seedAgreementScore: high
          weight multiplier: 1.2 (corroborating known good)
    No, novel territory → seedAgreementScore: nil
          weight multiplier: 1.0 (accumulating, no boost)
    No, contradicts seed rule → seedAgreementScore: negative
          weight multiplier: 0.5
          flag for investigation in candidate_rules
```

Seed agreement scoring is computed on-device by `PatternAtomExtractor` before transmission. The client downloads the current seed rule set (a small, non-PHI public artifact) and computes the score locally. The score is included in the `PatternAtom` as `seedAgreementScore`.

By the time Phase 2 opens, candidate rules have quality-weighted observation counts rather than raw counts — a much stronger foundation for the first real promotions.

### 8.5 Power User Bias Protection

Power users over-represent their specific document sources, scan quality, and medical context. A rule promoted primarily on power user corrections is optimized for power users, not the general population.

The `top_user_contribution_pct` gate is the primary defense: if any single `clientId` hash contributes more than the phase threshold (15-20%) of observations for a candidate rule, the promotion gate does not open regardless of total observation count. One power user hammering through documents cannot unilaterally graduate a rule.

Additional fields tracked per candidate rule:

```sql
unique_user_count           INT,      -- distinct users contributing
top_user_contribution_pct   FLOAT,    -- % from the single largest contributor
user_spread_score           FLOAT,    -- diversity across user cohorts
burst_flagged               BOOLEAN   -- true if burst detection fired
```

Burst detection: if more than 20% of observations for a candidate arrive within a 24-hour window from a correlated `clientId` cluster, the candidate is flagged and held. It continues accumulating but does not advance through the promotion pipeline until the burst period's share dilutes below 15%.

### 8.6 Outcome Delta Validation — The Confederate Defense

Threshold-based promotion measures quantity of signal, not quality of outcome. A coordinated set of bad corrections can reach N=25 and graduate. Outcome delta validation closes this by requiring evidence that a candidate rule actually improves extraction before it is promoted.

**Promotion pipeline:**

```
Candidate rule reaches observation threshold
→ Unique user gate passes
→ Diversity gate passes
→ Contradiction rate below halt threshold
→ DO NOT promote yet
→ Enter validation window (shadow mode)
→ Shadow-apply rule to incoming extractions in affected category
   (no production effect — shadow confidence scores computed in parallel)
→ Compute outcome delta over window duration
→ Evaluate against outcome gates (see below)
→ Gate passed  → promote to pattern_library
→ Gate failed  → reject, log to consensus_log, flag for investigation
→ Ambiguous    → extend window, continue accumulating
```

**Outcome gates — candidate must pass Tier 1 OR (Tier 2 AND Tier 3):**

```
Tier 1 — Canonical ID resolution (hard external anchor)
└── Shadow extraction resolves to a known canonical ID (RxNorm, LOINC,
    SNOMED-CT, ICD-10) that the pre-rule extraction did not resolve.
    Objective and ungameable without corrupting public ontology databases.
    Sufficient on its own for promotion.

Tier 2 — Correction rate reduction
└── Documents processed under shadow rule generate fewer downstream
    corrections than the baseline rate for that document category.
    Requires sufficient volume — typically 2-3 week window at Phase 3.
    Must be measured across at least K distinct providerLayoutHash values
    to prevent a single document source from producing a false positive.

Tier 3 — Confidence delta with diversity gate
└── Mean confidence improvement across documents from at least
    K distinct providerLayoutHash values AND K distinct clientId hashes.
    Required alongside Tier 2 — neither is sufficient alone.
```

**Statistical validity:**

For a two-sample comparison of extraction confidence rates at alpha=0.05, power=0.80, medium effect size (Cohen's d ≈ 0.5), approximately 64 documents per arm are required. The validation window length is adaptive:

- Phase 2: fixed 21 days (conservative, ensures volume regardless of usage rate)
- Phase 3: adaptive 7-14 days based on document volume in the affected category; extended automatically if the 64-document minimum has not been reached

**Confederate attack resilience:**

The outcome delta is grounded in real-world extraction performance, not correction voting. Real-world performance cannot be faked at scale without controlling documents being processed by other users — which is not a realistic attack surface. Combined with diversity weighting, burst detection, top contributor caps, and contradiction detection, the promotion pipeline has no single point of failure an attacker can exploit without large-scale system access.

### 8.7 Consensus CRON Job

Runs daily at 2:00 AM UTC via Cloudflare Workers Cron Trigger. See SERVER_INFRASTRUCTURE.md section 6.2 for wrangler.toml configuration.

```
1. Update system_maturity metrics
   (registered users, users with corrections, geographic spread score)

2. Check current maturity phase — apply appropriate threshold set

3. For each candidate in 'accumulating' status:
   a. Update observation_count, unique_user_count, top_user_contribution_pct
   b. Run burst detection — flag if triggered
   c. Check unique user gate — skip if not met
   d. Check diversity score — skip if below minimum
   e. Check contradiction rate — halt and flag if above threshold
   f. Check observation threshold — if met, advance to 'shadow' status
      (Phase 1: never advances to shadow — remains accumulating)

4. For each candidate in 'shadow' status:
   a. Compute outcome delta against shadow extractions since window opened
   b. Check if minimum document volume reached (64 per arm)
   c. If volume met and delta positive + significant → advance to 'passed'
   d. If volume met and delta flat or negative → advance to 'failed'
   e. If window exceeded maximum duration without volume → flag 'ambiguous'

5. For each candidate in 'passed' status:
   a. Assign new PatternLibrary version number
   b. Write to pattern_library table
   c. Compute diff from previous version
   d. Write diff to distribution endpoint
   e. Invalidate CDN cache for library version endpoint
   f. Log to consensus_log

6. For each candidate in 'failed' or 'ambiguous':
   a. Log to consensus_log with full diagnostic data
   b. Flag for your review if failure pattern is anomalous

7. Null client_id_hash values for atoms older than 30 days
```

---

## 9. Federated Learning Layer

### 9.1 Purpose

The rule consensus engine (Layer 2) promotes explicit, inspectable rules. The federated learning layer (Layer 3) trains an implicit visual model that learns failure modes too complex or subtle to express as explicit rules — font rendering artifacts at specific DPI thresholds, regional scan equipment characteristics, compression patterns from specific EHR print drivers.

### 9.2 What Crosses the Wire

Raw pixel crops never leave the device. The federated protocol operates on **gradient deltas** — the mathematical update produced by training the local model on local data.

```
Device training loop:
1. Download current global model weights
2. Train locally on CorrectionStore crops (full PHI context, on-device only)
3. Compute gradient delta = new_weights - starting_weights
4. Apply differential privacy noise to gradient
5. Upload gradient delta only
```

The gradient delta is a vector of floating point numbers representing how the model changed, not what it trained on. Raw crops are not recoverable from gradients, especially with differential privacy applied.

### 9.3 Differential Privacy

Before upload, each gradient delta has calibrated Gaussian noise added:

```swift
let noisedGradient = trueGradient + GaussianNoise(
    mean: 0,
    sigma: calibratedSigma(privacyBudget: epsilon, sensitivity: l2Sensitivity)
)
```

`epsilon` is set conservatively at v1 (stronger privacy, slightly reduced accuracy). It can be relaxed as the system matures and the aggregate signal is proven sufficient.

Noise is individually meaningful but cancels in aggregate across thousands of devices via federated averaging. The global model improves. Individual contributions are not recoverable.

### 9.4 Federated Averaging Server

The aggregation Worker:

1. Receives gradient deltas from participating devices (minimum 100 submissions before averaging runs)
2. Applies federated averaging: `global_update = mean(gradient_deltas)`
3. Adds server-side noise clip for additional privacy guarantee
4. Produces updated global model weights
5. Publishes to CDN for client download

Gradient deltas are deleted immediately after the aggregation round completes. Nothing is retained at the server after aggregation.

Federated learning participation follows the same trust ladder as the consensus engine. Gradient submissions are not aggregated until Phase 2 minimum.

### 9.5 Participation Gate

Federated learning participation requires:
- User is opted in (default or active)
- Device is on WiFi (no cellular gradient uploads)
- Device is charging
- App is backgrounded (Background Tasks framework)

Users never experience this as a foreground operation.

---

## 10. PatternLibrary Versioning and Distribution

### 10.1 Version Structure

```
PatternLibrary vMAJOR.MINOR.PATCH
├── MAJOR — breaking schema change, requires app update
├── MINOR — new rule categories added
└── PATCH — threshold adjustments, rule refinements within existing categories
```

Every extraction record in FactStore carries `patternLibraryVersion`. This is the prerequisite for retroactive re-scoring.

### 10.2 Library Metadata

```json
{
  "libraryVersion": "1.2.0",
  "minimumAppVersion": "1.4.0",
  "schemaVersion": 2,
  "maturityPhase": "scaling",
  "promotedRuleCount": 47,
  "affectedDocumentCategories": ["lab_report", "discharge_summary"],
  "retroactiveScoringEligible": true,
  "releaseNotes": "Added faxArtifact rule cluster for pre-2000 document sources"
}
```

The client reads this before applying any delta. If `schemaVersion` exceeds what the client knows how to handle, it holds the update and surfaces a soft nudge to update the app. Everything else applies silently.

### 10.3 Client Sync

On app open, the client checks the current library version against the server's latest. If behind:

1. Download delta patch (not full library) from CDN
2. Validate patch signature
3. Apply to local PatternLibrary atomically
4. Update `currentPatternLibraryVersion` in app state
5. Trigger retroactive re-scoring evaluation (see 10.4)

A version check is also piggybacked on the batch upload round-trip — a correction submission and a library sync happen in the same session, minimizing latency between a promoted rule and its delivery to the correcting user.

### 10.4 Retroactive Re-scoring

When a new library version is applied:

1. Query FactStore for all extractions where `patternLibraryVersion < currentVersion`
2. Filter to extractions whose field types or document categories are affected by the new rules
3. For each affected extraction, re-run the relevant rule against the stored tokenized OCR output
4. Compute confidence delta
5. If `confidencePost - confidencePre > threshold`:
   - Surface as "we may have read this better now — confirm?" (Tier 2 re-review)
   - Or auto-accept if `confidencePost > autoAcceptThreshold` AND `correctedValue` resolves to a known canonical ID

Re-scoring runs as a background task, never blocking the UI. Results queue into the existing review flow — no new surface required.

### 10.5 Update Delivery Channels

```
Trigger                         Latency         Mechanism
──────────────────────────────────────────────────────────────────────
App open (passive check)        Next open       GET /v1/pattern-library/latest
                                                Silent delta download if behind

Post-correction upload          Minutes         Version check piggybacked on
                                                batch upload round-trip

Background app refresh          Hours           iOS BGTaskScheduler

App Store update                Days-weeks      Required only for MAJOR library
                                                version or client logic changes
```

App Store updates are required only for: new `ConfusionClass` cases, PatternAtom schema changes, CoreML model architecture changes, or PHI strip verifier logic changes. Everything else flows through library deltas with no user action required.

---

## 11. Seed Corpus Strategy

### 11.1 The Cold Start Problem

At launch, the PatternLibrary has no user corrections. The seed corpus pre-populates the library so the flywheel is already turning at launch, and provides the quality anchor that gives Phase 1 corrections meaningful weight differentiation.

### 11.2 Public Document Sources

- **CMS sample documents** — Medicare EOBs, remittance notices, standardized form layouts
- **NLM / NIH published datasets** — de-identified lab report formats from published research
- **HL7 FHIR reference implementations** — canonical document structure examples
- **State health department public forms** — immunization records, vital statistics forms
- **Insurance company public specimen forms** — EOB layouts, prior authorization forms

Processed through the full extraction pipeline, manually corrected, flagged `correctionSource: .seedCorpus`.

### 11.3 Synthetic Atom Generation

For well-documented OCR failure modes:

- Render known medical terms (RxNorm, LOINC) in a matrix of font classes, sizes, and DPI levels using CoreGraphics
- Apply degradation filters (blur, JPEG compression, rotation, contrast reduction)
- Run through Vision OCR and capture all failure events
- Each failure generates a pattern atom flagged `correctionSource: .synthetic`

Covers common confusion classes across a wide range of rendering conditions before any user opens the app.

### 11.4 First-Party Bootstrapping

Every document processed during development and QA is a legitimate correction source. These are exported as seed atoms after PHI strip verification against any real documents used in testing.

**Minimum viable seed library at launch:**
- 500 promoted rules across common document categories
- Coverage across at least 8 confusion classes
- Representation across at least 5 document categories (lab, imaging, discharge, prescription, EOB)

### 11.5 Seed Corpus Weighting

Seed atoms carry a promotion threshold multiplier of 1.5x — they require proportionally more observations to graduate than real user corrections. As user corrections accumulate, seed-sourced rules are naturally superseded by higher-confidence user-sourced equivalents.

Seed rules are exempt from the outcome delta validation window (manually verified before entry). First-party bootstrapped corrections receive a shortened 3-day validation window.

---

## 12. Compliance Architecture

### 12.1 HIPAA De-identification

Pattern atoms satisfy HIPAA Safe Harbor de-identification under 45 CFR §164.514(b). The 18 enumerated identifiers are absent by construction:

| Identifier | Status in PatternAtom |
|---|---|
| Names | Absent — no text content |
| Geographic subdivisions | Absent — coarse geohash in clientId, discarded post-consensus |
| Dates | Absent — PHI strip verified |
| Phone/fax numbers | Absent |
| Email addresses | Absent |
| SSN | Absent |
| Medical record numbers | Absent |
| Account numbers | Absent |
| Certificate/license numbers | Absent |
| VINs | Absent |
| Device identifiers | Absent — clientId is hashed, discarded post-consensus |
| URLs | Absent |
| IP addresses | Not captured |
| Biometric identifiers | Absent |
| Full-face photos | Absent — no pixel data |
| Any unique identifying number | Absent |

### 12.2 Audit Narrative

*Record Health transmits anonymized optical character recognition failure signatures to improve system-wide extraction accuracy. These pattern atoms describe visual and structural conditions that produce OCR errors — font class, contrast ratio, document layout category, confusion type — and contain no protected health information. The transmission pathway is architecturally incapable of carrying PHI: the wire format schema contains no field that can hold patient identifiers, health values, provider names, or document images. Re-identification risk is cryptographically and statistically negligible. Pattern atoms are functionally equivalent to reporting that a given OCR engine confuses certain character shapes under certain rendering conditions.*

### 12.3 User Consent Language

**Privacy policy:**
*"To improve document reading accuracy across Record Health, your app may contribute anonymized document processing patterns — descriptions of optical conditions that affect text recognition — to our learning system. These patterns contain no personal or health information. You can opt out at any time in Settings → Privacy."*

**Opt-in prompt (active tier):**
*"Help Record Health get smarter for everyone. When you correct a misread, we learn from the pattern — not the content. Your health information never leaves your device."*

**Contribution metric (active tier):**
*"Your corrections have contributed to improvements across [N] document pattern types."*

### 12.4 Opt-In Tiers

```
Tier 0 — Opted out entirely
└── Pure on-device, no contribution
    Still receives PatternLibrary updates (free rider — acceptable)
    On-device personalization continues normally

Tier 1 — Default on, opt-out available
└── Anonymous pattern atoms transmitted
    HIPAA-defensible legalese in privacy policy
    User receives PatternLibrary updates

Tier 2 — Actively opted in
└── Same atoms, same privacy guarantees
    User sees contribution metrics
    Eligible for early feature access or extended token allocation
    Active opt-in corrections weighted 1.1x in consensus engine

Tier 3 — Research consent (Stage 4b, requires explicit activation)
└── User explicitly consents to de-identified health record data
    being used for clinical reasoning model training
    Different legal instrument from Tiers 1/2 — HIPAA Authorization
    required, not just Safe Harbor de-identification
    Full opt-out preserved at any time — corpus contributions
    deleted within 30 days of withdrawal
    Governed by a formal research data use agreement
    IRB review required before activation if prospective
    outcome data is involved
    Do NOT activate Tier 3 without regulatory counsel sign-off
    See EXPERT_ANNOTATION_AND_MODEL_TRAINING.md section 5.7
    for full Tier 3 consent framework, data flow, and schema
```

**Tier 3 data flow distinction:** Tiers 1–2 feed the ADI consensus pipeline (PatternAtoms → PatternLibrary rules). Tier 3 feeds the clinical reasoning model training pipeline on the private AWS instance. These are separate data flows — Tier 3 data does not enter the consensus engine and Tier 1/2 data does not enter the clinical reasoning training corpus. The pipelines are architecturally isolated.

### 12.5 Data Retention

- **pattern_atoms**: `client_id_hash` nulled after 30 days; full record retained for audit trail
- **Gradient deltas**: deleted immediately after federated averaging round completes
- **PatternLibrary versions**: retained indefinitely — this is the accumulated asset
- **consensus_log**: retained indefinitely — audit trail
- **client_metadata**: no PII at any point; `last_seen_at` and `lifetime_atom_count` retained

---

## 13. The Strategic Asset

The PatternLibrary accumulated over time is a proprietary trained artifact that cannot be replicated without the correction history that produced it. It is:

- **Hospital and practitioner agnostic** — learned from real-world document variation, not from institutional cooperation. Sidesteps the decades-long, billions-of-dollars interoperability problem by solving from the consumption side rather than the source.
- **Layout-universal** — covers the actual diversity of how medical documents are printed and scanned, not idealized standards.
- **Compounding** — accuracy improvements reduce friction, which increases usage, which generates more corrections, which improves accuracy.
- **Non-replicable on short timelines** — a competitor cannot acquire 18 months of correction consensus by any means other than 18 months of correction consensus.
- **Defensible at audit** — the trust ladder, outcome delta validation, and power user bias protections make the library a quality-controlled artifact, not a crowd-sourced guess.

Adjacent markets where the PatternLibrary has licensing or API value without the consumer app: insurance claims document processing, EHR document import, health system archival digitization, legal medical record review, life insurance underwriting.

---

## 14. Build Sequence

### Phase 1 — Signal Collection (sprint-near)
- CorrectionStore schema and write path
- Wire to existing review UI — every Tier 2 correction lands in CorrectionStore
- PatternAtomExtractor with PHI strip verifier
- Seed corpus agreement scoring (client downloads seed rule set, computes seedAgreementScore on-device)
- Local batch buffer (no upload yet)
- Visual pixel crop capture and encrypted local storage

### Phase 2 — On-Device Learning (sprint-near/medium)
- VisualFeatureExtractor (Vision framework)
- MLUpdateTask integration
- Confidence Router wired into TierAssignment
- On-device model initial training on seed corpus

### Phase 3 — Batch Upload and Server Repository (sprint-medium)
- BatchUploadService with threshold triggers and retry logic
- Worker ingestion endpoint with server-side PHI verification
- Neon Postgres ADI table migration
- Consensus CRON job v1 (Phase 0/1 behavior — accumulation only, no promotion)
- PatternLibrary versioning and CDN distribution
- Client sync on app open + post-upload piggyback

### Phase 4 — Consensus Engine Full Build (sprint-medium/later)
- Outcome delta validation and shadow testing infrastructure
- Diversity scoring, burst detection, top contributor gating
- Contradiction detection and human review flagging
- Retroactive re-scoring pipeline
- Phase transition tooling (manual confirmation interface)
- Promotion threshold tuning console

### Phase 5 — Federated Learning (sprint-later)
- Gradient delta protocol
- Differential privacy implementation
- Federated averaging aggregation Worker
- Global model weight distribution
- Background task participation gating

### Phase 6 — Seed Corpus (pre-launch, parallel track)
- Public document source identification and processing
- Synthetic atom generation pipeline
- First-party bootstrapping export
- Seed rule manual verification and quality audit
- Pre-populated PatternLibrary at launch minimum viable coverage
- Seed rule set published as client-downloadable artifact for agreement scoring

---

*End of specification.*

*This document governs ADI system design. Document version 2.0 incorporates: outcome delta validation pipeline, trust ladder with manual phase transitions, power user bias protection, seed corpus quality anchor with agreement weighting, and statistical validity framework for shadow A/B testing. Implementation prompts should reference specific sections. Schema changes require this document to be updated before implementation begins. All decisions are consistent with the Provenance Doctrine, PHI ultra hard floor, and append-only store constraints in CLAUDE.md and ARCHITECTURE.md. Infrastructure decisions defer to SERVER_INFRASTRUCTURE.md where the two documents conflict.*
