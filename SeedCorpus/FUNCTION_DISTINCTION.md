# Function Distinction and Operational Boundaries
## Record Health ADI — Programmatic Context for Implementation

**Document version:** 1.1
**Status:** Authoritative — supersedes conflicting assumptions in prior spec versions
**Purpose:** Precise function-level distinctions for Claude Code instances building each component.
Every sprint prompt should reference the relevant section of this document. When this document
conflicts with ADI v2.1 or EXPERT_ANNOTATION v1.2, this document governs.
**See also:** INTEGRATION_LAYER.md for model abstraction contract, provenance schema, and
migration delta framework. LOGGING_AND_RETENTION.md content is incorporated into
SERVER_INFRASTRUCTURE.md — do not create a separate logging document.
**Critical correction:** ADI v2.1 section 8.2 trust ladder phase gates tied transitions to user
correction volume. That model is superseded here. Phase transitions are now driven by offline
benchmark scores, not user activity. See section 2.

---

## 1. The Corrected Training Model

### 1.1 What Changed and Why

The original ADI architecture assumed users would act as reliable correction agents — that
user corrections would flow into the consensus engine and drive PatternLibrary promotions.
This assumption is wrong for the failure modes that matter most.

**The problem:** Real-world negative delta from bad user corrections is not noise — it is
active poison if it reaches the PatternLibrary. Most users cannot reliably correct:
- Structural failures invisible to the reading eye
- Domain failures requiring medical knowledge
- Silent non-recognition (fields that were never extracted)

**The corrected model:** The training loop is entirely offline and expert-driven.
What lands on device is pre-validated intelligence. Users benefit from it without
participating in producing it.

### 1.2 The Two Completely Separate Systems

These must never be conflated in implementation:

```
SYSTEM A — Offline training loop (AWS, expert annotation, no live traffic)
├── Expert annotation corpus builds continuously
├── Bedrock pre-annotates, human approves/modifies
├── Training runs produce candidate artifacts
├── Benchmark validates candidates against test silo
├── Production gate routes artifacts to correct delivery channel
└── Promoted artifacts distributed to devices / private instance

SYSTEM B — On-device production chain (live user traffic)
├── Receives pre-validated PatternLibrary deltas (rules)
├── Receives pre-validated CoreML model updates (weights)
├── Runs extraction against incoming documents
├── Achieves acceptable threshold without user correction
└── User flags → anomaly detection queue → human review
    NOT → automatic training signal
    NOT → PatternLibrary candidate
    NOT → consensus engine input
```

System A and System B share no data flow in the production direction.
System A output → System B (one-directional, pre-validated).
System B never feeds back to System A automatically.

---

## 2. Corrected Phase Gates (Supersedes ADI v2.1 Section 8.2)

### 2.1 What Drives Phase Transitions

**OLD (superseded):** Phase transitions gated on user correction volume
(500 users with corrections, geographic spread, correction accumulation)

**NEW (authoritative):** Phase transitions gated on offline benchmark scores
and expert annotation corpus milestones. User counts matter for business
revenue but do not gate intelligence improvement phases.

### 2.2 Corrected Phase Definitions

```
Phase 0 — Seed corpus only
─────────────────────────────────────────────────────────────────────
Training state:   Seed corpus pre-populated, no user data in training loop
Device state:     Seed PatternLibrary v0.x, no fine-tuned model
Acceptable UX:    Not yet — system not ready for public
Expert annotation: Active — building toward Phase 1 gate
User corrections: Logged to anomaly_flags table, not corpus
Transition gate:  Expert annotation corpus hits 500 Tier A documents
                  AND benchmark overall F1 > 0.61 on test silo
                  (baseline established, system ready for limited release)

Phase 1 — Offline training active, device on seed rules
─────────────────────────────────────────────────────────────────────
Training state:   First fine-tuning runs producing candidates
Device state:     Seed PatternLibrary + initial fine-tuned CoreML model
Acceptable UX:    Approaching — Tier 1 auto-accept rate > 70%
Expert annotation: Active — corpus growing, Bedrock analysis running weekly
User corrections: Logged to anomaly_flags, L0 reviews weekly
                  Genuine novel failures → expert annotation queue
                  Known failure classes → confirm benchmark is tracking
                  User misunderstandings → UX gap noted, no action
Transition gate:  Benchmark overall F1 > 0.78 on test silo
                  (production gate threshold met — system ready for public)
                  Tier 1 auto-accept rate > 82% on held-out validation set

Phase 2 — Acceptable UX achieved, continuous offline improvement
─────────────────────────────────────────────────────────────────────
Training state:   Regular training cadence (weekly/monthly per corpus growth)
Device state:     PatternLibrary updated regularly, CoreML model updated quarterly
Acceptable UX:    Yes — system is the product
Expert annotation: Ongoing permanent operation
User corrections: Same as Phase 1 — anomaly detection only, not training signal
Distillation:     Offline LLM learning distilled to device rules regularly
Promotion routing: All four routes active (see section 4)
Transition:       No discrete transition — Phase 2 runs indefinitely
                  Stage progression (1→2→3→4) is a separate axis from phase
```

