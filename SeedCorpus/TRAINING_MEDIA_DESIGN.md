# Training Media Design

**Status:** Draft v0.2 — Phase 0 output, pending Jason's review
**Created:** 2026-04-21
**Updated:** 2026-04-21 (v0.2 — incorporates BioMistral/AWS scope clarifications, three-track improvement framing, iOS regex layer as both context and tuning target)
**Location at rest:** `SeedCorpus/TRAINING_MEDIA_DESIGN.md`
**Purpose:** Define what the ADI must capture in order to produce training media — not just groundtruth — that can drive prompt re-engineering, iOS regex tuning, *and* custom LLM fine-tuning. This is the design target for ADI Phases 1–6.

---

## 1. Goal

Jason's framing: *"More than just 'fixing' a record ingest, I want to create the training media to make it better."*

The ADI's entire purpose is to produce optimized training media that compares groundtruth against current pipeline signal, in order to drive a promotion gate where ingest gets measurably smarter. Every reviewer action should contribute usable signal toward that goal. Every feature decision on the ADI should be evaluated against: *does this improve the quality or quantity of training media produced per reviewer-hour?*

## 2. The distinction that matters

**Groundtruth** is the answer — "this document contains atom X at location Y with code Z."

**Training media** is the answer *plus* the delta *plus* the reasoning. Specifically:
- The pipeline's original output (Layer 1, pre-grading) — captured *per layer* of the pipeline, see §3
- The locked corrected answer (Layer 3, post-grading)
- The delta between them (the *learning signal*)
- The reviewer's reasoning, where captured
- The context the reviewer used to decide (patient profile, sibling atoms, annotation guidelines)

Groundtruth is enough to measure pipeline accuracy. Training media is what you need to *teach the next pipeline*. The three-layer grading model already established in GT-2 captures L1 and L3 — the gap is that L2/reasoning and context aren't systematically logged today.

## 3. Target architecture and what training media is for

### 3.1 The pipeline being trained

The target ingest architecture is a three-stage pipeline, two stages of which are in scope for the ADI training scheme:

```
   Raw PDF + OCR
        │
        ▼
┌──────────────────┐
│  iOS regex layer │   ← in scope: tunable rules, currently rough/noisy
└──────────────────┘
        │
        ▼
┌──────────────────────────────────────────────┐
│  BioMistral (sandboxed AWS BAA instance)     │   ← in scope: identify, sequence, code
│  • atom span identification                  │
│  • PHI identification                        │
│  • kind classification                       │
│  • ontology coding (SNOMED/ICD/RxNorm)       │
│  • document-internal sequencing              │
└──────────────────────────────────────────────┘
        │
        ▼ (flat AI-ready layer; shape TBD, out of scope here)
┌──────────────────────────────────────────────┐
│  Bedrock (Claude)                            │   ← OUT of scope for training scheme
│  • cross-document reasoning                  │
│  • longitudinal reconciliation               │
│  • temporal ordering                         │
│  • condition/care plan synthesis             │
└──────────────────────────────────────────────┘
```

**The ADI's training scheme covers the iOS regex layer and BioMistral only.** Bedrock is downstream cross-document reasoning. Its training is a separate problem for a separate day.

### 3.2 The three improvement tracks training media must support

Training media captured in the ADI feeds three concurrent improvement workflows. Schema decisions in §6 are made to support all three first-class, not to optimize one at the expense of the others.

**Track A — iOS regex layer tuning.** The regex layer is currently emitting near-noise. Reviewer corrections that would have been catchable by a better regex rule are signal for this track. Cheapest to iterate; no model retraining required; shipped via app updates.

**Track B — BioMistral prompt engineering.** Standalone improvement path: distill reviewer corrections into prompt updates, register a new `pass2_extraction@vN+1`, A/B against current. No GPU time required. Fastest iteration cycle of the three.

**Track C — BioMistral fine-tuning.** LoRA fine-tune (or full-param if scaled) on the AWS BAA instance. Highest ceiling, slowest iteration. Same training media schema feeds it via per-atom token-classification or instruction-tuning conversion (§10).

Same captured training media, three exports, three improvement loops. The bake-off Jason mentioned earlier is not just "BioMistral fine-tune vs. prompt eng" — it's all three tracks running in parallel, with PPS (§9) telling us which track is producing the biggest gains per unit reviewer-hour invested.

