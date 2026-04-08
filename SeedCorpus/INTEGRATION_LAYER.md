# Integration Layer
## Model Abstraction, Provenance, and Migration Framework — Record Health ADI

**Document version:** 1.0
**Status:** Authoritative
**Governs:** Model abstraction contract, model provenance schema, learning lineage
tracking, migration delta framework, canonical benchmarking mean, threshold
configuration portability, feedback loop fidelity principle
**Depends on:** FUNCTION_DISTINCTION.md, SERVER_INFRASTRUCTURE.md,
ADAPTIVE_DOCUMENT_INTELLIGENCE.md, SEED_CORPUS_RECURSIVE_TRAINING_STARTER_KIT.md
**See also:** LOGGING_AND_RETENTION.md for raw output logging and retention strategy

---

## 1. Why This Layer Exists

The integration layer is a stable API contract between the model stack (Layers 1–3)
and the routing, observability, and feedback systems that depend on their output.
Its purpose is portability without reasoning handicap.

Without it, every model swap requires tracing model-specific assumptions through
threshold logic, tier assignment code, escalation conditions, and anomaly detection
rules. With it, those systems talk to a contract that doesn't change when the model
does.

**What the integration layer is:**
- A normalization boundary that reformats model output into a stable schema
- A logging checkpoint where raw outputs are preserved before normalization
- A configuration surface where model-specific parameters are isolated

**What the integration layer is not:**
- A reasoning layer — it does not interpret, filter, or adjudicate model output
- A training layer — it has no role in System A (offline training loop)
- A PHI boundary — PHI constraints are enforced upstream, not here

---

## 2. The Foundational Principle

> **The integration layer may reformat information but may never reduce it.**

Any transformation the layer performs must be lossless from the perspective of
the observability and feedback systems. The routing logic above the layer sees
the normalized schema. The feedback loop below the layer sees everything.

This principle is a hard constraint on all integration layer implementations.
If a normalization step would discard signal that could identify a model failure
mode, it is architecturally prohibited. Log the pre-normalization state first,
then normalize.

Violations of this principle attenuate the feedback loop that drives System A.
Attenuated feedback means slower training improvement and invisible failure modes.

---

## 3. Stable API Contract

### 3.1 Integration Layer Input (to model)

The following schema is the stable input contract. It does not change when the
underlying model changes. Model-specific prompt formatting is handled inside the
layer, not by the caller.

```json
{
  "extraction_request_id": "uuid",
  "document_category": "labReport | imaging | discharge | prescription | ...",
  "layout_region_type": "header | labTable | valueColumn | footerSignature | ...",
  "ocr_engine": "VisionKit | Tesseract | ...",
  "ocr_raw_output_tokenized": "string (PHI-tokenized)",
  "visual_feature_vector": { ... },
  "pattern_library_version": "0.7.1",
  "model_version": "BioMistral-7B-finetuned-v0.3.1"
}
```

### 3.2 Integration Layer Output (from model, post-normalization)

```json
{
  "extraction_run_id": "uuid",
  "model_version": "string",
  "tier_assignment": "1 | 2 | 3",
  "fields": [
    {
      "field_type": "numericLabValue | medicationName | date | ...",
      "extracted_value_tokenized": "string",
      "canonical_id": "string | null",
      "canonical_system": "LOINC | RxNorm | SNOMED-CT | ICD-10 | null",
      "confidence": 0.87,
      "confusion_class": "alphanumericSubstitution | null"
    }
  ],
  "escalation_flag": false,
  "escalation_reason": "null | lowConfidenceAggregate | novelConfusionClass | ..."
}
```

### 3.3 Raw Output (logged before normalization — never discarded)

```json
{
  "extraction_run_id": "uuid",
  "model_version": "string",
  "raw_confidence_vector": {
    "numericLabValue": 0.87,
    "medicationName": 0.43,
    "date": 0.91,
    "providerName": 0.61
  },
  "raw_model_output": "string (full model response before parsing)",
  "pre_normalization_tier": "2",
  "post_normalization_tier": "2",
  "normalization_delta": false
}
```

`normalization_delta: true` flags any case where normalization changed the
tier assignment. These cases are reviewed manually — they indicate either a
normalization logic error or a model output that doesn't fit the expected
distribution.