### 2.3 system_maturity Table Changes

The `system_maturity` table tracks the corrected phase definitions.
Remove user-count-based fields. Add benchmark-based fields:

```sql
system_maturity (
    id                          UUID PRIMARY KEY,
    recorded_at                 TIMESTAMPTZ,
    phase                       TEXT,           -- 'seed','training','acceptable','steady'
    expert_annotation_count     INT,            -- Tier A documents in training corpus
    benchmark_overall_f1        FLOAT,          -- latest test silo F1
    tier1_auto_accept_rate      FLOAT,          -- % of extractions auto-accepted
    training_runs_completed     INT,            -- total fine-tuning runs to date
    last_promotion_date         TIMESTAMPTZ,    -- last artifact promoted to any route
    phase_transition_log        JSONB,          -- history of phase changes
    -- REMOVED: registered_users, users_with_corrections, geographic_spread_score
    -- User counts tracked in business metrics, not system maturity
)
```

---

## 3. User Flag vs Training Signal — Precise Function Distinction

This distinction must be implemented exactly. No ambiguity.

### 3.1 User Flag Flow

```
User indicates something looks wrong in the app
        ↓
Write to: anomaly_flags table (NOT expert_annotations, NOT pattern_atoms)
Fields:   document_id, extraction_id, user_id (hashed), flag_type,
          user_comment (optional), created_at
        ↓
Weekly L0 review:
  Classification:
    'misunderstanding'  → note UX gap, close flag, no action
    'known_class'       → confirm benchmark tracks this class, close flag
    'novel_failure'     → promote to expert annotation queue
    'data_quality'      → investigate document source, close flag
        ↓
Only 'novel_failure' flags create expert_annotations rows
Everything else is closed after classification
```

```sql
anomaly_flags (
    id              UUID PRIMARY KEY,
    created_at      TIMESTAMPTZ,
    document_id     UUID,
    extraction_id   UUID,
    user_id_hash    TEXT,
    flag_type       TEXT,       -- 'wrong_value','wrong_label','missing_field','other'
    user_comment    TEXT,
    review_status   TEXT DEFAULT 'pending',  -- 'pending','misunderstanding',
                                              -- 'known_class','novel_failure','data_quality'
    reviewed_at     TIMESTAMPTZ,
    reviewed_by     TEXT,
    created_annotation_id  UUID   -- FK → expert_annotations if novel_failure
)
```

### 3.2 What Is NOT in the User Flag Flow

The following do not exist in the corrected architecture:

- User corrections entering `pattern_atoms` directly
- User corrections entering `candidate_rules` directly
- User correction volume as a phase gate condition
- Automatic consensus from user corrections without L0 review
- User corrections being weighted or scored for training

If any sprint prompt attempts to build these flows, reject and reference this document.

### 3.3 CorrectionStore — Revised Purpose

The CorrectionStore (on-device, append-only) still exists but its purpose changes:

```
CorrectionStore — corrected purpose
├── Records what the user flagged and what the correct value was
│   (still append-only, still encrypted, still provenance-tracked)
│
├── Feeds: on-device personal MLUpdateTask (Layer 3 personal model)
│   This is purely personal calibration — the user's own documents
│   Their specific providers, their scan quality, their corrections
│   These weights never leave the device
│   This personal calibration layer is unaffected by the training correction
│
├── Feeds: anomaly_flags table via batch upload
│   For L0 weekly review only
│   Not fed into PatternAtomExtractor directly
│
└── Does NOT feed: PatternAtomExtractor for cross-user training
    Does NOT feed: consensus engine
    Does NOT feed: candidate_rules
```

The PatternAtomExtractor is now fed exclusively from expert_annotations,
not from CorrectionStore. The only on-device learning from user corrections
is the personal MLUpdateTask — which is personal, local, and never distributed.

---

## 4. Artifact Routing — Precise Function Distinction

