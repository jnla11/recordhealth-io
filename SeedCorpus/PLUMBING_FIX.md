# PLUMBING_FIX — ADI Data Plumbing Inconsistencies

**Status:** Scoped backlog document v0.1
**Created:** 2026-04-22
**Location at rest:** `SeedCorpus/PLUMBING_FIX.md`
**Scope:** Architectural issues in how source regions, OCR blocks, and atom spans flow between iOS, Worker, and ADI console. Not a sprint plan; an inventory of known debt with enough detail to plan the fix when its turn comes.

---

## 1. Why this document exists

During Sprint 1.1 smoke testing (CT calcium scan, 2026-04-22), we discovered that the char offset columns added to `source_regions` were orphaned — no code path writes to them. Investigation revealed the columns were added to the wrong table; char offsets actually live on atom-level spans in `data_atoms.clinical_fields.source_region.spans[]` JSONB.

That misalignment is a symptom, not the root cause. The root cause is that "source regions" means two different things in this codebase, stored in two different places, with no formal relationship between them. The codebase has been living with this ambiguity since GT-1.6a when `source_regions` was first introduced, and CLINICAL_SHAPE_DESIGN §6 foresaw the many-to-many atom↔region problem but the junction table was never built.

This document captures the current state honestly so a future sprint can fix it with full context.

## 2. The two things called "source regions"

### 2.1 Type A — OCR blocks

**Where they live:** `source_regions` table. One row per Vision OCR block.

**Populated by:** iOS `DocumentTransitService` → `POST /v1/admin/documents/upload` handler. The iOS side runs Apple Vision on the PDF, producing `VNRecognizedTextObservation` objects. Each observation becomes an `OCRBlock` with `{text, boundingBox, confidence}`. The transit payload ships an `ocr_result.pages[].blocks[]` array; the Worker INSERTs one row per block.

**Typical volume:** ~1,000–3,000 rows per typical clinical document. (Measured: CT calcium scan report = 1,071 rows.)

**Data shape:** tiny. `avg_text_len ≈ 5.6 chars` on the measured document. One word or short phrase per row.

**Purpose today:** infrastructure. Spatial bookkeeping for the PDF overlay renderer. Not consumed by the ADI console in any meaningful way.

**Data dropped in transit:**
- `SourceSpan.wordRects: [WordRect]?` — per-word bounding boxes within a span, discarded at serialization
- `SourceSpan.valueBounds: NormalizedRect?` — tight value bbox, discarded at serialization
- Block-level character offsets into `OCRResult.fullText` — never computed, thus never sent

### 2.2 Type B — Atom spans

**Where they live:** `data_atoms.clinical_fields.source_region.spans[]` JSONB column on `data_atoms`.

**Populated by:** iOS `SourceTextCoordinateMatcher`, computed during `AIExtractionService.parseResponse()`. Each extracted atom gets its `source_region` attached if the matcher can locate its text in the OCR blocks. Transmitted in the `extractions[]` array of the upload payload.

**Typical volume:** tens per document (7 on the measured document, out of 20 total atoms).

**Data shape:** structured. Per span: `{page, x, y, width, height, char_offset_start, char_offset_end}`. Multiple spans per atom when text spans multiple lines or regions.

**Purpose today:** drives PDF overlay in the ADI console. When the reviewer clicks an atom, the console reads `atom.clinical_fields.source_region.spans[]` to draw the bbox. Also carries char offsets for future training-media export (TRAINING_MEDIA_DESIGN §6 + §10).

**Char offset population rate:** 100% of atoms that have source regions (7/7 on measured doc). Nil when the matcher fails to locate the atom text in OCR (13/20 on measured doc — these are pipeline-fragmented or AI-hallucinated atoms where no matching text exists).

### 2.3 The relationship between Type A and Type B

Today: **none in the database.** An atom-span covering "Sean Hayes, M.D." is spatially equivalent to three specific OCR blocks ("Sean", "Hayes,", "M.D.") but there is no stored link. If you want to ask "which OCR blocks are inside this atom's span?", the answer comes from geometric comparison in application code, not a JOIN.

CLINICAL_SHAPE_DESIGN §6 anticipated this:
- Planned: a separate `atom_regions` junction table with M:N cardinality
- Not built: the junction table, the INSERT path into it, the read paths that would benefit from it

## 3. What Sprint 1.1 exposed

Sprint 1.1 added `char_offset_start` and `char_offset_end` columns to `source_regions` (Type A) under the assumption that char offsets would be populated alongside OCR block data. The assumption was wrong:

1. iOS never computes per-block char offsets into `OCRResult.fullText` — offset computation happens at atom-span resolution in `SourceTextCoordinateMatcher`, not at OCR-block resolution in `OCRService`.
2. Even if iOS did compute per-block offsets, there was no matching plumbing on the transit side — the iOS OCR payload has no field for char offsets per block.
3. The atom-level char offsets that iOS *does* compute land in the Type B JSONB location, not the Type A table.

