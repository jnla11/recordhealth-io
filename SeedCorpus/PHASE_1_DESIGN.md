# Phase 1 Design — ADI Atom Detail Drill-Down

**Status:** Draft v0.1 — Phase 1 design, ready for sprint breakdown
**Created:** 2026-04-22
**Location at rest:** `SeedCorpus/PHASE_1_DESIGN.md`
**Supersedes:** Phase 1 scope bullets in `TRAINING_MEDIA_DESIGN.md` §13
**Prerequisites:** `TRAINING_MEDIA_DESIGN.md` v0.2 (authoritative for training media schema), Phase 1 pre-implementation audit (2026-04-21), Phase 1 docs pre-read (2026-04-22)

---

## 1. Goal

Convert the ADI console's existing inline atom-detail panel into a panel-replacement drill-down that gives the reviewer a complete, coherent correction experience: kind, verbatim value, bbox, rationale — all in one place, all captured into L2 workspace state, all flowing to L3 `grading_submissions` on lock-in.

Phase 1 ships the throughput loop that lets Jason start producing real training media at volume. Every feature decision below traces back to "does this improve quality or quantity of training media per reviewer-hour."

## 2. What's in and out of scope

### In scope

- Panel-replacement drill-down inside `#tab-atoms` (list view XOR detail view)
- Back button + Esc handling coordinated with existing keyboard globals
- "Next →" inter-atom navigation without returning to list
- Full atom metadata display (kind, verbatim, ID, confidence, status, regions count, canonical_codes read-only)
- Grouped kind dropdown with rules-based ranking using document-level signals
- Corrected verbatim value (plain text)
- Confusion class select, narrowed by selected kind
- Optional rationale input
- 3-state bbox edit: cancel existing / modify existing (drag handles) / add new (draw)
- Per-op `bbox_edit_history` capture (before/after coords)
- Zoom-aware horizontal pan on atom selection
- Locked-document read-only mode honored throughout
- Scanned-PDF graceful empty state (no crash when `spans` is empty)
- 4 schema additions landing in sprint 1.1

### Out of scope (deferred)

- AI ontology lookup integration → Phase 2
- "i" button canonical_codes reasoning UI → Phase 2 (layout slot reserved)
- AI-assisted kind suggestion → Phase 2
- Per-region list with per-region controls → later sprint (most likely alongside Phase 5)
- Patient profile / cold-start → Phase 4
- Negative-space annotation mode → Phase 5
- Training media export endpoint → Phase 6
- AUTH-2 migration → independent sprint
- Reviewer identity wiring (stays hardcoded to 'jason')

## 3. Sacred rules this design respects

From the docs pre-read, these constraints are load-bearing and must not be violated:

- **Atoms remain immutable pipeline output.** No PATCH to `data_atoms` from Phase 1. All corrections flow through `verdicts[atom.id]` → `grading_submissions` on lock-in. This is the GT-2d architectural correction and it's non-negotiable.
- **Verbatim is sacred in display.** Never reformat or normalize displayed atom values. Detokenization for display is allowed (existing `detokenize()` helper); reformatting is not.
- **Provenance Doctrine.** All bbox data comes from stored `source_regions` / `clinical_fields.source_region.spans`. Never reconstruct from PDF text search, never derive from OCR at display time.
- **Three-layer grading model.** L1 (`data_atoms`) read-only, L2 (sessionStorage) editable, L3 (`grading_submissions`) immutable append-only. Phase 1 writes to L2; L3 is only touched on lock-in.
- **Coordinates stay in Vision coordinate system.** Bottom-left origin, Y inverted from canvas. Existing transform `y_canvas = (1 - y_vision - height) * canvasHeight` stays canonical.
- **Append-only everywhere.** `bbox_edit_history` entries accumulate, never overwrite. Rationale edits produce new workspace snapshots, not mutations.
- **Locked state must dim mutation affordances.** Verdict buttons, edit handles, draw tool, correction inputs — all inherit `.locked` class behavior.
- **Single-selection invariant.** Selecting an atom clears PHI selection and vice versa. Drill-down preserves this.