## 4. How the field does this in 2026

A focused scan of the current state of clinical NLP annotation and fine-tuning practice. Not exhaustive; enough to orient design decisions.

### 4.1 BRAT standoff — still the lingua franca of NER annotation

BRAT standoff is the dominant annotation format across i2b2 / n2c2, BioNLP, ShARe/CLEF, and most academic clinical-NLP datasets. Annotations are stored separately from source text in an `.ann` file; the document `.txt` is never modified. Each annotation line carries:

- A typed ID (`T1` = text-bound entity, `R1` = relation, `A1` = attribute, `E1` = event)
- A label (e.g., `Medication`, `Dosage`)
- Character offsets into the source text (start/end pairs, semicolons separate discontinuous spans since v1.3)
- The reference text itself

This is the standard because it cleanly separates text from markup, supports discontinuous entities (medication name + dose split across a line), and converts readily to CoNLL / HuggingFace token-classification format via published scripts (`brat2CoNLL`, etc.).

**Implication for us:** our `source_regions` already capture bounding boxes in PDF coordinate space. We do *not* currently capture character offsets into the normalized OCR text. For training corpus portability, we need both — coords for spatial fine-tunes, character offsets for token-based BioMistral fine-tunes.

### 4.2 Instruction tuning — the dominant fine-tuning shape for LLMs

For LLM-based clinical extraction, the current convention is **Instruction-Input-Output (IIO) triples**:

- **Instruction** — task description, often including entity definitions and guidelines ("Extract all medications and their dosages from the following note. A medication is …")
- **Input** — the source document text (and, for our case, iOS regex pre-extraction output as additional context)
- **Output** — the structured answer, typically JSON or a delimited format

Recent work (Soroush et al., *Scientific Reports* 2025, LoRA-Llama-3.1-8B) reports **90% exact-match accuracy** — non-inferior to a second human annotator — using ~700 training examples with QLoRA fine-tuning on a single consumer GPU. That recipe is a *floor*, not a ceiling, for what's viable on Jason's setup. The BioMistral instance is on a sandboxed AWS BAA host that can be scaled — full-rank LoRA, larger batch sizes, faster iteration are all on the table. **A few hundred fully-corrected documents is enough to start moving the needle.**

Other findings worth noting:

- **Annotation guidelines embedded in the instruction significantly improve few-shot and fine-tuned performance** (Sugimoto et al., 2025). The guidelines themselves are training media. This is a Track B (prompt engineering) win that doubles as a Track C (fine-tune) win.
- **Confidence regularization** — penalizing overconfident incorrect predictions — measurably reduces hallucinations in medical feature extraction (Nazi et al., PMC 2025). Requires capturing *missed features* alongside *hallucinated features* — bidirectional matching.
- **Multimodal layout-aware models are emerging.** LayTextLLM (ACL 2025) encodes each bounding box as a single token embedding interleaved with text, boosting Key Information Extraction F1 by ~15% over OCR-only baselines. Our captured spatial data is directly usable for this class of model if we ever go there.

### 4.3 Negative examples are not optional

The spaCy and Prodigy communities have converged on a consistent finding: **NER models trained only on positive spans overgenerate false positives on real data**. The standard mitigation is explicit negative examples — spans that look extractable but should not be extracted — marked with an `incorrect_spans_key` or equivalent. Without this, models trained on "sparse" annotation collapse everything they see into entities.

This is directly relevant to Jason's observation: the current pipeline treats section titles ("FINAL RESULT PA"), field labels ("TYPE Accession No"), and generic terms ("Standard") as PHI or entities. These are the exact failure modes that negative examples prevent.

**Implication for us:** the ADI must let the reviewer explicitly mark spans as *negative* — "this is a section header, not PHI" — and capture a *reason* for that judgment. This is what Jason called "negative space annotation" and it is one of the highest-value training signals we can produce. It's also a Track A (regex) win — many of the current false positives are catchable by tightening regex rules to skip section-header layouts.

### 4.4 Double annotation and inter-annotator agreement

Field standard is double annotation with Cohen's kappa or F1-based IAA measurement. This is not practical for Jason as a solo annotator, but noting for two reasons:

1. A future "second-pass AI grader" — the pipeline re-runs against locked L3 data and agreement is computed — is a reasonable proxy for IAA.
2. Single-annotator corpora are considered lower-grade; this may matter if Record Health ever publishes or open-sources training data.

