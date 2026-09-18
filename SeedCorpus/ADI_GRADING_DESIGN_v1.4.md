# ADI Grading Design

Status: current, design v1.4 (shape, not spec), owner rulings of 2026-09-17/18 applied; supersedes v1.3 (`ADI_GRADING_DESIGN_v1.3.md`, now historical) and, behind it, v1.2 (`ADI_GRADING_DESIGN.md`).
Last verified: 2026-09-18
Date: 2026-09-18
Repo home: `RecordHealth.IO/SeedCorpus/ADI_GRADING_DESIGN_v1.4.md`

Owns the reviewer grading surface. v1.2 §1 and §10 stand unrestated; v1.2 §4 and §7 are amended by §6 and §8 here. v1.3 is carried forward whole except where GR-28 through GR-37 change it.

**A word on words.** The owner says *fact*; the console, the schema and this document's older sections say *atom*. One thing, two words. The 2026-09-17/18 rulings are written in the owner's register and mean the atom.

**Owner rulings, fixed points (2026-09-15, first session), added to GR-1 through GR-7:**

- GR-8. Ground truth is the product: the console exists to make the atom list and the relationship list correct, fast. The reviewer never explains why the ingest was wrong. ~~The one reviewer-supplied reason is on a delete, from a fixed list, more than one allowed, "no fitting kind exists" among them.~~ Struck by GR-18. The "error classes are derived later" clause is struck by GR-27 (§5).
- GR-9. ~~Reviewer actions are exactly: fix an atom's fields; fix its position by selecting words on the page image; create an atom by selecting words and picking a kind; fix or create relationships between atoms, rows and sections through a clickable tree; delete an atom or a relationship with reason codes. An atom left untouched is accepted.~~ Struck: untouched-means-accepted by GR-12, the reason codes by GR-18, the clickable tree by GR-30. The surviving list of reviewer actions is §7.
- GR-10. Every save is visible on the thing that was saved, at the moment it is saved. A control that needs something else before it will save says so on screen. Silent refusal is a fail state.
- GR-11. ~~Filtering is the tree plus one plain Kind dropdown listing only kinds with something to show.~~ The tree half is struck by GR-30: filtering is the Sections tab plus the Kind dropdown. The per-kind chip strip stays removed.

**Owner rulings, fixed points (2026-09-15, second session), superseding the first draft where they differ:**

- GR-12. Accept is explicit. Each atom has a checkbox meaning "vetted, valid as it stands". Checking it writes the accepted entry at once and the atom shows its vetted state. It can be unchecked; a vetted atom can still be corrected or deleted afterward. Untouched-means-accepted and derived acceptance are dropped. GR-5's one entry per item stands. (The control is the green checkmark: GR-19, meaning fixed by GR-28.)
- GR-13. Delete is an X on the atom, behind an "Are you sure you want to delete" dialog. ~~The dialog carries the delete reasons, multi-select, "no fitting kind exists" included.~~ Struck by GR-18: Cancel and Delete only.
- GR-14. Row authoring is a first-class reviewer action: create a table row inside a section and assign atoms to it, saved as log entries (§2). Deferred by GR-31 until the owner has stepped through the new panel.
- GR-15. ~~The tree is section > row > atom where rows exist, section > atom otherwise.~~ Retired by GR-30: there is no tree.
- GR-16. The package is the corrected, sorted atom list, stored, and it is what the phone and every downstream reader uses. The log is history and the before-and-after comparison, behind it. The stored corrected package is built by a full rebuild from original plus log at a lock step (Mark reviewed, in this job), never on every save. Before lock, readers get the original. Editing after lock requires unlock; the next lock rebuilds.

**Owner rulings, fixed points (2026-09-15, third session), superseding earlier sessions where they differ:**

- GR-17. The corrected package is the package after lock. Once locked, the served package is the corrected list only, under its own checksum with its own integrity checks; the original is not included in the download. Before lock, the served package is the original, as today. The original stays stored on the server behind the corrected package, for history and comparison.

**Owner rulings, fixed points (2026-09-15, fourth session), superseding earlier sessions where they differ:**