Net: columns added to Type A were orphans. Dropped in Sprint 1.1 cleanup (2026-04-22).

Atom-level char offsets continue to work correctly via Type B JSONB, which is where training-media export will read from.

## 4. Other dropped-data / dead-end paths

### 4.1 `wordRects` and `valueBounds` discarded at transit

`SourceSpan` on iOS carries two additional geometric fields populated by `SourceTextCoordinateMatcher`:

- **`wordRects: [WordRect]?`** — per-word bounding boxes. When a span covers "Sean Hayes, M.D.", `wordRects` has 3 entries, one per word. Provenance-rich data useful for word-level bbox editing and for training token-classification models.
- **`valueBounds: NormalizedRect?`** — tight bbox around just the value portion of a span, excluding surrounding label text. When the span covers "Patient Name: Nolte, Jason Alan", `valueBounds` tightly wraps just "Nolte, Jason Alan". Useful for producing clean training media without label noise.

Both are **computed then discarded** when `DocumentTransitService` serializes the span into the transit payload. The payload keeps only `{page, x, y, width, height, char_offset_start, char_offset_end}`.

**Fix when addressed:** extend the transit payload's span dict to include `word_rects` and `value_bounds`, extend the Worker INSERT / JSONB write to persist them. Would require schema decision on Worker side — either new columns on an `atom_spans` table (if created), or extending the JSONB shape.

### 4.2 `source_regions` rows sent to ADI console and ignored

`GET /v1/admin/documents/:id` returns a `regions` array populated from `SELECT * FROM source_regions`. The ADI console reads the document response but **never accesses `regions`** — atom bboxes come from atom JSONB, PHI bboxes from the PHI array.

On a measured document: 1,071 region rows * ~100 bytes/row = ~107 KB of data sent over the wire per document fetch, immediately discarded. Not the biggest bandwidth concern at current volumes, but real.

**Fix when addressed:** either start consuming the regions in the console for some purpose (e.g., overlay rendering alternative, word-level bbox edit mode), or stop sending them in this endpoint's response and remove from the SELECT. Either is fine; the current "send and ignore" is the wrong outcome.

### 4.3 The `source_regions.verbatim_text` column

Each `source_regions` row stores the text of its OCR block (avg ~5.6 chars — one word). This is redundant with the text available via atom spans (the atom carries its full verbatim text, of which individual OCR blocks are substrings). Stored per-block to support future word-level querying that isn't happening.

**Fix when addressed:** possibly redundant with an eventual `atom_spans` table + `OCRResult.fullText` storage. Revisit as part of the broader refactor.

## 5. The proper architecture (target state)

Rough sketch of where this is heading, not a commitment:

### 5.1 Separate concerns cleanly

Three distinct data concepts deserve three distinct storage locations:

- **OCR blocks** — raw Vision output. Per-page, per-block text + bbox. Read by: overlay renderer (if used), training media export (for token-level annotation). Mostly-write-once, rarely-read.
- **Atom spans** — extraction output. Per-atom, multi-span, with `word_rects` + `value_bounds` + char offsets. Read by: ADI console drill-down, training media export. Referenced by atom_id.
- **Reviewer bbox edits** — drill-down corrections. Per-submission, per-atom, history of edit ops. Read by: training media export.

### 5.2 Tables that would exist

- `source_regions` (exists) → potentially renamed to `ocr_blocks` to reflect actual content
- `atom_spans` (not built) — the junction table CLINICAL_SHAPE_DESIGN §6 anticipated. Rows: `{id, atom_id, page, x, y, width, height, word_rects_jsonb, value_bounds_jsonb, char_offset_start, char_offset_end, sequence_within_atom}`. M:N to atoms.
- `grading_submissions.bbox_edit_history` (exists) — already the right shape

### 5.3 What atom-level source_region JSONB becomes

Deprecated. `data_atoms.clinical_fields.source_region.spans[]` becomes a denormalized view of the `atom_spans` table for backward compatibility during migration, eventually removed.

### 5.4 Transit payload changes

iOS would send both block-level data and atom-span data in their final shapes:

```json
{
  "ocr_result": {
    "pages": [{
      "blocks": [
        {
          "text": "Sean",
          "bounding_box": { "x": ..., "y": ..., "width": ..., "height": ... },
          "char_offset_start": 1612,
          "char_offset_end": 1616,
          "confidence": 0.98
        }
      ]
    }]
  },
  "extractions": [{
    "entity_kind": "provider",
    "verbatim_value": "Sean Hayes, M.D.",
    "spans": [{
      "page": 1,
      "bounding_box": { ... },
      "word_rects": [
        { "text": "Sean",   "bbox": {...} },
        { "text": "Hayes,", "bbox": {...} },
        { "text": "M.D.",   "bbox": {...} }
      ],
      "value_bounds": { "x": ..., "y": ..., "width": ..., "height": ... },
      "char_offset_start": 1612,
      "char_offset_end": 1628
    }]
  }]
}
```