### 4.5 Pre-annotation + correction

The dominant annotation workflow in clinical corpora is: a weak model (or the current production pipeline) pre-annotates the document, the human corrects. Our three-layer grading model is already aligned with this pattern — L1 is the pipeline's pre-annotation, L3 is the correction. No change needed; calling it out so future sessions don't reinvent.

## 5. Where we are today

What the ADI captures right now, per the GT-2 handoff audit:

| Signal | Table | Captured today? |
|---|---|---|
| Entity spans (kind + value) | `data_atoms` | ✓ |
| Spatial provenance (bounding boxes) | `source_regions` | ✓ |
| Entity ↔ region links | `atom_region_links` | ✓ |
| PHI spatial provenance | `review_phi_detections` | ✓ |
| Verdicts (confirm / correct / reject) | `grading_submissions.verdicts` | ✓ |
| PHI verdicts | `grading_submissions.phi_verdicts` | ✓ |
| Discoveries (missed atoms) | `grading_submissions.discoveries` | ✓ |
| PHI discoveries | `grading_submissions.phi_discoveries` | ✓ |
| Prompt version used for L1 | `prompt_versions` (via pipeline_version synthesis) | Partial |
| Ontology traces (AI-led lookup) | `ontology_traces` | ✓ (backend, UI not wired) |

What's missing or sparse:

- **Character offsets** into normalized OCR text alongside PDF coords
- **iOS regex pre-extraction output** captured per document (Track A target)
- **Negative-space annotations with reasons** ("this is a section header, not a patient name, because it appears in a boldface banner with no value after the colon")
- **Correction rationale** ("corrected 'Otitis' → 'Otitis media' because the note references otoscopic findings earlier in the document")
- **Code-level corrections** (reviewer accepts/rejects/amends AI-led SNOMED/ICD/RxNorm suggestions — Phase 2 output)
- **Bounding-box edit history** (cancel/modify/add state transitions — Phase 3 output)
- **Cold-start patient context** (age/sex/etc. that the reviewer confirmed — Phase 4 output)
- **Annotation guideline version** bound to each grading session
- **Document linear order** explicitly preserved in atom sequences (needed for sequence-to-sequence fine-tuning)

## 6. Proposed training media schema

The unit of training media is one **locked grading record** — a single document's L3 output with everything needed to reconstruct the training pair. Shape:

```jsonc
{
  "training_record_id": "tm_...",
  "schema_version": "training-media-v0.2",
  "document": {
    "document_id": "bba0db7c-...",
    "patient_id": "984a54be-...",
    "record_category": "visit_note",
    "uploaded_at": "2026-04-21T23:24:41.472Z",
    "content_hash": "17e9d4...",
    "page_count": 4,
    "extraction_method": "pdf",
    "ocr_text_normalized": "...", // canonical text — char offsets index into this
    "pdf_object_ref": "r2://recordhealth-review-docs/..."
  },
  "pipeline_snapshot": {
    // L1 — what the pipeline produced, broken out per layer
    "ios_regex_output": {
      // Track A target. Currently noisy. Versioned because it will evolve.
      "regex_version": "ios-1.4.2",
      "candidate_spans": [
        {
          "rule_id": "patient_name_v3",
          "value": "TYPE Accession No",
          "kind_guess": "patientName",
          "regions": [{ "page": 1, "bbox": [...], "char_offset_start": 102, "char_offset_end": 119 }]
        }
      ]
    },
    "biomistral_output": {
      // Track B/C target — what BioMistral identified, sequenced, and coded
      "model_version": "biomistral-7b-base@untuned",
      "prompt_ids": ["pass1_document_read@v2", "pass2_extraction@v3"],
      "pass1_output": { "document_read": "..." },
      "atoms_l1": [
        {
          "atom_id": "a_...",
          "kind": "medication",
          "value": "Amoxicillin 500mg",
          "confidence": 0.87,
          "sequence_index": 14, // position in linear document order
          "regions": [
            {
              "page": 1,
              "bbox": [x0, y0, x1, y1],
              "char_offset_start": 1243,
              "char_offset_end": 1261
            }
          ],
          "codes_l1": [
            { "system": "rxnorm", "code": "723", "display": "Amoxicillin", "confidence": 0.91 }
          ]
        }
      ],
      "phi_l1": [ /* same shape for PHI detections */ ]
    }
  },
  "reviewer_record": {
    // L3 — what the reviewer locked in
    "session_id": "grs_...",
    "annotator_id": "jason",
    "guidelines_version": "v0.1",
    "patient_context": {
      "age_bucket": "6_to_11",
      "sex": "female",
      "known_conditions": []
    },
    "atoms_l3": [
      {
        "atom_id": "a_...", // matches L1 when verdict is confirm/correct
        "verdict": "correct",
        "kind_l3": "medication",
        "value_l3": "Amoxicillin 500mg PO TID x 10 days",
        "regions_l3": [
          // full post-edit state; see bbox_history for transitions
          { "page": 1, "bbox": [...], "char_offset_start": 1243, "char_offset_end": 1289 }
        ],
        "bbox_history": [
          { "op": "modify", "region_id": "r_...", "before": [x0,y0,x1,y1], "after": [x0',y0',x1',y1'] },
          { "op": "add", "region_id": "r_...", "after": [x0,y0,x1,y1] }
        ],
        "codes_l3": [
          { "system": "rxnorm", "code": "723", "display": "Amoxicillin", "verdict": "confirm" }
        ],
        "rationale": "Extended value to include dosing schedule; pipeline captured only drug name + strength."
      }
    ],
    "atoms_discoveries": [
      {
        "kind": "finding",
        "value": "Left tympanic membrane erythematous",
        "regions": [ /* ... */ ],
        "rationale": "Missed by pipeline. Clinical finding relevant to diagnosis.",
        "codes": [ { "system": "snomed", "code": "40021000", "verdict": "confirm" } ]
      }
    ],
    "negative_space": [
      {
        "region": { "page": 1, "bbox": [...], "text": "TYPE Accession No" },
        "was_extracted_as": [
          { "kind": "patientName", "by": "ios_regex", "rule_id": "patient_name_v3" },
          { "kind": "patientName", "by": "biomistral" }
        ],
        "correct_label": "form_field_header",
        "rationale": "Boldface banner text introducing a form field. Not PHI, not a clinical entity."
      }
    ],
    "phi_l3": [ /* verdicts + discoveries + negative space for PHI */ ]
  },
  "derived_signals": {
    // computed, not captured — for training-set filtering
    "regex_precision_l1": 0.31,
    "regex_recall_l1": 0.42,
    "biomistral_atom_precision_l1": 0.82,
    "biomistral_atom_recall_l1": 0.74,
    "biomistral_atom_f1_l1": 0.78,
    "biomistral_phi_precision_l1": 0.91,
    "biomistral_phi_recall_l1": 0.88,
    "correction_count": 3,
    "discovery_count": 2,
    "negative_space_count": 5,
    "bbox_edit_count": 4
  },
  "meta": {
    "locked_at": "2026-04-21T23:58:00Z"
  }
}
```

Notes on the shape:

- **Pipeline snapshot is split per layer.** `ios_regex_output` and `biomistral_output` are siblings under `pipeline_snapshot`. Each is independently version-stamped and independently graded for precision/recall in `derived_signals`. This is what makes Track A vs. Track B/C improvement attribution possible.
- **One record per document.** Joinable to per-atom rows for token-level training formats, joinable to per-document rows for instruction-tuning formats.
- **Every atom carries both L1 and L3.** The delta is recoverable without running extra queries.
- **`char_offset_start` / `char_offset_end` are first-class.** This is the single most important addition over today's schema. BioMistral fine-tuning will need these to build CoNLL-format training splits. Regex tuning will need them to ground rules in actual text positions.
- **`negative_space.was_extracted_as` is a list, not a single value.** A given region may be falsely extracted by both the regex layer and BioMistral, and the training signal needs to attribute to both.
- **`negative_space` is first-class.** Not a side effect of PHI verdicts — its own array, its own rationale, its own `was_extracted_as` vs `correct_label` pairing. This is the highest-leverage new signal for reducing false-positive rates *across all three tracks*.
- **`rationale` is optional but captured wherever the reviewer has the time.** Absent rationale is fine. Present rationale is gold.
- **`guidelines_version` is bound to each session.** Training-set curators can filter by guideline version when guidelines change.
- **`patient_context` is structured, not free text.** Buckets (age range, sex, etc.) feed forward into the BioMistral prompt as `patient_context`, and into the cold-start frequency detector (Phase 4).
- **`sequence_index`** preserves the linear document order BioMistral produced. Critical for sequence-to-sequence training and for measuring whether the model gets ordering right, not just spans.

