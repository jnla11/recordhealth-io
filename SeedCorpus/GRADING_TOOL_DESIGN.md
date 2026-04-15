# Record Health — Lightweight Grading Tool
## Design Specification v1.0

---

## Governing Principles

Every decision in this document is governed by:

1. **Provenance Doctrine** — every data point is first-class. No reconstruction, no derivation, no fabrication. If a value is not captured at source, it is null, never inferred.
2. **Silo Discipline** — annotated documents never touch Bedrock or any training pipeline. The grading corpus is a measurement instrument, not training data.
3. **Schema Continuity** — the lightweight schema is the Tier 3 correction DB schema minus persistence infrastructure. No migration required when Tier 3 ships. Every field defined here maps directly to an `audit_corrections` column.
4. **Defensibility** — every annotation, score, and export is timestamped, versioned, and reproducible. The system must be able to answer a compliance auditor's questions about validation methodology.
5. **Append-only** — corrections are never edited. A wrong annotation gets a superseding annotation with a `supersedes_id` reference. The original is preserved.

---

## Architecture Alignment

Before any implementation sprint, Claude Code must read:
- `CLAUDE.md` — sacred rules, workflow, architectural constraints
- `ARCHITECTURE.md` — five-layer structure, FactStore, PHI vault, audit pipeline
- `AUDIT_PIPELINE.md` — audit service conventions, field shapes, bounding box format
- This document — grading tool specification

**Sacred rules that apply directly:**
- Atomic writes, no `try?`
- PHI ultra hard floor — real PHI values never leave device, never enter grading DB
- Provenance Doctrine — no reconstruction
- All grading data references audit records by UUID — never duplicates audit data

---

## Core Concepts

### Grading Session
A human reviewer opens one or more documents and draws annotations. A grading session is scoped to a single sitting — one reviewer, one prompt version, one set of documents. It produces a versioned JSON export.

### Annotation
A single human-drawn rectangle on a PDF page, labeled with entity kind, verbatim value, and metadata. This is the ground truth atom.

### AI Field Match
A computed record linking one annotation to zero or one AI-extracted audit field, scored by IoU (spatial overlap) and NDC (value distance). Computed at export time, never stored as mutable state.

### Grading Export
A versioned, timestamped JSON document containing all annotations for a grading session plus all computed match scores. This is the durable artifact. It is immutable once written.

### Prompt Version
A string identifier incremented every time the Pass 2 prompt changes. Format: `pass2-vN` where N is a monotonically increasing integer. Stored in `AIExtractionService.swift` and travels through the audit pipeline into every audit record and every grading export.

---

## Schema

### Neon Table: `grading_sessions`

```sql
CREATE TABLE grading_sessions (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at        TIMESTAMPTZ,
  reviewer_id         TEXT NOT NULL,          -- opaque identifier, no PII
  prompt_ref          JSONB NOT NULL,         -- {"prompt_id":"pass2_extraction","version":"v1"}
  notes               TEXT,
  document_count      INTEGER DEFAULT 0
);
```

### Neon Table: `document_grades`

```sql
CREATE TABLE document_grades (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  grading_session_id  UUID NOT NULL REFERENCES grading_sessions(id),
  audit_document_id   UUID NOT NULL,          -- FK to audit_documents
  audit_session_id    UUID NOT NULL,          -- FK to audit_sessions
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  page_count          INTEGER NOT NULL,
  annotation_count    INTEGER DEFAULT 0,
  
  -- Computed at export time, stored for caching
  recall              FLOAT,                  -- hits / total annotations
  precision           FLOAT,                  -- correct AI fields / total AI fields
  f1                  FLOAT,                  -- harmonic mean of recall and precision
  
  -- Per entity kind breakdown (JSONB)
  -- { "condition": { recall, precision, f1, count }, ... }
  scores_by_kind      JSONB
);
```

### Neon Table: `annotations`

```sql
CREATE TABLE annotations (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_grade_id   UUID NOT NULL REFERENCES document_grades(id),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  supersedes_id       UUID REFERENCES annotations(id),  -- append-only correction
  
  -- Location
  page_index          INTEGER NOT NULL,       -- 1-indexed, matches audit pipeline
  
  -- Bounding box — normalized 0-1, Vision coordinate system (bottom-left origin)
  -- Matches audit_fields.bounding_box coordinate system exactly
  x                   FLOAT NOT NULL,
  y                   FLOAT NOT NULL,
  width               FLOAT NOT NULL,
  height              FLOAT NOT NULL,
  
  -- Classification
  entity_kind         TEXT NOT NULL,          -- condition, medication, vitalSign, etc.
  field_type          TEXT NOT NULL,          -- clinical, temporal, provider
  is_phi              BOOLEAN NOT NULL DEFAULT FALSE,
  phi_token           TEXT,                   -- {{PHI:DATE:date1}} if known
  
  -- Ground truth value
  -- verbatim text as it appears in the document
  -- PHI fields store token placeholder, never real value
  verbatim_value      TEXT NOT NULL,
  
  -- Context
  reviewer_notes      TEXT,
  confidence          FLOAT DEFAULT 1.0,      -- reviewer confidence 0-1
  
  -- Grouping — multiple annotations can form a logical entity
  -- e.g. a vital sign label + value drawn as separate rects
  group_id            UUID                    -- NULL = standalone annotation
);
```