## 4. Correction form philosophy

The reviewer's job in the drill-down is not to rebuild the atom. Each subfield decomposition the reviewer performs is an interpretation layer that compounds error risk and turns the reviewer into a competing extraction engine, which destroys the L1↔L3 delta we're trying to measure.

The reviewer's five decisions:

1. Is this a real atom? → confirm / reject / (negative-space — Phase 5)
2. Is the kind right? → confirm / correct (single-select kind, no subfield decomposition)
3. Is the span right? → confirm / modify the bbox (Phase 1 — this design)
4. Are the AI-suggested codes right? → confirm / amend from ranked list (Phase 2, slot reserved here)
5. Did I miss any atoms? → discover (existing discoveries flow)

Everything downstream of these five — structured FHIR decomposition, cross-document reasoning, temporal ordering, ontology coding — is BioMistral's or Bedrock's job. The reviewer confirms the ground-truth unit; downstream systems decompose it.

This framing is what keeps reviewer-hours high-leverage and training signal clean.

## 5. UI architecture

### 5.1 Container model

The right panel continues to hold three tabs (Atoms / PHI / Info). When an atom is selected in the Atoms tab, the tab's contents swap — list view hides, detail view shows. PHI and Info tabs are untouched and remain clickable; clicking either while in drill-down pops back to Atoms-list-view before switching tabs (the drill-down is local to Atoms).

```
┌─────────────────────────┐          ┌─────────────────────────┐
│ [Atoms] [PHI] [Info]    │          │ [Atoms] [PHI] [Info]    │
├─────────────────────────┤   click  ├─────────────────────────┤
│ ▼ medication (3)        │  atom    │ ← Back      Atom 3/47 → │
│   ▸ Amoxicillin 500mg   │   →      │                         │
│   ▸ Tylenol             │          │ Kind: medication ▼      │
│   ▸ Ibuprofen           │          │ Verbatim: Amoxicilln... │
│ ▼ condition (2)         │          │ Regions: 2 [edit bbox]  │
│   ▸ otitis media        │          │ Codes: RxNorm 723       │
│   ...                   │          │ [Confirm][Correct][Rej] │
│ (+ existing inline      │          │  correction form...     │
│  detail — to be         │          │                         │
│  replaced)              │          │  rationale: _________   │
└─────────────────────────┘          └─────────────────────────┘
    List view                              Detail view
```

### 5.2 State transitions

Three states inside `#tab-atoms`:

- **list** — default on doc open, atom list rendered, no atom selected
- **detail** — an atom is selected, list hidden, detail view shown
- **locked-detail** — document is locked; detail shown in read-only mode

Transitions:
- `list → detail`: user clicks an atom card, or presses arrow keys if we add list-keyboard-nav (Phase 1.5 polish)
- `detail → list`: back button, Esc (when no popovers are open), or user clicks PHI/Info tabs (which also clears selection)
- `detail → detail`: "Next →" / "← Prev" buttons advance to next/prev atom in the filtered-sorted list order

### 5.3 Detail view layout

Top to bottom:

1. **Header strip** — `[← Back]  Atom {stableIndex} of {total}  [← Prev][Next →]`
2. **Atom identity block** — detokenized verbatim value (large, verbatim-sacred), entity kind badge, truncated UUID, L1 confidence
3. **Source regions block** — count + compact preview ("2 source regions on pages 1, 3") + bbox edit controls (see §5.4)
4. **Canonical codes block** — read-only list of existing codes from `atom.canonical_codes`. Each code shows `{system} {code} — {display}`. Phase 2 adds `i` button + verdict UI here.
5. **Verdict row** — three buttons: Confirm / Correct / Reject. Color-coded per existing CSS tokens.
6. **Correction form** (visible when verdict = Correct) — see §5.5
7. **Reject form** (visible when verdict = Reject) — reject_reason select + optional rationale (existing pattern, lifted from current inline detail)
8. **Rationale input** — one-line optional text, visible on all verdicts when the reviewer wants to leave a note

