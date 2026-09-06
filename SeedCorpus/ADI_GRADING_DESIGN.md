# ADI Grading Design

Status: design v1.1 (shape, not spec), owner rulings applied, the storage + write + scores half shipped 2026-09-03 (sprint 6, §8); the console half is sprint 7, resumes at step 3 now that R2 has shipped (RELATIONSHIP_DESIGN.md §12)
Date: 2026-09-03; v1.1 supersedes v1.0 in place, 2026-09-05 (relationship model pointer); §3's section-addressing line corrected in place, 2026-09-06 (R2 shipped)
Repo home: `RecordHealth.IO/SeedCorpus/ADI_GRADING_DESIGN.md`

Owns the reviewer grading surface for document packages: what a reviewer can judge, how each judgment is recorded, how a document is marked done, and how scores are computed. Supersedes `GRADING_TOOL_DESIGN.md` (v1.0, now historical) for the grading surface; the F1, IoU and NDC formulas move here (§6). Package structure, amendment wire shape, and gradeable-unit list stay in `PACKAGE_DESIGN.md` §1, §3, §6; this doc points, never restates. Gates package sprints 6 and 7 (PACKAGE_DESIGN §9).

**Owner rulings, fixed points (2026-09-03):**

- GR-1. A verdict has exactly one home: the package's amendment log. No verdict, correction, or discovery is stored anywhere else. `grading_submissions` is retired (§4).
- GR-2. Grading is real time. Every reviewer action appends to the log the moment it happens. There is no draft, no browser-held workspace, no lock-in step.
- GR-3. Comprehensiveness test for every piece: a graded package exported from the ADI and imported to a phone shows the original plus every reviewer change, nothing reconstructed. Anything that works only inside the console fails.
- GR-4. One log entry per judgment. A correction is a `corrected` verdict carrying the new value in the same entry, never a verdict entry plus a separate value entry.
- GR-5. What is gradeable comes from the server's published entity schema (PACKAGE_DESIGN §5, the per-field `grading` capability), never from a list kept in the console. "Accept all" applies to exactly what is shown in the current view, one entry per item. Rows, cells, and the links between things are each judged on their own.
- GR-6. Scores are computed by the server from the log on demand, per class. Nothing stored that can go stale.
- GR-7. "Done" is a `reviewed` marker appended to the log. Export offers only packages carrying one. Grading may continue after; a later marker supersedes.

---

## 1. Framing

The reviewer never edits the core. Every judgment is an amendment (PACKAGE_DESIGN §3) with `author: adi_reviewer`. The log the phone reads back (sprint 9) is the same log the console writes, so the console has no private state worth losing. This replaces the three-layer model (pipeline output / browser workspace / locked submission) in `RecordHealth_App/docs/ARCHITECTURE.md` §8.4, which is retired with this design.

Silo discipline and the reviewer-authority rules from GRADING_TOOL_DESIGN carry over unchanged: graded packages are a measurement instrument, never training input to Bedrock; `reviewer_authority` travels on every entry.

---

## 2. The reviewer's flow

1. Open a document; the console lists its packages (one per ingest); pick one. The view is the core with the user's amendments folded in (R10: they always travel with the submission), so the reviewer judges what the user actually sees.
2. Judge things. Each click appends one entry. Changing a judgment appends a newer entry; the older one stays and "history" shows it. There is no undo, only supersession.
3. Go fast: "Accept N shown" accepts every item currently visible in the right-hand list that has no ruling yet. Scope is whatever the view is showing at that moment: the current page, a filter to one section, one kind, PHI only, ungraded only, or the whole document with no filter. Items hidden by a filter or on another page are untouched. The button carries the count.
4. Fix the misses individually: reject, correct (new value or new kind), or draw a discovery for something the pipeline missed.
5. Press "Mark reviewed". One marker entry lands. Scores are shown from the log at that moment. Keep going if needed; mark again.

Two reviewers on one package append to the same log; last entry per target wins in the folded view, both stay in history. Arbitration between reviewers is out of scope (GT.2 in ROADMAP stays parked).

---

## 3. Grading entries

All entries use the PACKAGE_DESIGN §3 shape. Grading adds nothing to the shape; it fixes how the fields are used.

**Target addressing.** `target` names the thing by its identity inside the core, never by an ADI row id: atom by `atom_id`; section by its id (RELATIONSHIP_DESIGN.md §10); the projection keeps `(package_id, ordinal)` as its row key; relationship by entry id (RELATIONSHIP_DESIGN.md §7); table row by `(table_id, row_index)`; cell by `table_cell_ref`; span by `(atom_id, span index)`; inventory by section; code by `(atom_id, kt_coding path)`; a user amendment by its `amendment_id`. Projection rows carry these ids so the console can always write a core-addressed target.

**Ops used by grading.**

