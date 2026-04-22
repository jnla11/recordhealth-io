# ADI Phase Roadmap — Phase 2 Onward

**Status:** Draft v0.1 — rough roadmap, shape-of-things-to-come
**Created:** 2026-04-22
**Location at rest:** `SeedCorpus/PHASE_ROADMAP.md`
**Supersedes:** Phase 2–7 bullets in `TRAINING_MEDIA_DESIGN.md` §13
**Relationship to Phase 1:** `SeedCorpus/PHASE_1_DESIGN.md` is the authoritative spec for Phase 1. This document sketches Phases 2–6+ at enough detail to plan against, not enough to implement against. Each phase gets its own detailed design doc when its turn comes.

---

## 1. Purpose

This document exists so that partway through Phase 1, Jason and a fresh Claude instance can answer: "what comes after this, and why does it come in that order?" Phase 1 is detailed and committed. Everything beyond Phase 1 is reshapeable. This roadmap captures the current best thinking without pretending it's locked.

A phase here = a coherent unit of ADI capability that produces value on its own. A phase is not a sprint; most phases decompose into 2–6 mini-sprints when their detailed design doc lands.

Priority ordering is provisional. Each phase has dependencies flagged; the dependency graph is what's real, the ordering is negotiable.

## 2. Phase map

```
Phase 1 ──┬── Phase 2 ──┬── Phase 5 ──── Phase 6+
          │             │
          └── Phase 3 ──┤
          │             │
          └── Phase 4 ──┘

AUTH-2 (lands independently, probably between P2 and P3)
iOS pre-App-Store (independent track, off-goal for training media)
DATA-1 (promotes if Phase 1.4 debugging surfaces it)
```

Phase 1 blocks everything. After Phase 1, Phases 2/3/4 can proceed in any order — they don't block each other. Phase 5 wants at least Phase 2 landed to have code-verdict data, and benefits from Phase 4 (negative space) being landed so the export covers all signal types. Phase 6+ is shaped by what Phase 5's bake-off reveals.

## 3. Phase 2 — AI ontology + code-level grading integration

### 3.1 Goal

Wire the existing GT-1.6d ontology backend (`/v1/admin/lookup`, `ontology_traces` table) into the Phase 1 drill-down. The canonical_codes block becomes interactive: reviewer confirms/amends/rejects AI-suggested codes, reasoning and caveats are surfaced via the `i` button pattern (CLINICAL_SHAPE_DESIGN §7.3), verdicts accumulate as training signal.

Also lands the AI-assisted kind suggestion deferred from Phase 1 — a narrow classifier call returning ranked kind guesses that layer on top of Phase 1's rules-based ranking.

### 3.2 What ships

- Interactive canonical_codes UI inside the drill-down's code block (slot was reserved in Phase 1 §5.3)
- `i` button per code: opens popover with `reasoning` and `caveats` from the JSONB attestation record
- Per-code verdict: confirm / amend / reject, persisted in L2 workspace alongside atom verdicts
- On-demand AI lookup trigger: "Get suggestions" button when canonical_codes is empty or reviewer wants alternatives
- AI-assisted kind suggestion: async call fires on drill-down open (Option B from the design conversation), caches per-atom; surfaces top-3 ranked kinds with one-line rationale in the kind dropdown
- Training signal capture: reviewer's actual pick vs. AI's top-ranked as training pair for classifier improvement
- Ontology traces continue logging to `ontology_traces` table (existing behavior)

### 3.3 Out of scope

- Manual ontology search UI. Reviewer confirms/rejects AI suggestions; they don't freetext-search SNOMED/RxNorm/ICD. Per §4 philosophy of Phase 1, this would turn the reviewer into a coder, which is downstream systems' job.
- Bulk code operations (apply code to all matching atoms). One code verdict per atom, preserving training unit granularity.
- Cross-document code consistency enforcement. Phase 5+ territory.

### 3.4 Sacred rules