- GR-18. Delete carries no reasons for now. The "Are you sure you want to delete?" dialog is Cancel and Delete only. The delete reasons list, `no_fitting_kind` included, is removed from the design entirely (§3).
- GR-19. The vetted control is a green checkmark icon on the atom: green when vetted, grey when not, click toggles. Not a checkbox, no "vetted" label. Its meaning is fixed by GR-28.

**Owner rulings, fixed points (2026-09-16), superseding earlier sessions where they differ:**

- GR-20. A reviewer's action is final and is never re-questioned. A move decides an atom's section; the rebuild rewrites the atom's section field and parent to match the newest move. "Two carriers" is an internal detail, not a design question.
- GR-21. Atom position is set only by highlighting words on the page image. Numbered position-entry boxes are removed (already F-NEW-TH). No position validator at save or at lock: what the reviewer highlights is what is saved.

**Owner rulings, fixed points (2026-09-17/18), superseding earlier sessions where they differ. These are the console's shape now; where they contradict GR-9, GR-11, GR-15 or anything the build-step-4 tree established, they win.**

- GR-28. The green checkmark means "this is correct and vetted as it currently stands". The X means "this is wrong, remove it". Nothing else writes or erases a checkmark. A checkmark on a link row that moves an object is a bug. Move-back behavior as built (GR-25: withdraws the reject, writes no accept) is consistent with this rule and stands.
- GR-29. The refusal of a section placed under its own descendant is enforced on the server as well as in the console (GR-24 made it a console refusal; it is now both).
- GR-30. The tree is removed entirely. A Sections tab replaces it: each section is drawn as a box on the page image, computed in the console from the lines it covers — one box per page for a section spanning pages; clicking a section filters the list to it; a section's detail shows the AI's section kind with a dropdown to change it, and its parent section as a dropdown. The server already accepts a section kind correction.
- GR-31. "Move to…" and drag are removed. Each fact's detail carries a "Section" dropdown showing the section it belongs to; changing it moves the fact and saves at once. Same for a section's parent. Table rows: decision deferred until the owner has stepped through the new panel.
- GR-32. Fact detail layout, top to bottom: checkmark and X at the top; the fact's text as a non-editable field with an edit checkbox beside it that opens a field pre-filled with the current text; Kind showing the current kind with a grouped dropdown next to it (main headings outdented, kinds indented); Section dropdown; "PHI" with a checkbox, and checking it reveals a PHI type dropdown next to it; then only the fields that apply to this fact's kind. Removed from the panel: Section ID, Position, "Record correction", the "SAVED / unvetted" row, column role, the dead lab-value and address rows, and the "Status: awaiting_review" line. Extracted text and source text are one stored thing; the panel shows it once.
- GR-33. Which fields apply to which kinds is declared by the server in the published field list (schema version bump); the console holds no list of its own (existing rule — PACKAGE_DESIGN §6: derived from the schema, not hand-maintained in the console). Date role appears only on date facts; subtype only on the kinds that use it.
- GR-34. Every change saves on its own the moment it is made; a typed field saves when the reviewer leaves it or presses Enter; unchecking the edit box without saving discards the typing. "Record correction" and the in-memory draft are gone. Every save still paints only from the re-read (GR-10).
- GR-35. PHI: checking PHI turns the fact red everywhere at once (card stripe, page box, grouping, PHI-only filter), fixed now. Marking a fact PHI makes an ADI-minted token, recorded in the amendment log like every other reviewer change, picked up by the phone on graded return per the existing token ruling (PACKAGE_DESIGN OR-16); built in this pass after its own audit. The lock should not pass a PHI fact with no token silently; the exact behavior is settled in that audit.
- GR-36. Word selection: the checkmark saves the selection as the fact's new position; the X cancels the selection and turns the tool off; the back circle undoes the last position save by writing a new entry restoring the prior position. "Re-point #N here" and "Clear" go.
- GR-37. The whole console layout is a trial: nothing is final until the owner has stepped through it on screen.

## 1. The reviewer's flow (replaces v1.2 §2)

1. Open a document, pick a package: the original core with the whole log folded in (§6.3).
2. Work the list, the Sections tab and the page image. Vet what is right (checkmark, GR-28). Fix what is wrong in the fact's detail panel (text, kind, section, PHI, the fields that apply) and its position on the page image. Create a missing fact by selecting words and picking a kind. Remove what is wrong (X). Each act is one append, saved on its own the moment it is made (GR-34), painted from the re-read that follows, in-flight until then (GR-10).
3. Press "Mark reviewed": the lock (§6). To keep going, unlock; the next lock rebuilds.

