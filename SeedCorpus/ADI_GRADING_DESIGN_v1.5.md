# ADI Grading Design

Status: current, design v1.5 (shape, not spec), owner rulings of 2026-09-18/19 applied; supersedes v1.4 (`ADI_GRADING_DESIGN_v1.4.md`, now historical) and, behind it, v1.3 (`ADI_GRADING_DESIGN_v1.3.md`) and v1.2 (`ADI_GRADING_DESIGN.md`). Repo home: `RecordHealth.IO/SeedCorpus/ADI_GRADING_DESIGN_v1.5.md`.
Last verified: 2026-09-25

Owns the reviewer grading surface. v1.2 §1 and §10 stand unrestated; v1.2 §4 and §7 are amended by §6 and §8 here. v1.4 is carried forward whole except where GR-39 through GR-51 change it.

**A word on words.** The owner says *fact*; the console, the schema and this document's older sections say *atom*. One thing, two words. The 2026-09-17/18/19 rulings are written in the owner's register and mean the atom.

**Owner rulings, fixed points (2026-09-15, first session), added to GR-1 through GR-7:**

- GR-8. Ground truth is the product: the console exists to make the atom list and the relationship list correct, fast. The reviewer never explains why the ingest was wrong. ~~The one reviewer-supplied reason is on a delete, from a fixed list, more than one allowed, "no fitting kind exists" among them.~~ Struck by GR-18. The "error classes are derived later" clause is struck by GR-27 (§5).
- GR-9. ~~Reviewer actions are exactly: fix an atom's fields; fix its position by selecting words on the page image; create an atom by selecting words and picking a kind; fix or create relationships between atoms, rows and sections through a clickable tree; delete an atom or a relationship with reason codes. An atom left untouched is accepted.~~ Struck: untouched-means-accepted by GR-12, the reason codes by GR-18, the clickable tree by GR-30. The surviving list of reviewer actions is §7.
- GR-10. Every save is visible on the thing that was saved, at the moment it is saved. A control that needs something else before it will save says so on screen. Silent refusal is a fail state.
- GR-11. ~~Filtering is the tree plus one plain Kind dropdown listing only kinds with something to show.~~ The tree half is struck by GR-30: filtering is the Sections panel plus the Kind dropdown. The per-kind chip strip stays removed.

**Owner rulings, fixed points (2026-09-15, second session), superseding the first draft where they differ:**

- GR-12. Accept is explicit. Each atom has a checkbox meaning "vetted, valid as it stands". Checking it writes the accepted entry at once and the atom shows its vetted state. It can be unchecked; a vetted atom can still be corrected or deleted afterward. Untouched-means-accepted and derived acceptance are dropped. GR-5's one entry per item stands. (The control is the green checkmark: GR-19, meaning fixed by GR-28, and it never revives a deleted object: GR-49.)
- GR-13. Delete is an X on the atom, behind an "Are you sure you want to delete" dialog. ~~The dialog carries the delete reasons, multi-select, "no fitting kind exists" included.~~ Struck by GR-18: Cancel and Delete only. A deleted object stays visible in the Deleted group and can be restored (GR-49).
- GR-14. Row authoring is a first-class reviewer action: create a table row inside a section and assign atoms to it, saved as log entries (§2). Deferred by GR-31; scheduled as §10 step 5 by the 2026-09-19 rulings.
- GR-15. ~~The tree is section > row > atom where rows exist, section > atom otherwise.~~ Retired by GR-30: there is no tree.
- GR-16. The package is the corrected, sorted atom list, stored, and it is what the phone and every downstream reader uses. The log is history and the before-and-after comparison, behind it. The stored corrected package is built by a full rebuild from original plus log at a lock step (Mark reviewed, in this job), never on every save. Before lock, readers get the original. Editing after lock requires unlock; the next lock rebuilds. Re-affirmed by GR-39 against per-save versioning: the save bumps the version, the lock does the totality.

**Owner rulings, fixed points (2026-09-15, third session), superseding earlier sessions where they differ:**

- GR-17. The corrected package is the package after lock. Once locked, the served package is the corrected list only, under its own checksum with its own integrity checks; the original is not included in the download. Before lock, the served package is the original, as today. The original stays stored on the server behind the corrected package, for history and comparison.

**Owner rulings, fixed points (2026-09-15, fourth session), superseding earlier sessions where they differ:**

- GR-18. Delete carries no reasons for now. The "Are you sure you want to delete?" dialog is Cancel and Delete only. The delete reasons list, `no_fitting_kind` included, is removed from the design entirely (§3).
- GR-19. The vetted control is a green checkmark icon on the atom: green when vetted, grey when not, click toggles. Not a checkbox, no "vetted" label. Its meaning is fixed by GR-28; it is refused on a deleted row by GR-49.

**Owner rulings, fixed points (2026-09-16), superseding earlier sessions where they differ:**

- GR-20. A reviewer's action is final and is never re-questioned. A move decides an atom's section; the rebuild rewrites the atom's section field and parent to match the newest move. "Two carriers" is an internal detail, not a design question. GR-47 closes the other carrier: a move is never written as a field correction.
- GR-21. Atom position is set only by highlighting words on the page image. Numbered position-entry boxes are removed (already F-NEW-TH). No position validator at save or at lock: what the reviewer highlights is what is saved.

**Owner rulings, fixed points (2026-09-17/18), superseding earlier sessions where they differ. These are the console's shape now; where they contradict GR-9, GR-11, GR-15 or anything the build-step-4 tree established, they win.**