### Neon Table: `grading_exports`

```sql
CREATE TABLE grading_exports (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  grading_session_id  UUID NOT NULL REFERENCES grading_sessions(id),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  prompt_ref          JSONB NOT NULL,
  export_json         JSONB NOT NULL,         -- full export blob, immutable
  sha256_checksum     TEXT NOT NULL           -- integrity verification
);
```

---

## JSON Export Format

### Top-level export document

```json
{
  "export_id": "uuid",
  "created_at": "2026-04-14T05:43:21.589Z",
  "prompt_ref": { "prompt_id": "pass2_extraction", "version": "v3" },
  "reviewer_id": "reviewer-opaque-id",
  "grading_session_id": "uuid",
  "schema_version": "1.0",
  "sha256_checksum": "...",
  
  "aggregate": {
    "document_count": 5,
    "annotation_count": 147,
    "ai_field_count": 312,
    "recall": 0.71,
    "precision": 0.84,
    "f1": 0.77,
    "scores_by_kind": {
      "condition": { "recall": 0.91, "precision": 0.95, "f1": 0.93, "count": 34 },
      "vitalSign":  { "recall": 0.22, "precision": 0.41, "f1": 0.29, "count": 18 },
      "medication": { "recall": 0.88, "precision": 0.79, "f1": 0.83, "count": 24 },
      "symptom":    { "recall": 0.64, "precision": 0.71, "f1": 0.67, "count": 31 },
      "provider":   { "recall": 0.95, "precision": 0.90, "f1": 0.92, "count": 8  },
      "visitDate":  { "recall": 1.00, "precision": 1.00, "f1": 1.00, "count": 5  },
      "procedure":  { "recall": 0.55, "precision": 0.68, "f1": 0.61, "count": 27 }
    }
  },
  
  "documents": [ ... ]
}
```

### Per document

```json
{
  "document_grade_id": "uuid",
  "audit_document_id": "uuid",
  "audit_session_id": "uuid",
  "document_filename": "Otolaryngology OP MD Note 11-04-2025.pdf",
  "document_category": "visit_note",
  "page_count": 4,
  "prompt_ref": { "prompt_id": "pass2_extraction", "version": "v3" },
  
  "scores": {
    "recall": 0.68,
    "precision": 0.81,
    "f1": 0.74,
    "annotation_count": 31,
    "ai_field_count": 53,
    "hit_count": 21,
    "miss_count": 10,
    "false_positive_count": 7,
    "scores_by_kind": { ... }
  },
  
  "annotations": [ ... ],
  "ai_fields": [ ... ],
  "matches": [ ... ]
}
```

### Per annotation

```json
{
  "annotation_id": "uuid",
  "supersedes_id": null,
  "created_at": "2026-04-14T05:43:21.589Z",
  
  "location": {
    "page_index": 1,
    "x": 0.119,
    "y": 0.501,
    "width": 0.305,
    "height": 0.035
  },
  
  "classification": {
    "entity_kind": "provider",
    "field_type": "provider",
    "is_phi": true,
    "phi_token": "{{PHI:PROVIDER:dr1}}"
  },
  
  "ground_truth": {
    "verbatim_value": "{{PHI:PROVIDER:dr1}}",
    "confidence": 1.0,
    "reviewer_notes": "Referring provider line, PHI tokenized"
  },
  
  "group_id": null
}
```

### Per AI field (from audit record, included for comparison)

```json
{
  "audit_field_id": "uuid",
  "entity_kind": "provider",
  "field_type": "provider",
  "value": "{{PHI:PROVIDER:dr1}}-Anaya",
  "source_text": "Referring Provider: {{PHI:PROVIDER:dr1}}-Anaya",
  "confidence": 0.95,
  "tier_assigned": 2,
  "auto_accepted": false,
  "bounding_box": {
    "spans": [
      {
        "page": 1,
        "x": 0.119, "y": 0.501,
        "width": 0.305, "height": 0.035,
        "word_rects": [ ... ]
      }
    ]
  }
}
```

### Per match record

```json
{
  "annotation_id": "uuid",
  "audit_field_id": "uuid",
  "match_type": "hit",
  
  "spatial": {
    "iou": 0.84,
    "iou_threshold": 0.50,
    "spatial_match": true
  },
  
  "normalization_delta": {
    "verbatim_match": false,
    "edit_distance": 0.12,
    "token_overlap": 0.88,
    "length_delta": 6,
    "human_value": "{{PHI:PROVIDER:dr1}}",
    "ai_value": "{{PHI:PROVIDER:dr1}}-Anaya",
    "delta_class": "minor"
  },
  
  "kind_match": true,
  "overall_correct": true
}
```