| Reviewer action | op | value | other fields |
|---|---|---|---|
| Accept | `verdict` | `accepted` | `batch_id` when from "Accept N shown" |
| Reject | `verdict` | `rejected` | `reason` from the reject taxonomy |
| Correct value or kind | `verdict` | `corrected` plus `{ field_path, new_value }` | `reason` optional |
| Discovery (missed thing) | `add` | the new entity, typed by the schema, with geometry | id minted in the discovery namespace |
| Withdraw a discovery | `remove` | | targets the discovery id |
| Judge a user amendment | `verdict` | accepted / rejected | targets the amendment id |
| Mark atom as PHI (or un-mark) | `verdict` | `corrected` plus `{ field_path: is_phi/phi_type, new_value }` | the ADI mints a token in its namespace and adds it to the package's tokens layer (PACKAGE_DESIGN R16) |
| Missing token on receive | `flag` | `phi_token_missing` | author `system`; a PHI atom with no token or no `phi_type`; appended by the receive route (the phone writes the same flag at seal), `reason` is the validator's own word, resolved by the reviewer |
| Unexpected token on receive | `flag` | `phi_token_unexpected` | author `system`; a token or `phi_type` on an atom the core does not mark PHI; same route, same resolution |
| Mark reviewed | `flag` | `reviewed` | `reviewer_authority`, scores snapshot as `provenance` (informational, not authoritative) |

`batch_id` is a new optional field in `provenance`: all entries from one "Accept N shown" click share it, so history reads "accepted together with 36 others on page 3". It does not change how any reader interprets the entry; each entry stands alone (GR-5).

**Versioning.** Each entry bumps `amendment_version` (1.n). Under real time this counts clicks, which is correct: the manifest's `amendment_version` is the length of the log. Each append also produces a new `package_hash` (PACKAGE_DESIGN R15); the ADI records `(amendment_version, package_hash, recorded_at)` per version so any transit can be checked against the version it claims.

---

## 4. Storage on the ADI

Under PACKAGE_DESIGN §4 shape (b): the log is the `amendments` JSONB on `document_packages`, append-only by handler discipline plus trigger. One write route, `POST /v1/admin/packages/:package_id/amendments`, accepting one entry or a batch (the "Accept N shown" case); the handler validates every entry against the schema's grading capability for its target class, the verdict allowlist, and the reject taxonomy, and refuses the whole batch on any failure.

**`grading_submissions` is retired.** No lock-in means no submission. The table's `verdicts`, `discoveries`, `phi_verdicts`, `phi_discoveries`, `section_verdicts`, `section_discoveries`, `summary` columns had no other purpose. The migration file PACKAGE_DESIGN §4 planned for the two Neon-only columns is not written; the table is dropped in the sprint 6 baseline. `GET /v1/admin/grading/stats` and `/submissions` are replaced by §6's routes. F-NEW-AF (stale premise about those columns) closes with the table. Both ADI databases are empty; wipe-and-rebuild costs nothing.

**Reads.** The console reads the package (manifest, core, tokens, log) through one route and folds the log client-side for display, the same fold the phone does (PACKAGE_DESIGN §3 "Views"). One fold rule, stated once in DATA_MODEL §7.13, implemented twice (Swift, console JS), pinned by a shared fixture.

---

## 5. The console surface

**What appears as gradeable** is read from `GET /v1/schema`: each entity's fields carry `grading: verdict | correction | authoring | none`. The console builds its right-hand list classes and its verdict controls from that. A class with `authoring` gets a draw tool for discoveries; `correction` gets the value/kind editor; `verdict` gets accept/reject only; `none` is shown but not judgeable. When the Worker emits a new class and bumps `SCHEMA_VERSION`, it is gradeable on the next console load with no console deploy. Hand-kept lists in the console (`SECTION_KINDS`, kind groups as presentation hints) retire where the schema or dictionary now covers them; F-NEW-HP closes.

**Classes and what "judge it" means for each** (PACKAGE_DESIGN §6):

- Atom (clinical, PHI): is this a real thing in the document, is the value right, is the kind right. Synthesized atoms are judged as synthesis and never enter extraction scores.
- Section: right kind, right extent, right parent.
- Table row: is this one row. Cell: right value, right column role. Judged separately from each other and from the atoms in them.
- Relationships: grading and authoring, RELATIONSHIP_DESIGN.md §7.
- Code (kt_coding) on an atom: right code.
- Geometry: the box is on the right spot (tolerance by IoU, §6).
- Section inventory: the section holds what the census says.
- User amendment: accept or reject the user's own change.
- Ground-truth-only classes (checkbox state, negation, strikethrough, handwriting, signature, true table structure): authored as discoveries; sprint 10 scope.