- GR-28. The green checkmark means "this is correct and vetted as it currently stands". The X means "this is wrong, remove it". Nothing else writes or erases a checkmark. A checkmark on a link row that moves an object is a bug. Move-back behavior as built (GR-25: withdraws the reject, writes no accept) is consistent with this rule and stands. GR-49 adds: the checkmark never revives a deleted object either.
- GR-29. The refusal of a section placed under its own descendant is enforced on the server as well as in the console (GR-24 made it a console refusal; it is now both).
- GR-30. The tree is removed entirely. A Sections surface replaces it: each section is drawn as a box on the page image, computed in the console from the lines it covers — one box per page for a section spanning pages; clicking a section filters the list to it; a section's detail shows the AI's section kind with a dropdown to change it, and its parent section as a dropdown. The server already accepts a section kind correction. (Where that surface lives is fixed by GR-48: a panel beside the list, not a tab.)
- GR-31. "Move to…" and drag are removed. Each fact's detail carries a "Section" dropdown showing the section it belongs to; changing it moves the fact and saves at once. Same for a section's parent. Table rows: decision deferred until the owner has stepped through the new panel. (Which step removes which control is fixed by GR-42; rows land at §10 step 5.)
- GR-32. Fact detail layout, top to bottom: checkmark and X at the top; the fact's text as a non-editable field with an edit checkbox beside it that opens a field pre-filled with the current text; Kind showing the current kind with a grouped dropdown next to it (main headings outdented, kinds indented); Section dropdown; "PHI" with a checkbox, and checking it reveals a PHI type dropdown next to it; then only the fields that apply to this fact's kind. Removed from the panel: Position, "Record correction", the "SAVED / unvetted" row, column role, the dead lab-value and address rows, and the "Status: awaiting_review" line. ~~Section ID~~ — the ID line stays, by GR-43. Extracted text and source text are one stored thing; the panel shows it once.
- GR-33. Which fields apply to which kinds is declared by the server in the published field list (schema version bump); the console holds no list of its own (existing rule — PACKAGE_DESIGN §6: derived from the schema, not hand-maintained in the console). Date role appears only on date facts; subtype only on the kinds that use it. Shipped as `ATOM_KIND_FIELDS` at `SCHEMA_VERSION` 24; the structure-versus-values line and what is still owed are GR-46.
- GR-34. Every change saves on its own the moment it is made; a typed field saves when the reviewer leaves it or presses Enter; unchecking the edit box without saving discards the typing. "Record correction" and the in-memory draft are gone. Every save still paints only from the re-read (GR-10). A change attempted while a save is in flight is refused on screen, not queued (GR-45).
- GR-35. PHI: checking PHI turns the fact red everywhere at once (card stripe, page box, grouping, PHI-only filter), fixed now. Marking a fact PHI computes the Worker's token (the ADI calls the same function with the same secret and the package's `user_subject`), recorded in the amendment log like every other reviewer change; the phone takes it as it stands on graded return, with no reconciliation (PACKAGE_DESIGN OR-18 g, superseding OR-16); built in this pass after its own audit. The lock should not pass a PHI fact with no token silently; the exact behavior is settled in that audit. ~~Editing a PHI fact afterward updates the tokens table behind the existing token and mints nothing new (GR-40).~~ Superseded by the shipped rule (PACKAGE_DESIGN OR-18 i, 2026-09-22): a value edit moves the fact to the token for the new value; an unmark retires the token's use; a re-mark revives the same uid.
- GR-36. Word selection: the checkmark saves the selection as the fact's new position; the X cancels the selection and turns the tool off; the back circle undoes the last position save by writing a new entry restoring the prior position. "Re-point #N here" and "Clear" go. The back circle's exact scope and its refusal are GR-44.
- GR-37. The whole console layout is a trial: nothing is final until the owner has stepped through it on screen.
- GR-38. There is one ADI console deployment, on `main`; there is no staging console. §10's close conditions for the console steps are a live check on the one console, pointed at staging data — sharpened by GR-51 into who drives and who proves.

**Owner rulings, fixed points (2026-09-18/19), superseding earlier sessions where they differ. Recorded in the owner's register; applied to §1, §2, §6, §7, §9, §10 and §11.**