### Match types

```
hit           — IoU > 0.5, kind matches, counted in recall
partial_iou   — 0.3 < IoU < 0.5, spatial near-miss
partial_kind  — IoU > 0.5 but wrong entity kind
miss          — no AI field overlaps annotation above threshold
false_positive — AI field with no matching annotation
```

### NDC delta classes

```
exact    — verbatim match, edit_distance = 0
minor    — edit_distance < 0.15, token_overlap > 0.85
moderate — edit_distance 0.15-0.50
major    — edit_distance > 0.50, likely label expansion or truncation
wrong    — IoU matches but semantically different entity
```

---

## IoU Computation

```javascript
function computeIoU(rectA, rectB) {
  // Both rects in normalized 0-1 Vision coordinate space
  const xOverlap = Math.max(0,
    Math.min(rectA.x + rectA.width, rectB.x + rectB.width) -
    Math.max(rectA.x, rectB.x)
  );
  const yOverlap = Math.max(0,
    Math.min(rectA.y + rectA.height, rectB.y + rectB.height) -
    Math.max(rectA.y, rectB.y)
  );
  const intersection = xOverlap * yOverlap;
  const union = (rectA.width * rectA.height) +
                (rectB.width * rectB.height) - intersection;
  return union === 0 ? 0 : intersection / union;
}
```

Note: IoU operates in Vision coordinate space (bottom-left origin). The y-axis inversion applied for canvas rendering is NOT applied here — both annotation rects and AI field rects are stored and compared in the native Vision coordinate system.

---

## NDC Computation

```javascript
function computeNDC(humanValue, aiValue) {
  if (!humanValue || !aiValue) return null;
  
  const verbatimMatch = humanValue === aiValue;
  const editDistance = normalizedLevenshtein(humanValue, aiValue);
  
  const humanTokens = new Set(humanValue.toLowerCase().split(/\s+/));
  const aiTokens = new Set(aiValue.toLowerCase().split(/\s+/));
  const shared = [...humanTokens].filter(t => aiTokens.has(t)).length;
  const tokenOverlap = shared / Math.max(humanTokens.size, aiTokens.size);
  
  const lengthDelta = aiValue.length - humanValue.length;
  
  let deltaClass;
  if (verbatimMatch) deltaClass = "exact";
  else if (editDistance < 0.15) deltaClass = "minor";
  else if (editDistance < 0.50) deltaClass = "moderate";
  else deltaClass = "major";
  
  return {
    verbatim_match: verbatimMatch,
    edit_distance: editDistance,
    token_overlap: tokenOverlap,
    length_delta: lengthDelta,
    delta_class: deltaClass
  };
}
```

---

## Prompt Identity and Versioning

Governed by ARCHITECTURE.md §3.3 (RecordHealth_App repo).

In `AIExtractionService.swift` (Stage 1 transitional — moves to
Worker registry in GT-1.5), add two static constants:

```swift
static let promptId = "pass2_extraction"
static let promptVersion = "v1"
```

These travel together as `prompt_ref` through the audit payload
and into `audit_fields.prompt_ref`:

```json
{ "prompt_id": "pass2_extraction", "version": "v1" }
```

`promptId` is permanent. `promptVersion` is incremented on every
prompt text change. The pair is the primary key for delta
tracking across re-engineerings — a grading export from one
version is only comparable to an export from a different version
if both pairs are known.

The authoritative list of prompt IDs lives in
`PROMPT_ID_REGISTRY.md` at the SeedCorpus repo root.

---

## Sprint Staging

---

### Sprint GT-1 — Schema + Prompt Versioning
**Scope:** Neon schema, Worker endpoints, prompt version field, no UI

**Pre-sprint audit prompt for Claude Code:**
```
Read CLAUDE.md fully before proceeding.
Read ARCHITECTURE.md fully before proceeding.
Read AUDIT_PIPELINE.md fully before proceeding.
Read GRADING_TOOL_DESIGN.md fully before proceeding.

This is Sprint GT-1. Audit only — no implementation yet.

1. In AIExtractionService.swift, find the Pass 2 prompt.
   Report the exact location where a static promptVersion
   constant should be added.

2. In AuditService.swift sendFields(), report what change
   is needed to include prompt_ref in the field payload.

3. In recordhealth-api/src/index.js, report:
   - What ALTER TABLE is needed to add prompt_ref JSONB
     to audit_fields
   - What INSERT change is needed to store it

4. In the staging Neon DB, report the exact SQL needed to
   create the four grading tables from GRADING_TOOL_DESIGN.md:
   grading_sessions, document_grades, annotations, grading_exports

5. Report what Worker endpoints are needed:
   - POST /v1/admin/grading/session — create grading session
   - POST /v1/admin/grading/session/:id/document — add document grade
   - POST /v1/admin/grading/annotation — insert annotation
   - POST /v1/admin/grading/export — write export blob
   - GET /v1/admin/grading/sessions — list grading sessions
   - GET /v1/admin/grading/session/:id — full session with documents

Return findings only. No code changes.
```