---

## 4. Model Provenance Schema

### 4.1 Extended training_artifacts Table

The existing `training_artifacts` table (FUNCTION_DISTINCTION.md section 4.3)
is extended with full provenance fields.

```sql
training_artifacts (
    id                      UUID PRIMARY KEY,
    created_at              TIMESTAMPTZ,

    -- Base model provenance
    base_model_id           TEXT,       -- e.g. 'BioMistral-7B-v1.0'
    base_model_source       TEXT,       -- HuggingFace model ID or local path
    base_model_sha256       TEXT,       -- checksum of base weights at training time

    -- LoRA adapter configuration
    lora_rank               INT,
    lora_alpha              FLOAT,
    lora_target_modules     TEXT[],     -- e.g. ['q_proj', 'v_proj']
    lora_dropout            FLOAT,

    -- Training configuration
    corpus_snapshot_id      UUID,       -- FK → export run from expert_annotations
    hyperparameters         JSONB,      -- lr, epochs, batch_size, warmup_steps, etc.
    training_framework      TEXT,       -- 'HuggingFace PEFT', 'Axolotl', etc.
    training_hardware       TEXT,       -- e.g. 'g4dn.xlarge'
    training_duration_mins  INT,

    -- Benchmark results
    benchmark_run_id        UUID,       -- FK → benchmark_runs
    benchmark_overall_f1    FLOAT,
    benchmark_by_category   JSONB,      -- F1 per document_category
    benchmark_by_field      JSONB,      -- F1 per field_type
    benchmark_by_confusion  JSONB,      -- F1 per confusion_class

    -- Routing outcome
    gate_decision           TEXT,       -- 'promoted', 'held', 'rejected'
    gate_decision_reason    TEXT,
    gate_decided_at         TIMESTAMPTZ,
    gate_decided_by         TEXT,       -- admin user or 'automated'
    promoted_to_route       TEXT,       -- 'A', 'B', 'C', 'D', or null
    deployed_at             TIMESTAMPTZ,

    -- Migration tracking
    supersedes_artifact_id  UUID,       -- FK → training_artifacts (prior version)
    migration_delta_score   JSONB       -- comparison against prior artifact at promotion time
)
```

**Decision rationale:** Every field in this schema answers a specific question
you will need to answer during a model migration. `base_model_sha256` ensures
you know exactly which weights were used even if the model hub changes.
`corpus_snapshot_id` lets you replay the training run against the same data.
`benchmark_by_confusion` decomposed scores are what prevent a regression in
one confusion class being hidden by aggregate F1 improvement.

### 4.2 model_versions Table

Tracks what is currently deployed and what it replaced.

```sql
model_versions (
    id                      UUID PRIMARY KEY,
    created_at              TIMESTAMPTZ,
    training_artifact_id    UUID,       -- FK → training_artifacts
    model_version_string    TEXT,       -- e.g. 'BioMistral-7B-finetuned-v0.3.1'
    layer                   TEXT,       -- '1_ondevice', '2_private', '3_bedrock_passthrough'
    route                   TEXT,       -- 'A', 'B', 'C', 'D'
    status                  TEXT,       -- 'staging', 'active', 'retired'
    deployed_at             TIMESTAMPTZ,
    retired_at              TIMESTAMPTZ,
    replaced_by             UUID,       -- FK → model_versions
    rollback_available_until TIMESTAMPTZ
)
```

---

## 5. Learning Lineage Table

The lineage table is the connective tissue that links an initial failure event
to its eventual training outcome. Without it, each stage of the ADI pipeline
is a separate log. With it, the full chain is traceable in a single query.

