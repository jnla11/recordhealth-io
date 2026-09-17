# ADI Grading Design

Status: current, design v1.3 (shape, not spec), owner rulings of 2026-09-15 applied; supersedes v1.2 (`ADI_GRADING_DESIGN.md`, now historical).
Last verified: 2026-09-16
Date: 2026-09-15
Repo home: `RecordHealth.IO/SeedCorpus/ADI_GRADING_DESIGN_v1.3.md`

Owns the reviewer grading surface. v1.2 §1 and §10 stand unrestated; v1.2 §4 and §7 are amended by §6 and §8 here.

**Owner rulings, fixed points (2026-09-15, first session), added to GR-1 through GR-7:**

- GR-8. Ground truth is the product: the console exists to make the atom list and the relationship list correct, fast. The reviewer never explains why the ingest was wrong; error classes are derived later (§5). The one reviewer-supplied reason is on a delete, from a fixed list, more than one allowed, "no fitting kind exists" among them.
- GR-9. Reviewer actions are exactly: fix an atom's fields; fix its position by selecting words on the page image; create an atom by selecting words and picking a kind; fix or create relationships between atoms, rows and sections through a clickable tree; delete an atom or a relationship with reason codes. ~~An atom left untouched is accepted.~~ Struck by GR-12.
- GR-10. Every save is visible on the thing that was saved, at the moment it is saved. A control that needs something else before it will save says so on screen. Silent refusal is a fail state.
- GR-11. Filtering is the tree plus one plain Kind dropdown listing only kinds with something to show. The per-kind chip strip is removed.

**Owner rulings, fixed points (2026-09-15, second session), superseding the first draft where they differ:**

- GR-12. Accept is explicit. Each atom has a checkbox meaning "vetted, valid as it stands". Checking it writes the accepted entry at once and the atom shows its vetted state. It can be unchecked; a vetted atom can still be corrected or deleted afterward. Untouched-means-accepted and derived acceptance are dropped. GR-5's one entry per item stands.
- GR-13. Delete is an X on the atom, behind an "Are you sure you want to delete" dialog. The dialog carries the delete reasons, multi-select, "no fitting kind exists" included.
- GR-14. Row authoring is a first-class reviewer action: create a table row inside a section and assign atoms to it, saved as log entries (§2).
- GR-15. The tree is section > row > atom where rows exist, section > atom otherwise.
- GR-16. The package is the corrected, sorted atom list, stored, and it is what the phone and every downstream reader uses. The log is history and the before-and-after comparison, behind it. The stored corrected package is built by a full rebuild from original plus log at a lock step (Mark reviewed, in this job), never on every save. Before lock, readers get the original. Editing after lock requires unlock; the next lock rebuilds.

**Owner rulings, fixed points (2026-09-15, third session), superseding earlier sessions where they differ:**

- GR-17. The corrected package is the package after lock. Once locked, the served package is the corrected list only, under its own checksum with its own integrity checks; the original is not included in the download. Before lock, the served package is the original, as today. The original stays stored on the server behind the corrected package, for history and comparison.

**Owner rulings, fixed points (2026-09-15, fourth session), superseding earlier sessions where they differ:**

- GR-18. Delete carries no reasons for now. The "Are you sure you want to delete?" dialog is Cancel and Delete only. The delete reasons list, `no_fitting_kind` included, is removed from the design entirely (§3); §5's derived error classes that read a reviewer-supplied reason are not derivable until a reason mechanism returns (§9).
- GR-19. The vetted control is a green checkmark icon on the atom: green when vetted, grey when not, click toggles. Not a checkbox, no "vetted" label.

**Owner rulings, fixed points (2026-09-16), superseding earlier sessions where they differ:**

- GR-20. A reviewer's action is final and is never re-questioned. A move through the tree decides an atom's section; the rebuild rewrites the atom's section field and parent to match the newest move. "Two carriers" is an internal detail, not a design question.
- GR-21. Atom position is set only by highlighting words on the page image. Numbered position-entry boxes are removed (already F-NEW-TH). No position validator at save or at lock: what the reviewer highlights is what is saved.