**Build prompt for Claude Code:**
```
Read CLAUDE.md fully before proceeding.
Read ARCHITECTURE.md fully before proceeding.
Read AUDIT_PIPELINE.md fully before proceeding.
Read GRADING_TOOL_DESIGN.md fully before proceeding.

This is Sprint GT-1 implementation.
The Provenance Doctrine is absolute.
No reconstruction, no fabrication, no fallbacks.

STEP 1 — Prompt identity constants (iOS)
In AIExtractionService.swift, add:
  static let promptId = "pass2_extraction"
  static let promptVersion = "v1"
Include both in the Pass 2 request context sent to Bedrock
so they are logged but do not affect extraction behavior.

STEP 2 — Prompt version in audit payload (iOS)
In AuditService.swift sendFields(), add to each field dict:
  "prompt_ref": { "prompt_id": AIExtractionService.promptId,
                  "version": AIExtractionService.promptVersion }
No other changes to the payload.

STEP 3 — Prompt version column in Worker
In src/index.js:
- ALTER TABLE audit_fields ADD COLUMN IF NOT EXISTS
  prompt_ref JSONB
- Update INSERT to include prompt_ref from f.prompt_ref ?? null
- Add to /admin/migrate-main endpoint

STEP 4 — Grading tables in Worker
In src/index.js /admin/migrate-main, add CREATE TABLE IF NOT EXISTS
for all four grading tables exactly as specified in
GRADING_TOOL_DESIGN.md:
  grading_sessions
  document_grades
  annotations
  grading_exports

STEP 5 — Grading Worker endpoints
Implement all six endpoints listed in GT-1 audit.
All endpoints gated by isADIAdminAuthorized.
All inputs validated — reject missing required fields with 400.
All DB errors caught and returned as structured JSON errors.

STEP 6 — Build and deploy
iOS: build must succeed zero new errors.
Worker: deploy to staging only.
Run /admin/migrate-main on staging to create tables.
Do not commit until confirmed via curl test of each endpoint.
```

---

### Sprint GT-1.5 — Prompt Registry Storage
**Scope:** Stand up the Worker-side prompt registry keyed by
`(prompt_id, version)`. Populated by GT-1.5a audit sprint before
any grading export joins against it.

This sprint stores prompt text. It does NOT move prompt assembly
from iOS to Worker — that is a separate future sprint tracked in
ROADMAP.md.

**Pre-sprint audit prompt for Claude Code:**
```
Read /Users/jnolte/Projects/RecordHealth.IO/RecordHealth_App/CLAUDE.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/RecordHealth_App/docs/ARCHITECTURE.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/SeedCorpus/AUDIT_PIPELINE.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/SeedCorpus/GRADING_TOOL_DESIGN.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/SeedCorpus/PROMPT_ID_REGISTRY.md fully before proceeding.

This is Sprint GT-1.5 pre-sprint audit. No code changes.

Report:

1. In recordhealth-api/src/index.js, report the exact location
   where the new prompt_versions CREATE TABLE should be added
   in the /admin/migrate-main handler.

2. Report the exact location where the four new Worker endpoints
   should be wired into the router:
   - POST /v1/admin/prompts/register
   - GET  /v1/admin/prompts/:prompt_id/:version
   - GET  /v1/admin/prompts/:prompt_id
   - GET  /v1/admin/prompts

3. Report the current implementation of isADIAdminAuthorized so
   the new endpoints reuse the same gate with no duplication.

4. Report whether any existing iOS code currently sends prompt
   text to the Worker. Expected: no — iOS sends tokenized record
   content through the Worker to Bedrock, not prompt text.
   Confirm by inspection.

Return findings only. No code changes.
```