## 7. Reviewer capture requirements (what the UI has to ask)

This is the Phase 0 answer to "what does the reviewer need to provide that we're not asking for today?"

Per-atom (in the drill-down view, Phase 1/2):

- Verdict (already captured): confirm / correct / reject
- Corrected value (already captured when verdict = correct)
- **Correction rationale** (new, optional) — free text, one-line prompt: "*Why the correction?*"
- **Ontology code(s)** (new, Phase 2) — reviewer confirms/rejects/amends AI-led suggestions
- **Bounding-box edit ops** (new, Phase 3) — cancel / modify / add; before/after captured automatically

Per-document (in the header / summary panel):

- **Guidelines acknowledgement** (new) — "I reviewed this document against guidelines v0.1" checkbox; binds session to guidelines version.
- **Patient profile confirmation** (new, Phase 4) — reviewer verifies cold-start-derived age bucket + sex; edits if wrong.

Per-document for negative space (new tab or mode, Phase 5):

- Reviewer draws a box around text the pipeline (regex *or* BioMistral *or* both) should not have extracted as a specific kind
- Labels it (`form_field_header`, `section_title`, `template_boilerplate`, `decorative`, `redacted`, etc.)
- Optional rationale

Per-session:

- Lock time, annotator, guidelines version (automatic)

The reviewer is not asked to code every atom, write every rationale, or annotate every negative-space region on every document. These are *solicited but optional* signals. A document with every field filled is a high-value training record; a document with just verdicts + corrections is still training media.

## 8. Annotation guidelines as training media

Per §4.2 and §4.3, annotation guidelines — the written definitions and edge-case rules for each entity kind — measurably improve both human annotation consistency and LLM few-shot/fine-tuning performance when embedded in prompts.

Record Health doesn't have a written annotation guidelines document today. What's implicit in the Pass 2 prompt is an informal definition; what's implicit in Jason's head is more nuanced. **Producing `ANNOTATION_GUIDELINES.md` is itself a training media deliverable** and should be a Phase 0.5 sprint before heavy reviewer work begins.

Minimum structure per entity kind:

- **Definition** — what counts as this kind
- **Positive examples** — 2–3 clear cases
- **Negative examples** — 2–3 edge cases that *look like* this kind but aren't, with reason
- **Boundary rules** — when an adjacent span is vs. isn't included
- **Kind overlaps** — which other kinds this can be confused with, and the tiebreaker

For 21 extraction-target kinds, that's a 40–60 page doc. Iterative — ship v0.1 with the 8–10 kinds most often graded, extend as reviewer sessions surface ambiguities.

## 9. Promotion gate metric proposal

Starting hypothesis, not a decision. Open for revision once we see real training-media volume. Designed to evaluate BioMistral output (the in-scope target). Bedrock is downstream and out of scope.

**Gate name:** Pipeline Promotion Score (PPS)

**Formula:**

```
PPS(v_new) = ΔF1_atoms(v_new, v_current) 
           + ΔF1_phi(v_new, v_current)
           + ΔCode_accuracy(v_new, v_current)
           + ΔSequence_accuracy(v_new, v_current)
           - λ × ΔFalse_positive_rate(v_new, v_current)
```

Computed over the held-out evaluation subset of training media (say, 20% split). `λ` weighted to penalize regressions on false positives — because the current pain point is over-extraction, not under-extraction.

**Promotion rule:** `v_new` is promoted if PPS > 0 *and* no kind regresses by more than 5% F1. Both gates matter — a net-positive score that tanks one kind is not acceptable in a clinical context.

**Minimum corpus size to apply the gate:** 200 locked documents (held out: 40). Below that, sample variance dominates and the gate is noise.

**Per-track attribution:** PPS is computed on the BioMistral output, but the *cause* of a PPS bump is attributed to whichever track's change preceded it. If a Track A regex change ships and PPS holds steady, the regex change is neutral. If a Track B prompt update ships and PPS jumps, prompt eng is winning. Standard A/B discipline; the per-layer pipeline_snapshot in §6 makes this attribution clean.

## 10. Feeding training media to downstream training pipelines

