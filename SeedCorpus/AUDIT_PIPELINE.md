# Audit Pipeline
## Superuser Extraction Audit System — Record Health

**Document version:** 1.0
**Status:** Pre-implementation spec
**Governs:** AuditService (iOS), audit Worker endpoints, audit Neon schema,
SEED Master Control audit dashboard, superuser session model
**Depends on:** FUNCTION_DISTINCTION.md, SERVER_INFRASTRUCTURE.md,
INTEGRATION_LAYER.md, CLAUDE.md (superuser toggle — Phase 0A)
**Companion documents:** ADAPTIVE_DOCUMENT_INTELLIGENCE.md

---

## 1. Purpose and Design Philosophy

The audit pipeline is an internal developer quality assurance tool. It gives
the developer real-time visibility into what the extraction pipeline sees,
tags, accepts, and misses — without transmitting PHI.

This is not a production telemetry system. It is not user-facing. It is the
equivalent of running Instruments or a Charles proxy session — an internal
diagnostic instrument that is only active when explicitly enabled.

**HIPAA posture:** The superuser audit session is a covered entity conducting
internal quality assurance on its own pipeline. No PHI values transit the
network. No document images transit the network. Coordinates and structural
metadata are transmitted — these are not PHI. Data is stored temporarily
(30-day TTL) in infrastructure controlled by Tenavet LLC.

---

## 2. System Boundaries

### 2.1 What transits the network (acceptable)
- Extraction run metadata (document category, field types, tier assignments)
- Confidence scores per field
- Bounding box coordinates in normalized 0-1 space
- PHI token placeholders (e.g. `{{PHI:PROVIDER:dr3}}`) — not values
- Tokenizer pattern names that fired — not matched text
- Negative space region metadata — not content
- Document filename — used to pair with local PDF in dashboard

### 2.2 What never transits the network (hard floor)
- Raw extracted values
- PHI token values
- Document images or page renders
- Source text content of any kind
- Patient identifiers of any kind

### 2.3 Activation gate
All audit pipeline code paths are gated behind:
```swift
SuperuserManager.shared.isEnabled
```
When false (all production users, all normal sessions): zero telemetry fires.
Zero network calls. Zero data leaves the device beyond existing flows.
When true (developer superuser session only): audit events fire.

---

## 3. Architecture Overview

```
Device (superuser ON)
├── AuditService.swift — orchestrates all audit event sends
├── Fires on: extraction complete, tier assignment, tokenizer complete,
│   negative space analysis complete
├── Sends to: POST /v1/admin/audit/* (Worker, admin-key gated)
└── Gated: SuperuserManager.shared.isEnabled — zero cost when off

Worker (recordhealth-api)
├── Receives audit payloads
├── Writes to Neon audit tables
└── Serves audit data to dashboard

Neon Postgres
├── audit_sessions, audit_documents, audit_fields
├── audit_phi_detections, audit_negative_space
├── audit_session_summary (pre-aggregated)
└── 30-day TTL — cleaned by adiRetentionCleanupHandler

Admin Dashboard (browser, developer Mac)
├── PDF loaded locally from developer's file system
│   (same documents used for test runs — no upload required)
├── Left panel: PDF.js viewer
├── Right panel: tabbed data (auto-accepted, PHI, signal)
├── Overlay: SVG layer on PDF canvas, bounding boxes per tab
└── Page-sync: right panel updates as left panel page changes
```

---

## 4. Neon Schema

### 4.1 audit_sessions
```sql
audit_sessions (
    id                      UUID PRIMARY KEY,
    created_at              TIMESTAMPTZ,
    device_id_hash          TEXT,           -- one-way hash, no PII
    app_version             TEXT,
    pattern_library_version TEXT,
    ios_version             TEXT,
    session_label           TEXT,           -- optional developer label
    completed_at            TIMESTAMPTZ,    -- null until session closed
    document_count          INT DEFAULT 0
)
```

### 4.2 audit_documents
```sql
audit_documents (
    id                      UUID PRIMARY KEY,
    session_id              UUID,           -- FK → audit_sessions
    created_at              TIMESTAMPTZ,
    document_filename       TEXT,           -- filename only, no path
                                            -- used to pair with local PDF in dashboard
    document_category       TEXT,
    page_count              INT,
    ocr_engine              TEXT,
    total_fields_extracted  INT,
    total_fields_accepted   INT,            -- Tier 1
    total_fields_review     INT,            -- Tier 2
    total_fields_escalated  INT,            -- Tier 3
    processing_duration_ms  INT,
    pass1_duration_ms       INT,
    pass2_duration_ms       INT,
    ingest_pipeline_version TEXT
)
```