Thumbs-up is the checkmark, thumbs-down is the X. "Accept N shown" is retired unbuilt.

## 2. Reviewer actions as log entries (replaces v1.2 §3's ops table)

PACKAGE_DESIGN §3 shape, v1.2 §3 addressing, no new op; declaration additions in §9 item 7. GR-28 through GR-37 change which control writes an entry, not the entries themselves: the Section dropdown (GR-31) writes exactly what "Move to…" and drag wrote, and save-on-change (GR-34) writes exactly what "Record correction" wrote.

| Action | entry | note |
|---|---|---|
| Vet | `verdict accepted` on the atom, relationship, row or user amendment | one entry per checkmark toggle (GR-19, GR-28) |
| Un-vet | `remove`, `target { entity: amendment, id: <the accepted entry> }` | §4.1 |
| Fix a field | `verdict corrected` + `field_path` + `new_value`, one per field (GR-4) | written on leave or Enter (GR-34) |
| Fix a position | four `corrected` entries (`page`, `line`, `word_start`, `word_end`), one `batch_id` | the checkmark in the word tool saves it (GR-36) |
| Undo a position save | four `corrected` entries restoring the prior position, one `batch_id` | the back circle (GR-36); a new entry, never an erasure |
| Create an atom | `add`, discovery namespace: `class: atom`, `kind`, `page`, `value`, optional pointer fields | |
| Move a fact to another section | the relationship route, as build step 4 shipped it (GR-24) | written by the Section dropdown (GR-31) |
| Change a section's parent | the same relationship route; refused when the target is the section's own descendant (GR-24, GR-29) | written by the parent dropdown (GR-31) |
| Fix a section's kind | `verdict corrected` on the section's kind | the server already accepts this (GR-30) |
| Mark a fact PHI | `verdict corrected` on the PHI field and its type, plus the ADI-minted token in the log | GR-35; shape settled in the token audit, build step 4 of §10 |
| Create a row (GR-14) | `add`, discovery namespace: `class: table_row`, `table_id`, `row_index`, `section_id` | deferred (GR-31) |
| Put an atom in a row | `verdict corrected` on `table_cell_ref`, `new_value { table_id, row_index }` | deferred (GR-31) |
| Move a row to another section | `verdict corrected` on the row's add, `target { entity: amendment, id, field_path: section_id }` | deferred (GR-31) |
| Remove a row, withdraw own add | `remove` on the discovery or relationship id, no reasons | deferred (GR-31) |
| Fix or create a relationship | `corrected` on `source` / `target` / `kind`, `rejected` then `add` where cardinality forbids; `add` with value `relationship_authored` | |
| Delete an atom or relationship (GR-13) | `verdict rejected`, no reasons | `reasons`, `reason` and `rationale` all retire for now (GR-18, §3) |
| Lock, unlock | `flag reviewed` (provenance §6.1); `flag unlocked` | the lock triggers the rebuild |

`row_in_table` and `table_in_section` are never written by the reviewer: the rebuild derives them from row entries and cell refs (§6.2), absorbing the Sprint 10 intent for both. Sprint 10 keeps the Worker's own emitters at ingest, the cell id rule and cell grading (`F-NEW-SX` narrows to cells), and PACKAGE_DESIGN §6's ground-truth-only units.

## 3. Delete: no reasons for now (GR-18)

The GR-13 "Are you sure you want to delete?" dialog is Cancel and Delete only. No reason list is shown or collected; `grading_vocabularies.delete_reasons`, every code in it (`not_in_document`, `not_a_fact`, `duplicate`, `fragment`, `no_fitting_kind`, `not_related`, `other`), and the `fp_*` taxonomy (`F-NEW-TC`) are removed from the design entirely, not just deferred. Older `fp_*` entries fold as `rejected`.

A reviewer-supplied delete reason, including a `no_fitting_kind` signal for INGEST_VOCABULARY_DESIGN's off-list census, is a parked idea with no trigger to bring it back (§9).

## 4. Vetting, un-vetting and the fold (replaces v1.2 §6's buckets)