Quick sketch of how the above schema converts to the formats different tracks consume.

### 10.1 Track A — iOS regex tuning

Extract from locked records:
- `ios_regex_output.candidate_spans` joined with `negative_space` entries — every region the regex produced that the reviewer marked as negative space is a **regex false positive case** to either tighten the rule against or add an exclusion for
- `atoms_discoveries` regions that fall in plausible regex territory (formatted IDs, dates, structured fields) — **regex false negative cases** for new rule candidates
- `derived_signals.regex_precision_l1` / `regex_recall_l1` over time = regex layer health metric

Output: updated iOS regex rules (versioned, captured in next `regex_version` field).

### 10.2 Track B — BioMistral prompt re-engineering (no model training)

Extract from locked records:
- Positive examples → few-shot exemplars for the BioMistral extraction prompt
- Negative-space entries → explicit "do not extract" examples in the guidelines section of the prompt
- Correction rationales → prose additions to the entity definitions
- Ontology code verdicts → bias/allowlist for the lookup prompt

Output: updated `pass2_extraction@v4` prompt registered to `prompt_versions`. A/B tested against v3 on held-out set. **This is the cheapest, fastest improvement loop and should be exercised first when each new batch of training media lands.**

### 10.3 Track C — BioMistral LoRA fine-tune (sandboxed AWS BAA instance)

Convert per-atom L3 rows to CoNLL-BIO format via a `brat2CoNLL`-style script. Char offsets make this deterministic. Roughly:

```
Amoxicillin    B-medication
500            I-medication
mg             I-medication
PO             I-medication
TID            I-medication
x              I-medication
10             I-medication
days           I-medication
```

The AWS instance is BAA-scoped and Jason-controlled, so detokenized PHI flows there fine — no third-party API constraint. Train with LoRA (full-rank if scaled, QLoRA if cost-constrained). The Soroush et al. 2025 recipe on Llama-3.1 8B is a reasonable starting template adapted to BioMistral. Target: match or beat Track B's `pass2_extraction@v4` held-out F1.

For instruction-tuning instead of token-classification, use:

```jsonc
{
  "instruction": "You are a clinical entity extractor. Extract all atoms (medications, conditions, findings, providers, etc.), classify their PHI status, assign ontology codes where applicable, and preserve their order in the document. Use the entity definitions in the guidelines below: [embedded guidelines]. The iOS regex layer pre-extracted the following candidate spans, which may be noisy: [ios_regex_output]. Return a JSON array.",
  "input": "<document OCR text>",
  "output": "<biomistral atoms_l3 serialized as JSON>"
}
```

Note the instruction includes regex output as context — matching the production architecture from §3.1.

### 10.4 Optional later: layout-aware fine-tune

LayTextLLM-style training where bounding box coords are interleaved as tokens with text. Our `source_regions` are already in the correct shape. Higher compute, not on the near-term path. Keep the spatial data; don't optimize for this until tracks A/B/C have been exercised.

## 11. Gap to close before Phase 1 starts

Concrete list of schema and pipeline changes implied by the above. This is the Phase 0.5 / Phase 1 prerequisite work:

1. **Add `char_offset_start` / `char_offset_end`** columns to `source_regions` (or equivalent; design during Phase 1 audit). Backfill from OCR text reconstruction where possible.
2. **Capture `ios_regex_output` per document.** New JSONB column on `review_documents`, populated by `DocumentTransitService` at submit time. Includes `regex_version` for stamping.
3. **Add `rationale` column** to `grading_submissions` atom entries and PHI verdicts. Nullable.
4. **Add `negative_space` table or JSONB column** to `grading_submissions`. Shape per §6. Highest leverage of any schema change.
5. **Add `bbox_edit_history` column** to `source_regions` or `grading_submissions`. Populated by Phase 3 UI.
6. **Add `guidelines_version` column** to `grading_sessions`. Default to v0.1 once guidelines doc exists.
7. **Add `patient_context_confirmed` JSONB column** to `grading_sessions`. Populated by Phase 4 UI.
8. **Add `sequence_index` column** to `data_atoms`. Preserves linear document order. Needed for sequence-aware training and for the §9 sequence accuracy metric.
9. **Write `ANNOTATION_GUIDELINES.md` v0.1.** Phase 0.5 sprint — before heavy reviewer use.
10. **Spec the training media export endpoint.** `GET /v1/admin/training-media/export?from=YYYY-MM-DD&track=A|B|C` — produces the schema in §6 from joined data. Track filter slices the export to what each improvement loop needs.