**Build prompt for Claude Code:**
```
Read /Users/jnolte/Projects/RecordHealth.IO/RecordHealth_App/CLAUDE.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/RecordHealth_App/docs/ARCHITECTURE.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/SeedCorpus/AUDIT_PIPELINE.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/SeedCorpus/GRADING_TOOL_DESIGN.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/SeedCorpus/PROMPT_ID_REGISTRY.md fully before proceeding.

This is Sprint GT-1.5 implementation.
The Provenance Doctrine is absolute.
Append-only. No overwrites of registered (prompt_id, version)
pairs.

STEP 1 — prompt_versions table
In src/index.js /admin/migrate-main, add:

CREATE TABLE IF NOT EXISTS prompt_versions (
  prompt_id         TEXT NOT NULL,
  version           TEXT NOT NULL,
  prompt_text       TEXT NOT NULL,
  prompt_type       TEXT NOT NULL,
  model_target      TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deprecated_at     TIMESTAMPTZ,
  changelog_note    TEXT,
  author            TEXT,
  PRIMARY KEY (prompt_id, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_prompt_id
  ON prompt_versions (prompt_id);

STEP 2 — Worker endpoints
Implement the four endpoints identified in the GT-1.5 audit.
All gated by isADIAdminAuthorized.
Register endpoint is idempotent on exact (prompt_id, version,
prompt_text) match. If (prompt_id, version) exists with
different prompt_text, return 409 Conflict — bumping version
is required to change text.
All DB errors caught and returned as structured JSON errors.

STEP 3 — Deploy to staging only
Run /admin/migrate-main to create the table.
Test each endpoint via curl.
Do not commit until all four endpoints verified.

Do not populate the registry in this sprint. Registry population
is GT-1.5a.
```

---

### Sprint GT-1.5a — Prompt Registry Audit and Population
**Scope:** Walk the iOS codebase, enumerate every system prompt,
assign a stable prompt_id to each, and populate
PROMPT_ID_REGISTRY.md and the prompt_versions table. Audit-first
discipline: findings reported and confirmed by the developer
before any IDs are codified.

**Pre-sprint audit prompt for Claude Code:**
```
Read /Users/jnolte/Projects/RecordHealth.IO/RecordHealth_App/CLAUDE.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/RecordHealth_App/docs/ARCHITECTURE.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/SeedCorpus/GRADING_TOOL_DESIGN.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/SeedCorpus/PROMPT_ID_REGISTRY.md fully before proceeding.

This is Sprint GT-1.5a pre-sprint audit. No code changes.
No edits to PROMPT_ID_REGISTRY.md in this pass.

Walk the iOS codebase at
/Users/jnolte/Projects/RecordHealth.IO/RecordHealth_App and
produce a complete inventory of every system prompt currently
in the app.

For each prompt found, report:
- File path and line range
- A verbatim excerpt of the prompt's opening (first 200
  characters) for identification
- The calling context (which service or view uses it)
- The current model target if determinable (Bedrock Claude
  Sonnet, etc.)
- The prompt type (extraction, user_chat, synthesis, ui_hint,
  classification, other)
- A proposed prompt_id following snake_case convention

Include in the inventory:
- Pass 1 document read prompt
- Pass 2 extraction prompt
- Any Ask AI system framing
- Any category-aware instructions
- Appointment prep prompt
- FHIR synthesis prompt
- Any suggested question template strings
- Any other prompt-shaped string sent to an LLM

Do not include:
- User-typed chat messages
- PHI tokenizer patterns
- UI copy that is not sent to an LLM

Return inventory only. No file edits. Flag any ambiguous cases
as open questions for the developer to resolve before
codification.
```

**Build prompt for Claude Code (runs only after developer
confirms the inventory from the audit above):**
```
Read /Users/jnolte/Projects/RecordHealth.IO/RecordHealth_App/CLAUDE.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/RecordHealth_App/docs/ARCHITECTURE.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/SeedCorpus/GRADING_TOOL_DESIGN.md fully before proceeding.
Read /Users/jnolte/Projects/RecordHealth.IO/SeedCorpus/PROMPT_ID_REGISTRY.md fully before proceeding.

This is Sprint GT-1.5a implementation.
Use only the prompt_id assignments confirmed by the developer
after the GT-1.5a audit. Do not invent or adjust IDs.

STEP 1 — Populate PROMPT_ID_REGISTRY.md
Fill in the registry table with one row per confirmed prompt.
Columns: prompt_id, current_version (v1 for all initial
entries), type, location (file path), notes.

STEP 2 — Register prompts in Worker
For each prompt, POST to /v1/admin/prompts/register with the
full prompt_text extracted verbatim from the source file.
version = "v1" for all initial registrations.
author = "GT-1.5a initial audit".
changelog_note = "Initial registration from iOS codebase audit".

STEP 3 — Add promptId constants to iOS
For each prompt whose calling service currently holds only a
promptVersion constant or no constant at all, add a matching
promptId constant. The constant pair (promptId, promptVersion)
must match exactly what was registered in step 2.

STEP 4 — Verification
Report:
- Count of prompts registered
- Diff of PROMPT_ID_REGISTRY.md
- Diff of every iOS file modified
- Confirmation that every registered prompt_text matches the
  source file verbatim

Do not commit. Surface diffs for review.
```

---

### Sprint GT-2 — PDF Canvas Annotation UI
**Scope:** Rectangle drawing on PDF canvas in ADI console. No scoring yet.