```sql
learning_lineage (
    id                      UUID PRIMARY KEY,
    created_at              TIMESTAMPTZ,

    -- Origin event
    origin_type             TEXT,       -- 'anomaly_flag' | 'seed_document' | 'mimic_document'
    origin_id               UUID,       -- FK → anomaly_flags | seed_documents | mimic_documents

    -- Expert annotation (if origin became one)
    expert_annotation_id    UUID,       -- FK → expert_annotations, null if not annotated
    annotation_created_at   TIMESTAMPTZ,
    annotator_level         TEXT,       -- L0–L5

    -- Corpus inclusion
    corpus_snapshot_id      UUID,       -- FK → corpus export that included this annotation
    corpus_included_at      TIMESTAMPTZ,

    -- Training artifact that consumed this annotation
    training_artifact_id    UUID,       -- FK → training_artifacts
    training_weight         FLOAT,      -- 1.0 standard, 0.7 distilled, 1.1 active opt-in

    -- Outcome measurement
    post_training_benchmark_id UUID,    -- FK → benchmark_runs after this artifact deployed
    field_type              TEXT,       -- which field type this lineage record covers
    confusion_class         TEXT,
    f1_before               FLOAT,      -- benchmark F1 on this class before training
    f1_after                FLOAT,      -- benchmark F1 on this class after training
    delta                   FLOAT,      -- f1_after - f1_before

    -- Annotation cycle tracking
    annotation_cycle_count  INT         -- how many expert annotation cycles for this class
                                        -- before hitting promotion threshold
)
```

**What this enables:**
- Trace any deployed model improvement back to the specific failures that produced it
- Trace any failure forward to whether it was addressed and how long it took
- Measure annotation difficulty per confusion class (cycle count before promotion)
- Route future cases in high-cycle-count classes to higher proficiency annotators
- Support machine unlearning triage: identify which training_artifact_id consumed
  a specific user's data if consent is withdrawn

---

## 6. Threshold Configuration as Model-Specific

Tier cutoffs, escalation conditions, and confidence floors are not global constants.
They are model-specific parameters stored in the `consensus_config` table keyed
by model_version.

**Decision rationale:** BioMistral 7B and a successor model may both produce
outputs in the same schema but with different confidence distributions. A Tier 1
auto-accept floor calibrated for BioMistral at 0.85 may be too permissive or
too conservative for the successor. Hardcoding thresholds causes silently
miscalibrated routing after a model swap.

```sql
-- consensus_config rows for model-specific thresholds
INSERT INTO consensus_config (key, value, updated_at) VALUES
  ('tier1_floor.BioMistral-7B-finetuned-v0.3.1', '0.85', now()),
  ('tier2_floor.BioMistral-7B-finetuned-v0.3.1', '0.61', now()),
  ('escalation_floor.BioMistral-7B-finetuned-v0.3.1', '0.45', now());
```

When a new model is promoted, threshold recalibration against the new model's
output distribution is a required pre-deployment step. Thresholds for the new
model version are written to `consensus_config` before the model goes live.
The old model's thresholds are retained for rollback.

---

## 7. Migration Delta Framework

### 7.1 Shadow Evaluation Run

When a candidate replacement model is being evaluated, it runs against a frozen
snapshot of the test silo in parallel with the current production model. Neither
model's output affects the other. The comparison produces a migration delta score.

```
Shadow evaluation inputs:
├── Frozen test silo snapshot (same set used for current production benchmark)
├── All anomaly-flagged extraction_runs from the past 90 days
└── 10% sampled clean extraction_runs from the past 90 days (see LOGGING_AND_RETENTION.md)

Shadow evaluation outputs:
├── Candidate F1 per document_category vs production F1 per document_category
├── Candidate F1 per field_type vs production F1 per field_type
├── Candidate F1 per confusion_class vs production F1 per confusion_class
├── Confidence distribution comparison (percentile bands)
├── Normalization_delta rate (how often candidate output doesn't fit stable schema)
└── Estimated threshold recalibration requirements
```

### 7.2 Canonical Benchmarking Mean

The canonical mean is the aggregate of all benchmark_runs records against the
production test silo, weighted by corpus_snapshot_id recency. It is the stable
reference point for all migration delta scoring.

The canonical mean is never a single run — it is a rolling average that accounts
for natural benchmark variance. A candidate must beat the canonical mean on
decomposed dimensions, not just the most recent single run.