## 12. Open questions

1. **Normalized OCR text canonical form.** Do we commit to one canonical string per document (newline-joined pages, or flat)? Char offsets are meaningless without a canonical text. Current state unclear.
2. **Ontology code storage granularity.** One primary code per atom, or a ranked list with verdicts per code? The Phase 2 UI design will need this answer.
3. **Guidelines versioning discipline.** Semver? Date-stamped? Tied to prompt version? Matters for training-set reproducibility.
4. **Negative-space labels — closed or open vocabulary?** Starter list (`form_field_header`, `section_title`, `template_boilerplate`, `decorative`, `redacted`) vs. free-text labels with post-hoc clustering. Starter closed list is easier for training signal; open is richer.
5. **Per-page vs per-document char offsets.** BRAT is per-document. Multi-page PDFs argue for per-page; sequence-to-sequence models prefer per-document. Pick one and stick.
6. **Regex versioning discipline.** iOS releases are versioned (`1.4.2`). Is the regex layer version coupled to app version, or independently versioned? Affects how training media filters by `regex_version`.
7. **Cross-model parallel inference.** Once BioMistral is serving, do we run it in parallel with the existing Bedrock-based extraction during the transition period and surface disagreements in the ADI? Phase 7+, but a useful North Star.

## 13. Scoping

Phases the rest of the ADI arc maps to, given this design:

- **Phase 0** (this doc) — design, no code
- **Phase 0.5** — write `ANNOTATION_GUIDELINES.md` v0.1 (covering the 8–10 most-graded kinds)
- **Phase 1** — Atom detail drill-down shell (nav, metadata, PDF-pan-to-atom). Add `char_offset` columns, `rationale` field, `negative_space` JSONB, `sequence_index`, `ios_regex_output` column to schema.
- **Phase 2** — AI ontology + code-level grading integration inside drill-down. Wire `/v1/admin/lookup`. Persist code verdicts.
- **Phase 3** — Bounding-box edit (cancel/modify/add) with state history capture.
- **Phase 4** — Patient profile tab + cold-start frequency detection. Populate `patient_context_confirmed`.
- **Phase 5** — Negative-space annotation mode + reason capture. The UI surface for §6's `negative_space` array.
- **Phase 6** — Training media export endpoint with track filtering. End-to-end smoke test: ingest → grade → lock → export → (round-trip through one of the three improvement tracks).
- **Phase 7+** (future, not committed) — Cross-model parallel inference and disagreement-routing UI. BioMistral runs alongside Bedrock during the transition; ADI surfaces disagreement-heavy documents as high-priority for grading. Both a training-throughput multiplier and (eventually) a Bedrock-drift metric.

Phase 6 is also where promotion gate (§9) becomes live — first measurable pipeline version bump happens when Phase 6's export feeds a Track A regex revision, a Track B prompt update, or a Track C BioMistral fine-tune.

## 14. References

- i2b2 / n2c2 shared tasks — https://n2c2.dbmi.hms.harvard.edu/
- BRAT standoff format — https://brat.nlplab.org/standoff.html
- `brat2CoNLL` — https://github.com/pranav-s/brat2CoNLL
- Soroush et al., "Human-level information extraction from clinical reports with fine-tuned language models," *Scientific Reports*, 2025 (LoRA Llama-3.1 8B, 90% exact match on 4 clinical tasks)
- Lu et al., "A Bounding Box is Worth One Token: Interleaving Layout and Text in a Large Language Model for Document Understanding," ACL 2025 (LayTextLLM)
- Sugimoto et al., "Efficient medical NER with limited data: Enhancing LLM performance through annotation guidelines," 2025
- Nazi et al., "Medical Feature Extraction From Clinical Examination Notes: Development and Evaluation of a Two-Phase Large Language Model Framework," 2025 (confidence regularization)
- Mayer et al., "DeIDNER Corpus: Annotation of Clinical Discharge Summary Notes for Named Entity Recognition Using BRAT Tool," 2021 (double annotation + IAA methodology)
- spaCy `incorrect_spans_key` — negative annotations in NER training

---

**End of doc. v0.2, Phase 0 deliverable. Please annotate, push back, or reshape.**