**Pre-sprint audit prompt for Claude Code:**
```
Read CLAUDE.md fully before proceeding.
Read ARCHITECTURE.md fully before proceeding.
Read GRADING_TOOL_DESIGN.md fully before proceeding.
Read admin/adi-console.html fully before proceeding.

This is Sprint GT-2 pre-sprint audit. No code changes.

Report:
1. Where in the current PDF canvas overlay system would
   annotation drawing be added without conflicting with
   existing field/PHI box rendering?

2. What state variables are needed to track:
   - Current grading session ID
   - Whether grading mode is active
   - Annotations drawn in current session (array)
   - Currently drawing rectangle (start point, current point)
   - Selected annotation (for editing label/value)

3. What UI controls are needed:
   - Toggle grading mode on/off
   - Rectangle drawing interaction (mousedown, mousemove, mouseup)
   - Annotation list panel
   - Label/value entry form per annotation

4. What conflicts exist with the current overlay SVG approach
   that would need to be resolved for interactive drawing?

Return findings only. No code changes.
```

**Build prompt for Claude Code:**
```
Read CLAUDE.md fully before proceeding.
Read ARCHITECTURE.md fully before proceeding.
Read GRADING_TOOL_DESIGN.md fully before proceeding.
Read admin/adi-console.html fully before proceeding.

This is Sprint GT-2. The Provenance Doctrine is absolute.

Implement annotation drawing on the PDF canvas.

STEP 1 — Grading mode toggle
Add a "Grade" button to the document toolbar next to
the existing zoom controls. Clicking it toggles
state.gradingMode (boolean).

When gradingMode is true:
- Show a green "GRADING MODE" indicator in the toolbar
- Disable field/PHI box overlay rendering
- Enable annotation canvas layer

When gradingMode is false:
- Restore normal field/PHI overlay behavior
- Annotation layer hidden but annotations preserved in state

STEP 2 — Annotation canvas layer
Add a transparent HTML canvas element positioned absolutely
over the PDF canvas. This is the annotation drawing surface.
It must resize correctly with zoom changes.

STEP 3 — Rectangle drawing interaction
On mousedown: record start point in normalized Vision
coordinates (apply y-axis inversion from canvas to Vision space)
On mousemove: draw a live red dashed rectangle from start to
current point
On mouseup: finalize the rectangle, add to state.annotations array

Coordinates stored in Vision coordinate system (bottom-left origin)
to match the audit pipeline. Apply (1 - y - height) transform
when converting from canvas to Vision coords.

STEP 4 — Annotation state
Each annotation in state.annotations:
{
  id: uuid,
  page_index: current page,
  x, y, width, height: normalized Vision coords,
  entity_kind: null (set in GT-3),
  field_type: null,
  verbatim_value: null,
  is_phi: false,
  phi_token: null,
  reviewer_notes: null,
  confidence: 1.0,
  group_id: null,
  created_at: ISO timestamp
}

STEP 5 — Annotation rendering
Draw all finalized annotations for the current page as
solid red rectangles with 2px stroke and 10% fill opacity.
Selected annotation gets brighter fill and thicker stroke.
Clicking an annotation selects it.

STEP 6 — Annotation count indicator
Show annotation count in the toolbar: "3 annotations"
Updates as annotations are added.

Do not implement label/value entry (GT-3).
Do not implement scoring (GT-4/GT-5).
Do not commit. Test in browser.
```

---

### Sprint GT-3 — Entity Labeling + Value Entry
**Scope:** Form UI for labeling each annotation with entity kind, value, PHI flag.

**Build prompt for Claude Code:**
```
Read CLAUDE.md fully before proceeding.
Read ARCHITECTURE.md fully before proceeding.
Read GRADING_TOOL_DESIGN.md fully before proceeding.
Read admin/adi-console.html fully before proceeding.

This is Sprint GT-3. The Provenance Doctrine is absolute.

Add annotation labeling panel.

STEP 1 — Annotation detail panel
When an annotation is selected, show a panel in the right
pane (replacing or alongside the existing field/PHI panel).

Panel contains:
- Annotation ID (truncated UUID)
- Location: Page N, coordinates
- Entity kind dropdown:
  condition, diagnosis, symptom, medication, allergy,
  procedure, vitalSign, labValue, provider, organization,
  visitDate, reportDate
- Field type: auto-populated from entity kind selection
  (clinical/temporal/provider)
- PHI toggle: checkbox "Contains PHI"
- PHI token field: text input, shown only when PHI is checked
  placeholder: "{{PHI:DATE:date1}}"
- Verbatim value: text input
  label: "Verbatim value — copy exactly from document"
  monospace font
- Confidence: slider 0.0-1.0, default 1.0
- Reviewer notes: textarea
- Group ID: optional, for linking related annotations
- Delete button: removes annotation (append-only — marks
  as superseded, does not destroy)
- Save button: persists to state.annotations

STEP 2 — Auto-populate verbatim value
When an annotation is finalized (mouseup), attempt to
pre-populate verbatim_value by reading word_rects from
the nearest AI field that overlaps the drawn rectangle
(IoU > 0.3). Join the word_rects text values.

This is a convenience pre-fill only — the reviewer must
confirm or correct the value. Label the field clearly:
"Pre-filled from AI word rects — verify against document"

This is NOT reconstruction — it is reading first-class
word_rect data from the audit record as a convenience.
The reviewer is responsible for confirming accuracy.

STEP 3 — Annotation list
Show all annotations for the current document in a
scrollable list below the drawing controls.
Each row: entity kind badge, truncated value, page number,
confidence indicator.
Clicking a row selects the annotation and scrolls PDF to
its location.

STEP 4 — Page navigation with annotations
When navigating pages, preserve all annotations in state.
Show annotation count per page in the page nav indicator:
"Page 2 of 4 (5 annotations)"

Do not implement scoring (GT-4/GT-5).
Do not implement export (GT-6).
Do not commit. Test in browser with real annotation data.
```