### 4.3 audit_fields
```sql
-- One row per extracted field per document
audit_fields (
    id                      UUID PRIMARY KEY,
    document_id             UUID,           -- FK → audit_documents
    page_index              INT,            -- zero-based
    field_type              TEXT,           -- condition, medicationName, labValue, etc.
    entity_kind             TEXT,           -- maps to EntityKind enum
    tier_assigned           INT,            -- 1, 2, or 3
    confidence              FLOAT,
    auto_accepted           BOOLEAN,
    extraction_pass         TEXT,           -- 'pass1_regex', 'pass2_ai', 'reconciled'
    confusion_class         TEXT,           -- null if clean
    canonical_id            TEXT,           -- LOINC, RxNorm, SNOMED-CT if resolved
    canonical_system        TEXT,
    source_text_length      INT,            -- character count, not the text itself
    bounding_box            JSONB,          -- {page:0, x:0.12, y:0.34, width:0.15, height:0.02}
    word_count              INT,
    was_reconciled          BOOLEAN,
    reconciliation_delta    TEXT            -- 'match','pass2_override','pass1_only','pass2_only'
)
```

### 4.4 audit_phi_detections
```sql
-- Tokenizer PHI hits BEFORE the AI call — what was redacted
audit_phi_detections (
    id                      UUID PRIMARY KEY,
    document_id             UUID,           -- FK → audit_documents
    page_index              INT,
    token_type              TEXT,           -- PROVIDER, DATE, MRN, PATIENT_NAME, DOB,
                                            -- PHONE, EMAIL, ADDRESS, FACILITY, SSN, etc.
    token_placeholder       TEXT,           -- {{PHI:PROVIDER:dr3}} — placeholder, not value
    bounding_box            JSONB,
    confidence              FLOAT,
    pattern_matched         TEXT            -- regex pattern name, not matched text
)
```

### 4.5 audit_negative_space
```sql
-- Regions processed but producing no extraction — the "what it missed" signal
audit_negative_space (
    id                      UUID PRIMARY KEY,
    document_id             UUID,           -- FK → audit_documents
    page_index              INT,
    region_type             TEXT,           -- 'unextracted_text_block',
                                            -- 'low_ocr_confidence_region',
                                            -- 'skipped_section',
                                            -- 'empty_after_tokenization'
    bounding_box            JSONB,
    ocr_confidence          FLOAT,
    character_count         INT,
    reason                  TEXT            -- 'below_ocr_threshold','no_pattern_match',
                                            -- 'section_excluded','post_tokenization_empty'
)
```

### 4.6 audit_session_summary
```sql
-- Pre-aggregated per session — dashboard reads this, not raw tables
audit_session_summary (
    session_id              UUID PRIMARY KEY,
    updated_at              TIMESTAMPTZ,

    total_extractions       INT,
    tier1_count             INT,
    tier2_count             INT,
    tier3_count             INT,
    tier1_rate              FLOAT,

    high_confidence_count   INT,            -- >= 0.85
    medium_confidence_count INT,            -- 0.60 - 0.84
    low_confidence_count    INT,            -- < 0.60

    by_field_type           JSONB,          -- {condition: {count:12, avg_confidence:0.71, tier1_rate:0.58}}
    by_document_category    JSONB,          -- {labReport: {count:4, avg_confidence:0.84}}
    by_page                 JSONB,          -- {"0": {field_count:8, phi_count:3}}

    total_phi_detections    INT,
    phi_by_token_type       JSONB,          -- {PROVIDER:4, DATE:12, MRN:1}

    total_negative_regions  INT,
    negative_by_reason      JSONB,          -- {no_pattern_match:8, below_ocr_threshold:2}

    pass1_pass2_agreement_rate FLOAT,
    pass2_override_count    INT
)
```

### 4.7 Indexes
```sql
CREATE INDEX idx_audit_documents_session ON audit_documents (session_id);
CREATE INDEX idx_audit_fields_document ON audit_fields (document_id);
CREATE INDEX idx_audit_fields_page ON audit_fields (document_id, page_index);
CREATE INDEX idx_audit_phi_document ON audit_phi_detections (document_id);
CREATE INDEX idx_audit_phi_page ON audit_phi_detections (document_id, page_index);
CREATE INDEX idx_audit_negative_document ON audit_negative_space (document_id);
CREATE INDEX idx_audit_negative_page ON audit_negative_space (document_id, page_index);
CREATE INDEX idx_audit_sessions_created ON audit_sessions (created_at DESC);
```