Every artifact produced by the offline training loop is classified and routed
before distribution. The routing decision is made at the production gate,
not after distribution begins.

### 4.1 Artifact Types and Default Routes

```
Artifact type                        Default route
─────────────────────────────────────────────────────────────────────
PatternLibrary rule delta            Route A: Device delta (CDN, silent sync)
Distilled rule from model analysis   Route A: Device delta
LoRA adapter (small, arch unchanged) Route B: Device model download
LoRA adapter (large / arch changed)  Route D: App Store update
Full model update (arch unchanged)   Route B: Device model download
Full model update (arch changed)     Route D: App Store update
Clinical reasoning model update      Route C: Private instance update
PHI gateway model update             Route C: Private instance update
```

### 4.2 Route Definitions

```
Route A — Device PatternLibrary delta
Delivery:  CDN → client polls on app open → silent apply
Size:      Typically < 50KB per delta
Latency:   Available within hours of promotion
Rollback:  Prior PatternLibrary version in consensus_log, revert via admin
Risk:      Low — rules are inspectable and reversible
Gate:      Standard production gate (ADI spec section 4.9.2)
Schema:    patternLibraryDelta.json — addition/modification of rule entries
No app update required.

Route B — Device model download
Delivery:  CloudFront hosted .mlmodelc → background download → hot-swap
Size:      10MB–200MB typical (LoRA adapter range)
Latency:   Available after staged rollout clears
Rollback:  Prior CoreML model retained on device for 14 days
Risk:      Medium — replaces extraction model, staged rollout required
Gate:      Elevated production gate + staged rollout protocol:
           10% of users day 1 → monitor correction rate delta
           50% of users day 3 if metrics positive
           100% of users day 7 if metrics positive
           Halt and rollback if correction rate increases vs control
Schema:    model_versions row created, deployed_at populated on 100% rollout
No app update required for architecture-unchanged model updates.

Route C — Private instance update
Delivery:  Blue/green deployment on AWS private VPC
           Old instance stays warm until new instance passes health checks
Size:      Not device-relevant — server-side only
Latency:   Zero downtime if blue/green executes correctly
Rollback:  Old instance kept warm for 48 hours after promotion
Risk:      Medium-high — PHI gateway is compliance-critical
Gate:      Elevated production gate + PHI gateway compliance check:
           phi_gateway_log audit entries correct format
           No regression on PHI detection test suite
           Clinical reasoning output schema unchanged
Schema:    private_instance_deployments log (on-instance, not Neon)
No app update required. Transparent to users.

Route D — App Store update required
Triggers:  New confusion class enum case
           New field type enum case
           PatternAtom schema change (new fields)
           CoreML architecture change (different input/output spec)
           PHI strip verifier logic change
           On-device encryption or keychain access changes
Risk:      High surface area — App Store review cycle
Mitigation: Front-load enum breadth at launch to minimize Route D frequency
            Current taxonomy is intentionally broad to avoid forced upgrades
```

### 4.3 Routing Decision in the CRON Pipeline

```
Consensus CRON (daily 2AM UTC):

1. Evaluate candidate rules (existing ADI pipeline)
2. For each promoted rule:
   a. Classify artifact type → determine default route
   b. Run production gate for that route's threshold
   c. If approved: write distribution record, trigger delivery
   d. If blocked: log gate failure, no distribution

3. Check for pending model artifacts (from async training loop):
   a. Read training_artifacts table for candidates ready for gate
   b. Classify each → determine route
   c. Run elevated production gate
   d. If approved and Route B: initiate staged rollout
   e. If approved and Route C: initiate blue/green deployment
   f. If approved and Route A (distilled rule): add to next delta batch
   g. If requires Route D: flag for your manual review + App Store prep

4. Record all routing decisions in promotion_routing_log
```

```sql
training_artifacts (
    id                      UUID PRIMARY KEY,
    created_at              TIMESTAMPTZ,
    artifact_type           TEXT,    -- 'loraAdapter','fullModel','distilledRule','reasoningUpdate'
    model_version           TEXT,
    base_model              TEXT,
    training_corpus_version TEXT,
    artifact_size_bytes     INT,
    architecture_changed    BOOLEAN,
    benchmark_results       JSONB,
    gate_status             TEXT,    -- 'pending','approved','blocked','routeD_required'
    assigned_route          TEXT,    -- 'A','B','C','D'
    rollout_status          TEXT,    -- 'pending','10pct','50pct','100pct','rolled_back'
    deployed_at             TIMESTAMPTZ
)

promotion_routing_log (
    id              UUID PRIMARY KEY,
    logged_at       TIMESTAMPTZ,
    artifact_id     UUID,
    artifact_type   TEXT,
    assigned_route  TEXT,
    gate_result     TEXT,
    gate_scores     JSONB,
    rollout_day     INT,
    rollout_pct     INT,
    correction_rate_delta  FLOAT,  -- real-world signal during staged rollout
    decision        TEXT,   -- 'continue','halt','rollback','complete'
    notes           TEXT
)
```

