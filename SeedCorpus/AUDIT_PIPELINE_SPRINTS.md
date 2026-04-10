# Audit Pipeline — Sub-Sprint Prompts
## Record Health — AP-1 through AP-10

**Document version:** 1.0
**References:** AUDIT_PIPELINE.md, CLAUDE.md, ARCHITECTURE.md
**Workflow:** One sub-sprint at a time. Audit before build. Test before next sprint.
**Rule:** Never begin a sub-sprint until the prior sub-sprint passes on-device or
in-browser testing and is committed.

---

## AP-1 — Neon Schema Migration

### Pre-sprint audit prompt
```
Read AUDIT_PIPELINE.md sections 4 and 8.
Read SERVER_INFRASTRUCTURE.md section 4.2 (existing tables).

Audit only — do not implement anything.

1. List any conflicts between the audit table schema and existing ADI tables.
2. Identify the correct migration file naming convention for this project.
3. Confirm the index strategy in section 4.7 is appropriate for the
   page-level query pattern in GET /v1/admin/audit/document/:id/page/:n.
4. Identify any foreign key constraints that should be added.

Return assessment only. No code.
```

### Build prompt
```
Read AUDIT_PIPELINE.md section 4 (complete schema) and section 8 (build sequence).
Read SERVER_INFRASTRUCTURE.md section 4.2 and 7.2.

Create a Neon Postgres migration file that adds all six audit tables:
audit_sessions, audit_documents, audit_fields, audit_phi_detections,
audit_negative_space, audit_session_summary.

Include all indexes from section 4.7.

Migration file should be idempotent (CREATE TABLE IF NOT EXISTS).
Do not modify any existing tables.
Do not add foreign key constraints across audit and non-audit tables —
audit tables are isolated by design.

Place migration at: recordhealth-api/migrations/audit_pipeline_v1.sql
```

### Test gate
Run migration against Neon staging branch. Verify all tables and indexes
exist. Verify no existing tables were modified. Commit before AP-2.

---

## AP-2 — Worker Endpoints: Session and Document Ingestion

### Pre-sprint audit prompt
```
Read AUDIT_PIPELINE.md sections 5.1, 5.2, and 9.
Read SERVER_INFRASTRUCTURE.md sections 3 (auth pattern) and 5.3 (ADI routes).
Read CLAUDE.md for the Worker routing architecture note (section 10).

Audit only — do not implement anything.

1. The audit endpoints use ADI_ADMIN_KEY authentication, not user JWT.
   Describe exactly how the admin key middleware should differ from the
   existing JWT middleware in index.js.
2. The existing Worker is a manual if-chain at ~1,000 lines post-ADI.
   Where should the audit route handlers be inserted to maintain
   readability without requiring a router refactor?
3. POST /v1/admin/audit/fields accepts a batch of fields. What is the
   correct Neon batch insert pattern for the serverless HTTP driver?
4. Should audit endpoints return 201 or 200 on successful insert?

Return assessment only. No code.
```

### Build prompt
```
Read AUDIT_PIPELINE.md sections 5.1 and 5.2.
Read SERVER_INFRASTRUCTURE.md sections 3 and 10.
Read the existing recordhealth-api/src/index.js routing pattern.

Add the following endpoints to index.js:

POST /v1/admin/audit/session/start
POST /v1/admin/audit/session/complete
POST /v1/admin/audit/document
POST /v1/admin/audit/fields       (batch insert — array of field rows)
POST /v1/admin/audit/phi          (batch insert)
POST /v1/admin/audit/negative-space (batch insert)

All require ADI_ADMIN_KEY header authentication.
Implement admin key middleware as a separate function from JWT middleware.
Server generates id (UUID) and created_at (TIMESTAMPTZ) — do not accept
these from the client.

After each document insert, update audit_sessions.document_count += 1.
After each batch insert to audit_fields, update audit_session_summary
with recalculated aggregates (tier counts, confidence bands, by_field_type).

Do not modify any existing routes.
Do not modify auth middleware for existing routes.
```

### Test gate
Deploy to staging Worker. Test each endpoint via curl with admin key.
Verify rows appear in Neon staging branch. Verify existing routes unaffected.
Commit before AP-3.

---

## AP-3 — Worker Endpoints: Read and Page Endpoint