---

## 5. Worker Endpoints

All audit endpoints require admin authorization. The primary path is the user
JWT with `adi_admin` in its `rh:roles` claim; the Worker's `requireRole`
helper enforces this. A legacy `env.ADI_ADMIN_KEY` bearer is still accepted
as a transitional fallback (ADI console only; AUTH-2 removes it). iOS always
sends the user JWT.

### 5.1 Session management
```
POST /v1/admin/audit/session/start
Body: { device_id_hash, app_version, pattern_library_version,
        ios_version, session_label? }
Returns: { session_id }

POST /v1/admin/audit/session/complete
Body: { session_id }
Returns: { completed_at }
```

### 5.2 Document and field ingestion
```
POST /v1/admin/audit/document
Body: audit_documents row (minus id/created_at — server generates)
Returns: { document_id }

POST /v1/admin/audit/fields
Body: { document_id, fields: [audit_fields rows] }
Returns: { inserted_count }

POST /v1/admin/audit/phi
Body: { document_id, detections: [audit_phi_detections rows] }
Returns: { inserted_count }

POST /v1/admin/audit/negative-space
Body: { document_id, regions: [audit_negative_space rows] }
Returns: { inserted_count }
```

### 5.3 Dashboard read endpoints
```
GET /v1/admin/audit/sessions
Returns: [audit_sessions list, most recent first]

GET /v1/admin/audit/session/:id
Returns: audit_session_summary + document list

GET /v1/admin/audit/document/:id
Returns: audit_documents row + summary stats

GET /v1/admin/audit/document/:id/page/:n
Returns: {
  fields: [audit_fields for this page],
  phi: [audit_phi_detections for this page],
  negative_space: [audit_negative_space for this page]
}
-- This is the primary dashboard endpoint — called on every page change
```

---

## 6. iOS — AuditService

New file: `Services/AuditService.swift`

```swift
// AuditService.swift
// Superuser-only extraction audit telemetry service
// ALL methods are no-ops when SuperuserManager.shared.isEnabled == false

@MainActor
final class AuditService {
    static let shared = AuditService()
    private var currentSessionId: UUID?
    private var documentIdMap: [UUID: UUID] = [:] // recordId → auditDocumentId

    func startSession(label: String? = nil) async
    func completeSession() async

    func sendDocument(record: RecordV2, result: ExtractionResult,
                      durations: ExtractionDurations) async -> UUID?

    func sendFields(documentId: UUID, fields: [TieredInterpretation]) async

    func sendPHIDetections(documentId: UUID, tokenMap: PHITokenMap,
                           pageCoordinates: [PHICoordinate]) async

    func sendNegativeSpace(documentId: UUID,
                           regions: [UnextractedRegion]) async
}
```

**Touch points in extraction pipeline:**

```
RecordIngestPipeline.swift
├── After session begins: AuditService.shared.startSession()
├── After Pass 1 + Pass 2 complete: AuditService.shared.sendDocument()
├── After tier assignment: AuditService.shared.sendFields()
├── After tokenizer runs: AuditService.shared.sendPHIDetections()
└── After negative space analysis: AuditService.shared.sendNegativeSpace()
```

All calls wrapped in `guard SuperuserManager.shared.isEnabled else { return }`.
All calls are fire-and-forget async — never block the ingest pipeline.
All failures are silently swallowed — audit telemetry must never crash ingest.

---

## 7. Admin Dashboard

Single-file HTML artifact served from Cloudflare Worker or opened locally.
No framework required — vanilla JS + PDF.js + SVG overlays.

### 7.1 Layout
```
┌─────────────────────────────────────────────────────┐
│  Session selector dropdown          [Load Session]   │
├──────────────────────────┬──────────────────────────┤
│                          │  [Auto-accepted] [PHI] [Signal] │
│   PDF.js viewer          │                          │
│   (local file loaded     │  Page N field list       │
│    via file picker)      │  sortable, filterable    │
│                          │                          │
│   SVG overlay layer      │  Click row → jump to     │
│   bounding boxes per     │  bounding box on left    │
│   active tab             │                          │
│                          │                          │
│   [< Prev] Page N [Next >]│ Summary stats bar       │
└──────────────────────────┴──────────────────────────┘
```