## 1. The reviewer's flow (replaces v1.2 §2)

1. Open a document, pick a package: the original core with the whole log folded in (§6.3).
2. Walk the tree and the page image. Vet what is right (checkbox). Fix what is wrong (field, position, home, row, missing atom, delete by X). Each act is one append, painted from the re-read that follows, in-flight until then (GR-10).
3. Press "Mark reviewed": the lock (§6). To keep going, unlock; the next lock rebuilds.

Thumbs-up is the checkbox, thumbs-down is the X. "Accept N shown" is retired unbuilt.

## 2. Reviewer actions as log entries (replaces v1.2 §3's ops table)

PACKAGE_DESIGN §3 shape, v1.2 §3 addressing, no new op; declaration additions in §9 item 7.

| Action | entry | note |
|---|---|---|
| Vet | `verdict accepted` on the atom, relationship, row or user amendment | one entry per checkmark toggle (GR-19) |
| Un-vet | `remove`, `target { entity: amendment, id: <the accepted entry> }` | §4.1 |
| Fix a field | `verdict corrected` + `field_path` + `new_value`, one per field (GR-4) | `F-NEW-TD`'s four fields become writable |
| Fix a position | four `corrected` entries (`page`, `line`, `word_start`, `word_end`), one `batch_id` | |
| Create an atom | `add`, discovery namespace: `class: atom`, `kind`, `page`, `value`, optional pointer fields | |
| Create a row (GR-14) | `add`, discovery namespace: `class: table_row`, `table_id`, `row_index`, `section_id` | `table_id`: the section's minted table, else console-minted once per section |
| Put an atom in a row | `verdict corrected` on `table_cell_ref`, `new_value { table_id, row_index }` | the validator must accept a reviewer-minted `table_id` |
| Move a row to another section | `verdict corrected` on the row's add, `target { entity: amendment, id, field_path: section_id }` | |
| Remove a row, withdraw own add | `remove` on the discovery or relationship id, no reasons | refused while atoms remain; a pipeline row is `rejected` |
| Fix or create a relationship | `corrected` on `source` / `target` / `kind`, `rejected` then `add` where cardinality forbids; `add` with value `relationship_authored` | |
| Delete an atom or relationship (GR-13) | `verdict rejected`, no reasons | `reasons`, `reason` and `rationale` all retire for now (GR-18, §3) |
| Lock, unlock | `flag reviewed` (provenance §6.1); `flag unlocked` | the lock triggers the rebuild |

`row_in_table` and `table_in_section` are never written by the reviewer: the rebuild derives them from row entries and cell refs (§6.2), absorbing the Sprint 10 intent for both. Sprint 10 keeps the Worker's own emitters at ingest, the cell id rule and cell grading (`F-NEW-SX` narrows to cells), and PACKAGE_DESIGN §6's ground-truth-only units.

## 3. Delete: no reasons for now (GR-18)

The GR-13 "Are you sure you want to delete?" dialog is Cancel and Delete only. No reason list is shown or collected; `grading_vocabularies.delete_reasons`, every code in it (`not_in_document`, `not_a_fact`, `duplicate`, `fragment`, `no_fitting_kind`, `not_related`, `other`), and the `fp_*` taxonomy (`F-NEW-TC`) are removed from the design entirely, not just deferred. Older `fp_*` entries fold as `rejected`.

A reviewer-supplied delete reason, including a `no_fitting_kind` signal for INGEST_VOCABULARY_DESIGN's off-list census, is a parked idea with no trigger to bring it back (§9). Until it returns, §5's error classes that would read it are not derivable.

## 4. Vetting, un-vetting and the fold (replaces v1.2 §6's buckets)

Per class C, folded to a position P (one fold rule, v1.2 §4): instances_C, every core instance minus synthesized atoms; rejected_C, whole-object head `rejected`; corrected_C, not rejected and any head `corrected`; accepted_C, neither and whole-object head `accepted`; unvetted_C, the rest, a count, never scored; discoveries_C, live reviewer adds (not walker adds). Formulas as v1.2 §6, computed at the newest lock, later entries `pending`, nothing stored (GR-6).