### Pre-sprint audit prompt
```
Read AUDIT_PIPELINE.md sections 5.3 and 7.3.

Audit only — do not implement anything.

1. GET /v1/admin/audit/document/:id/page/:n is the hot path —
   called on every page change in the dashboard. What query structure
   minimizes round trips for the three-table join
   (audit_fields + audit_phi_detections + audit_negative_space)?
2. Should the page endpoint return empty arrays or 404 when a page
   has no extractions? Dashboard behavior differs for each.
3. The session summary endpoint returns audit_session_summary plus
   a document list. Should documents be embedded in the summary
   response or returned as a separate array?

Return assessment only. No code.
```

### Build prompt
```
Read AUDIT_PIPELINE.md section 5.3.

Add the following read endpoints to index.js:

GET /v1/admin/audit/sessions
  Returns: array of audit_sessions ordered by created_at DESC
  Include document_count and completed_at in each row

GET /v1/admin/audit/session/:id
  Returns: audit_session_summary row + array of audit_documents for session
  Return 404 if session not found

GET /v1/admin/audit/document/:id
  Returns: audit_documents row
  Return 404 if not found

GET /v1/admin/audit/document/:id/page/:n
  Returns: {
    fields: [...],         -- audit_fields where page_index = n
    phi: [...],            -- audit_phi_detections where page_index = n
    negative_space: [...]  -- audit_negative_space where page_index = n
  }
  Return empty arrays (not 404) when a page has no data for a category
  This endpoint must return in < 200ms — index-backed queries only

All read endpoints require ADI_ADMIN_KEY header.
All read endpoints are read-only — no writes permitted.
```

### Test gate
Deploy to staging. Verify page endpoint returns correct data for each
page index. Verify empty arrays returned for pages with no data.
Verify response time acceptable. Commit before AP-4.

---

## AP-4 — iOS AuditService Skeleton + SuperuserManager Gate

### Pre-sprint audit prompt
```
Read AUDIT_PIPELINE.md sections 6 and 2.3.
Read CLAUDE.md sections: Sprint Audit Checklist, Conventions.
Read ARCHITECTURE.md layer definitions.

Audit only — do not implement anything.

1. AuditService is @MainActor. The ingest pipeline runs async.
   Describe the correct actor isolation pattern for fire-and-forget
   audit calls that must never block the ingest pipeline.
2. SuperuserManager.shared.isEnabled — does this class already exist
   from Phase 0A planning, or does it need to be created?
   If it exists, where does it live?
3. AuditService maintains documentIdMap: [UUID: UUID] mapping recordId
   to auditDocumentId. What is the correct persistence strategy for
   this map across an ingest session? In-memory only? Or does it need
   to survive app backgrounding?
4. What is the correct base URL for audit endpoints — same as the
   existing Worker URL or a separate config?

Return assessment only. No code.
```

### Build prompt
```
Read AUDIT_PIPELINE.md section 6.
Read CLAUDE.md conventions (one type per file).

Create two new files:

1. Services/SuperuserManager.swift (if it does not already exist)
   @MainActor singleton
   isEnabled: Bool — persisted in UserDefaults (not Keychain —
   this is a dev toggle, not a secret)
   toggle() function
   Never enabled in release builds:
   #if DEBUG
   // superuser toggle available
   #else
   var isEnabled: Bool { false }
   #endif

2. Services/AuditService.swift
   @MainActor singleton
   currentSessionId: UUID? (in-memory only)
   documentIdMap: [UUID: UUID] (in-memory only — session-scoped)

   Implement stub methods that:
   - Guard on SuperuserManager.shared.isEnabled — return immediately if false
   - Log to console that they would fire (for verification)
   - Do NOT make network calls yet (that is AP-5)

   Methods:
   startSession(label: String?) async
   completeSession() async
   sendDocument(record:result:durations:) async -> UUID?
   sendFields(documentId:fields:) async
   sendPHIDetections(documentId:tokenMap:pageCoordinates:) async
   sendNegativeSpace(documentId:regions:) async

Do not wire AuditService to any existing pipeline yet.
Do not modify any existing files.
```

### Test gate
Build succeeds. SuperuserManager toggle works in Settings (or via
console for now). AuditService methods log correctly when superuser
on, silent when off. Commit before AP-5.

---

## AP-5 — iOS: Wire sendDocument + sendFields to Ingest Pipeline