These are progress counts. They are not scores and nothing derives a score from them (§5). Per class C, folded to a position P (one fold rule, v1.2 §4): instances_C, every core instance minus synthesized atoms; rejected_C, whole-object head `rejected`; corrected_C, not rejected and any head `corrected`; accepted_C, neither and whole-object head `accepted`; unvetted_C, the rest; discoveries_C, live reviewer adds (not walker adds). The console and the lock header read these counts; the lock stores progress (§6.1).

**4.1 Un-vet on an append-only log (proposal).** Unchecking writes `remove` naming the accepted entry's `amendment_id`, no reasons: the reviewer withdraws their own entry. The fold gains one pre-pass: collect the ids such removes name, skip those entries, then newest-wins. The atom's head falls back to whatever else is on its key (a correction stays; nothing, and it is unvetted again). Vetting never changes the build (§6.2), so the rebuild pays nothing. Validator: the named entry must be a live reviewer `accepted` in this log. Cost: the pre-pass in three folds (server, console, phone at sprint 9) under one shared fixture, one validator rule, `judged` reading the pre-passed fold. Rejected: a fourth verdict value, which breaks PACKAGE_DESIGN §6's fixed three.

## 5. Derived error classes — retired (GR-27, 2026-09-17)

Retired: counting the reviewer's log entries as a score was inverted. Scoring is truth-versus-candidate: the corrected package is the ground truth (PACKAGE_DESIGN §7), and the bakeoff scorer (VENDOR_ABSTRACTION_DESIGN §4.1) compares any candidate package against it; GR-6 retires with this section. The review console shows reviewer progress — vetted N of M, entries since lock, lock state — never scores; the lock stores progress, not scores. Scorer spec pass owed in VENDOR_ABSTRACTION_DESIGN §4.1 (ROADMAP F-NEW-TT).

The owner's own statement of the model, verbatim:

> "we're creating groundtruth then testing that groundtruth against ingests, either version / prompt engineering testing or bakeoffs. I don't see a use-case to manually score AI."

And on the axes:

> "I want the design to accommodate infinite axis scoring at any vector."

So: one record per matched or unmatched instance, carrying every known dimension; any slice is a count over those records; no instance may cite a design list to refuse an axis.

## 6. The lock and the stored corrected package (GR-16; amends v1.2 §4 and §7)

**6.1 What the lock writes.** One request. The server builds the corrected core (§6.2), writes it to R2 at `documents/{record_id}/{package_id}/corrected/{amendment_version}/core.json`, then appends `flag reviewed` with `provenance { progress, corrected_core_hash, rebuild_version }` in one transaction; a failed build appends nothing. `document_packages` gains `corrected_core_r2_key`, `corrected_core_hash`, `locked_at_version`; the versions ledger row gains `corrected_core_hash`. Every build is kept (R15); the original core never changes. The lock refuses, on screen, while any atom is unvetted, the control reporting the count (GR-17; "accept all remaining" is parked, §9). On a PHI fact with no token the lock does not pass silently (GR-35); whether it refuses is unruled, and the exact behavior is settled in the token audit of §10 step 4, parked under `F-NEW-SW` until then (§9 item 6).

**6.2 The rebuild rule.** Deterministic, pinned by a fixture beside the fold's. Fold to the lock; drop rejected atoms, relationships and rows; apply every `corrected` head; add live reviewer discoveries as atoms and rows with `origin: reviewer` and their log ids; apply relationship adds and removes; rewrite `section_id`, `parentId` and `table_cell_ref` from the entries that won; emit `row_in_table` and `table_in_section` from rows and cell refs; re-derive `source_region` and `source_text` for a re-pointed atom (GR-23); drop nothing else. Sort atoms by `(page, line, word_start)`, unlocated last within their page; sections by first line; relationships by source. Vetting changes nothing here.

**6.3 Lock state and readers.** Lock state is the newest of `reviewed` and `unlocked` in the log. While locked, the write route refuses reviewer entries (`package_locked`, with an Unlock button), and every reader is served the corrected list alone (GR-17): its own hash, its own integrity checks, the original core withheld from the download though it stays stored on the server behind it, for history and comparison. Unlock appends `flag unlocked` and nothing else: the build stays stored, `corrected` is no longer served, export is withheld, readers get the original — alone, as before lock — until the next lock. The console never reads `corrected`: between saves it shows the original with the whole log folded in, re-read after every append, the rebuild's fold minus sorting and writing. Each atom shows its state from that fold: vetted, corrected (per field), deleted (history only), created, in a row, in-flight. A header shows reviewer progress, never a score: "Locked at 1.n" or "Unlocked, N entries since".