Locked mode: header strip shows `(locked)` indicator, all mutation controls disabled via `.locked` class, but nav (Back / Next / Prev) remains enabled so the reviewer can inspect all atoms.

### 5.4 Bbox edit controls

The bbox edit is the most UI-intensive piece of Phase 1. Three operations:

**Modify existing region (drag):**
- Each region of the selected atom renders with 8 drag handles (4 corners, 4 edge midpoints) overlaid on the PDF via SVG
- Handles are visible only when drill-down is open and atom is selected
- Drag to resize; underlying region rect updates live; committed on mouseup
- Before-coords captured at dragstart; after-coords at mouseup → `bbox_edit_history` entry

**Cancel existing region:**
- Small X button (red, ~14px) at top-right corner of each region's overlay
- Click → confirms with a subtle inline prompt ("Remove this region?") → region removed from reviewer workspace copy
- History entry: `{op: 'cancel', region_id, before: {...coords}, after: null}`

**Add new region (draw):**
- When drill-down is open and atom is selected, activating Draw tool (existing `s/d` toggle → `d`) enters add-region mode for *this atom specifically*
- Existing drag-to-draw behavior (app.js:1034-1100) is reused but routed to append to the selected atom's region list rather than creating a discovery
- Commit on mouseup → new region added to reviewer workspace copy
- History entry: `{op: 'add', region_id: 'new_<uuid>', before: null, after: {...coords}}`

**Storage:** bbox edits accumulate in L2 workspace alongside verdicts. They don't mutate `data_atoms` or `source_regions`. On lock-in, the full `bbox_edit_history` goes into the grading_submissions payload.

**Visual distinction:** to avoid confusion, bbox edits *only* appear for the currently-selected atom in drill-down. Other atoms' regions continue to render statically on the overlay.

### 5.5 Correction form — kind ranking and confusion class

When verdict = Correct, the form shows:

- **Kind dropdown** — grouped (Clinical / Orders / Observations / Administrative / PHI), with rules-based ranking inside the first group
- **Corrected verbatim value** — plain text input, pre-filled with current detokenized value
- **Confusion class** — existing grouped dropdown (app.js:184-199), narrowed to show only classes compatible with the selected corrected kind
- **Rationale** — optional, one-line

**Rules-based kind ranking** uses these signals (all available from current payload, no new fetches):