- AI-suggested codes have `attestation: ai_suggested` until a reviewer touches them. Only codes with `attestation: reviewer_assessed`, `source_document`, or `fhir_import` count as ground truth for F1 (per CLINICAL_SHAPE_DESIGN §7.3).
- Append-only amendments: a reviewer correction creates a new code entry with `supersedes_id`, never overwrites. Original AI suggestion preserved permanently.
- No PATCH to `data_atoms.canonical_codes` from Phase 2. All code verdicts flow through `grading_submissions`, preserving L1↔L3 delta for training.

### 3.5 Dependencies

- Phase 1 drill-down must exist (for the code block UI to live in)
- `/v1/admin/lookup` backend (already shipped in GT-1.6d)
- `ontology_traces` table (already exists on staging)

### 3.6 Scope estimate

~4 mini-sprints. Smaller than Phase 1 because the backend exists; we're wiring UI and adding a second AI-call surface.

Rough breakdown:
- 2.1 — Interactive canonical_codes UI (confirm/amend/reject, `i` button, popover)
- 2.2 — AI ontology lookup trigger + response handling + workspace persistence
- 2.3 — AI-assisted kind suggestion (separate classifier call, ranked-list integration with Phase 1's rules-based ranking)
- 2.4 — End-to-end smoke test + training media schema alignment

### 3.7 Training media implications

After Phase 2, `codes_l1` and `codes_l3` in the TRAINING_MEDIA_DESIGN §6 schema carry real data for BioMistral training — not just the kind-and-span training signal. Per-track:

- Track A: unchanged from Phase 1
- Track B: prompt improvements can now include "here's how the reviewer disambiguated ICD-10 E10 vs E11"
- Track C: coding training signal unlocks; BioMistral fine-tune has target codes to learn toward, not just target kinds

### 3.8 Kind Assignment Wizard

Decision-tree UI that walks reviewers through kind assignment
via plainspoken questions ("What kind of information is this?" →
"What kind of date is this?") rather than requiring FHIR
fluency or taxonomy memorization. Each branch terminates in
either a kind assignment or a reject recommendation (for
non-clinical content like report metadata dates).

Sibling to the AI-assisted kind suggestion in §3.2. The two
approach the same problem differently: wizard is deterministic
tree-walking with upfront content work; AI-assist is
probabilistic classification with model inference. Both may
coexist — wizard as reviewer training and AI-fallback tool,
AI-assist as experienced-reviewer accelerator.

Content scope: approximately 40-60 decision nodes covering
the 20 entity kinds. Needs upfront design work on tree
structure + wording. Replaces the current `i` button as the
primary kind-disambiguation surface; `i` button is retired
or repurposed when the wizard ships.

Why Phase 2: too much scope to fold into Phase 1. Content-heavy
(decision tree design + wording across 20 kinds). Co-designs
with AI-assist; the two systems inform each other's
architecture.

Context for this addition (2026-04-22): Surfaced during Sprint
1.3 design discussion when ADI reviewer flow revealed that
(a) the `i` button popover is insufficient for resolving
commonly-confused kinds (symptom vs condition vs diagnosis,
visitDate vs reportDate vs report metadata dates), and (b) the
current taxonomy includes date kinds that need reviewer
guidance to distinguish from administrative metadata that
should be rejected rather than classified.

### 3.9 Submitted Documents Review Flow

Today the ADI console shows documents in pending-review states
only. Once locked, a document disappears from the workflow and
the reviewer has no way to revisit their prior grading.

This gap matters for several reviewer workflows:

- Spot-checking prior verdicts ("I think I misjudged that atom")
- Reviewing grading patterns across submitted documents
- Re-grading when the AI pipeline has been re-run on a
  previously-submitted document and new atoms exist
- Auditing consistency of one's own grading across time

Scope includes:

- New section or filter in the document list showing
  previously-submitted documents
- Read-only drill-down into the prior grading state (atoms,
  verdicts, corrections, rationale, bbox edits)
- Ability to create an amendment — a new grading submission
  that supersedes the prior one. Since `grading_submissions`
  is append-only, amendments are new rows with a reference
  back to the superseded submission.
- UI to distinguish "original submission" from "amended by
  reviewer" state at the document level

Architectural questions to resolve in detail design:

- Which grading submission wins for training media export —
  the latest? The one flagged canonical? All of them with
  attribution? This is a non-trivial design call with
  implications for Phase 5 export shape.
- How re-graded atoms interact with negative-space annotations
  (Phase 4) — if a reviewer initially rejected an atom as
  template boilerplate, then on re-grading decides it's a
  real condition, does the original negative-space
  annotation stay as training signal or get superseded?
- Whether amendments require a reason/rationale themselves
  (probably yes, for audit trail)

Why Phase 2: not required for initial grading throughput;
surfaces once reviewers have grading history worth
re-examining. Touches document list UI, drill-down state,
grading_submissions semantics, and training media export
filter logic. Meaningful scope.

Context for this addition (2026-04-22): Surfaced during
Sprint 1.3 design discussion when reviewer noted that no
path currently exists to revisit submitted documents. Related
to but distinct from audit-trail needs for HIPAA/compliance.

## 4. Phase 3 — Per-patient grouping + patient profile

### 4.1 Goal

Surface the patient dimension in the ADI console. Today the console is a flat document list; every document is context-free. A reviewer grading document 47 for patient X has no way to know documents 18, 22, and 31 were also for patient X and contained related atoms.

Also: populate the `patient_context` (age bucket, sex, known conditions) that TRAINING_MEDIA_DESIGN §6 specifies, using the cold-start rosetta pattern — frequency scan of first-ingested documents → candidate patient names → user confirmation → profile seeded.

Two sides of the same pipe: reviewer-side (ADI console patient view) and ingest-side (iOS cold-start detection).

### 4.2 What ships

**Console side:**

- Document list groups by patient (or: new "Patient" pivot alongside the existing status filter)
- Per-patient view: list of documents for this patient, with per-doc summary (status, atom counts, F1 once locked)
- Patient profile panel: name, age bucket, sex, known conditions (read from the structured profile populated via cold-start)
- When a document is open in the drill-down, the Patient tab (or equivalent surface) shows sibling atoms for this patient across documents — relevant for the reviewer judging whether "OM" in an ENT note resolves to "otitis media" given prior ear-infection history

**iOS side:**

- Cold-start frequency detection: on first ~5 documents ingested for a patient, scan for name-candidate tokens appearing 3+ times
- Surface candidates to the user with a "Which of these is the patient's name?" prompt
- User selection populates `PatientProfile` with confirmed name + any demographic fields the documents yielded (DOB, sex)
- Profile persists on device, syncs forward into each subsequent document's transit payload

**Worker side:**

- `patient_profile` JSONB column on `review_documents` (or a separate `patients` table — design decision for Phase 3's detail spec)
- `patient_context_confirmed` JSONB column on `grading_sessions` (per TRAINING_MEDIA_DESIGN §11 item 7)
- Update GET /v1/admin/documents to include patient context

### 4.3 Out of scope

- Full patient record management. The ADI patient view is a lens for grading, not a patient CRM.
- Cross-patient de-duplication. If "J. Smith" appears in two documents, they might be the same patient or different patients. Phase 3 treats them as separate until evidence says otherwise.
- Patient context-driven re-extraction. Phase 3 captures the context; Phase 5+ uses it to drive improved extraction.

### 4.4 Sacred rules

- Patient profile lives on-device for production users (iOS PHI boundary). The ADI console sees detokenized patient names only because it's the superuser/admin path that already handles real PHI.
- Cold-start frequency thresholds (3+ mentions, first 5 documents) are tunable, not hardcoded — captured as config at design time.
- Patient profile is append-only in the same sense as FactStore: corrections to patient name/profile create a new profile version, don't mutate the prior one. Prevents corruption when a reviewer misidentifies a patient in early ingests.

### 4.5 Dependencies

- Phase 1 drill-down (for the Patient tab to live in the right panel)
- iOS `DocumentTransitService` must carry patient profile in the upload payload
- No dependency on Phase 2 — Phase 3 can ship before or after

### 4.6 Scope estimate

~3–4 mini-sprints, split across three repos:

- 3.1 — Worker schema + Patient endpoint (patients table or JSONB extension, GET by patient_id)
- 3.2 — Console patient pivot + patient profile panel
- 3.3 — iOS cold-start frequency detection + confirmation prompt UI
- 3.4 — End-to-end test: fresh patient → 5 documents ingested → cold-start fires → profile populated → ADI console displays it

### 4.7 Training media implications

Populates `patient_context` field in the TRAINING_MEDIA_DESIGN §6 schema. Becomes input to the BioMistral prompt ("patient is a 6-year-old female — interpret 'OM' accordingly"). Unlocks patient-context-aware prompt engineering (Track B) and fine-tuning (Track C).

## 5. Phase 4 — Negative-space annotation

### 5.1 Goal

Ship the single highest-leverage training signal from TRAINING_MEDIA_DESIGN §4.3 and §6: reviewer-drawn boxes around text that the pipeline *should not* have extracted as a specific kind, with label and optional rationale.

This directly attacks Jason's observed failure mode where the pipeline treats section headers ("TYPE Accession No"), form field labels ("FINAL RESULT PA"), and generic terms ("Standard") as PHI or entities. Without explicit negative examples, a model trained on positive spans alone will keep producing these false positives (§4.3 is unambiguous on this in the field's consensus).

### 5.2 What ships

- New capture mode in the ADI console — either a fourth right-panel tab (Atoms / PHI / Info / Negative Space) or a mode toggle within Atoms. Decision deferred to Phase 4's detail design.
- Reviewer draws a box around text the pipeline incorrectly extracted
- Labels from a closed vocabulary: `form_field_header`, `section_title`, `template_boilerplate`, `decorative`, `redacted`, `legal_notice`, `footer`, `other` — closed list keeps training signal crisp; `other` as escape hatch
- `was_extracted_as` attribution: reviewer specifies which layer(s) produced the false positive — ios_regex, biomistral, both
- Optional rationale, one line
- Persistence: `negative_space` JSONB on `grading_submissions` (per TRAINING_MEDIA_DESIGN §11 item 4)
- Locked-document mode: read-only display of prior negative-space annotations
- Overlay rendering: negative-space regions render on PDF overlay with a visually distinct stroke (dashed gray or similar — must not be confused with atom rects or PHI rects)

### 5.3 Out of scope

- Open-vocabulary negative-space labels. Closed list first; if the `other` bucket gets heavy usage, Phase 4.5 expands the vocabulary based on observed patterns.
- Negative-space rule auto-suggestions. Phase 5+ territory: "these 12 negative-space annotations all share a visual pattern — generate a regex rule?"
- Undo/redo for negative-space annotations. First pass is simple draw-and-label-and-save; undo via cancel-region if something's wrong.

### 5.4 Sacred rules

- Negative-space annotations are first-class training signal, not verdict metadata. They live in their own JSONB array in `grading_submissions`, not as side effects of atom verdicts.
- Append-only per the established pattern. A reviewer amending a negative-space annotation creates a new one with `supersedes_id`.
- Attribution is required: a negative-space annotation without `was_extracted_as` is incomplete and shouldn't enter the training export.

### 5.5 Dependencies

- Phase 1 drill-down (shares PDF overlay infrastructure)
- Preferred: Phase 3 landed first, so patient-context is available when reviewer judges "this is a section title for this document type given this patient's record category"
- No hard dependency on Phase 2

### 5.6 Scope estimate

~2 mini-sprints:

- 4.1 — Schema addition + draw-and-label UI + closed-vocabulary label selector + overlay rendering
- 4.2 — End-to-end test: full grading session including ≥5 negative-space annotations, lock-in, verify payload round-trip, verify overlay re-renders on re-open

### 5.7 Training media implications

High-leverage for all three tracks:

- Track A: negative-space annotations attributed to `ios_regex` directly identify regex rules to tighten or exclusions to add
- Track B: closed-vocabulary negative labels become explicit "do not extract" examples in the BioMistral prompt's guidelines section
- Track C: negative-space regions become `incorrect_spans_key` equivalents in the CoNLL export, per the spaCy-community consensus that models trained on only-positive examples overgenerate

## 6. Phase 5 — Training media export + first bake-off

### 6.1 Goal

The payoff phase. Where capture stops and consumption starts. First measurable improvement to the pipeline through the promotion gate.

### 6.2 What ships

**Worker:**

- `GET /v1/admin/training-media/export?from=YYYY-MM-DD&track=A|B|C` endpoint (per TRAINING_MEDIA_DESIGN §11 item 10)
- Track filter slices the export to the fields each track needs (Track A wants regex candidate_spans + negative_space; Track B wants corrections + rationales; Track C wants full per-atom L1/L3 pairs)
- Canonical format: JSONL (one training record per line, schema-compatible with TRAINING_MEDIA_DESIGN §6)

**Tooling (new scripts, live in a tools/ or scripts/ dir in recordhealth-api):**

- JSONL → CoNLL-BIO converter (Track C token-classification format)
- JSONL → IIO triple converter (Track C instruction-tuning format)
- JSONL → prompt-exemplar extractor (Track B — pulls positive + negative examples + rationales for prompt refinement)
- JSONL → regex-false-positive pattern miner (Track A — clusters negative-space annotations by visual pattern and surfaces regex-rule candidates)

**First Track B run (prompt engineering):**

- Use first ~50 graded documents to distill `pass2_extraction@v4` prompt refinements
- Register new prompt via POST /v1/admin/prompts/register (existing GT-1.5a mechanism)
- A/B test v3 vs v4 on a 10-doc held-out subset
- Ship whichever wins per PPS (TRAINING_MEDIA_DESIGN §9)

**First Track C setup (BioMistral LoRA fine-tune):**

- Pull Track C export at current volume
- Convert to CoNLL-BIO or IIO (decide per what the BioMistral training toolchain expects)
- Run first LoRA fine-tune on the AWS BAA instance (BioMistral base → BioMistral-rh-v1)
- Evaluate on held-out subset against base model
- Decide per PPS whether to promote

**First Track A run (iOS regex tuning):**

- Pull Track A export (regex candidate_spans + attributed negative_space)
- Review false-positive clusters
- Tighten regex rules in iOS
- Ship via app update; new documents stamp with `regex_version: ios-1.5.0`

**Promotion gate:**

- PPS formula live per TRAINING_MEDIA_DESIGN §9
- Minimum corpus size check (200 locked documents, 40 held out) — if below, PPS is reported but not used for promotion decision
- Per-track attribution logged

### 6.3 Out of scope

- Automated retraining pipelines. Phase 5 is manual runs on small datasets with human-in-the-loop decisions. Automation is Phase 6+ if it earns its keep.
- Multi-version concurrent deployment. One pipeline version live at a time; A/B is evaluation-only, not production traffic splitting.
- Bedrock changes. Explicitly out of scope per the three-stage pipeline architecture (TRAINING_MEDIA_DESIGN §3.1).

### 6.4 Sacred rules

- Exports from production data must honor PHI policy. For the sandboxed AWS BAA instance (BioMistral), detokenized PHI is fine. For any future export that might leave the BAA boundary, tokenized-only (per §11 Q6 of TRAINING_MEDIA_DESIGN).
- Held-out test set is never seen by training. Phase 5's first act is fixing a ~20% held-out split from the first export, and that split is quarantined going forward — no later training run is allowed to touch it, so PPS measurements stay honest.
- Promotion decisions are logged with attribution. Every pipeline version bump writes a row: which track caused it, what the delta was, what documents were in training vs held-out. Reproducibility over cleverness.

### 6.5 Dependencies

- Phase 1 landed (primary training data source)
- Phase 2 strongly recommended (code verdicts are high-signal)
- Phase 4 strongly recommended (negative-space is the highest-leverage single signal per §4.3 of TRAINING_MEDIA_DESIGN)
- Phase 3 optional for first bake-off (patient context improves results but isn't required)
- Minimum 200 locked documents for promotion gate to be meaningful — if below, Phase 5 runs are indicative, not promotion-worthy

### 6.6 Scope estimate

Hard to estimate — depends on volume and what the tracks reveal. Rough sketch:

- 5.1 — Export endpoint + JSONL output
- 5.2 — Format converters (CoNLL, IIO, regex miner)
- 5.3 — First Track B run (prompt distillation + A/B + PPS eval)
- 5.4 — First Track C run (LoRA fine-tune on AWS + eval)
- 5.5 — First Track A run (regex tuning + ship)
- 5.6 — Promotion gate implementation + attribution logging

3–5 active sprints. Could stretch longer if fine-tune iteration cycles are long.

### 6.7 Success signal

Phase 5 is successful when one of the three tracks produces a measurable PPS gain, the gain survives held-out evaluation, and the improved artifact ships (new prompt registered, new LoRA adapter serving, or new regex rules deployed). Success is not "all three tracks win" — it's "we learned which track is currently winning and why."

A null result is also information: if no track produces PPS gain after a meaningful corpus, that tells us groundtruth quality or quantity is the limiting factor, not the training approach.

## 7. Phase 6+ — Open

By the time Phase 5 runs, there's real data about which track is producing gains, where ceilings are, and what the next highest-leverage work is. Committing to Phase 6+ work now would be pretending we know what the data will say. We don't yet.

Candidates to promote to "Phase 6" when the time comes:

### 7.1 Cross-model parallel inference + disagreement routing

Run BioMistral (fine-tuned per Phase 5) in parallel with the current Bedrock-Claude pipeline. Surface disagreement-heavy documents as high-priority in the ADI grading queue. Multiplies throughput of high-value training signal because the reviewer spends their time on documents where one of the two models is wrong — not on documents where both agree.

Long-term, this also becomes a Bedrock-drift detector: if BioMistral is stable and Bedrock's agreement rate changes over time, that's signal about Bedrock behavior evolving.

Was flagged as "Phase 7+ North Star" in TRAINING_MEDIA_DESIGN §13; promotes once BioMistral is fine-tuned enough to be a meaningful second opinion.

### 7.2 Per-category schema specialization

If Phase 5 reveals that visit notes are hard, lab reports are easy, imaging has unique structure — split the BioMistral prompt and/or fine-tune into per-`record_category` variants. Each category gets its own tight shopping list (Soroush et al. framing). Dispatcher at the top of the pipeline picks category first, then routes to the category-specialized extractor.

Could be pure Track B (per-category prompts) or Track C (per-category adapters) or both. Reshapes the pipeline architecture slightly; would get its own detail design if promoted.

### 7.3 Guidelines v0.2 onward

This isn't really a phase — it's a standing activity. Every batch of grading surfaces new ambiguities that should be codified in `ANNOTATION_GUIDELINES.md`. Keep iterating. Version-stamp guidelines per TRAINING_MEDIA_DESIGN §11 item 6 so the training corpus stays reproducible across guideline changes.

Not a scheduled sprint; a rhythm.

### 7.4 Reviewer-throughput QoL

Whatever shows up as friction when Jason is grading at volume during Phase 1.6 onward. Candidates that have come up so far:

- Keyboard navigation inside the atom list (arrow keys to move between atoms without entering drill-down)
- Bulk actions (confirm-all-remaining-in-this-kind-group)
- Auto-advance after confirm (verdict → next atom automatically, no explicit "Next" click)
- Side-by-side compare (show me all documents where the pipeline extracted this same verbatim value)

None of these are worth building speculatively. Promote if reviewer fatigue data shows a specific one is the bottleneck.

### 7.5 IAA via AI grader

Once BioMistral is fine-tuned (Phase 5 Track C winning), run it against already-locked grading submissions as a virtual second annotator. Agreement rate becomes a proxy for single-annotator corpus quality (per TRAINING_MEDIA_DESIGN §4.4).

Valuable if Record Health ever wants to publish or open-source training corpora, or if we need a quality signal on Jason's annotation consistency to trust batch-level PPS numbers.

## 8. Non-ADI work in the background

These aren't ADI phases but are in the shared backlog. Surface here so the ADI phase plan doesn't pretend to live in isolation.

### 8.1 AUTH-2

Migrate the ADI console from the legacy `ADI_ADMIN_KEY` bearer to user JWT. Unblocks GT-1.6c and GT-2e v3 production prompt registrations (per the original session handoff). Removes a static credential from production.

Can land any time between Phase 2 and Phase 3. Its own handoff doc already exists in the session handoff series.

Not on the ADI training-media critical path; pure cleanup.

### 8.2 iOS pre-App-Store

From the original session handoff:
- Remove JWT expiration debug block in `LLMClient.swift:60-79`
- Rotate exposed staging credentials (`ADI_ADMIN_KEY`, `DATABASE_URL`)
- Fix `.dev.vars` formatting
- Clean up orphan rows in production `users` table

None of this affects ADI training media. Separate track, needs to land before TestFlight/App Store submission.

### 8.3 DATA-1 (null-byte investigation)

Low priority today. Promotes if Phase 1.4 bbox-edit debugging surfaces null-byte correlation with specific document features, or if the regex tuning in Phase 5 Track A reveals null-byte patterns in false positives.

### 8.4 Bedrock handoff shape

TRAINING_MEDIA_DESIGN §3.1 marks the BioMistral → Bedrock handoff as "shape TBD, out of scope." At some point — probably Phase 6+ territory — this needs a design pass. The AI-ready layer coming out of BioMistral is the input to Bedrock's cross-document reasoning, and its shape affects everything downstream.

Flagged here so it doesn't get forgotten. Not urgent.

## 9. Sprint totals, rough

Very approximate, subject to scope drift:

| Phase | Mini-sprints | Cumulative |
|---|---|---|
| Phase 1 | 6 | 6 |
| Phase 2 | 4 | 10 |
| Phase 3 | 3–4 | 13–14 |
| Phase 4 | 2 | 15–16 |
| Phase 5 | 3–5 | 18–21 |
| Phase 6+ | open | open |

~18–21 mini-sprints from today to "ADI is running the improvement loop in earnest with at least one Track delivering measurable pipeline gains."

That's implementation sprints only. The grading-hour investment (Jason annotating documents) is a parallel track that's separate from sprint hours. Producing the 200-document corpus for Phase 5's promotion gate is an activity, not a sprint.

## 10. How this document stays honest

This roadmap is a draft. The honest expected lifecycle:

- v0.1 (this document) captures the shape today
- Each phase, when promoted to "next up," gets its own detail design doc: `PHASE_N_DESIGN.md` in SeedCorpus
- Phase detail design is allowed to diverge from this roadmap. This roadmap updates (v0.2, v0.3) when divergences become material
- Once Phase 5 runs and produces bake-off data, Phase 6+ section gets rewritten based on what the data said
- When Phase 5 lands, a v1.0 of this roadmap captures what actually happened through Phase 5 + what's next

Versions are cheap. Locking the plan isn't.

## 11. References

- `SeedCorpus/TRAINING_MEDIA_DESIGN.md` v0.2 — authoritative for training media schema and the three improvement tracks
- `SeedCorpus/PHASE_1_DESIGN.md` — authoritative for Phase 1 detailed spec
- `RecordHealth_App/docs/DATABASE_LAYOUT.md` — DB topology reference
- `SeedCorpus/GRADING_TOOL_DESIGN.md` — historical ADI console design decisions
- `SeedCorpus/CLINICAL_SHAPE_DESIGN.md` — canonical_codes, attestation model, entity kind definitions
- `SeedCorpus/SERVER_INFRASTRUCTURE.md` — Worker + Neon + R2 infrastructure reference

---

**End of draft v0.1. Shape, not specification.**