### Pre-sprint audit prompt
```
Read AUDIT_PIPELINE.md section 6 (touch points).
Read CLAUDE.md Sprint Audit Checklist.
Read RecordIngestPipeline.swift.

Audit only — do not implement anything.

1. Identify the exact lines in RecordIngestPipeline.swift where
   sendDocument should fire (after Pass 1 + Pass 2, before tier assignment)
   and where sendFields should fire (after tier assignment).
2. sendDocument requires ExtractionDurations — are pass1 and pass2
   durations currently measured in the pipeline? If not, what is the
   minimum instrumentation needed?
3. sendFields requires TieredInterpretation array with bounding boxes.
   Confirm bounding box coordinate data is available at the tier
   assignment stage — reference Sprint H1/H1b work.
4. Confirm that AuditService fire-and-forget calls cannot throw into
   the ingest pipeline. What is the correct Swift pattern?

Return assessment only. No code.
```

### Build prompt
```
Read AUDIT_PIPELINE.md section 6.
Read the audit prompt output from above before writing any code.

Implement network calls in AuditService for startSession,
sendDocument, and sendFields.

Wire AuditService calls into RecordIngestPipeline.swift:
- AuditService.shared.startSession() at pipeline start
  (only if no session is active — check currentSessionId)
- AuditService.shared.sendDocument() after extraction completes
- AuditService.shared.sendFields() after tier assignment

All calls:
- Wrapped in guard SuperuserManager.shared.isEnabled else { return }
- Fire-and-forget: Task { await AuditService.shared.sendX() }
- Failures silently caught — never propagate to ingest pipeline
- Atomic write rules from CLAUDE.md apply to audit payloads

Do not modify extraction logic.
Do not modify tier assignment logic.
Do not modify FactStore writes.
Touch points only — minimum viable wiring.
```

### Test gate
Enable superuser on device. Ingest one test document. Verify
audit_sessions and audit_documents rows appear in Neon staging.
Verify audit_fields rows appear with correct page_index and bounding_box.
Verify normal ingest completes correctly — no regression.
Commit before AP-6.

---

## AP-6 — iOS: Wire sendPHIDetections to Tokenizer

### Pre-sprint audit prompt
```
Read AUDIT_PIPELINE.md sections 2.1, 2.2, and 6.
Read RecordTokenizer.swift and PHITokenStore.swift.

Audit only — do not implement anything.

1. At what point in the tokenizer does a PHI hit have both a
   token_placeholder AND a bounding box coordinate available?
   The bounding box requires the word-level coordinate work from
   Sprint H1/H1b — confirm this data is accessible at tokenizer time.
2. The audit sends token_placeholder (e.g. {{PHI:PROVIDER:dr3}})
   but never the matched value. Confirm the tokenizer produces
   placeholders in this format and that the value is never in scope
   at the point where the audit call would fire.
3. pattern_matched should be the regex pattern name, not the matched
   text. Does RecordTokenizer track which named pattern fired?
   If not, what is the minimum change to surface pattern names
   without surfacing matched text?

Return assessment only. No code.
```

### Build prompt
```
Read AUDIT_PIPELINE.md sections 2.1, 2.2, and 6.
Read the audit prompt output before writing code.

Implement AuditService.sendPHIDetections() network call.

Wire into RecordTokenizer.swift or RecordIngestPipeline.swift
at the point where tokenization is complete and bounding boxes
are available.

Payload per detection:
- token_type: string (PROVIDER, DATE, MRN, etc.)
- token_placeholder: string ({{PHI:PROVIDER:dr3}})
- bounding_box: normalized coordinates
- confidence: tokenizer confidence if available, null if not
- pattern_matched: regex pattern name only

Hard constraint: the matched PHI value must never appear in the
audit payload at any point. Verify this in code review before commit.

Do not modify tokenization logic.
Do not modify PHITokenStore.
```

### Test gate
Enable superuser. Ingest a document with known PHI (provider name,
date, etc.). Verify audit_phi_detections rows appear in Neon with
correct token_type and placeholder. Verify no PHI values appear
anywhere in the Neon rows. Commit before AP-7.

---

## AP-7 — iOS: Wire sendNegativeSpace

> DEFERRED: Negative space is assessed by the human reviewer during
> tier review. Automated gap detection is out of scope at this stage.

### Pre-sprint audit prompt
```
Read AUDIT_PIPELINE.md sections 4.5 and 6.
Read the current extraction pipeline (RecordIngestPipeline.swift,
DocumentReadService.swift, any OCR services).

Audit only — do not implement anything.

1. Does the current pipeline track regions that were processed but
   produced no extraction? If not, what is the minimum instrumentation
   needed to identify negative space regions?
2. The region_type taxonomy in audit_negative_space has four values:
   'unextracted_text_block', 'low_ocr_confidence_region',
   'skipped_section', 'empty_after_tokenization'.
   Which of these can be derived from existing pipeline data without
   new instrumentation?
3. Are OCR confidence scores per region currently available from
   VisionKit? If so, at what granularity (word, line, block)?

Return assessment only. No code.
```