### 7.2 Overlay color scheme
```
Auto-accepted tab:
  Green solid border    → Tier 1 auto-accepted (confidence >= threshold)
  Yellow solid border   → Tier 2 shown for review
  Orange solid border   → Tier 3 escalated

PHI tab:
  Red solid border      → PHI detection, labeled by token_type
  Label shows: {{PHI:PROVIDER}} not the value

Signal tab (all extractions with confidence metadata):
  Color gradient border → green (1.0) through yellow (0.6) to red (0.0)
  Grey hatched fill     → negative space regions (what was missed)
  Right panel: sortable by confidence ASC to surface worst performers first
```

### 7.3 Page sync behavior
- User opens PDF in left panel via browser file picker (local file, no upload)
- Dashboard loads page 1, calls GET /v1/admin/audit/document/:id/page/0
- Right panel populates with page 0 data
- User navigates PDF pages via Prev/Next buttons
- Each page change calls the page endpoint for the new page index
- Clicking a row in the right panel scrolls PDF to that page (if not already there)
  and pulses the corresponding bounding box

---

## 8. Retention

All audit tables are cleaned by `adiRetentionCleanupHandler` (daily 4AM CRON).

```
audit_fields                30 days
audit_phi_detections        30 days
audit_negative_space        30 days
audit_documents             30 days
audit_sessions              30 days
audit_session_summary       90 days
```

Add to `adiRetentionCleanupHandler`:
```sql
DELETE FROM audit_fields WHERE document_id IN (
  SELECT id FROM audit_documents WHERE created_at < NOW() - INTERVAL '30 days'
);
DELETE FROM audit_phi_detections WHERE document_id IN (
  SELECT id FROM audit_documents WHERE created_at < NOW() - INTERVAL '30 days'
);
DELETE FROM audit_negative_space WHERE document_id IN (
  SELECT id FROM audit_documents WHERE created_at < NOW() - INTERVAL '30 days'
);
DELETE FROM audit_documents WHERE created_at < NOW() - INTERVAL '30 days';
DELETE FROM audit_sessions WHERE created_at < NOW() - INTERVAL '30 days';
DELETE FROM audit_session_summary WHERE updated_at < NOW() - INTERVAL '90 days';
```

---

## 9. Environment Bindings

```
env.JWT_SECRET       HMAC-SHA256 secret for worker-minted user JWTs.
                     Primary auth path for all authenticated endpoints,
                     including audit. Rotation invalidates all tokens.

env.ADI_ADMIN_KEY    Legacy static bearer, still accepted by requireRole
                     as a fallback for the ADI console only. iOS does not
                     read or send this. Removed in AUTH-2.
                     Generate (if rotating): openssl rand -hex 32
```

---

## 10. Build Sequence (Sub-Sprints)

See sprint prompts in sub-sprint documents. Build in this order —
each sub-sprint has testable output before the next begins.

```
AP-1  Neon schema migration (audit tables + indexes)
AP-2  Worker endpoints — session + document ingestion
AP-3  Worker endpoints — read/page endpoint
AP-4  iOS AuditService skeleton + SuperuserManager gate
AP-5  iOS — wire sendDocument + sendFields to ingest pipeline
AP-6  iOS — wire sendPHIDetections to tokenizer
AP-7  iOS — wire sendNegativeSpace (requires negative space analysis)
AP-8  Admin dashboard — session list + document list
AP-9  Admin dashboard — PDF viewer + bounding box overlay
AP-10 Admin dashboard — tabbed panels + page sync
```

---

## 11. Write Permission Boundaries

Consistent with FUNCTION_DISTINCTION.md section 8.2.

| Component | Can write to | Cannot write to |
|---|---|---|
| AuditService (iOS) | audit_* tables via Worker | Any non-audit table |
| Worker audit endpoints | audit_* tables | Any non-audit table |
| Retention CRON | Delete from audit_* tables | Insert to audit_* tables |
| Dashboard | Nothing — read only | Everything |

---

## 12. Trigger Boundaries

| Trigger | Starts | Does NOT start |
|---|---|---|
| SuperuserManager.isEnabled = true | Nothing automatic | AuditService calls |
| Extraction pipeline completes | AuditService.sendDocument() if superuser on | Any production data write |
| Tier assignment completes | AuditService.sendFields() if superuser on | PatternAtom creation |
| Tokenizer completes | AuditService.sendPHIDetections() if superuser on | Server-side PHI processing |
| Dashboard page change | GET /v1/admin/audit/document/:id/page/:n | Any write operation |

---

## AP-10a Addendum — sendFields() payload conventions