- GR-39. Per-save versioning stands as ruled: every save appends one entry, bumps the version and the package checksum. Re-affirmed after review. The corrected package at lock is the totality step (GR-16); the per-save bump is not a per-save rebuild.
- GR-40. Editing a PHI fact — its text or its fields — updates the ADI's tokens layer behind the existing token; no new token is minted for an edit. Ships whole in §10 step 4 with the token work. No interim. (Superseded by the shipped edit rule, PACKAGE_DESIGN OR-18 i, 2026-09-22 — see GR-35.)
- GR-41. No interim or temporary builds of any kind. A feature is scoped to land whole at its step or it waits. The owner's reason: scaffolding is the main source of drift.
- GR-42. "Move to…" is removed from the fact panel at step 1 and everywhere at step 3. Drag is removed at step 3.
- GR-43. The ID line stays on the fact panel.
- GR-44. The back circle undoes one position save — one step, not a walk back through history. A prior position that was unlocated is refused on screen ("The earlier position was unlocated; nothing to restore"): never a partial restore, never hidden.
- GR-45. A change made while a save is in flight is refused with "Saving, one moment". There is no queue.
- GR-46. Which fields a kind carries is STRUCTURE and is declared in the published schema per kind (`ATOM_KIND_FIELDS`); which values a field allows is the dictionary's. The write route enforces it (`amendment_field_not_on_kind`); the pipeline prompt is guarded against naming a kind the schema lacks; the console renders from it and holds no list of its own. A newly curated kind gets the base structure — no subtype, no date role — until it is declared. Subtype kinds as confirmed: `documentReference`, `emergencyContact`, `guardianInfo`, `organization`, `patientAddress`, `patientContact`, `patientDemographic`, `patientIdentifier`, `provider`, `providerContact`; `date_role`: `dateAtom`. Owed: the per-kind subtype VALUE lists still live in the prompt; they belong in the dictionary (ROADMAP item, next pass — §9 item 16).
- GR-47. A fact's section and a section's parent are never written as field corrections; the route refuses both (`amendment_move_rides_relationship`). Moves ride the relationship carrier only.
- GR-48. The Sections panel sits beside the list, where the tree was. The "Ground Truth" top-bar tab is removed. Section detail — kind dropdown, parent dropdown — renders on the picked row inside the panel. Owner, 2026-09-19: the section boxes and this breakout are not yet judged usable; a sharpening sprint follows step 4 (§10 step 6).
- GR-49. Deleted facts, links and sections stay visible in a "Deleted" group at the bottom of the list, with a "Restore" control that withdraws the reviewer's own delete; the object returns unvetted. The checkmark never revives anything: the console refuses it on a deleted row, and the server refuses an `accepted` on a live reviewer `rejected` head (`amendment_accept_on_rejected`).
- GR-50. A created fact is a fact: same row, same panel, same controls, same filters, same Deleted group; a small "created" marker only. "Withdraw" is removed — the X is its delete.
- GR-51. Close condition for a console step: Claude Code drives the exact saves the panel sends against staging data and proves them in the log, suite green; the on-screen proof is the owner stepping through it (GR-37). No browser automation.

## 1. The reviewer's flow (replaces v1.2 §2)

1. Open a document, pick a package: the original core with the whole log folded in (§6.3).
2. Work the list, the Sections panel and the page image. Vet what is right (checkmark, GR-28). Fix what is wrong in the fact's detail panel (text, kind, section, PHI, the fields that apply) and its position on the page image. Create a missing fact by selecting words and picking a kind — it joins the list as a fact like any other (GR-50). Remove what is wrong (X); it drops to the Deleted group, restorable (GR-49). Each act is one append, saved on its own the moment it is made (GR-34), bumping the version and the package checksum (GR-39), painted from the re-read that follows, in-flight until then (GR-10) — and a change attempted mid-flight is refused, not queued (GR-45).
3. Press "Mark reviewed": the lock (§6). To keep going, unlock; the next lock rebuilds.

Thumbs-up is the checkmark, thumbs-down is the X. "Accept N shown" is retired unbuilt.

## 2. Reviewer actions as log entries (replaces v1.2 §3's ops table)

PACKAGE_DESIGN §3 shape, v1.2 §3 addressing, no new op; declaration additions in §9 item 7. GR-28 through GR-37 changed which control writes an entry, not the entries themselves: the Section dropdown (GR-31) writes exactly what "Move to…" and drag wrote, and save-on-change (GR-34) writes exactly what "Record correction" wrote. GR-39 through GR-51 change no entry shape either; they fix which carrier is legal (GR-47), what the route refuses (GR-46, GR-49), and which control the reviewer reaches for.

| Action | entry | note |
|---|---|---|
| Vet | `verdict accepted` on the atom, relationship, row or user amendment | one entry per checkmark toggle (GR-19, GR-28); refused on a deleted object (GR-49) |
| Un-vet | `remove`, `target { entity: amendment, id: <the accepted entry> }` | §4.1 |
| Fix a field | `verdict corrected` + `field_path` + `new_value`, one per field (GR-4) | written on leave or Enter (GR-34); refused off the kind's structure (`amendment_field_not_on_kind`, GR-46); never `section_id` or `parentId` (`amendment_move_rides_relationship`, GR-47) |
| Fix a position | four `corrected` entries (`page`, `line`, `word_start`, `word_end`), one `batch_id` | the checkmark in the word tool saves it (GR-36) |
| Undo a position save | four `corrected` entries restoring the prior position, one `batch_id` | the back circle, one step (GR-44); a new entry, never an erasure; refused on screen when the prior position was unlocated |
| Create an atom | `add`, discovery namespace: `class: atom`, `kind`, `page`, `value`, optional pointer fields | the created fact is an ordinary fact from then on (GR-50); its position rides its creation entry and is not re-pointed (§9 item 14) |
| Move a fact to another section | the relationship route, as build step 4 shipped it (GR-24) | written by the Section dropdown (GR-31); the only legal carrier (GR-47) |
| Change a section's parent | the same relationship route; refused when the target is the section's own descendant (GR-24, GR-29) | written by the parent dropdown inside the Sections panel (GR-31, GR-48); never a field correction (GR-47) |
| Fix a section's kind | `verdict corrected` on the section's kind | the server already accepts this (GR-30) |
| Mark a fact PHI | `verdict corrected` on the PHI field and its type, plus the token in the log | GR-35; shape settled in the token audit, §10 step 4 |
| Edit a PHI fact afterward | the ordinary `corrected` entry; the fact moves to the token for the new value | ~~GR-40: no new token for an edit~~ superseded by PACKAGE_DESIGN OR-18 i (GR-41 stands: no interim) |
| Delete an atom, relationship or section (GR-13) | `verdict rejected`, no reasons | `reasons`, `reason` and `rationale` all retire for now (GR-18, §3); the object stays visible in the Deleted group (GR-49) |
| Restore a deleted object | `remove`, `target { entity: amendment, id: <the rejected entry> }` | the reviewer withdraws their own delete; the object returns unvetted (GR-49); same withdrawal shape as un-vet (§4.1) |
| Create a row (GR-14) | `add`, discovery namespace: `class: table_row`, `table_id`, `row_index`, `section_id` | §10 step 5 |
| Put an atom in a row | `verdict corrected` on `table_cell_ref`, `new_value { table_id, row_index }` | §10 step 5 |
| Move a row to another section | `verdict corrected` on the row's add, `target { entity: amendment, id, field_path: section_id }` | §10 step 5 |
| Remove a row | `remove` on the discovery or relationship id, no reasons | §10 step 5 |
| Fix or create a relationship | `corrected` on `source` / `target` / `kind`, `rejected` then `add` where cardinality forbids; `add` with value `relationship_authored` | |
| Lock, unlock | `flag reviewed` (provenance §6.1); `flag unlocked` | the lock triggers the rebuild |