## 7. The console surface (replaces v1.2 §5's "Views" and v1.3 §7's tree)

Everything here is a trial: nothing is final until the owner has stepped through it on screen (GR-37).

**The fact's detail panel (GR-32).** Top to bottom: the green checkmark and the X (GR-28); the fact's text as a non-editable field with an edit checkbox beside it that opens a field pre-filled with the current text; Kind, showing the current kind with a grouped dropdown next to it, main headings outdented and kinds indented; the Section dropdown (GR-31); "PHI" with a checkbox, revealing a PHI type dropdown next to it when checked (GR-35); then only the fields that apply to this fact's kind, per the server's declaration (GR-33) — date role only on date facts, subtype only on the kinds that use it. Gone from the panel: Section ID, Position, "Record correction", the "SAVED / unvetted" row, column role, the dead lab-value and address rows, the "Status: awaiting_review" line. Extracted text and source text are one stored thing and the panel shows it once.

**Saving (GR-34).** Every change saves on its own the moment it is made. A typed field saves when the reviewer leaves it or presses Enter. Unchecking the edit box without saving discards the typing. There is no draft and no "Record correction" button. Every save paints only from the re-read (GR-10).

**The Sections tab (GR-30).** Replaces the tree. Each section is a box drawn on the page image, computed in the console from the lines the section covers — one box per page where a section spans pages. Clicking a section filters the list to it. A section's detail shows the AI's section kind with a dropdown to change it (the server already accepts the correction) and its parent section as a dropdown; a parent that is the section's own descendant is refused, in the console and on the server (GR-29). "Move to…" and drag are gone (GR-31).

**Filters.** The Kind dropdown lists the kinds the current section filter shows; Status and PHI-only stay. Class bar, grouped kind picker, per-class groups, thumbs and "Accept N shown" go.

**PHI (GR-35).** Checking PHI turns the fact red everywhere at once: card stripe, page box, grouping, PHI-only filter.

**The page image and word selection (GR-36).** Selectable words set position (GR-21); a cross-line selection is refused on screen. In the word tool: the checkmark saves the selection as the fact's new position; the X cancels the selection and turns the tool off; the back circle undoes the last position save by writing a new entry restoring the prior position. "Re-point #N here" and "Clear" are gone. The re-read after a 201 remains the only painter.

**Table rows.** Deferred until the owner has stepped through the new panel (GR-31).

## 8. PACKAGE_DESIGN amendment, files under F-NEW-SV