These rules apply to the iOS `AuditService.sendFields()` payload and the
corresponding `audit_fields` rows. They resolve column-name and type
mismatches between the iOS extraction model and the Neon schema.

### Tier numbering

`tier_assigned` is an INT derived from `ReviewTier.tierNumber`:

| ReviewTier         | tier_assigned |
|--------------------|---------------|
| `autoAccept`       | 1             |
| `smartReview`      | 2             |
| `explicitApproval` | 3             |

Lower numbers = less friction. Any rename or reordering of `ReviewTier`
cases requires a coordinated Neon migration before the iOS change ships.

### Extraction pass coverage

`extraction_pass` is hardcoded `"pass2"` for every field leaving
`sendFields()`. The current pipeline only routes AI Pass 2 output
(`AIExtractionService.extract`) through `TierAssignmentService`, so every
item reaching the audit payload is by construction a Pass 2 field.

**Not yet covered by the audit:**

- Regex clinical suggestions emitted by `UnifiedExtractor` in
  `RecordIngestPipeline.run()` step 4. These go directly to
  `PendingInterpretationStore` and never flow through `sendFields()`.
- FHIR-sourced imports (`ExtractionMethod.fhirImport`).
- Manually annotated items from `RecordAnnotationView`
  (`ExtractionMethod.userManual`).
- Reconciliation `corroborations` (written directly to `FactStore` as new
  `FactInterpretation`s, never entering `PendingInterpretation`).
- Reconciliation `duplicates` (dropped entirely).

A follow-on sprint should decide which of these belong in the audit and
either plumb them through `sendFields()` or give them a dedicated endpoint.

### source_text_length and word_count

Both scalars are computed on the **tokenized** `sourceText` that the iOS
side holds at audit time. PHI placeholders (`{{PHI:DATE:date1}}`,
`{{PHI:PROVIDER:dr2}}`, etc.) are longer than the underlying values they
replace, so both counts are slightly inflated relative to the original
document text. This is intentional: detokenizing for measurement would
pull PHI into a code path whose output then leaves the device. Dashboards
consuming these columns should treat them as analytic approximations, not
as exact document metrics.

### was_reconciled semantics

`was_reconciled = true` means the field was classified as a near-match
against an existing FactStore entry by `EntityReconciliationService` and
merged with the user's prior knowledge rather than entering as a fresh
atom. `false` means the field is a new atom with no prior corroboration.

**Reconciliation outcomes NOT currently expressed in the audit:**
- `corroborations` — strong matches written directly to FactStore.
  Invisible to the audit. See coverage gap above.
- `duplicates` — exact-match drops. Invisible to the audit.

### bounding_box shape

`bounding_box` is a JSONB object with a single top-level key `spans`, an
array of per-span dictionaries. Each span carries the union rect for the
full sourceText region and — when AP-10a value-narrowing succeeds — a
narrower rect around the `proposedValue` subset of the span's wordRects:

```
{
  "spans": [
    {
      "page": 2,
      "x": 0.12, "y": 0.34, "width": 0.50, "height": 0.03,
      "value_x": 0.18, "value_y": 0.34, "value_width": 0.07, "value_height": 0.03
    }
  ]
}
```

- `x/y/width/height` (full-span bounds) are always present.
- `value_x/value_y/value_width/value_height` are **only present** when
  the matcher located `proposedValue` inside that span's wordRects.
- **`valueBounds == nil` is not an error.** It means the value could not
  be located within the span (e.g. AI truncation, date format drift,
  numeric ambiguity across line). Dashboards should fall back to the
  full-span bounds in that case.
- `page_index` (the INT column) is populated from `spans[0].page` as a
  convenience index for the tab-panel query. Multi-page items lose
  later spans from the column-level filter — the authoritative page
  list lives inside `bounding_box.spans[*].page`.

### Keys dropped from the payload

The following keys used to appear in the pre-AP-10a payload and are
**no longer sent**:

- `value`, `source_text` — PHI-adjacent; the audit must never receive
  raw extracted values or source strings.
- `tier_reason`, `status`, `kind`, `tier`, `extraction_method` —
  superseded by the renamed/retyped columns above.

---

*End of document.*

*Document version 1.1 (AP-10a addendum). Governs the superuser
extraction audit pipeline. All sprint prompts implementing audit
components must reference the relevant sections of this document.
Schema changes require this document to be updated before
implementation begins. PHI boundary (section 2) is a hard
constraint on all implementations — no exceptions.*