- `document.record_category` — visit_note prioritizes condition/symptom/finding; lab_report prioritizes labValue/procedure
- Sibling atoms on the same page — kind co-location: if 5 atoms on page 2 are labValue, a sixth is more likely labValue than medication
- Existing `atom.entity_kind` is *displayed* as the L1 suggestion, but *not used to rank* (per your framing — the correction is challenging L1, so L1 can't inform ranking)

Ranking rules live in a small static config: `KIND_RANK_RULES` object keyed by `record_category`, values are ordered arrays of kind names. Plus one helper `rankKindsForAtom(atom, doc, siblingAtoms)` that produces the final ordered list. All vanilla JS, no new dependencies.

The full 21-kind list remains selectable — ranking just reorders, doesn't exclude.

## 6. Data flow

### 6.1 L2 workspace shape

Existing verdicts map (app.js:21) holds:

```js
verdicts[atom.id] = {
  verdict: 'confirmed' | 'corrected' | 'rejected',
  correctedValue: string,
  confusionClass: string,
  rationale: string,
  corrected_kind: string,
  reject_reason: string
}
```

Phase 1 extends this:

```js
verdicts[atom.id] = {
  verdict: ...,
  correctedValue: ...,
  confusionClass: ...,
  rationale: ...,              // now surfaced on all verdict states, not just corrected
  corrected_kind: ...,
  reject_reason: ...,
  // NEW:
  bbox_edits: [                // ordered list of edit operations
    { op: 'modify' | 'cancel' | 'add',
      region_id: string | null,
      before: { page, x, y, width, height } | null,
      after: { page, x, y, width, height } | null,
      edited_at: ISO8601
    }
  ],
  regions_workspace: [          // reviewer's current view of what the regions should be
    { id: string, page, x, y, width, height, origin: 'l1' | 'edited' | 'new' }
  ]
}
```

`regions_workspace` is computed from L1 regions + applied `bbox_edits`. Redundant with `bbox_edits` + original regions, but caching it in workspace avoids recomputing on every render.

`saveWorkspace()` at app.js:470 already handles sessionStorage persistence keyed by doc_id. No changes needed beyond widening the serialized shape.

### 6.2 Lock-in payload

Existing `buildVerdictsPayload()` at app.js:2167 translates `verdicts` into the grading-submit body. Phase 1 extends this to include:

- `bbox_edit_history` array per atom (from `verdicts[atom.id].bbox_edits`)
- `rationale` on all verdicts, not just corrected (already technically supported, just make sure the payload includes it unconditionally)

The grading_submissions table row accumulates:

- `verdicts` — existing column
- `bbox_edit_history` — **new column, added in sprint 1.1**
- (no other changes; rationale lives inside existing `verdicts` entries)

### 6.3 Regions fetch semantics

The GET /v1/admin/documents/:id response already returns a `regions` array from `source_regions`. The audit flagged this as "orphaned in the UI" — no current code reads it. Phase 1 continues to ignore `regions`; atom bboxes come from `atom.clinical_fields.source_region.spans` as today. The `regions` array and its semantics are a separate question (audit follow-up) and don't block Phase 1.

## 7. Schema additions (sprint 1.1)

Four columns to add. SQL runs against `RecordHealth-ADI / staging` via Neon browser editor (Jason executes; Claude never runs production SQL).

```sql
-- 1. bbox_edit_history on grading_submissions
ALTER TABLE grading_submissions
  ADD COLUMN bbox_edit_history JSONB NOT NULL DEFAULT '{}'::jsonb;
-- Keyed by atom_id, value is array of edit ops.
-- Example: { "a_123": [ { "op": "modify", "before": {...}, "after": {...} } ] }

-- 2. char_offset_start / char_offset_end on source_regions
ALTER TABLE source_regions
  ADD COLUMN char_offset_start INTEGER,
  ADD COLUMN char_offset_end INTEGER;
-- Nullable — existing rows have no offsets until the iOS side populates them.
-- Added now for training media export (Phase 6 prerequisite).

-- 3. sequence_index on data_atoms
ALTER TABLE data_atoms
  ADD COLUMN sequence_index INTEGER;
-- Nullable — existing rows have no index until the pipeline populates them.
-- Added now for sequence accuracy metric in PPS (§TRAINING_MEDIA_DESIGN §9).

-- 4. rationale support on grading_submissions.verdicts entries
-- NO SCHEMA CHANGE. Existing verdicts JSONB column already supports
-- arbitrary fields per atom entry. Just ensure client always writes
-- the field (null-safe).
```

Three actual ALTERs. The fourth is a code-side contract. Sprint 1.1's SQL is short; the bulk of the sprint is Worker-side plumbing to accept and return the new payload fields.

## 8. Sub-sprint breakdown

Six mini-sprints. Each gets its own pre-audit, implementation prompt, and post-audit verification. Audit-first discipline per convention.

### Sprint 1.1 — Schema additions + Worker plumbing

**Scope:** three DDL statements, Worker-side acceptance of new payload fields, response-shape updates.

**Pre-audit:** confirm current schema of the three tables; confirm no collisions with existing columns; dry-run the ALTERs on a staging snapshot or equivalent.

**Implementation:** Jason runs the ALTERs via Neon browser editor. Claude Code updates `src/index.js` to accept `bbox_edit_history` in the grading-submit payload and echo it back on fetch. Updates the GET /v1/admin/documents/:id handler to include the new columns (nullable fields; existing rows are unaffected).

**Post-audit:** three verification SQLs — one per ALTER — run against staging, confirm column presence and type. Smoke test: submit a grading-submission with a `bbox_edit_history` field populated, fetch it back, confirm round-trip.

**Commits:** one Worker commit. Parent submodule bump follows.

**Blocks:** all subsequent sprints depend on 1.1 landing.

### Sprint 1.2 — Drill-down shell

**Scope:** panel-replacement mechanism inside `#tab-atoms`, back button, Esc coordination, Next/Prev inter-atom navigation, existing `renderAtomDetail()` content lifted into new container with minimal changes.

**Pre-audit:** confirm current tab-switching implementation has no side effects that would collide with the list↔detail swap; identify the exact integration point for Next/Prev (which list — filtered? sorted? stable-indexed?).

**Implementation:** add a new `#tab-atoms-detail` container adjacent to `#atom-list` in index.html. Add `viewMode` state variable with values `list | detail`. Add `enterDetailView(atomIdx)` and `exitDetailView()` functions. Move existing `renderAtomDetail()` rendering target to the new container. Add header strip with Back button, "Atom N of M" indicator, Prev/Next buttons. Wire Esc to `exitDetailView()` when in detail mode. Update `selectAtom()` at app.js:1693 to call `enterDetailView()` in addition to existing behavior.

**Post-audit:** manual test script — open a document, click an atom, verify list hides and detail shows; click Back, verify list returns; click Next, verify advancement; press Esc, verify exit; click PHI tab mid-detail, verify graceful return-then-switch.

**Commits:** one console commit.

**No schema changes; no API changes.**

### Sprint 1.3 — Correction form upgrade

**Scope:** grouped kind dropdown, rules-based ranking via `KIND_RANK_RULES` and `rankKindsForAtom()`, rationale surfaced on all verdict states (not just Correct), confusion-class narrowing based on selected kind.

**Pre-audit:** confirm current `ENTITY_KINDS` and `CONFUSION_CLASSES` structures and their consumers; identify the correct place to insert ranking logic without breaking existing filter dropdowns (which share `ENTITY_KINDS`).

**Implementation:** add `KIND_GROUPS` (Clinical / Orders / Observations / Administrative / PHI) as a new const. Add `KIND_RANK_RULES` keyed by `record_category`. Add `rankKindsForAtom(atom, doc, siblingAtoms)` helper. Rewrite the corrected-kind `<select>` builder to render `<optgroup>` elements with ranked items. Narrow confusion class on kind change. Update rationale field to always render. Ensure the verdicts map serialization still round-trips.

**Post-audit:** manual test — correct a visit_note atom from condition → finding, verify ranking favors condition/symptom/finding over labValue/medication. Correct a lab_report atom, verify labValue/vitalSign prominent. Confirm rationale saves with confirmed and rejected verdicts, not just corrected.

**Commits:** one console commit.

### Sprint 1.4 — Interactive PDF overlay (bbox edit)

**Biggest sprint.** Most UI surface area.

**Scope:** 8-handle drag-resize on selected atom's regions, cancel-region X control, add-region routing via existing Draw tool, `bbox_edits` and `regions_workspace` in verdicts map, edit ops flowing to `buildVerdictsPayload()`.

**Pre-audit:** confirm current overlay-rendering code (updateOverlay at app.js:625-806) can be extended without a rewrite; confirm existing Draw tool code (app.js:1034-1100) can be routed to atom-region-add mode; confirm no keyboard shortcut collisions.

**Implementation:** extend `updateOverlay()` with an `interactiveMode` flag that, when true for the selected atom, renders handles and X controls. Add drag handlers for handles (4 corners + 4 edges). Add click handler for X controls. Re-route Draw tool behavior: when `viewMode === 'detail'` and tool is Draw, drawn regions append to the selected atom's workspace regions (not to discoveries). Compute `regions_workspace` from L1 regions + applied edits on every verdicts write. Surface a visual indicator when an atom has pending bbox edits (e.g., asterisk or color change on the atom identity block in the detail view header).

**Post-audit:** extensive manual test — drag-resize a region, verify history captures before/after; cancel a region, verify it disappears from overlay + history logged; draw a new region while in detail view, verify it attaches to the atom not to discoveries; exit detail view and re-enter, verify edits persist via workspace; lock-in submit, verify payload includes `bbox_edit_history`.

**Commits:** one console commit.

### Sprint 1.5 — Zoom-aware pan + polish

**Scope:** extend `scrollToAtomSpan()` with horizontal pan behavior (only when `pdfContainer.scrollWidth > pdfContainer.clientWidth`), polish any rough edges from 1.1–1.4, ensure scanned-PDF graceful empty state (no crash on `spans === []`).

**Pre-audit:** confirm current `scrollToAtomSpan()` vertical logic is clean; identify scanned-PDF test case (will need one in grading submissions history or a fresh upload).

**Implementation:** add horizontal scroll computation in `scrollToAtomSpan()`; only act when `pdfContainer.scrollWidth > pdfContainer.clientWidth + 1` (small margin for rounding). Add empty-state rendering in the drill-down regions block when `spans.length === 0` ("No source regions captured for this atom. (Scanned PDF support pending — GT-INGEST-4.)"). Check other null/empty paths.

**Post-audit:** test with a zoomed-in PDF at zoom 3.0 — verify horizontal pan fires. Test at fit-width — verify it doesn't. Test on a scanned-PDF atom (or mock one) — verify empty state renders cleanly.

**Commits:** one console commit.

### Sprint 1.6 — End-to-end smoke test

**Scope:** no new code. Pure verification.

**Pre-audit:** confirm all five prior sprints landed, confirm schema migrations applied to staging, confirm latest Worker and console deployed.

**Test plan:**
1. Upload a fresh document via iOS (or use an existing pending_review doc)
2. Open in ADI console
3. Grade through 5–10 atoms with a mix of verdicts (confirm, correct with kind change, reject, correct with bbox modify, correct with bbox add, correct with bbox cancel)
4. Add at least one rationale
5. Lock-in submit
6. Query `grading_submissions` in Neon — verify `bbox_edit_history` shape matches payload
7. Verify existing F1 computation still works (summary JSON present, values plausible)
8. Fetch the doc back via GET /v1/admin/documents/:id — confirm no regressions

**Output:** A verification report documenting what passed, what needs fixing. Any failures block Phase 1 completion; fixes land as follow-up commits, then smoke test re-runs.

**Commits:** documentation of verification; no code.

## 9. Risks

1. **Sprint 1.4 could sprawl.** Interactive SVG editing is the single biggest UI piece in this design. If mid-sprint it's getting larger than planned, the fallback is to ship only drag-modify in 1.4 and defer cancel+add to a 1.4b sprint. Not ideal, not tragic.

2. **The `regions` orphan in GET response.** The audit flagged that the server returns a `regions` array that the UI ignores. Phase 1 continues to ignore it. But the server-side join that populates it still runs on every fetch, wasting bandwidth. Not a Phase 1 problem but worth a follow-up: either start using it, or stop sending it.

3. **Scanned PDFs (GT-INGEST-4).** Jason has documents in the pipeline where `spans === []`. The drill-down needs to handle this without crashing, which is cheap. But bbox edit on a scanned-PDF atom is meaningless. For Phase 1, the add-region action still works (reviewer can add fresh regions to a scanned PDF atom), but modify/cancel are disabled because there's nothing to modify or cancel.

4. **Keyboard shortcut conflicts.** Current globals include `s`/`d` for tool switching and arrows for page navigation. `n` for Next and `p` for Prev in the drill-down could collide with user expectations. Alternative: only Right-arrow for Next, Left-arrow for Prev *when in detail view* (gated by `viewMode`). Page navigation shifts to Shift+Arrow in detail mode. Needs a small disambiguation decision in sprint 1.2.

5. **"locked" documents entering drill-down.** If Jason opens a reviewed (L3-locked) document for inspection, the drill-down must render read-only. Existing `.locked` class handles most of this, but bbox handles and Draw tool routing in 1.4 need their own locked-gate. Easy, just a reminder not to forget.

6. **Three-layer invariant under bbox edit.** The `regions_workspace` derived view is a convenience but must never be confused for L1 data. Any code that reads atom regions for *display* should prefer workspace if drill-down is active, L1 otherwise. Code that reads regions for *training media export* always reads L1 + edit history separately (so the delta is recoverable). This split is important and worth a comment in the 1.4 implementation.

## 10. Training media alignment

Phase 1 produces signal for all three improvement tracks from `TRAINING_MEDIA_DESIGN.md`:

- **Track A (iOS regex tuning):** kind corrections + bbox edits both surface regex false positives and missed regions. Especially valuable: regex-produced atoms the reviewer rejects entirely.
- **Track B (BioMistral prompt eng):** correction rationales + kind-group confusion data point at prompt refinements. The confusion matrix from "L1 said medication, L3 said finding" is directly consumable as prompt guidance.
- **Track C (BioMistral fine-tune):** per-atom L1→L3 deltas with bbox-before-bbox-after pairs are the token-classification training signal, once char offsets catch up in a later sprint.

Phase 1 doesn't build the export endpoint (that's Phase 6), but every piece of data captured here is schema-compatible with v0.2's §6 shape. The only gap after Phase 1 is negative-space annotations (Phase 5) and patient context (Phase 4).