**4.1 Un-vet on an append-only log (proposal).** Unchecking writes `remove` naming the accepted entry's `amendment_id`, no reasons: the reviewer withdraws their own entry. The fold gains one pre-pass: collect the ids such removes name, skip those entries, then newest-wins. The atom's head falls back to whatever else is on its key (a correction stays; nothing, and it is unvetted again). Vetting never changes the build (§6.2), so the rebuild pays nothing. Validator: the named entry must be a live reviewer `accepted` in this log. Cost: the pre-pass in three folds (server, console, phone at sprint 9) under one shared fixture, one validator rule, `judged` reading the pre-passed fold. Rejected: a fourth verdict value, which breaks PACKAGE_DESIGN §6's fixed three.

## 5. Derived error classes (computed at the lock, never reviewer-stored)

GT_C is the corrected package's instances of C; I_C the original's. Per instance at the lock, several allowed: `missed` (in GT, not in I); `invented` and `unkindable` not derivable for now — both read a reviewer-supplied delete reason, dropped by GR-18 (§3), pending a reason mechanism (§9); `wrong_kind` (`corrected` on `kind`); `wrong_boundary` (on a pointer field); `wrong_home` (on `source`, `target` or `table_cell_ref`); `wrong_phi` (on `is_phi` or `phi_type`); `wrong_<field_path>` for any other field. Served as `by_error_class` per class and per relationship kind; the bakeoff resolver reads the corrected package.

## 6. The lock and the stored corrected package (GR-16; amends v1.2 §4 and §7)

**6.1 What the lock writes.** One request. The server builds the corrected core (§6.2), writes it to R2 at `documents/{record_id}/{package_id}/corrected/{amendment_version}/core.json`, then appends `flag reviewed` with `provenance { scores, corrected_core_hash, rebuild_version }` in one transaction; a failed build appends nothing. `document_packages` gains `corrected_core_r2_key`, `corrected_core_hash`, `locked_at_version`; the versions ledger row gains `corrected_core_hash`. Every build is kept (R15); the original core never changes. The lock refuses, on screen, while any atom is unvetted, the control reporting the count (GR-17; "accept all remaining" is parked, §9); a lock refusal on unresolved system PHI flags is unruled and not built, parked under `F-NEW-SW` (§9 item 6).

**6.2 The rebuild rule.** Deterministic, pinned by a fixture beside the fold's. Fold to the lock; drop rejected atoms, relationships and rows; apply every `corrected` head; add live reviewer discoveries as atoms and rows with `origin: reviewer` and their log ids; apply relationship adds and removes; rewrite `section_id`, `parentId` and `table_cell_ref` from the entries that won; emit `row_in_table` and `table_in_section` from rows and cell refs; re-derive `source_region` and `source_text` for a re-pointed atom (GR-23); drop nothing else. Sort atoms by `(page, line, word_start)`, unlocated last within their page; sections by first line; relationships by source. Vetting changes nothing here.

**6.3 Lock state and readers.** Lock state is the newest of `reviewed` and `unlocked` in the log. While locked, the write route refuses reviewer entries (`package_locked`, with an Unlock button), and every reader is served the corrected list alone (GR-17): its own hash, its own integrity checks, the original core withheld from the download though it stays stored on the server behind it, for history and comparison. Unlock appends `flag unlocked` and nothing else: the build stays stored, `corrected` is no longer served, export is withheld, readers get the original — alone, as before lock — until the next lock. The console never reads `corrected`: between saves it shows the original with the whole log folded in, re-read after every append, the rebuild's fold minus sorting and writing. Each atom shows its state from that fold: vetted, corrected (per field), deleted (history only), created, in a row, in-flight. A header says "Locked at 1.n" or "Unlocked, N entries since".

## 7. The console surface (replaces v1.2 §5's "Views")

**The tree.** GR-15. Sections from the core and the live relationship fold; rows from cell refs and live row entries, a pipeline table under the section of its row-0 atom; atoms under their row or section. Selecting a node filters list and overlay to its subtree. Drag or "Move to" writes §2's entries; "New row" writes the row add; relationship rows sit under their source.