---

## 5. The Async Training Loop — Precise Function Boundary

### 5.1 What the Async Loop Does

The async training loop is a completely offline system. It never touches
live user traffic. It produces artifacts. Artifacts are staged. Staged
artifacts pass gate evaluation. Approved artifacts enter delivery routes.

```
ASYNC TRAINING LOOP (offline, no live traffic)
─────────────────────────────────────────────────────────────────────
Input:    expert_annotations (Neon, from annotation sessions)
          ground_truth JSON (local disk / S3)
          prior model version (S3 model storage)

Process:
  1. Export annotation corpus to JSONL training format
     (export_corpus.py — runs against Neon, outputs to /training/corpus/)

  2. Launch training instance (AWS spot, on-demand, or physical box)
     (train.py — reads JSONL, loads base model, runs LoRA fine-tuning)

  3. Evaluate candidate model against validation silo
     (eval.py — runs candidate against validation corpus, computes F1)

  4. If validation positive: run production gate against test silo
     (gate.py — runs candidate against test silo, compares to thresholds)

  5. If gate passes: write training_artifacts row, trigger routing

  6. Routing pipeline delivers artifact via assigned route

Output:   training_artifacts row + delivered artifact (rules/model/update)

What it does NOT do:
  - Never reads from anomaly_flags directly (L0 review is the gate)
  - Never reads live user correction data directly
  - Never touches production Neon database during training
  - Never modifies production PatternLibrary directly
  - Promotion always goes through the gate pipeline, never direct write
```

### 5.2 The Distillation Path — Training → Rules

After a training run improves the model, the distillation analysis runs:

```
Distillation analysis (post-training, before gate):
  1. Run improved model against validation corpus
  2. Run current rule engine against same validation corpus
  3. Find cases: model correct, rules incorrect
  4. For each case: can this pattern be expressed as a rule?
     Yes → generate candidate rule definition
     No  → leave in model weights, not distillable

  5. Candidate distilled rules enter PatternLibrary promotion pipeline
     (same gate process as regular promoted rules)
     Tagged: correction_source: 'distilledFromModel'

  6. Distilled rules that pass gate → Route A (device delta)
     These arrive on device faster than the model itself
     Users get the rule improvement before the next model update
```

The distillation path means improvements the model learned can propagate
to device as explicit rules faster than a full model update would ship.
Rules are lighter (Route A, no staged rollout) and arrive sooner.

### 5.3 Bedrock's Role in the Async Loop

Bedrock is called at two specific points in the async loop only:

```
Point 1 — Pre-annotation (during annotation sessions)
Input:    extraction output + ground truth diff (no MIMIC content)
Output:   pre-classified correction suggestion with rationale
Purpose:  Accelerates human annotation — forms pre-filled for approval
Gate:     Human approves every suggestion — Bedrock proposes, you dispose

Point 2 — Post-benchmark analysis (Step 9 weekly CRON)
Input:    benchmark failure distribution + unresolved terminology
          (no MIMIC content, no raw PHI, no patient data)
Output:   failure classification validation, terminology suggestions,
          rule suggestions for highest-frequency failure clusters
Purpose:  Directs next annotation session focus
Gate:     Human approves every suggestion before corpus entry
```

Bedrock does NOT:
- See raw documents (training or production)
- See MIMIC source content
- Write to any database directly
- Make promotion decisions
- Trigger training runs
- Access the production chain

---

## 6. Device Intelligence Layers — Precise Function Boundary

Three layers run on device simultaneously. Each has a distinct source,
update cadence, and scope. They must not be conflated in implementation.

### 6.1 Layer 1 — PatternLibrary Rules

```
Source:       Offline training loop → Route A delivery
Update:       Silent delta sync on app open (frequent, lightweight)
Scope:        Cross-user — same rules for all users
What it does: Explicit, inspectable rule matching against extraction output
              Rule fires → apply correction → adjust extraction result
              Rule uncertain → pass to Layer 2
What it is:   JSON rule definitions in PatternLibrary versioned store
Size:         Kilobytes per delta, megabytes total library
PHI exposure: Zero — rules contain no patient data
Rollback:     Prior version in consensus_log, revert via admin endpoint
Built by:     Offline training loop (expert annotations → consensus → promotion)
              Also receives: distilled rules from model analysis
```