**Views.** Same three panels as today (thumbnails, page with overlay, list). List filters: page, section, class, kind, PHI only, ungraded only. "Accept N shown" sits at the top of the list and is scoped by the filters in force. Overlay draws boxes for the items in the list, coloured by class; discoveries thicker and dashed as today.

**PHI.** Real values are visible (R11, development-only posture, PACKAGE_DESIGN §8.4). The tokens layer supplies the reverse map; `review_phi_detections` and `phi_reverse_map` on the document row are gone.

---

## 6. Scores

Computed on request, never stored. `GET /v1/admin/packages/:package_id/scores` and `GET /v1/admin/grading/stats` (counts packages carrying a `reviewed` marker, per class aggregate).

Per class C over the folded log (newest entry per target):

- precision = accepted_C / (accepted_C + corrected_C + rejected_C)
- recall = (accepted_C + corrected_C) / (accepted_C + corrected_C + discoveries_C)
- F1 = 2 × precision × recall / (precision + recall)

`corrected` counts against precision (the pipeline was wrong) and for recall (it found the thing). Unjudged items are reported as a count, not scored. Geometry uses IoU in the core's page-normalised coordinate space; hit at IoU ≥ 0.5, partial 0.3 to 0.5. Value distance (NDC) classes: exact, minor (< 0.15 normalised edit distance), moderate (< 0.5), major. These three definitions are carried from GRADING_TOOL_DESIGN v1.0 unchanged and live here now.

The bakeoff resolver (VENDOR_ABSTRACTION §4.1) reads the same folded log; PACKAGE_DESIGN §7 unchanged.

---

## 7. Export and return

Sprint 8 exports a graded package: manifest and core unchanged, log as is. Only packages with a `reviewed` marker are offered. Sprint 9 on the phone folds reviewer entries like user entries, newest wins, history visible (PACKAGE_DESIGN §2.4, R5).

---

## 8. Effect on the sprint series (PACKAGE_DESIGN §9)

- Sprint 6 (api): **DONE 2026-09-03.** Baseline dropped `grading_submissions` and `review_phi_detections`; `document_packages.amendments` with the append-only trigger (four rules, all exercised live and refused); the amendments write route with batch validation, per-index refusal and optimistic concurrency on `amendment_version`; the package read route; and §6's two scores routes, computed on demand and stored nowhere. The planned verdict-columns migration file was not written, and `F-NEW-AF` closed with the table. One version per REQUEST rather than per entry (owner ruling) — `batch_id` is what groups a click. NOT implemented: §6's IoU tolerance and NDC value-distance classes, both per-item scoring the sprint-7 console computes. Detail: `recordhealth-api/docs/WORKER_ARCHITECTURE.md § Package receive and store`.
- Sprint 7 (api ADI): console rewired: schema-driven classes, real-time entries, "Accept N shown", "Mark reviewed", scores routes. Link authoring now ships per RELATIONSHIP_DESIGN.md §7 after R2, superseding the 2026-09-04 ruling that it shipped directly in sprint 7. Reviewer PHI marking ships here too (R16 / OR-16, ruled 2026-09-04): marking an atom PHI or un-marking it, with the ADI minting a token in its own namespace into the tokens layer, and resolving the receive route's `phi_token_missing` / `phi_token_unexpected` findings, which land and wait today. Close condition unchanged: one real document graded end to end with a non-zero F1.
- Sprint 8 (api): unchanged; export gated on the marker.
- Sprint 10 (api ADI): unchanged.

F-NEW-QK (panelHeaders newline) still must not rot past sprint 6.

---

## 9. Hard questions

1. **Click volume.** A 400-atom lab report accepted in one click appends 400 entries. The log grows by a few hundred KB per graded package. R14: watched via `package_size_bytes`, not ruled.
2. **Mis-click.** No undo; a wrong accept is corrected by a newer reject. History shows both. This is the price of GR-2 and it is the same rule the phone lives with.
3. **Two reviewers.** Newest wins per target. No arbitration surface (GT.2 parked).
4. **Schema bump mid-grading.** The core's `schema_version` fixes what is gradeable for that package; the console reads the schema at that version (`?version=`), not the latest.
5. **A user amendment and a reviewer correction on the same field.** Both in the log; folded view shows the reviewer's (newer). Sprint 9's phone view lets the user flip (PACKAGE_DESIGN §8.3).

---

## 10. Not in this design

No arbitration between reviewers. No reviewer accounts beyond the JWT role (AUTH-2 stays backlog). No user-facing ADI submission. No training-media export beyond the graded package. No ground-truth-only authoring before sprint 10.

---

## 11. Rulings log

- GR-1 through GR-7: ruled 2026-09-03 in chat; text above.
- 2026-09-05: relationship model ruled — `RELATIONSHIP_DESIGN.md`. §3 and §5 point there; sprint 7 link authoring re-scoped to ship after R2 (§8).
- Open: none at v1.1.