**The atom.** A green checkmark icon (vetted: green when vetted, grey when not, click toggles — GR-19, not a checkbox, no "vetted" label), an X (delete, behind the Cancel/Delete-only GR-13/GR-18 dialog), the field editor, marks on corrected fields, a saved-state mark painted only from the re-read.

**Filters.** GR-11: the Kind dropdown lists the kinds the tree selection shows; Status and PHI-only stay. Class bar, grouped kind picker, per-class groups, thumbs and "Accept N shown" go; counts move into tree labels.

**The page image.** Selectable words replace the draw tool for atoms; a cross-line selection is refused on screen. The re-read after a 201 remains the only painter.

## 8. PACKAGE_DESIGN amendment, files under F-NEW-SV

Not applied to `PACKAGE_DESIGN.md`; recorded for the amendment pass F-NEW-SV owes it.

- §1: a fifth member, `corrected`, the build of §6.2, replaces `core` in the served package once locked (GR-17); before lock the served package is `core` alone, as today. The manifest gains `lock { locked_at_version, corrected_core_hash, rebuild_version }`. `core` and `core_hash` stay on the object, server-side, for history and comparison, but drop out of the download once locked; `package_hash` and the rest of the integrity checks apply to whichever list is being served — `core` before lock, `corrected` after.
- §0.1, §2.4, R5: the corrected core is a projection of original plus log, never the source. Once locked, a returning package carries `corrected` alone, under its own hash; before lock it carries `core` alone, unchanged. The phone builds views from whichever is served; the log stays history behind it, and the original stays stored behind the corrected package for comparison.
- §3: reviewer rejects carry `reasons[]`; `flag` gains `unlocked`; a `remove` may target the reviewer's own `accepted` entry (§4.1).
- §4: the columns, ledger column and R2 key of §6.1.
- §9: sprint 7 reads as §10 here; sprint 8 exports only a locked package; sprint 9 displays `corrected`, the log as history; sprint 10 as narrowed in §2. ROADMAP's sprint 7 line goes stale with it.
- GR-2 and GR-3 narrow: appends stay real time; the lock is a build, not a draft; the phone reads the build instead of reconstructing.

## 9. Findings (stated, not resolved)

Defects in the shipped console:

1. `appendInFlight` drops a second click without a word (`adi-console/app.js` 1021, 4112).
2. "Record correction" returns silently on an empty draft (`app.js` 4103).
3. The class bar shows "table_row 15" for a package with zero rows: `instancesOf` counts `parsed_pages[].tables[].rows` while the served `table_row` declaration defines a row by cell refs on a minted table; the server's core index counts both. One definition must serve count, tree and validator.

Open:

4. **Current dictionary (v1.2 §9.4) versus `no_fitting_kind`.** Moot for now under GR-18 (§3): an off-list kind is refused, so a real thing with no kind can only be deleted, with no reason captured and `unkindable` not derivable (§5). Whether a returning reason feeds the misfire census or `F-NEW-SV`'s heal-by-class path stays unruled until item 12 resolves.
5. **The list-only hold** (`LIST_ONLY_CLASSES`, pins at `test/adi-console-grading.test.mjs` 333–351, 471). Step 1 keeps it, checkbox and X on atoms and user amendments; the tree step lifts it.
6. **`F-NEW-SW`.** A PHI mark is an ordinary field fix and the ADI mints no token for it; the discovery declaration has no `is_phi` / `phi_type`; the lock's refusal on unresolved flags is unruled.
7. **Schema bumps needed** (`SCHEMA_VERSION` 19 today): `reasons[]` and `delete_reasons`; `unlocked`; discovery pointer fields declared (`SCHEMA_VERSION` 23); discovery row fields open, build step 5; `origin: reviewer` and `tables[]` on the corrected core, or the phone's drift beacon fires.
8. **Unchecked corrections.** A `table_cell_ref` naming a reviewer-minted table needs the same check.
9. **Unlisted classes under GR-11** (span, cell, code, inventory): where they show is unruled.
10. **Owner's calls in §6.** The sort key. (Refusing the lock on unvetted atoms is ruled: GR-17.)
11. **Parked: "accept all remaining."** A bulk action to vet every unvetted atom at once, raised so GR-17's lock-refuses-while-unvetted rule doesn't force clicking through a large document one atom at a time. Parked, not designed or built.
12. **Parked: a delete-reason mechanism.** GR-18 drops reasons from delete entirely, including `no_fitting_kind` and the `fp_*` taxonomy (§3); `invented` and `unkindable` are not derivable until one returns (§5), and item 4 waits on it too. Parked, no trigger to bring it back.