---

### Sprint GT-4 — AI Comparison + IoU Computation
**Scope:** Match annotations against AI fields, compute IoU, display comparison.

**Build prompt for Claude Code:**
```
Read CLAUDE.md fully before proceeding.
Read ARCHITECTURE.md fully before proceeding.
Read GRADING_TOOL_DESIGN.md fully before proceeding.
Read admin/adi-console.html fully before proceeding.

This is Sprint GT-4. The Provenance Doctrine is absolute.

Implement IoU matching between human annotations and AI fields.

STEP 1 — IoU computation function
Implement computeIoU(rectA, rectB) exactly as specified
in GRADING_TOOL_DESIGN.md.
Both rects in Vision coordinate space (bottom-left origin).
No coordinate transformation applied during IoU computation.

STEP 2 — Matching algorithm
For each annotation, find the best-matching AI field:
1. Filter AI fields to same page_index as annotation
2. For each AI field, extract its bounding box union rect:
   minX, minY across all spans on the same page
   maxX = max(span.x + span.width) across spans
   maxY = max(span.y + span.height) across spans
3. Compute IoU between annotation rect and AI union rect
4. Best match = AI field with highest IoU
5. If best IoU >= 0.5 and entity kinds match: hit
6. If best IoU >= 0.5 but kinds differ: partial_kind
7. If 0.3 <= best IoU < 0.5: partial_iou
8. If best IoU < 0.3: miss

AI fields with no annotation match above 0.3 IoU: false_positive

STEP 3 — Match visualization
When grading mode is active, show both annotation rects (red)
and matched AI field rects (blue) simultaneously.
Color coding:
- Green annotation: hit
- Yellow annotation: partial match
- Red annotation: miss
- Gray AI field: false positive

STEP 4 — Comparison panel
Add a "Comparison" tab to the right pane in grading mode.
Shows a table: one row per annotation.
Columns: entity kind, human value, AI value, IoU, match type.
Rows sorted by match type (misses first, hits last).

STEP 5 — Per-page score summary
Show a score card at the top of the comparison panel:
- Annotations on this page: N
- Hits: N (N%)
- Misses: N (N%)
- False positives: N
Recomputes whenever annotations change.

Do not implement NDC (GT-5).
Do not implement export (GT-6).
Do not commit. Test with real annotation and AI field data.
```

---

### Sprint GT-5 — NDC Computation + Aggregate Scoring
**Scope:** Normalization delta, F1 score, per-entity-kind breakdown.

**Build prompt for Claude Code:**
```
Read CLAUDE.md fully before proceeding.
Read ARCHITECTURE.md fully before proceeding.
Read GRADING_TOOL_DESIGN.md fully before proceeding.
Read admin/adi-console.html fully before proceeding.

This is Sprint GT-5. The Provenance Doctrine is absolute.

Implement NDC computation and aggregate scoring.

STEP 1 — Levenshtein distance
Implement normalizedLevenshtein(a, b) — standard edit distance
normalized by max(a.length, b.length). Returns 0.0-1.0.

STEP 2 — NDC computation
Implement computeNDC(humanValue, aiValue) exactly as specified
in GRADING_TOOL_DESIGN.md.
Returns: verbatim_match, edit_distance, token_overlap,
length_delta, delta_class (exact/minor/moderate/major).

Apply NDC only to hit and partial_kind matches where both
human value and AI value are non-null.

STEP 3 — Per entity kind scoring
For each entity kind present in annotations:
  recall = hits for this kind / annotations for this kind
  precision = hits for this kind / AI fields for this kind
  f1 = 2 * (precision * recall) / (precision + recall)
  avg_edit_distance = mean NDC edit_distance for hits
  avg_token_overlap = mean NDC token_overlap for hits

STEP 4 — Document-level aggregate
  recall = total hits / total annotations
  precision = total hits / total AI fields
  f1 = harmonic mean
  scores_by_kind = per entity kind breakdown

STEP 5 — Score dashboard
Add a "Scores" tab to the right pane in grading mode.
Shows:
- Document F1, recall, precision
- Per entity kind table: kind, count, recall, precision, F1,
  avg edit distance, avg token overlap
- NDC distribution: count of exact/minor/moderate/major per kind
- Worst performers: entity kinds sorted by F1 ascending

STEP 6 — Prompt version display
Show current prompt version prominently in the grading toolbar.
"Grading against: pass2-v1"
This must match the prompt_ref in the audit records
being graded.

Do not implement export (GT-6).
Do not commit. Test with full annotation set on a real document.
```