```sql
-- View: canonical benchmarking mean
CREATE VIEW canonical_benchmark_mean AS
SELECT
    field_type,
    confusion_class,
    document_category,
    AVG(f1_score) as mean_f1,
    STDDEV(f1_score) as stddev_f1,
    COUNT(*) as run_count,
    MAX(run_date) as last_run_date
FROM benchmark_runs
WHERE model_version = (SELECT model_version_string FROM model_versions WHERE status = 'active' AND layer = '2_private')
  AND run_date > NOW() - INTERVAL '90 days'
GROUP BY field_type, confusion_class, document_category;
```

### 7.3 Migration Gate Criteria

A model swap is approved when the candidate meets all of the following:

```
Overall F1               ≥ canonical mean overall F1
Per document_category    No category regresses > 2 F1 points
Per field_type           No field type regresses > 3 F1 points
Per confusion_class      No class regresses > 5 F1 points
Normalization_delta rate < 1% (candidate output fits stable schema)
Threshold recalibration  New thresholds identified and written to consensus_config
```

A candidate that improves overall F1 but regresses on any material dimension
is held, not promoted. The decomposed gate prevents aggregate improvement from
masking class-level regression.

---

## 8. Layer-Specific Portability Budgets

### 8.1 Layer 2 (Private Server — BioMistral)

Freely swappable. Any model architecture, any size, any framework. The integration
layer contract is the only constraint. Shadow evaluation and decomposed gate
apply. No Apple toolchain involvement.

### 8.2 Layer 1 (On-Device — CoreML)

Constrained by CoreML export compatibility. Not every model architecture exports
to CoreML cleanly. Before evaluating a Layer 1 candidate, verify:

- CoreML export path exists for the architecture (documented or community-verified)
- coremltools version compatibility with the architecture
- Quantization mode supported by target iOS deployment target (iOS 18.0 minimum)
- Model size after quantization fits reasonable on-device storage budget

Phi-3 Mini has a documented CoreML export path and is the current Layer 1
base model reference. New Layer 1 candidates must pass CoreML export validation
before shadow evaluation begins. A model that cannot be exported is not a
candidate regardless of benchmark performance.

---

## 9. Annotator Variance as Training Signal

Inter-annotator disagreement on the same case is a training signal about
annotation guideline ambiguity, not about the model.

When two L2+ annotators classify the same case differently, that disagreement
is logged to `annotator_variance_log`. Cases with high disagreement rates within
a confusion class identify guidelines that need tightening before more annotations
in that class are added to the corpus.

A confusion class with high annotator variance should not be promoted to the
PatternLibrary until variance drops below threshold — the annotations are not
reliable enough to train on.

```sql
annotator_variance_log (
    id                      UUID PRIMARY KEY,
    logged_at               TIMESTAMPTZ,
    expert_annotation_id    UUID,
    field_type              TEXT,
    confusion_class         TEXT,
    annotator_a_level       TEXT,
    annotator_b_level       TEXT,
    annotator_a_class       TEXT,
    annotator_b_class       TEXT,
    resolution              TEXT,       -- 'a_correct','b_correct','escalated','guideline_gap'
    guideline_gap_noted     BOOLEAN DEFAULT FALSE
)
```

---

## 10. Implementation Constraints

The following are hard constraints on any sprint implementing integration layer
components:

1. Raw output logging occurs before normalization. Never after.
2. `normalization_delta` is computed and logged on every extraction run.
3. Tier assignment thresholds are read from `consensus_config` keyed by
   `model_version`. No hardcoded thresholds anywhere in routing logic.
4. The stable output schema (section 3.2) is the only interface exposed to
   routing logic, anomaly detection, and tier assignment. Raw output (section 3.3)
   is written to `raw_output_log` and is never consumed by those systems directly.
5. `learning_lineage` rows are written for every expert_annotation that enters
   a corpus snapshot. No annotation enters training without a lineage record.
6. Model swap is not complete until new thresholds are written to
   `consensus_config` and shadow evaluation delta score is recorded in
   `training_artifacts.migration_delta_score`.

---

*End of document.*

*Document version 1.0 establishes the integration layer architecture, model
provenance schema, learning lineage table, migration delta framework, canonical
benchmarking mean, threshold portability, and layer-specific portability budgets.
All sprint prompts implementing extraction routing, tier assignment, anomaly
detection, or model deployment must reference the relevant sections of this
document. Schema changes require this document to be updated before implementation
begins.*