The reviewer's "Withdraw" on their own creation is gone: the X is the delete for a created fact like any other (GR-50), and the Deleted group's Restore is the way back (GR-49).

`row_in_table` and `table_in_section` are never written by the reviewer: the rebuild derives them from row entries and cell refs (§6.2), absorbing the Sprint 10 intent for both. Sprint 10 keeps the Worker's own emitters at ingest, the cell id rule and cell grading (`F-NEW-SX` narrows to cells), and PACKAGE_DESIGN §6's ground-truth-only units.

## 3. Delete: no reasons for now (GR-18)

The GR-13 "Are you sure you want to delete?" dialog is Cancel and Delete only. No reason list is shown or collected; `grading_vocabularies.delete_reasons`, every code in it (`not_in_document`, `not_a_fact`, `duplicate`, `fragment`, `no_fitting_kind`, `not_related`, `other`), and the `fp_*` taxonomy (`F-NEW-TC`) are removed from the design entirely, not just deferred. Older `fp_*` entries fold as `rejected`.

A delete is visible after the fact, not silent: the object sits in the Deleted group with a Restore control (GR-49).

A reviewer-supplied delete reason, including a `no_fitting_kind` signal for INGEST_VOCABULARY_DESIGN's off-list census, is a parked idea with no trigger to bring it back (§9).

## 4. Vetting, un-vetting and the fold (replaces v1.2 §6's buckets)

These are progress counts. They are not scores and nothing derives a score from them (§5). Per class C, folded to a position P (one fold rule, v1.2 §4): instances_C, every core instance minus synthesized atoms; rejected_C, whole-object head `rejected`; corrected_C, not rejected and any head `corrected`; accepted_C, neither and whole-object head `accepted`; unvetted_C, the rest; discoveries_C, live reviewer adds (not walker adds). The console and the lock header read these counts; the lock stores progress (§6.1).

**4.1 Un-vet, restore, and the fold (proposal).** Unchecking writes `remove` naming the accepted entry's `amendment_id`, no reasons: the reviewer withdraws their own entry. Restore (GR-49) is the same shape one verdict over — `remove` naming the reviewer's own `rejected` entry — and the object comes back unvetted, because the withdrawal leaves nothing on its key. The fold gains one pre-pass: collect the ids such removes name, skip those entries, then newest-wins. The atom's head falls back to whatever else is on its key (a correction stays; nothing, and it is unvetted again). Vetting never changes the build (§6.2), so the rebuild pays nothing for un-vet; a restore does change the build, by putting the object back in it. Validator: the named entry must be a live reviewer `accepted` or `rejected` in this log. Cost: the pre-pass in three folds (server, console, phone at sprint 9) under one shared fixture, one validator rule, `judged` reading the pre-passed fold. Rejected: a fourth verdict value, which breaks PACKAGE_DESIGN §6's fixed three.

## 5. Derived error classes — retired (GR-27, 2026-09-17)

Retired: counting the reviewer's log entries as a score was inverted. Scoring is truth-versus-candidate: the corrected package is the ground truth (PACKAGE_DESIGN §7), and the bakeoff scorer (VENDOR_ABSTRACTION_DESIGN §4.1) compares any candidate package against it; GR-6 retires with this section. The review console shows reviewer progress — vetted N of M, entries since lock, lock state — never scores; the lock stores progress, not scores. Scorer spec pass owed in VENDOR_ABSTRACTION_DESIGN §4.1 (ROADMAP F-NEW-TT).

The owner's own statement of the model, verbatim:

> "we're creating groundtruth then testing that groundtruth against ingests, either version / prompt engineering testing or bakeoffs. I don't see a use-case to manually score AI."

And on the axes:

> "I want the design to accommodate infinite axis scoring at any vector."

So: one record per matched or unmatched instance, carrying every known dimension; any slice is a count over those records; no instance may cite a design list to refuse an axis.

## 6. The lock and the stored corrected package (GR-16; amends v1.2 §4 and §7)

**6.0 Per save, and at lock (GR-39).** Two things happen at two different moments and neither replaces the other. Every save appends one entry, bumps the amendment version and the package checksum — that is the save's whole visible effect, and it is what the re-read paints (GR-10). The totality step is the lock: the full rebuild from original plus log, stored once, under its own checksum (§6.1, §6.2). Re-affirmed after review 2026-09-18: a per-save version bump is not a per-save rebuild.