Worker then:
- INSERTs blocks into `ocr_blocks` (previously `source_regions`)
- INSERTs spans into `atom_spans` with foreign key to atom_id

## 6. Impact assessment

### 6.1 What this fixes

- Single source of truth for atom span data (one table, queryable, joinable)
- Per-block char offsets available for token-classification training exports
- `word_rects` and `value_bounds` preserved rather than discarded
- Clean separation between "raw OCR" and "extraction output"

### 6.2 What this does NOT fix

- The broken atoms on Jason's Dashboard (those are an AI extraction quality issue, separate workstream — addressed by ADI reviewer flow + prompt engineering + fine-tune per PHASE_ROADMAP Phase 5)
- `patientName: "TYPE Accession No"` (same — AI extraction quality, not plumbing)
- Hallucinated fragments like "Very low CVD risk." being persisted as patient conditions (same)

### 6.3 Required changes summary

**iOS:**
- `DocumentTransitService` serializer: extend span dict to include `word_rects`, `value_bounds`
- `OCRService`: compute per-block char offsets into `fullText` during page-text assembly
- `OCRBlock` model: add char offset fields
- Extraction pipeline: ensure atoms carry spans ready to hydrate new `atom_spans` table

**Worker:**
- New migration: create `atom_spans` table with FKs to `data_atoms`
- Optional migration: rename `source_regions` → `ocr_blocks` (with alias view for backward compat during migration)
- Optional migration: add `char_offset_start` / `char_offset_end` to `ocr_blocks`
- `POST /v1/admin/documents/upload`: INSERT into `atom_spans` in addition to current paths
- `GET /v1/admin/documents/:id`: decide whether to return `regions` array (ocr_blocks) at all, or only atom spans joined by atom_id
- `GET /v1/admin/atoms/:id`: JOIN to `atom_spans` for rendering

**Console:**
- `updateOverlay()`: read from atom_spans (via document fetch joined shape) instead of `clinical_fields.source_region.spans[]` JSONB
- Test: re-render every existing bbox the console currently draws to confirm no regression

**Training media export (Phase 6):**
- Schema consumers: switch from JSONB reads to joined table reads
- CoNLL export: now has per-OCR-block char offsets to produce full document-level token annotations

## 7. Scope estimate

Rough sketch. Not committed.

Three to five mini-sprints:

- **PF.1 — iOS payload expansion:** transit serializer + OCR service updates. Ship iOS with new payload shape while Worker is still accepting old shape.
- **PF.2 — Worker schema + INSERT paths:** new table, migration, dual-write to JSONB and new table for one release cycle.
- **PF.3 — Worker read paths:** GET endpoints start returning joined shape.
- **PF.4 — Console migration:** `updateOverlay` and any other atom-span consumer reads new shape.
- **PF.5 — JSONB deprecation + cleanup:** remove `clinical_fields.source_region` writes, drop any orphan columns, decide `source_regions` fate.

## 8. When to do this

Not urgent. Not blocking Phase 1. Indicators that it's time:

- **Phase 6 training media export starts getting complicated** because char offsets live in two places and atoms need joining to their blocks
- **Phase 1.4 bbox editing** shows friction because `wordRects` could have enabled word-level editing but was discarded
- **Dashboard data bloat** (1,071 region rows × N documents × repeated fetches) becomes measurable
- **A new developer** onboarding gets confused by the source_regions vs clinical_fields split — the "multiple sessions debugging this" signal

Rough estimate of timing: probably between Phase 2 and Phase 3 of the main ADI roadmap, or when Phase 6 export work forces it.

## 9. What to do in the meantime

Not nothing. These low-cost actions can happen any time without the full refactor:

- **Document the dual-location pattern** in CLAUDE.md so new sessions don't misdiagnose it — done implicitly via this file
- **Add a comment in `DocumentTransitService.swift`** near the span serializer explaining what's being dropped and why — small, pragmatic
- **Avoid adding new columns to `source_regions`** unless specifically for OCR-block purposes — rule of thumb going forward

## 10. Open questions for when the fix is scoped

1. Rename `source_regions` → `ocr_blocks`, or leave the name? Rename is clearer but disruptive.
2. Keep `source_regions.verbatim_text` or treat as redundant?
3. Once `atom_spans` exists, do we still need `clinical_fields.source_region` at all, or is it purely denormalized cache?
4. Should `char_offset_*` be on `ocr_blocks` AND on `atom_spans`, or only one?
5. Who owns the decision to break backward-compat on the GET /documents/:id shape — the console team (Jason)? Downstream consumers (none currently)?
6. Should this refactor coincide with the M:N atom↔region work CLINICAL_SHAPE_DESIGN §6 anticipated, or stay separate?

---

**End of v0.1. Document intentionally shape-not-spec; promote to a detail design when scope is decided.**