### 6.2 Layer 2 — Fine-Tuned CoreML Extraction Model

```
Source:       Offline training loop → Route B delivery
Update:       Background download, hot-swap (periodic, larger payload)
Scope:        Cross-user — same model weights for all users
              (personal calibration is Layer 3, not this layer)
What it does: ML inference on document regions
              Generalizes beyond explicit rules
              Handles novel layouts, complex terminology, spatial failures
What it is:   CoreML compiled model (.mlmodelc) — LoRA adapter weights
Size:         10MB–200MB depending on model size and quantization
PHI exposure: Zero — model weights don't encode patient data
Rollback:     Prior .mlmodelc retained on device for 14 days
Staged:       10% → 50% → 100% rollout with correction rate monitoring
Built by:     Offline training loop (expert annotations → fine-tuning → gate)
```

### 6.3 Layer 3 — Personal MLUpdateTask Model

```
Source:       On-device only — trains on user's own corrections via MLUpdateTask
Update:       Continuous — updates when CorrectionStore accumulates 10 new records
Scope:        Personal — specific to this user's documents, providers, scan quality
What it does: Personal calibration on top of Layer 2
              Learns this user's specific LabCorp layout fingerprint
              Learns this user's iPhone camera scan quality
              Learns this user's specific medication list terminology
What it is:   Small CoreML classifier, personal weights, stored in PHI vault
Size:         Small — task-specific classifier, not a language model
PHI exposure: Contained — weights trained on device, never transmitted
Rollback:     N/A — personal weights, user can reset in Settings
Built by:     On-device MLUpdateTask reading CorrectionStore
              This is the ONLY automatic learning from user corrections
              Everything else requires offline expert review
```

### 6.4 Layer Interaction

```
Document region arrives
        ↓
Layer 1 (PatternLibrary rules) evaluates first
  Rule fires, confidence > threshold → accept result
  Rule fires, confidence ≤ threshold → Layer 2
  No applicable rule → Layer 2
        ↓
Layer 2 (fine-tuned model) evaluates
  Confidence > threshold → Tier 1 (auto-accept)
  Confidence ≤ threshold → Layer 3 check
        ↓
Layer 3 (personal model) applies personal calibration
  Adjusts confidence based on personal history with this layout
  Combined confidence score → Tier 1 or Tier 2 assignment
        ↓
Tier 1: extraction shown, no user action required
Tier 2: extraction shown with review prompt
User flags something → anomaly_flags table (NOT training signal)
```

---

## 7. The Acceptable UX Threshold — Precise Definition

"Acceptable threshold for user experience" is a specific measurable state,
not a vague quality target. Implementation must track these metrics explicitly.

### 7.1 Threshold Metrics

```
Metric 1: Tier 1 auto-accept rate
Target:   > 82% of all extractions
Meaning:  82% of extracted fields are high enough confidence that
          the system shows them without requesting user review
Measured: extraction_runs table, confidence scores vs tier thresholds
Gate:     Must reach 82% on held-out validation silo before Phase 1→2

Metric 2: True error rate
Target:   < 5% of total extractions are actual errors
Meaning:  Of all extractions, fewer than 1 in 20 are factually wrong
Measured: expert_annotations where correctionClass IS NOT NULL / total extractions
Gate:     Monitored weekly, not a hard phase gate

Metric 3: Clinically significant error rate
Target:   < 1% of total extractions
Meaning:  Wrong value + wrong label + wrong association = rare
Measured: expert_annotations where clinical_significance = 'high' or 'critical'
Gate:     Monitored weekly, triggers L3 review if approached

Metric 4: Silent miss rate
Target:   < 3% of expected extractions not captured
Meaning:  Fields present in documents but absent in extraction output
Measured: negative_space_annotations / (extractions + negative_space)
Gate:     Monitored weekly
```

### 7.2 Who Monitors These Metrics

The benchmark engine (Step 7) computes all four metrics in every run.
They appear on the SEED Master Control dashboard.
They are not surfaced to end users.
They drive annotation focus: worst-performing metric → annotation priority this week.

### 7.3 User Experience Without User Correction

When the system reaches acceptable threshold:

```
User uploads a document
        ↓
Extraction runs (Layers 1 + 2 + 3)
        ↓
82%+ of fields auto-accepted → shown directly
18%- of fields in Tier 2 → shown with subtle confidence indicator
        ↓
User reads their results
Most look correct → no action needed
Occasional flag → taps "this looks wrong" → anomaly_flags
        ↓
System does NOT ask user to train it
System does NOT present correction forms to users
System does NOT weight user flags as training signal
The system just works, and gets better in the background
```

The correction form UI (Class A–E selections, canonical ID entry, clinical rationale)
is an INTERNAL tool for the SEED Master Control / admin interface only.
It is NOT exposed to end users of the Record Health consumer app.

---

## 8. Long-Tail Function Distinctions Reference

This section captures precise function boundaries for every component
that might be ambiguous in implementation. Reference the relevant row
when building any component.

### 8.1 Storage Boundary Table

| Data type | Where it lives | Who writes it | Who reads it |
|---|---|---|---|
| Raw user documents | Device only (PHI vault) | iOS app | iOS app, Swift CLI (local only) |
| CorrectionStore records | Device only (PHI vault) | iOS app | Layer 3 MLUpdateTask, anomaly_flags uploader |
| anomaly_flags | Neon (Worker API) | BatchUploadService (tokenized) | L0 weekly review |
| expert_annotations | Neon | SEED Master Control (admin) | Export script → training loop |
| pattern_atoms | Neon | PatternAtomExtractor (from expert_annotations only) | Consensus CRON |
| candidate_rules | Neon | Consensus CRON | Consensus CRON, admin module |
| pattern_library | Neon | Consensus CRON (after gate) | CDN distribution, iOS client |
| training_artifacts | Neon | Async training loop (train.py) | Routing pipeline |
| promotion_routing_log | Neon | Routing pipeline | Admin review |
| phi_gateway_log | Private instance only | PHI gateway (Role 1) | HIPAA audit |
| consented_training_corpus | Private instance only | PHI gateway (Tier 3 flow) | Training loop |
| benchmark_runs | Neon | Sampling engine (Step 7) | Admin dashboard, gate evaluation |
| model_versions | Neon | Routing pipeline | Admin dashboard, integration layer (threshold lookup) |
| raw_output_log | Neon (hot 30d) + S3 (raw strings) | Integration layer | Summarization CRON, L0 review |
| raw_output_summary | Neon (indefinite) | Summarization CRON | Migration delta framework, threshold recalibration |
| learning_lineage | Neon | Corpus export pipeline, async training loop | Admin dashboard, annotator routing, unlearning triage |
| annotator_variance_log | Neon | SEED Master Control (on annotator disagreement) | L0 review, guideline quality dashboard |

### 8.2 Write Permission Boundaries

| Component | Can write to | Cannot write to |
|---|---|---|
| iOS app | CorrectionStore (device), anomaly_flags (via Worker) | pattern_atoms, candidate_rules, pattern_library |
| Worker API | anomaly_flags, pattern_atoms (from PatternAtomExtractor), extraction_runs, seed_documents | pattern_library (only CRON can write this) |
| Consensus CRON | candidate_rules, pattern_library, consensus_log, benchmark_runs | expert_annotations, anomaly_flags |
| SEED Master Control | expert_annotations, negative_space_annotations | pattern_library (read-only), anomaly_flags (read-only) |
| Async training loop | training_artifacts | pattern_library (goes through CRON + gate) |
| Bedrock | Nothing — inference only, reads prompts, returns text | Everything |
| Integration layer | raw_output_log | raw_output_summary, learning_lineage |
| Summarization CRON | raw_output_summary | raw_output_log (read-only after initial write) |
| Corpus export pipeline | learning_lineage (corpus inclusion event) | training_artifacts |
| Async training loop (lineage) | learning_lineage (training_artifact_id field) | expert_annotations |
| SEED Master Control | expert_annotations, negative_space_annotations, annotator_variance_log | pattern_library (read-only), anomaly_flags (read-only) |

### 8.3 Read-Only Boundaries

| What | Read-only for these components |
|---|---|
| pattern_library | iOS app, SEED Master Control, benchmark engine |
| expert_annotations | Export script, benchmark engine (read-only for scoring) |
| test silo documents | Benchmark engine (scoring only, no annotation allowed) |
| phi_gateway_log | Compliance audit only, no operational reads |

### 8.4 Trigger Boundaries — What Starts What