**6.1 What the lock writes.** One request. The server builds the corrected core (§6.2), writes it to R2 at `documents/{record_id}/{package_id}/corrected/{amendment_version}/core.json`, then appends `flag reviewed` with `provenance { progress, corrected_core_hash, rebuild_version }` in one transaction; a failed build appends nothing. `document_packages` gains `corrected_core_r2_key`, `corrected_core_hash`, `locked_at_version`; the versions ledger row gains `corrected_core_hash`. Every build is kept (R15); the original core never changes. The lock refuses, on screen, while any atom is unvetted, the control reporting the count (GR-17; "accept all remaining" is parked, §9). An object in the Deleted group is not unvetted and does not hold the lock: its head is the reviewer's own `rejected` (GR-49). On a PHI fact with no token, the lock refuses (`package_lock_phi_untokenized`, shipped 2026-09-22); §10 step 4 and `F-NEW-SW` close with it (§9 item 6).

**6.2 The rebuild rule.** Deterministic, pinned by a fixture beside the fold's. Fold to the lock; drop rejected atoms, relationships and rows — a restored object is not rejected at the fold and stays in (GR-49); apply every `corrected` head; add live reviewer discoveries as atoms and rows with `origin: reviewer` and their log ids; apply relationship adds and removes; rewrite `section_id`, `parentId` and `table_cell_ref` from the entries that won — for `section_id` and `parentId` that means the relationship entries alone, since no other carrier is legal (GR-47); emit `row_in_table` and `table_in_section` from rows and cell refs; re-derive `source_region` and `source_text` for a re-pointed atom (GR-23); drop nothing else. Sort atoms by `(page, line, word_start)`, unlocated last within their page; sections by first line; relationships by source. Vetting changes nothing here.

**6.3 Lock state and readers.** Lock state is the newest of `reviewed` and `unlocked` in the log. While locked, the write route refuses reviewer entries (`package_locked`, with an Unlock button), and every reader is served the corrected list alone (GR-17): its own hash, its own integrity checks, the original core withheld from the download though it stays stored on the server behind it, for history and comparison. Unlock appends `flag unlocked` and nothing else: the build stays stored, `corrected` is no longer served, export is withheld, readers get the original — alone, as before lock — until the next lock. The console never reads `corrected`: between saves it shows the original with the whole log folded in, re-read after every append, the rebuild's fold minus sorting and writing. Each atom shows its state from that fold: vetted, corrected (per field), deleted (in the Deleted group, GR-49), created (the "created" marker, GR-50), in a row, in-flight. A header shows reviewer progress, never a score: "Locked at 1.n" or "Unlocked, N entries since".

## 7. The console surface (replaces v1.2 §5's "Views" and v1.3 §7's tree)

Everything here is a trial: nothing is final until the owner has stepped through it on screen (GR-37). The section boxes and the Sections breakout are already judged not-yet-usable and get their own sharpening sprint (GR-48, §10 step 6).

**The fact's detail panel (GR-32).** Top to bottom: the green checkmark and the X (GR-28); the ID line (GR-43); the fact's text as a non-editable field with an edit checkbox beside it that opens a field pre-filled with the current text; Kind, showing the current kind with a grouped dropdown next to it, main headings outdented and kinds indented; the Section dropdown (GR-31); "PHI" with a checkbox, revealing a PHI type dropdown next to it when checked (GR-35); then only the fields that apply to this fact's kind, per the server's declaration (GR-33, GR-46) — date role only on date facts, subtype only on the kinds that carry it. Gone from the panel: Position, "Record correction", the "SAVED / unvetted" row, column role, the dead lab-value and address rows, the "Status: awaiting_review" line, and "Move to…" (GR-42). Extracted text and source text are one stored thing and the panel shows it once.

**A created fact is a fact (GR-50).** Same row in the list, same detail panel, same controls, same filters, same Deleted group; only a small "created" marker sets it apart. "Withdraw" is gone — the X is its delete. Two things about it are narrower than an ingested fact, and they are findings, not design: it cannot be re-pointed, because its position rides its creation entry (§9 item 14), and the server's off-kind field check does not bind on it, because it has no kind in the core index (§9 item 15).

**Saving (GR-34, GR-45).** Every change saves on its own the moment it is made. A typed field saves when the reviewer leaves it or presses Enter. Unchecking the edit box without saving discards the typing. There is no draft and no "Record correction" button. Every save bumps the version and the checksum (GR-39) and paints only from the re-read (GR-10). A change made while a save is in flight is refused on screen with "Saving, one moment" — no queue, nothing silently dropped (GR-45).

**The Sections panel (GR-30, GR-48).** Replaces the tree, and sits where the tree was: beside the list. The "Ground Truth" top-bar tab is removed. Each section is a box drawn on the page image, computed in the console from the lines the section covers — one box per page where a section spans pages. Clicking a section filters the list to it. Section detail renders on the picked row inside the panel: the AI's section kind with a dropdown to change it (the server already accepts the correction) and its parent section as a dropdown; a parent that is the section's own descendant is refused, in the console and on the server (GR-29). Neither dropdown writes a field correction (GR-47). "Move to…" and drag are gone (GR-31, GR-42).

**The Deleted group (GR-49).** Deleted facts, links and sections stay visible, grouped at the bottom of the list, each with a "Restore" control that withdraws the reviewer's own delete; the object comes back unvetted. The checkmark never revives anything: the console refuses it on a deleted row, and the server refuses an `accepted` over a live reviewer `rejected` head (`amendment_accept_on_rejected`).

**Filters.** The Kind dropdown lists the kinds the current section filter shows; Status and PHI-only stay. Class bar, grouped kind picker, per-class groups, thumbs and "Accept N shown" go.