## 11. Open questions

1. **Next/Prev ordering semantics.** The atom list today is sorted by kind group (filtered list) with stable-index by reading-order within a group. Should Next/Prev follow the *current filtered+grouped order* (predictable for the reviewer) or pure reading-order (predictable for document flow)? My lean: current filtered order, so Next doesn't suddenly jump across groups in a way the reviewer didn't expect.

2. **Should the drill-down preserve scroll position on return?** When the reviewer clicks Back, does the atom list re-scroll to show the just-edited atom, or does it return to wherever the list was scrolled before? My lean: scroll to the just-edited atom so the reviewer sees context.

3. **Bbox edit — commit per-handle-drop or per-mouseup-only?** Dragging a handle could emit one history entry per micro-adjustment or one at the end. Lean: one at mouseup (less noise in history, still captures intent).

4. **Draw-to-add-region cancellation.** If the reviewer starts a draw in the detail view and decides mid-drag they don't want the region, how do they cancel? Escape-during-drag? No cancel (commit what was drawn)? Lean: Esc cancels in-progress draw.

## 12. Non-goals

Just to make it explicit what Phase 1 is *not* doing, so we don't quietly scope-creep:

- Not building the AI-assisted kind suggestion — that's Phase 2
- Not wiring ontology lookup or code verdicts — Phase 2
- Not decomposing atoms into structured FHIR subfields — never (per §4)
- Not changing how discoveries work — existing discoveries flow is untouched
- Not changing auth — existing ADI_ADMIN_KEY bearer path continues until AUTH-2
- Not surfacing reviewer identity properly — stays hardcoded 'jason'
- Not touching PHI tab or Info tab — Atoms-tab-only changes
- Not changing the grading-submit lock-in flow or F1 computation — existing logic extended, not replaced

---

**End of draft v0.1. Ready for sprint 1.1 pre-audit prompt when approved.**