### Build prompt
```
Read AUDIT_PIPELINE.md section 4.5 and 6.
Read the audit prompt output before writing code.

Implement AuditService.sendNegativeSpace() network call.

Wire into the extraction pipeline at the point where negative space
regions can be identified. Start with what is derivable from existing
data — do not add new OCR instrumentation for this sprint.

Minimum viable negative space detection:
- Regions where OCR confidence is below Tier 2 threshold
- Text blocks present in the document that produced no extracted fields
- Sections skipped by the section detector

If negative space analysis requires new instrumentation that would
modify core extraction logic, scope this sprint to only the regions
derivable without modification and flag the rest for a future sprint.

Do not modify extraction logic beyond minimum necessary instrumentation.
```

### Test gate
Enable superuser. Ingest a multi-page document. Verify
audit_negative_space rows appear for at least one page.
Verify bounding boxes are present and normalized correctly.
Commit before AP-8.

---

## AP-8 — Admin Dashboard: Session List + Document List

### Pre-sprint audit prompt
```
Read AUDIT_PIPELINE.md sections 7.1 and 5.3.
Read the existing record_health_reference.html for UI style reference.

Audit only — do not implement anything.

1. The dashboard needs ADI_ADMIN_KEY to call Worker endpoints.
   For a browser-based tool, where should this key be stored?
   (Options: hardcoded in HTML for local use only,
   prompted on load and stored in sessionStorage,
   URL parameter)
   What is the correct choice for an internal-only local tool?
2. The session list calls GET /v1/admin/audit/sessions.
   Should the dashboard auto-refresh or require manual refresh?
3. PDF.js is loaded from CDN. Which version and which CDN URL
   is appropriate given the CSP constraints in the Worker?

Return assessment only. No code.
```

### Build prompt
```
Read AUDIT_PIPELINE.md section 7.

Create a single-file HTML dashboard at:
recordhealth-api/admin/audit-dashboard.html

This file is opened locally in a browser — it is NOT served by the Worker.
It calls Worker endpoints directly using the admin key.

Phase 1 scope (this sprint — no PDF viewer yet):

On load:
- Prompt for admin key (stored in sessionStorage for the tab session)
- Call GET /v1/admin/audit/sessions
- Display session list: label, created_at, document_count, completed status

On session click:
- Call GET /v1/admin/audit/session/:id
- Display session summary stats:
  tier1_rate, total_extractions, phi_by_token_type, total_negative_regions
- Display document list: filename, category, page_count, tier1/2/3 counts

On document click:
- Call GET /v1/admin/audit/document/:id
- Display document detail stats
- Show page selector (buttons 1 through page_count)
- On page select: call GET /v1/admin/audit/document/:id/page/:n
- Display raw JSON of fields, phi, negative_space for that page
  (formatted, not a viewer yet — that is AP-9)

Style: clean, minimal, functional. This is a dev tool not a product UI.
Single file — no external dependencies except CDN-hosted libraries.
```

### Test gate
Open dashboard in browser. Load a completed audit session.
Navigate to a document. Navigate pages and verify correct data
loads per page. Commit before AP-9.

---

## AP-9 — Admin Dashboard: PDF Viewer + Bounding Box Overlay

### Pre-sprint audit prompt
```
Read AUDIT_PIPELINE.md section 7.

Audit only — do not implement anything.

1. PDF.js renders to a canvas element. SVG overlays sit on top of
   the canvas as an absolutely positioned layer. Describe the
   correct CSS positioning to make the SVG track the PDF canvas
   exactly, including when the user zooms the PDF.
2. Bounding boxes in audit_fields are normalized 0-1 coordinates.
   The PDF.js canvas has pixel dimensions. Describe the coordinate
   transformation required to convert normalized coords to canvas
   pixel positions.
3. The dashboard loads the PDF from a local file (browser file picker,
   file:// URL). PDF.js supports this. Are there any browser security
   restrictions on loading local files into PDF.js that need to be
   handled?

Return assessment only. No code.
```