**PHI (GR-35).** Checking PHI turns the fact red everywhere at once: card stripe, page box, grouping, PHI-only filter. ~~Editing the fact afterward updates the tokens table behind its existing token and mints nothing new (GR-40).~~ Superseded by PACKAGE_DESIGN OR-18 i: a value edit moves the fact to the token for the new value.

**The page image and word selection (GR-36).** Selectable words set position (GR-21); a cross-line selection is refused on screen. In the word tool: the checkmark saves the selection as the fact's new position; the X cancels the selection and turns the tool off; the back circle undoes one position save — one step (GR-44) — by writing a new entry restoring the prior position, and refuses on screen when that prior position was unlocated ("The earlier position was unlocated; nothing to restore"), never restoring part of it and never failing quietly. "Re-point #N here" and "Clear" are gone. The re-read after a 201 remains the only painter.

**Table rows.** §10 step 5, audit first (GR-14).

## 8. PACKAGE_DESIGN amendment, files under F-NEW-SV

Not applied to `PACKAGE_DESIGN.md`; recorded for the amendment pass F-NEW-SV owes it. (§7 and §9's sprint 7 row of PACKAGE_DESIGN were corrected in place 2026-09-18 under GR-27; the rest of this list is still owed.)

- §1: a fifth member, `corrected`, the build of §6.2, replaces `core` in the served package once locked (GR-17); before lock the served package is `core` alone, as today. The manifest gains `lock { locked_at_version, corrected_core_hash, rebuild_version }`. `core` and `core_hash` stay on the object, server-side, for history and comparison, but drop out of the download once locked; `package_hash` and the rest of the integrity checks apply to whichever list is being served — `core` before lock, `corrected` after.
- §0.1, §2.4, R5: the corrected core is a projection of original plus log, never the source. Once locked, a returning package carries `corrected` alone, under its own hash; before lock it carries `core` alone, unchanged. The phone builds views from whichever is served; the log stays history behind it, and the original stays stored behind the corrected package for comparison.
- §3: `flag` gains `unlocked`; a `remove` may target the reviewer's own `accepted` or `rejected` entry (§4.1, GR-49). (Reviewer rejects carry no `reasons[]`: GR-18.)
- §4: the columns, ledger column and R2 key of §6.1.
- §5, §6: the per-kind field declaration of GR-33 and GR-46, with its schema version bump — shipped as `ATOM_KIND_FIELDS` at `SCHEMA_VERSION` 24.
- §9: sprint 7 reads as §10 here; sprint 8 exports only a locked package; sprint 9 displays `corrected`, the log as history; sprint 10 as narrowed in §2. ROADMAP's sprint 7 line goes stale with it.
- GR-2 and GR-3 narrow: appends stay real time and each bumps the version (GR-39); the lock is a build, not a draft; the phone reads the build instead of reconstructing.

## 9. Findings (stated, not resolved)

Defects in the shipped console:

1. ~~`appendInFlight` drops a second click without a word.~~ **Resolved** at build step 1 (GR-45: the refusal is on screen, "Saving, one moment", no queue). The v1.4 line numbers (`adi-console/app.js` 1021, 4112) are stale.
2. "Record correction" returns silently on an empty draft. Removed with the button itself at §10 step 1 (GR-34).
3. The class bar shows "table_row 15" for a package with zero rows: `instancesOf` counts `parsed_pages[].tables[].rows` while the served `table_row` declaration defines a row by cell refs on a minted table; the server's core index counts both. One definition must serve count, list and validator. Bears on §10 step 5.

Open:

4. **Current dictionary (v1.2 §9.4) versus `no_fitting_kind`.** Moot for now under GR-18 (§3): an off-list kind is refused, so a real thing with no kind can only be deleted, with no reason captured. Whether a returning reason feeds the misfire census or `F-NEW-SV`'s heal-by-class path stays unruled until item 12 resolves.
5. ~~**The list-only hold** (`LIST_ONLY_CLASSES`).~~ **Resolved**: the hold is retired, and §10 step 3 shipped over the same ground.
6. **`F-NEW-SW`.** **Resolved 2026-09-22** — `package_lock_phi_untokenized`, shipped: the lock refuses a PHI fact with no live token. GR-35 rules the mark: it computes the Worker's token, logged like any other reviewer change; GR-40's edit rule is superseded by the shipped rule (PACKAGE_DESIGN OR-18 i): a value edit moves the fact to the token for the new value, an unmark retires the token's use, a re-mark revives the same uid. The discovery declaration still has no `is_phi` / `phi_type`.
7. **Schema bumps needed** (`SCHEMA_VERSION` 24 today, the per-kind field declaration shipped at that bump): `unlocked`; discovery PHI fields (item 6); discovery row fields open, with §10 step 5; `origin: reviewer` and `tables[]` on the corrected core, or the phone's drift beacon fires.
8. **Unchecked corrections.** A `table_cell_ref` naming a reviewer-minted table needs the same check.
9. **Unlisted classes** (span, cell, code, inventory): where they show, now that the tree is gone (GR-30, GR-48), is unruled.
10. **Owner's calls in §6.** The sort key. (Refusing the lock on unvetted atoms is ruled: GR-17.)
11. **Parked: "accept all remaining."** A bulk action to vet every unvetted atom at once, raised so GR-17's lock-refuses-while-unvetted rule doesn't force clicking through a large document one atom at a time. Parked, not designed or built.
12. **Parked: a delete-reason mechanism.** GR-18 drops reasons from delete entirely, including `no_fitting_kind` and the `fp_*` taxonomy (§3); item 4 waits on it. Parked, no trigger to bring it back.
13. **Staging Pages alias, drift.** A staging Pages alias for the ADI console, deployed 2026-09-16, was drift: GR-38 rules one console deployment only, on `main`. Removed as operator cleanup, not build-order work. Unchanged: still owed as cleanup.
14. **A created fact cannot be re-pointed.** Its position rides its creation entry, so the word tool's re-point has nothing to correct on it. Stated as it stands after step 3; not ruled either way.
15. **The server's off-kind field check does not bind on a created fact.** `amendment_field_not_on_kind` (GR-46) resolves a fact's kind through the core index, and a created fact has no entry there. The refusal therefore protects ingested facts only.
16. **Per-kind subtype VALUE lists still live in the prompt.** GR-46 puts structure in the schema and values in the dictionary; the value half is owed. ROADMAP item, next pass.

## 10. Build order (replaces v1.4 §10)

Each step ships alone, suite green, staging then production. **No interim or temporary builds (GR-41):** a feature is scoped to land whole at its step or it waits — scaffolding is the main source of drift. Close condition for a console step (GR-51): Claude Code drives the exact saves the panel sends against staging data and proves them in the log, suite green; the on-screen proof is the owner stepping through it (GR-37). No browser automation. One console, on `main`, pointed at staging data (GR-38).

1. **The fact detail panel (console only) — SHIPPED 2026-09-18** in `recordhealth-api`: `f25132b`, `36cc353`, `cfe412e`, with the fix pass `8fb256c` and `9b94efb`. GR-32's layout and its removals with the ID line kept (GR-43), GR-34's save-on-change with "Record correction" and the draft gone, GR-45's in-flight refusal, GR-36's word-selection controls with the back circle at one step (GR-44), "Move to…" off the panel (GR-42). See `recordhealth-api/docs/archive/SESSION_LOG.md`.
2. **Server: per-kind field declaration and the descendant refusal — SHIPPED 2026-09-18/19** in `recordhealth-api`: `5d99e4e`, `ace2e5d`, `a98dcb4`, at `SCHEMA_VERSION` 24. GR-33/GR-46's `ATOM_KIND_FIELDS` with `amendment_field_not_on_kind` on the write route and the console rendering from the declaration alone; GR-29's server-side descendant refusal; GR-47's `amendment_move_rides_relationship` closing `section_id` and `parentId` to corrections. See `recordhealth-api/docs/archive/SESSION_LOG.md`.
3. **The Sections panel and the section dropdowns — SHIPPED 2026-09-19** in `recordhealth-api`: `c29fc78`, `8524a1d`, `93d58b5`, `5955aca`; console deployment `grading-v1.4-step3`. GR-30's boxes on the page image and click-to-filter, GR-48's panel beside the list with section detail on the picked row and the "Ground Truth" tab removed, GR-31's Section dropdown on the fact, GR-49's Deleted group and Restore with `amendment_accept_on_rejected` behind it, GR-50's created-fact-is-a-fact; the tree, "Move to…" and drag removed everywhere (GR-42). Close met on staging: staging closes on `64d10137`, the lock half on `9e16cb41` re-locked at 1.135. See `recordhealth-api/docs/archive/SESSION_LOG.md`.
4. **PHI.** In order inside the step: the red-everywhere fix (GR-35), then the token audit, then the token build, whole (GR-41). Close, as shipped 2026-09-22: on staging, a fact marked PHI is red in card stripe, page box, grouping and PHI-only filter at once; a marked fact carries the Worker's token in the log, computed by the shared mint function over the live published dictionary, `ADI_TOKEN_SECRET` and the manifest's `user_subject` (api `c5cb0c8`; `package-tokens.mjs` derives nothing of its own); the mark refuses whole with 409 `phi_mint_subject_missing` (a per-user type, no `user_subject`) or 503 `dictionary_unavailable` (unpublished dictionary, or a type without its prefix or shared flag); editing the fact afterward moves it to the token for its new value, an unmark retires the token's use and a re-mark revives the same uid, proven live 2026-09-24 (PACKAGE_DESIGN OR-18 i, superseding GR-40's edit-behind-the-token rule); the lock refuses a PHI fact with no live token (`package_lock_phi_untokenized`).
5. **Table rows, audit first.** GR-14's row authoring: the §2 row entries, the declaration fields §9 item 7 owes, and §9 item 3's one definition of a row for count, list and validator. Audit before build (the owner: grading a real document needs rows).
6. **Sharpening sprint: the Sections panel and the boxes.** Owner-led on screen. GR-48: the section boxes and the Sections breakout are not yet judged usable; this step follows step 4.