---

### Sprint GT-6 — Export + Persistence
**Scope:** JSON export, DB write, checksum, grading session management.

**Build prompt for Claude Code:**
```
Read CLAUDE.md fully before proceeding.
Read ARCHITECTURE.md fully before proceeding.
Read GRADING_TOOL_DESIGN.md fully before proceeding.
Read admin/adi-console.html fully before proceeding.

This is Sprint GT-6. The Provenance Doctrine is absolute.
Export is immutable once written. No edits to exports.

STEP 1 — Export JSON assembly
Implement assembleGradingExport() that produces the full
JSON structure specified in GRADING_TOOL_DESIGN.md:
- Top-level: export_id, created_at, prompt_ref,
  reviewer_id, grading_session_id, schema_version,
  aggregate scores
- Per document: document_grade, all annotations,
  all AI fields, all match records with IoU and NDC
- SHA-256 checksum of the JSON string (SubtleCrypto API)

STEP 2 — Export to file
"Export JSON" button downloads the assembled export
as a .json file named:
  grade_{prompt_id}_{version}_{date}_{session_id_prefix}.json

STEP 3 — Export to DB
"Save to DB" button POSTs the export to:
  POST /v1/admin/grading/export
  Body: { grading_session_id, prompt_ref,
          export_json, sha256_checksum }
Worker writes to grading_exports table.
Returns export ID on success.

STEP 4 — Grading session management
Grading session list view: shows all sessions from
GET /v1/admin/grading/sessions
Columns: date, reviewer, prompt version, document count,
export count.
Clicking a session loads its exports for review.

STEP 5 — Export comparison view
When two exports exist for the same document at different
prompt versions, show a delta comparison:
- F1 delta: v2 F1 - v1 F1 (green if positive, red if negative)
- Per entity kind delta table
- Regression alerts: any kind where F1 dropped > 0.05

STEP 6 — Grading history in document view
When viewing a document in the ADI console (non-grading mode),
show a "Grading History" section in Session Detail tab:
- Number of grading sessions that included this document
- Latest F1 score
- Prompt version of latest grade
- Link to open grading comparison

Do not commit until full export round-trip verified:
annotate → score → export JSON → save to DB → retrieve.
```

---

## Prompt Version Increment Discipline

Every time a registered prompt's text changes, before the sprint
implementing the change:

1. Bump the prompt's `version` in both the source file and
   `PROMPT_ID_REGISTRY.md`. Example: `("pass2_extraction", "v2")`
   becomes `("pass2_extraction", "v3")`. `promptId` never changes.
2. Register the new `(prompt_id, version)` pair in the Worker
   `prompt_versions` table via POST /v1/admin/prompts/register
   with the full new prompt_text, an author identifier, and a
   changelog_note describing what changed and why.
3. Document the change in a `PROMPT_CHANGELOG.md` entry:

```
   ## (pass2_extraction, v3) — 2026-04-14
   Changed: Added CRITICAL verbatim value contract as first rule.
   Reason: Vitals extracting labels instead of values.
   Expected delta: vitalSign edit_distance should decrease.
```

4. Re-ingest the benchmark documents under the new version.
5. Run a grading export.
6. Compare the F1 delta against the previous version by joining
   `audit_fields.prompt_ref` to `prompt_versions`.
7. Accept the prompt change only if F1 improves or holds on every
   entity kind.

This discipline is the core of defensible prompt engineering.
Every change is addressable by `(prompt_id, version)`, stored in
the registry, documented in the changelog, and measured against
prior versions before being promoted.

Once registered, a `(prompt_id, version)` pair is append-only —
its `prompt_text` cannot change. Corrections require a new
version bump.

---

## Migration Path to Full Tier 3

When Tier 3 ships, the migration is:

1. `annotations` table moves from grading Neon branch to dedicated Tier 3 Neon instance
2. Add columns: `reviewer_qualification`, `training_batch_id`, `promoted_at`, `included_in_training`
3. `grading_exports` becomes the promotion gate artifact — exports that clear F1 thresholds get flagged for BioMistral training batch inclusion
4. ADI console grading UI gains reviewer login, qualification tracking, batch management
5. JSON export format gains `training_eligible` flag per annotation based on confidence and delta class

No annotation data is lost. No format changes to existing exports. The lightweight schema is the Tier 3 schema minus three columns and one table.

---

*Document version: 1.0*
*Author: Record Health Architecture*
*Status: Design — pre-implementation*