| Trigger | Starts | Does NOT start |
|---|---|---|
| App open | Pattern library version check + delta download | Training run |
| User document upload | On-device extraction (Layers 1+2+3) | Server-side extraction |
| User flag | anomaly_flags write | PatternAtom creation |
| L0 novel_failure classification | expert_annotations row creation | Automatic training run |
| Monday 6AM CRON | Benchmark run → Bedrock analysis chain | Training run |
| Manual (you) | Training run | Automatic promotion |
| Gate approval (you, admin module) | Artifact routing + delivery | Training run |
| Route B staged rollout | Correction rate monitoring | Automatic 100% rollout |
| Correction rate delta negative | Staged rollout halt | Automatic rollback (manual decision) |
| Extraction run completes | raw_output_log write (before normalization) | Normalization |
| Normalization completes | normalized extraction_runs write, normalization_delta computation | raw_output_log write (already done) |
| 30-day raw output window expires | Summarization CRON (daily 3AM) | Hard deletion (soft-delete only, hard delete +7 days) |
| Model swap gate approved | Threshold recalibration write to consensus_config | Model deployment (requires thresholds first) |
| Annotation enters corpus snapshot | learning_lineage row creation | Training run (manual trigger only) |
| Annotator disagreement logged | annotator_variance_log write | Automatic guideline update |

### 8.5 The Difference Between Similar-Sounding Things

**PatternAtom vs expert_annotation:**
- `expert_annotation`: Human-labeled training record. Contains correction class, clinical
  rationale, canonical ID, annotator level. Source of training data. Written by L0–L5.
- `pattern_atom`: PHI-stripped, non-PHI artifact derived FROM expert_annotations by
  PatternAtomExtractor. Feeds consensus engine. Never written directly by humans.

**anomaly_flag vs CorrectionStore record:**
- `CorrectionStore record`: On-device, PHI-containing, used for personal Layer 3 calibration
  only. Never transmitted in raw form.
- `anomaly_flag`: Server-side, PHI-stripped, used for L0 anomaly detection review only.
  Never feeds training automatically.

**PatternLibrary rule vs CoreML model weight:**
- PatternLibrary rule: Explicit JSON definition. Inspectable. You can read it and understand
  exactly what it does and when it fires. Route A delivery.
- CoreML model weight: Implicit float values encoding learned patterns. Not directly readable.
  Generalizes from training examples. Route B delivery.

**Distilled rule vs promoted rule:**
- Promoted rule: Emerged from expert annotation → PatternAtom → consensus accumulation.
  Correction_source: 'seedCorpus' or 'expertAnnotation'.
- Distilled rule: Extracted from model behavior analysis — what the model learned that can
  be expressed explicitly. Correction_source: 'distilledFromModel'. Same promotion pipeline,
  different origin tag. Useful for tracking what the model contributed to the rule engine.

**Staged rollout (Route B) vs immediate delivery (Route A):**
- Route A (PatternLibrary delta): Immediate — next time any user opens the app, they get
  the new rules. No monitoring period. Rollback available but not staged.
- Route B (model download): Staged — 10% of users first, monitor correction rate, expand
  or rollback based on real-world performance signal. Takes 7 days to full rollout.

**Benchmark delta vs correction rate delta:**
- Benchmark delta: Computed offline against expert-annotated test silo. Measures extraction
  accuracy against known ground truth. Used to make the gate decision.
- Correction rate delta: Computed from real user behavior during staged rollout. Measures
  whether users are flagging more or fewer things after a model update. Used to make the
  continue/halt decision during rollout. Real-world correction rate is the ground truth
  that the benchmark approximates.

**raw_output_log vs raw_output_summary:**
- `raw_output_log`: Full fidelity record. Raw confidence vector per field type, full raw
  model output string, normalization delta audit. Written before normalization. Retained
  30 days (flagged runs retained until anomaly_flag reaches terminal review_status). High
  storage cost.
- `raw_output_summary`: Summarized form. Percentile bands replace raw vector. Raw string
  gone. Written by summarization CRON after hot window expires. Retained indefinitely.
  Supports migration delta and threshold recalibration but not per-field exact confidence
  recovery for unflagged runs older than 30 days.

**learning_lineage vs consensus_log:**
- `consensus_log`: Records PatternLibrary rule promotion decisions — what rule, what version,
  what observation count, what diversity score. Audit trail for the consensus engine.
- `learning_lineage`: Records the full chain from failure event to training outcome. Links
  anomaly_flag → expert_annotation → corpus_snapshot → training_artifact → benchmark delta.
  Spans the entire System A pipeline. Supports unlearning triage and annotator routing.

**model_versions vs training_artifacts:**
- `training_artifacts`: Production record of a training run. Base model, corpus snapshot,
  hyperparameters, benchmark scores, gate decision. One row per training run.