## 10. Build order

Each step ships alone, suite green, staging then production.

1. **Vet and delete (console + api, small).** Checkbox accept, one `accepted` per atom; un-vet per §4.1; X delete behind the GR-13 dialog with `reasons[]` and `delete_reasons`; saved state visible on the atom; the two silent refusals fixed; the row count on one definition; thumbs retired. Close: one atom vetted, un-vetted, corrected and deleted, each visible from the re-read.
2. **Lock and stored package (api, then console).** §6 whole: rebuild rule and fixture, R2 object, columns, ledger, `unlocked`, write-route refusal, the lock refusing on unvetted atoms, `corrected` served alone under its own checksum and the download's checksum rewritten off `core` onto it (GR-17), lock header and Unlock. Sprint 8 exports it. Close: one package locked, hash read back, unlocked, edited, re-locked with a new hash and ledger row.
3. **Words on the page (console, one schema bump) — SHIPPED 2026-09-16.** Select-to-repoint writes four pointer entries under one `batch_id`; select-and-kind writes a located discovery. Close: one atom re-pointed, one missed atom created, both on the overlay.
4. **The tree (console).** Sections > atoms; the tree filters; GR-11's filters; moves write `member_of_section` / `section_in_section`; the list-only hold retires. Close: one atom re-homed through the tree, scored `wrong_home`.
5. **Rows (api schema bump, then console).** Row fields on the discovery declaration; `table_cell_ref` writable and validated; the row level in the tree; the rebuild emitting both containment kinds. Close: one lab row created, three atoms assigned, locked, the corrected core carrying it.

## 11. Rulings log

- GR-8 through GR-11: ruled 2026-09-15, first live session. GR-12 through GR-16: ruled 2026-09-15, second session. GR-17: ruled 2026-09-15, third session. GR-20, GR-21, GR-22, GR-23: ruled 2026-09-16.
- Build step 1 (§10 item 1) shipped 2026-09-15/16 in `recordhealth-api`, commits `3d4a6cd` through `f85a17d`; see that repo's `docs/archive/SESSION_LOG.md`.
- Build step 2 (§10 item 2) shipped 2026-09-16 in `recordhealth-api`, commits `22cdd7d` through `ed98109` plus `b9ad031`; deployed to staging and production, live close met on staging; see that repo's `docs/archive/SESSION_LOG.md`.
- GR-22 (2026-09-16): field corrections and relationship corrections are applied from reviewer-authored entries only, in the rebuild, the server fold and the console fold; an entry from any other author never overrides a reviewer's correction. Newest by log position among reviewer entries.
- GR-23 (2026-09-16): a re-point recomputes the atom's `source_text` from the newly selected words; an unresolved pointer keeps the atom's existing text and loses its span (GR-21 unchanged); when a hand text correction and a re-point both exist on one atom, the newer by log position wins; reviewer-created atoms take their text from the discovery's value.
- Build step 3 (§10 item 3) shipped 2026-09-16 in `recordhealth-api`, api commits `9ce1800..5470441` and `a54288f`, console commits `fae1319..cf94eac` and `2b074fc`; `SCHEMA_VERSION` 23, `rh.rebuild/3`; live close met on staging (package `9e16cb41`); see that repo's `docs/archive/SESSION_LOG.md`.
- Open: §9; the codes in §3; §4.1 and §6.2's sort key as proposals; "accept all remaining" parked (§9 item 11).