### Build prompt
```
Read AUDIT_PIPELINE.md sections 7.1, 7.2, and 7.3.
Read the audit prompt output before writing code.

Extend audit-dashboard.html with PDF viewer and overlay:

Left panel:
- File picker: user selects local PDF (file:// — no upload)
- PDF.js renders selected PDF
- Page navigation: Prev / Next buttons, current page indicator
- SVG overlay layer: absolutely positioned on top of PDF canvas
  Overlay updates when page changes or tab changes

Right panel (replace raw JSON from AP-8 with formatted tabs):
- Three tabs: Auto-accepted | PHI | Signal
- Each tab shows a list of items for the current page
- List columns vary by tab:
  Auto-accepted: field_type, tier, confidence, was_reconciled
  PHI: token_type, token_placeholder, pattern_matched
  Signal: field_type, confidence, extraction_pass, region_type (negative space)

Overlay colors per tab (AUDIT_PIPELINE.md section 7.2):
- Auto-accepted: green (T1), yellow (T2), orange (T3)
- PHI: red, labeled with token_type abbreviation
- Signal: gradient green→red by confidence, grey hatched for negative space

Clicking a row in the right panel:
- Pulses (brief highlight animation) the corresponding bounding box
- If item is on a different page, navigates PDF to that page first
```

### Test gate
Load a real test document PDF locally. Load a completed audit session
for that document. Verify bounding boxes render in correct positions
on the PDF. Verify tab switching changes overlay. Verify page navigation
updates both panels. Commit before AP-10.

---

## AP-10 — Admin Dashboard: Polish + Signal Tab

### Build prompt
```
Read AUDIT_PIPELINE.md sections 7.2 and 7.3.

Final dashboard polish sprint:

1. Signal tab completion:
   - Negative space regions rendered as grey hatched SVG fills
   - Sorted by confidence ASC (worst performers first)
   - Confidence shown as a colored pill (green/yellow/red thresholds)
   - Reconciliation delta shown: match / pass2_override / pass1_only / pass2_only

2. Session summary bar:
   Below the tab panel, always visible:
   - Tier 1 rate (large number, color-coded: green > 0.80, yellow > 0.60, red below)
   - Total PHI detections
   - Total negative space regions
   - Pass 1 / Pass 2 agreement rate

3. Document filename pairing UX:
   - When viewing a session document, show the expected filename
   - If the loaded PDF filename matches the document filename, show green checkmark
   - If mismatch, show warning (wrong document loaded)

4. Keyboard shortcuts:
   - Arrow keys: prev/next page
   - 1/2/3: switch tabs
   - Space: pulse all bounding boxes on current page

No new endpoints required. Polish only.
```

### Test gate
Full end-to-end audit session: ingest 3+ test documents with superuser
on, open dashboard, load session, load matching PDFs, navigate all tabs
and pages, verify all overlays correct, verify summary stats accurate.
This is the acceptance test for the full audit pipeline.
Commit and tag: audit-pipeline-v1-complete.

---

## Commit Convention for This Sprint Series

```bash
# AP-1
git commit -m "feat(audit): Neon schema migration — audit pipeline tables AP-1"

# AP-2
git commit -m "feat(audit): Worker ingestion endpoints — session/document/fields AP-2"

# AP-3
git commit -m "feat(audit): Worker read endpoints — session list and page endpoint AP-3"

# AP-4
git commit -m "feat(audit): AuditService skeleton + SuperuserManager gate AP-4"

# AP-5
git commit -m "feat(audit): wire sendDocument + sendFields to ingest pipeline AP-5"

# AP-6
git commit -m "feat(audit): wire sendPHIDetections to tokenizer AP-6"

# AP-7
git commit -m "feat(audit): wire sendNegativeSpace to extraction pipeline AP-7"

# AP-8
git commit -m "feat(audit): admin dashboard session list + document list AP-8"

# AP-9
git commit -m "feat(audit): admin dashboard PDF viewer + bounding box overlay AP-9"

# AP-10
git commit -m "feat(audit): admin dashboard signal tab + polish AP-10"

# Series complete
git tag audit-pipeline-v1-complete
```

---

## Reference Checklist (paste at top of every Claude Code session)

```
Before implementing any AP sub-sprint:
1. Read AUDIT_PIPELINE.md — full document
2. Read CLAUDE.md — sprint audit checklist + integration layer constraints
3. Read ARCHITECTURE.md — layer definitions
4. Run the pre-sprint audit prompt for this sub-sprint
5. Confirm audit output before writing a single line of code
6. Implement only the scoped sub-sprint — nothing beyond it
7. Test on device / in browser before committing
8. Commit before starting the next sub-sprint
```

---

*End of document.*

*Sub-sprint prompts for AUDIT_PIPELINE.md implementation.
Follow the workflow exactly: audit → build → test → commit → next sprint.
Never combine sub-sprints. Never skip the audit step.*