## 11. Rulings log

- GR-8 through GR-11: ruled 2026-09-15, first live session. GR-12 through GR-16: ruled 2026-09-15, second session. GR-17: ruled 2026-09-15, third session. GR-20, GR-21, GR-22, GR-23: ruled 2026-09-16.
- Build step 1 (v1.3 §10 item 1) shipped 2026-09-15/16 in `recordhealth-api`, commits `3d4a6cd` through `f85a17d`; see that repo's `docs/archive/SESSION_LOG.md`.
- Build step 2 (v1.3 §10 item 2) shipped 2026-09-16 in `recordhealth-api`, commits `22cdd7d` through `ed98109` plus `b9ad031`; deployed to staging and production, live close met on staging; see that repo's `docs/archive/SESSION_LOG.md`.
- GR-22 (2026-09-16): field corrections and relationship corrections are applied from reviewer-authored entries only, in the rebuild, the server fold and the console fold; an entry from any other author never overrides a reviewer's correction. Newest by log position among reviewer entries.
- GR-23 (2026-09-16): a re-point recomputes the atom's `source_text` from the newly selected words; an unresolved pointer keeps the atom's existing text and loses its span (GR-21 unchanged); when a hand text correction and a re-point both exist on one atom, the newer by log position wins; reviewer-created atoms take their text from the discovery's value.
- Build step 3 (v1.3 §10 item 3) shipped 2026-09-16 in `recordhealth-api`, api commits `9ce1800..5470441` and `a54288f`, console commits `fae1319..cf94eac` and `2b074fc`; `SCHEMA_VERSION` 23, `rh.rebuild/3`; live close met on staging (package `9e16cb41`); see that repo's `docs/archive/SESSION_LOG.md`.
- GR-24 (2026-09-17): moves are written through the relationship route only; created atoms are valid endpoints; a section is never moved under its own descendant (console refusal — extended to the server by GR-29, and the other carrier closed by GR-47).
- GR-25 (2026-09-17): a move-back withdraws the reviewer's own reject and writes no accepted; the withdrawal counts as a move at its own log position. Confirmed consistent with GR-28 and standing.
- GR-26 (2026-09-17): containment kinds count reviewer-authored entries only (adds, removes, corrections, accepts, rejects) in rebuild, server fold and console fold; other authors' non-containment kinds untouched.
- **The reason behind GR-22 and GR-26, recorded 2026-09-18:** a new process or a runaway process must never write a log item that becomes ground truth. Only the reviewer's own entries correct ground truth.
- GR-27 (2026-09-17): the §5 retirement and open-axes ruling (§5), with the owner's own words on the model quoted there.
- Build step 4 (v1.3 §10 item 4, the tree) shipped 2026-09-17 in `recordhealth-api`, commits `d919abb..3df7042`, `rh.rebuild/4`; see that repo's `docs/archive/SESSION_LOG.md`. The tree it shipped is removed by GR-30; the relationship route it established is what GR-31's dropdowns write.
- GR-28 through GR-37 (2026-09-17/18): the console's shape — checkmark and X meaning (GR-28), server-side descendant refusal (GR-29), the tree replaced by the Sections surface (GR-30), dropdowns instead of "Move to…" and drag with rows deferred (GR-31), the fact detail layout and its removals (GR-32), server-declared per-kind fields (GR-33), save-on-change (GR-34), PHI red everywhere and the token on mark (GR-35; the Worker's token since OR-18 g), the word-selection controls (GR-36), the whole layout a trial until the owner has stepped through it (GR-37). Applied to §1, §2, §6.1, §7, §9 and §10.
- GR-38 (2026-09-18): the "no staging console" question is ruled. There is one ADI console deployment, on `main`; there is no staging console. The staging Pages alias deployed 2026-09-16 was drift, not a second deployment, and is removed as operator cleanup, not build-order work (§9 item 13). §10's close conditions for the console-only steps are rewritten to a live check on the one console, pointed at staging data — sharpened by GR-51.
- **v1.4 §10 build step 1 (the fact detail panel) shipped 2026-09-18** in `recordhealth-api`, commits `f25132b`, `36cc353`, `cfe412e`, with the fix pass `8fb256c` and `9b94efb`; see that repo's `docs/archive/SESSION_LOG.md`.
- **v1.4 §10 build step 2 (per-kind field declaration, the descendant refusal, the move carrier) shipped 2026-09-18/19** in `recordhealth-api`, commits `5d99e4e`, `ace2e5d`, `a98dcb4`; `SCHEMA_VERSION` 24; see that repo's `docs/archive/SESSION_LOG.md`.
- **v1.4 §10 build step 3 (the Sections panel and the section dropdowns) shipped 2026-09-19** in `recordhealth-api`, commits `c29fc78`, `8524a1d`, `93d58b5`, `5955aca`; console deployment `grading-v1.4-step3`; close met on staging — staging closes on `64d10137`, the lock half on `9e16cb41` re-locked at 1.135; see that repo's `docs/archive/SESSION_LOG.md`.
- GR-39 through GR-51 (2026-09-18/19): per-save versioning re-affirmed with the lock as the totality step (GR-39), the PHI edit updating the tokens layer behind the existing token (GR-40, superseded by OR-18 i), no interim builds of any kind (GR-41), when "Move to…" and drag come out (GR-42), the ID line stays on the fact panel (GR-43), the back circle at one step with an on-screen refusal for an unlocated prior position (GR-44), the in-flight refusal with no queue (GR-45), structure in the schema per kind and values in the dictionary (GR-46), moves on the relationship carrier only (GR-47), the Sections panel beside the list with the "Ground Truth" tab removed and a sharpening sprint owed (GR-48), the Deleted group and Restore with the checkmark never reviving (GR-49), a created fact is a fact (GR-50), and the console step's close condition (GR-51). Applied to §1, §2, §6, §7, §9, §10 and §11.
- OR-18 (PACKAGE_DESIGN) moved minting to the Worker (shipped 2026-09-22 through 2026-09-24); the ADI mint re-keyed onto the Worker's token function (api `248c761`, `c5cb0c8`, `43904e9`), and the ADI receive heals nothing.

**UNRULED — recorded, not to be built:**

- ~~Whether a lock refuses on unresolved PHI flags. Stays under `F-NEW-SW` (§9 item 6). GR-35 rules only that the lock must not pass silently.~~ Ruled: the lock refuses (`package_lock_phi_untokenized`, shipped 2026-09-22). No longer unruled.

- Open: §9; the codes in §3; §4.1 and §6.2's sort key as proposals; "accept all remaining" parked (§9 item 11).