Not applied to `PACKAGE_DESIGN.md`; recorded for the amendment pass F-NEW-SV owes it. (§7 and §9's sprint 7 row of PACKAGE_DESIGN were corrected in place 2026-09-18 under GR-27; the rest of this list is still owed.)

- §1: a fifth member, `corrected`, the build of §6.2, replaces `core` in the served package once locked (GR-17); before lock the served package is `core` alone, as today. The manifest gains `lock { locked_at_version, corrected_core_hash, rebuild_version }`. `core` and `core_hash` stay on the object, server-side, for history and comparison, but drop out of the download once locked; `package_hash` and the rest of the integrity checks apply to whichever list is being served — `core` before lock, `corrected` after.
- §0.1, §2.4, R5: the corrected core is a projection of original plus log, never the source. Once locked, a returning package carries `corrected` alone, under its own hash; before lock it carries `core` alone, unchanged. The phone builds views from whichever is served; the log stays history behind it, and the original stays stored behind the corrected package for comparison.
- §3: `flag` gains `unlocked`; a `remove` may target the reviewer's own `accepted` entry (§4.1). (Reviewer rejects carry no `reasons[]`: GR-18.)
- §4: the columns, ledger column and R2 key of §6.1.
- §5, §6: the per-kind field declaration of GR-33, with its schema version bump.
- §9: sprint 7 reads as §10 here; sprint 8 exports only a locked package; sprint 9 displays `corrected`, the log as history; sprint 10 as narrowed in §2. ROADMAP's sprint 7 line goes stale with it.
- GR-2 and GR-3 narrow: appends stay real time; the lock is a build, not a draft; the phone reads the build instead of reconstructing.

## 9. Findings (stated, not resolved)

Defects in the shipped console:

1. `appendInFlight` drops a second click without a word (`adi-console/app.js` 1021, 4112).
2. "Record correction" returns silently on an empty draft (`app.js` 4103). Removed with the button itself in §10 step 1 (GR-34).
3. The class bar shows "table_row 15" for a package with zero rows: `instancesOf` counts `parsed_pages[].tables[].rows` while the served `table_row` declaration defines a row by cell refs on a minted table; the server's core index counts both. One definition must serve count, list and validator.

Open:

4. **Current dictionary (v1.2 §9.4) versus `no_fitting_kind`.** Moot for now under GR-18 (§3): an off-list kind is refused, so a real thing with no kind can only be deleted, with no reason captured. Whether a returning reason feeds the misfire census or `F-NEW-SV`'s heal-by-class path stays unruled until item 12 resolves.
5. **The list-only hold** (`LIST_ONLY_CLASSES`, pins at `test/adi-console-grading.test.mjs` 333–351, 471). Where it stands after build step 4 of v1.3 shipped is unverified here; the Sections tab step (§10 step 3) touches the same ground.
6. **`F-NEW-SW`.** GR-35 rules the mark: it mints an ADI token, logged like any other reviewer change. The discovery declaration still has no `is_phi` / `phi_type`; whether the lock refuses on unresolved flags is unruled and not built, and the token's exact shape and the lock's non-silent behavior are settled in §10 step 4's audit.
7. **Schema bumps needed** (`SCHEMA_VERSION` 23 today): the per-kind field declaration (GR-33, §10 step 2); `unlocked`; discovery PHI fields (item 6); discovery row fields open, deferred with rows; `origin: reviewer` and `tables[]` on the corrected core, or the phone's drift beacon fires.
8. **Unchecked corrections.** A `table_cell_ref` naming a reviewer-minted table needs the same check.
9. **Unlisted classes** (span, cell, code, inventory): where they show, now that the tree is gone (GR-30), is unruled.
10. **Owner's calls in §6.** The sort key. (Refusing the lock on unvetted atoms is ruled: GR-17.)
11. **Parked: "accept all remaining."** A bulk action to vet every unvetted atom at once, raised so GR-17's lock-refuses-while-unvetted rule doesn't force clicking through a large document one atom at a time. Parked, not designed or built.
12. **Parked: a delete-reason mechanism.** GR-18 drops reasons from delete entirely, including `no_fitting_kind` and the `fp_*` taxonomy (§3); item 4 waits on it. Parked, no trigger to bring it back.

## 10. Build order (replaces v1.3 §10)

Each step ships alone, suite green, staging then production. Close condition for every step: a live check by Claude Code on staging.

1. **The fact detail panel (console only).** GR-32's layout and its removals, GR-34's save-on-change with "Record correction" and the draft gone, GR-36's word-selection controls. No server change. Close: on staging, one fact's text, kind and a kind-specific field each corrected and painted from the re-read; one position saved from the word tool and undone with the back circle; the removed rows absent from the panel.
2. **Server: per-kind field declaration and the descendant refusal.** GR-33's published field list with its schema version bump, GR-29's server-side refusal of a section placed under its own descendant. Carries the phone's drift check (§9 item 7). Close: on staging, the published schema names the fields per kind and the console renders from it alone; a descendant parent is refused by the route, not only by the console; no drift beacon.
3. **The Sections tab and the section dropdowns.** GR-30's boxes on the page image, click-to-filter, section kind dropdown and parent dropdown; GR-31's Section dropdown on the fact; the tree and "Move to…" and drag removed. Close: on staging, one fact moved between sections from its dropdown, one section re-parented, one section's kind corrected, each carried into the corrected core at lock.
4. **PHI.** In order inside the step: the red-everywhere fix (GR-35), then the token audit, then the token build. Close: on staging, a fact marked PHI is red in card stripe, page box, grouping and PHI-only filter at once; a marked fact carries an ADI-minted token in the log; the lock's behavior on a PHI fact with no token is whatever the audit settled, and is not silent.

**Rows: deferred** (GR-31), until the owner has stepped through the new panel.

## 11. Rulings log

- GR-8 through GR-11: ruled 2026-09-15, first live session. GR-12 through GR-16: ruled 2026-09-15, second session. GR-17: ruled 2026-09-15, third session. GR-20, GR-21, GR-22, GR-23: ruled 2026-09-16.
- Build step 1 (v1.3 §10 item 1) shipped 2026-09-15/16 in `recordhealth-api`, commits `3d4a6cd` through `f85a17d`; see that repo's `docs/archive/SESSION_LOG.md`.
- Build step 2 (v1.3 §10 item 2) shipped 2026-09-16 in `recordhealth-api`, commits `22cdd7d` through `ed98109` plus `b9ad031`; deployed to staging and production, live close met on staging; see that repo's `docs/archive/SESSION_LOG.md`.
- GR-22 (2026-09-16): field corrections and relationship corrections are applied from reviewer-authored entries only, in the rebuild, the server fold and the console fold; an entry from any other author never overrides a reviewer's correction. Newest by log position among reviewer entries.
- GR-23 (2026-09-16): a re-point recomputes the atom's `source_text` from the newly selected words; an unresolved pointer keeps the atom's existing text and loses its span (GR-21 unchanged); when a hand text correction and a re-point both exist on one atom, the newer by log position wins; reviewer-created atoms take their text from the discovery's value.
- Build step 3 (v1.3 §10 item 3) shipped 2026-09-16 in `recordhealth-api`, api commits `9ce1800..5470441` and `a54288f`, console commits `fae1319..cf94eac` and `2b074fc`; `SCHEMA_VERSION` 23, `rh.rebuild/3`; live close met on staging (package `9e16cb41`); see that repo's `docs/archive/SESSION_LOG.md`.
- GR-24 (2026-09-17): moves are written through the relationship route only; created atoms are valid endpoints; a section is never moved under its own descendant (console refusal — extended to the server by GR-29).
- GR-25 (2026-09-17): a move-back withdraws the reviewer's own reject and writes no accepted; the withdrawal counts as a move at its own log position. Confirmed consistent with GR-28 and standing.
- GR-26 (2026-09-17): containment kinds count reviewer-authored entries only (adds, removes, corrections, accepts, rejects) in rebuild, server fold and console fold; other authors' non-containment kinds untouched.
- **The reason behind GR-22 and GR-26, recorded 2026-09-18:** a new process or a runaway process must never write a log item that becomes ground truth. Only the reviewer's own entries correct ground truth.
- GR-27 (2026-09-17): the §5 retirement and open-axes ruling (§5), with the owner's own words on the model quoted there.
- Build step 4 (v1.3 §10 item 4, the tree) shipped 2026-09-17 in `recordhealth-api`, commits `d919abb..3df7042`, `rh.rebuild/4`; see that repo's `docs/archive/SESSION_LOG.md`. The tree it shipped is removed by GR-30; the relationship route it established is what GR-31's dropdowns write.
- GR-28 through GR-37 (2026-09-17/18): the console's shape — checkmark and X meaning (GR-28), server-side descendant refusal (GR-29), the tree replaced by the Sections tab (GR-30), dropdowns instead of "Move to…" and drag with rows deferred (GR-31), the fact detail layout and its removals (GR-32), server-declared per-kind fields (GR-33), save-on-change (GR-34), PHI red everywhere and the ADI-minted token (GR-35), the word-selection controls (GR-36), the whole layout a trial until the owner has stepped through it (GR-37). Applied to §1, §2, §6.1, §7, §9 and §10.

**UNRULED — recorded, not to be built:**

- The created-fact detail panel. Today a created fact has no panel. What it should show, and whether it is the GR-32 panel or something narrower, is unruled.
- Whether a lock refuses on unresolved PHI flags. Stays under `F-NEW-SW` (§9 item 6). GR-35 rules only that the lock must not pass silently.
- The "no staging console" rule in `recordhealth-api/CLAUDE.md` ("The ADI console is ONE Pages deployment, on `main` — there is no staging console"), which the owner never ruled. It bears on §10: every step's close condition is a live check on staging, and the console half of a step has no staging deployment to check under that rule.

- Open: §9; the codes in §3; §4.1 and §6.2's sort key as proposals; "accept all remaining" parked (§9 item 11).