- `model_versions`: Deployment record of what is currently live. Points to a training_artifact.
  Tracks staged rollout status, deployment timestamp, retirement timestamp, rollback window.

---

## 10. Integration Layer Constraints

Hard constraints on any sprint implementing extraction routing, tier assignment,
or model output handling. Reference INTEGRATION_LAYER.md for full schema and rationale.

1. Raw output logging occurs BEFORE normalization. Never after. The integration layer
   writes to raw_output_log first. Normalization runs second. This order is non-negotiable.

2. Tier assignment thresholds are read from consensus_config keyed by model_version.
   No hardcoded thresholds anywhere in routing logic.

3. normalization_delta is computed and logged on every extraction run. When pre- and
   post-normalization tier differ, the case is flagged for manual review.

4. The stable output schema (INTEGRATION_LAYER.md §3.2) is the only schema consumed
   by routing logic and anomaly detection. Raw output (§3.3) is write-only for those systems.

5. Model swap is not complete until new model_version thresholds are written to
   consensus_config and shadow evaluation migration_delta_score is recorded in
   training_artifacts.

6. learning_lineage row is written for every annotation entering a corpus snapshot.
   No annotation enters training without a lineage record.

---

## 9. Sprint Prompt Reference Guide

When Claude Code is implementing a specific component, it should reference
the section of this document that governs that component's behavior.

| Component being built | Reference sections |
|---|---|
| User flag UI in iOS app | 3.1 (flag flow), 7.3 (no correction form for users) |
| anomaly_flags Worker endpoint | 3.1 (schema), 8.2 (write permissions) |
| CorrectionStore iOS implementation | 3.3 (revised purpose), 6.3 (Layer 3 only) |
| PatternAtomExtractor | 3.3 (no longer reads CorrectionStore for cross-user training) |
| BatchUploadService | 3.1 (uploads to anomaly_flags, not pattern_atoms directly) |
| Consensus CRON job | 2.2 (phase gates), 4.3 (routing pipeline) |
| system_maturity table | 2.3 (corrected schema, no user counts) |
| training_artifacts table | 4.3 (schema), 5.1 (what the async loop writes) |
| promotion_routing_log | 4.3 (schema), 4.4 (Route B staged rollout) |
| SEED Master Control dashboard | 7.1 (threshold metrics to display) |
| SEED Master Control annotation queue | 3.2 (correction form is admin only) |
| Route B staged rollout | 4.2 (staged rollout protocol), 8.5 (correction rate delta) |
| Route C blue/green deployment | 4.2 (private instance update) |
| Personal MLUpdateTask (Layer 3) | 6.3 (personal scope, never distributed) |
| Export script (corpus → JSONL) | 5.1 (reads expert_annotations, not CorrectionStore) |
| Distillation analysis script | 5.2 (post-training, produces Route A candidates) |
| Bedrock pre-annotation (Step 5b) | 5.3 (Point 1 — annotation sessions only) |
| Bedrock benchmark analysis (Step 9) | 5.3 (Point 2 — post-benchmark only) |
| PHI gateway (Stage 4 Role 1) | 8.1 (phi_gateway_log on private instance only) |
| Integration layer normalization boundary | 10 (constraints), INTEGRATION_LAYER.md §3 (schema) |
| raw_output_log Worker write | 10.1 (before normalization), INTEGRATION_LAYER.md §3.3 |
| Summarization CRON handler | SERVER_INFRASTRUCTURE.md §6.2, INTEGRATION_LAYER.md §3.3 |
| model_versions deployment tracking | INTEGRATION_LAYER.md §4.2 (schema) |
| learning_lineage write path | INTEGRATION_LAYER.md §5, 10.6 (no annotation without lineage) |
| Shadow evaluation / migration delta | INTEGRATION_LAYER.md §7 |
| Threshold recalibration on model swap | INTEGRATION_LAYER.md §6, 10.2 |

---

*End of document.*

*This document is authoritative for all function-level implementation decisions.
When a sprint prompt references this document, Claude Code instances should treat
the distinctions defined here as hard constraints, not suggestions. The corrected
training model (section 1), corrected phase gates (section 2), and user flag
boundary (section 3) supersede corresponding sections in ADI v2.1 and
EXPERT_ANNOTATION v1.2. All other sections in those documents remain in effect.
Document version 1.1 adds: integration layer rows to sections 8.1–8.5, new
section 10 (integration layer constraints), and integration layer entries to the
sprint prompt reference guide. See INTEGRATION_LAYER.md for full schema.*
