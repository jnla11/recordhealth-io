# Server Infrastructure
## Record Health API — Cloudflare Worker Reference

**Document version:** 1.1
**Status:** Current state + ADI build requirements
**Describes:** recordhealth-api Worker project, existing bindings, route surface, DB schema, and infrastructure gaps to be provisioned for ADI
**Companion documents:** ADAPTIVE_DOCUMENT_INTELLIGENCE.md, ARCHITECTURE.md, INTEGRATION_LAYER.md

---

## 1. Project Overview

```
Project name:     recordhealth-api
Entry point:      src/index.js
Runtime:          Cloudflare Worker (nodejs_compat enabled)
Architecture:     Single-file monolith, 688 lines
Routing:          Manual if-chain — no router library
Deploy:           wrangler deploy (CLI, manual)
Account email:    jason_nolte@hotmail.com
```

All routes, auth middleware, AI proxying, token metering, and cron logic live in `src/index.js`. There is no build step — the file is deployed directly.

---

## 2. Environment Bindings

All secrets and external service credentials are injected via Cloudflare Worker environment variables. Never hardcoded.

```
env.DATABASE_URL              Neon Postgres connection string (all persistent data)
env.AWS_ACCESS_KEY_ID         AWS credentials for Bedrock
env.AWS_SECRET_ACCESS_KEY
env.AWS_REGION
env.BEDROCK_MODEL_ID          claude-sonnet-4-6 (or current model string)
env.JWT_SECRET                HS256 signing key for worker-issued JWTs
env.DEV_BYPASS_USER           User ID that skips token budget enforcement in dev
```

New bindings required for ADI are listed in section 8.

---

## 3. Authentication Pattern

**Flow:** Apple Sign In on device → Apple identity token → POST /auth/apple → worker-issued HS256 JWT (30-day expiry) → all subsequent requests carry Bearer JWT.

Auth0 was removed in Sprint 24e. The worker is now the sole JWT issuer.

**Auth middleware pattern** (from index.js):
- Extract `Authorization: Bearer {token}` header
- Verify with `env.JWT_SECRET` using HS256
- Reject with 401 if missing, malformed, or expired
- Attach decoded payload to request context for downstream handlers
- All `/protected` routes run through this middleware before handler logic

New ADI routes follow this same pattern. No new auth mechanism required.

---

## 4. Database — Neon Postgres

### 4.1 Connection

Driver: `@neondatabase/serverless` (HTTP-based, compatible with Cloudflare Worker runtime)  
Connection: `env.DATABASE_URL` (pooled connection string from Neon dashboard)  
No connection pooling configuration required — Neon serverless handles this.

### 4.2 Existing Tables

```sql
users               -- user accounts, Apple sub ID, tier, created_at
subscriptions       -- StoreKit subscription records per user
token_usage         -- per-user token consumption ledger
token_boosts        -- one-time boost pack credits
health_records      -- user health records (currently thin, iOS is source of truth)
audit_log           -- server-side audit events
```

**Stored function:**
```sql
get_token_balance(user_id)  -- computes available tokens across usage + boosts
```

### 4.3 ADI Tables — To Be Provisioned

The following tables are added to Neon Postgres as part of ADI Phase 3. They do not require a separate D1 database (see section 7 for the rationale).

```sql
-- Raw pattern atom index (queryable, no raw content)
pattern_atoms (
    id                      UUID PRIMARY KEY,
    created_at              TIMESTAMPTZ,
    batch_id                UUID,
    client_id_hash          TEXT,           -- nulled after consensus processing
    app_version             TEXT,
    pattern_library_version TEXT,
    document_category       TEXT,
    provider_layout_hash    TEXT,
    layout_region_type      TEXT,
    field_type              TEXT,
    confusion_class         TEXT,
    ocr_engine              TEXT,
    ocr_confidence_pre      FLOAT,
    ocr_confidence_post     FLOAT,
    resolved_canonical_id   TEXT,
    canonical_system        TEXT,
    correction_source       TEXT,
    opt_in_level            TEXT,
    visual_features         JSONB,          -- VisualFeatureVector struct
    processed               BOOLEAN DEFAULT FALSE
)

-- Candidate rules accumulating toward promotion threshold
candidate_rules (
    id                      UUID PRIMARY KEY,
    created_at              TIMESTAMPTZ,
    confusion_class         TEXT,
    document_category       TEXT,
    field_type              TEXT,
    ocr_engine              TEXT,
    visual_feature_cluster  JSONB,          -- centroid of contributing atoms
    observation_count       INT DEFAULT 0,
    diversity_score         FLOAT,
    contradiction_rate      FLOAT,
    status                  TEXT,           -- 'accumulating', 'flagged', 'promoted', 'rejected'
    flagged_reason          TEXT,
    last_evaluated_at       TIMESTAMPTZ
)

-- Promoted rules — the versioned PatternLibrary
pattern_library (
    id                      UUID PRIMARY KEY,
    promoted_at             TIMESTAMPTZ,
    library_version         TEXT,           -- semver e.g. '0.7.1'
    confusion_class         TEXT,
    document_category       TEXT,
    field_type              TEXT,
    ocr_engine              TEXT,
    rule_definition         JSONB,          -- the actionable correction rule
    confidence_score        FLOAT,
    source_candidate_id     UUID,           -- FK → candidate_rules
    superseded_by           UUID            -- FK → pattern_library (if replaced)
)

-- Audit trail of all promotion decisions
consensus_log (
    id                      UUID PRIMARY KEY,
    logged_at               TIMESTAMPTZ,
    candidate_id            UUID,
    decision                TEXT,           -- 'promoted', 'rejected', 'flagged', 'held'
    decision_reason         TEXT,
    library_version_before  TEXT,
    library_version_after   TEXT,
    observation_count       INT,
    diversity_score         FLOAT
)

-- Client metadata for burst detection and diversity scoring
client_metadata (
    client_id_hash          TEXT PRIMARY KEY,
    opt_in_level            TEXT,
    first_seen_at           TIMESTAMPTZ,
    last_seen_at            TIMESTAMPTZ,
    lifetime_atom_count     INT DEFAULT 0
    -- No PII. client_id_hash is one-way, non-reversible.
)

-- Consensus engine configuration — tunable without code deploy
consensus_config (
    key                     TEXT PRIMARY KEY,
    value                   TEXT,
    updated_at              TIMESTAMPTZ
    -- Stores promotion thresholds, diversity minimums, burst detection params
    -- Also stores model-version-keyed tier thresholds for integration layer:
    -- e.g. key = 'tier1_floor.BioMistral-7B-finetuned-v0.3.1', value = '0.85'
)

-- Full chain lineage from failure event to training outcome
learning_lineage (
    id                          UUID PRIMARY KEY,
    created_at                  TIMESTAMPTZ,
    origin_type                 TEXT,       -- 'anomaly_flag' | 'seed_document' | 'mimic_document'
    origin_id                   UUID,       -- FK → anomaly_flags | seed_documents | mimic_documents
    expert_annotation_id        UUID,       -- FK → expert_annotations, null if not annotated
    annotation_created_at       TIMESTAMPTZ,
    annotator_level             TEXT,       -- L0–L5
    corpus_snapshot_id          UUID,       -- FK → corpus export run
    corpus_included_at          TIMESTAMPTZ,
    training_artifact_id        UUID,       -- FK → training_artifacts
    training_weight             FLOAT,      -- 1.0 standard, 0.7 distilled, 1.1 active opt-in
    post_training_benchmark_id  UUID,       -- FK → benchmark_runs after artifact deployed
    field_type                  TEXT,
    confusion_class             TEXT,
    f1_before                   FLOAT,      -- benchmark F1 on this class before training
    f1_after                    FLOAT,      -- benchmark F1 on this class after training
    delta                       FLOAT,      -- f1_after - f1_before
    annotation_cycle_count      INT         -- annotation cycles before promotion threshold hit
)

-- Raw model output before normalization — 30-day hot window
-- Flagged runs retained until linked anomaly_flag reaches terminal review_status
raw_output_log (
    id                          UUID PRIMARY KEY,
    logged_at                   TIMESTAMPTZ,
    extraction_run_id           UUID,
    model_version               TEXT,
    is_sampled                  BOOLEAN,    -- true = 10% clean sample; false = flagged (always logged)
    is_flagged                  BOOLEAN,
    raw_confidence_vector       JSONB,      -- {field_type: confidence_float, ...}
    raw_model_output_s3_key     TEXT,       -- S3 key (preferred; route raw strings to S3)
    raw_model_output            TEXT,       -- fallback only if S3 routing not active
    pre_normalization_tier      TEXT,
    post_normalization_tier     TEXT,
    normalization_delta         BOOLEAN,    -- true if tier changed during normalization
    normalization_delta_reason  TEXT,
    summarized_at               TIMESTAMPTZ,
    deleted_at                  TIMESTAMPTZ -- soft delete; hard delete runs 7 days after
)

-- Summarized form replacing raw_output_log after 30-day hot window
raw_output_summary (
    id                          UUID PRIMARY KEY,
    extraction_run_id           UUID,
    model_version               TEXT,
    summarized_at               TIMESTAMPTZ,
    confidence_p10              FLOAT,
    confidence_p25              FLOAT,
    confidence_p50              FLOAT,
    confidence_p75              FLOAT,
    confidence_p90              FLOAT,
    confidence_by_field         JSONB,      -- median confidence per field_type (preserved)
    tier_assignment             TEXT,
    escalation_flag             BOOLEAN,
    normalization_delta         BOOLEAN,    -- preserved even after summarization
    anomaly_flag_id             UUID        -- FK → anomaly_flags if this run was flagged
)

-- Currently deployed model versions and rollback window
model_versions (
    id                          UUID PRIMARY KEY,
    created_at                  TIMESTAMPTZ,
    training_artifact_id        UUID,
    model_version_string        TEXT,       -- e.g. 'BioMistral-7B-finetuned-v0.3.1'
    layer                       TEXT,       -- '1_ondevice' | '2_private' | '3_bedrock_passthrough'
    route                       TEXT,       -- 'A' | 'B' | 'C' | 'D'
    status                      TEXT,       -- 'staging' | 'active' | 'retired'
    deployed_at                 TIMESTAMPTZ,
    retired_at                  TIMESTAMPTZ,
    replaced_by                 UUID,       -- FK → model_versions
    rollback_available_until    TIMESTAMPTZ
)

-- Inter-annotator disagreement tracking — guideline quality signal
annotator_variance_log (
    id                          UUID PRIMARY KEY,
    logged_at                   TIMESTAMPTZ,
    expert_annotation_id        UUID,
    field_type                  TEXT,
    confusion_class             TEXT,
    annotator_a_level           TEXT,
    annotator_b_level           TEXT,
    annotator_a_class           TEXT,
    annotator_b_class           TEXT,
    resolution                  TEXT,       -- 'a_correct' | 'b_correct' | 'escalated' | 'guideline_gap'
    guideline_gap_noted         BOOLEAN DEFAULT FALSE
)
```

---

## 5. Existing Route Surface

### 5.1 Public (no auth)

```
OPTIONS  *                   CORS preflight — all routes
GET      /health             Liveness check — returns 200 OK
GET      /health/db          DB connectivity — runs SELECT now()
POST     /auth/apple         Apple identity token → HS256 JWT (30d expiry)
```

### 5.2 Protected (Bearer JWT required)

```
GET      /me                         Current user profile
GET      /usage                      Token balance, usage %, warnings
GET      /subscription               Current subscription row
POST     /subscription/verify        StoreKit receipt → tier upgrade or boost credit

GET      /records                    List health records (?type=, ?limit=)
GET      /records/:id                Single record
POST     /records                    Create record
PUT      /records/:id                Update record
DELETE   /records/:id                Delete record

POST     /ai/chat                    Multi-turn chat via Bedrock, token-metered
POST     /ai/query                   Single-prompt with optional record context
POST     /ai/test                    Lightweight Bedrock connectivity test
```

### 5.3 ADI Routes — To Be Added

```
POST     /v1/pattern-atoms           Batch atom ingestion (auth required)
GET      /v1/pattern-library/latest  Current library version metadata
GET      /v1/pattern-library/delta   Delta since ?from_version= (CDN-cacheable)
POST     /v1/gradients               Federated gradient delta submission (Phase 5)
GET      /v1/gradients/model/latest  Current global model weights (Phase 5)
```

All ADI routes are versioned under `/v1/` to distinguish from the unversioned existing surface. Consider backfilling `/v1/` prefix to existing routes in a future cleanup sprint — not a blocker.

---

## 6. Cron Triggers

### 6.1 Existing

```
Schedule: 0 0 1 * *   (1st of every month, midnight UTC)
Purpose:  Token drip — credits 3,000 tokens to all free-tier users
Handler:  scheduledHandler() in index.js
```

### 6.2 ADI Cron — To Be Added

```
Schedule: 0 2 * * *   (daily at 2:00 AM UTC)
Purpose:  Consensus CRON — evaluate candidate rules, promote to PatternLibrary,
          compute diversity scores, run burst detection, generate library diff,
          invalidate distribution cache
Handler:  adiConsensusHandler() — to be added to index.js or extracted

Schedule: 0 3 * * *   (daily at 3:00 AM UTC — after consensus CRON)
Purpose:  ADI summarization — summarize raw_output_log rows past 30-day hot
          window, write raw_output_summary rows, soft-delete raw rows
Handler:  adiSummarizationHandler()

Schedule: 0 4 * * *   (daily at 4:00 AM UTC — after summarization)
Purpose:  ADI retention cleanup — hard delete soft-deleted rows older than 7 days,
          archive normalized extraction_runs to S3 past 180 days,
          archive resolved anomaly_flags to S3 past 365 days
Handler:  adiRetentionCleanupHandler()
```

**wrangler.toml change required:**
```toml
[triggers]
crons = [
  "0 0 1 * *",    # existing token drip
  "0 2 * * *",    # ADI consensus job
  "0 3 * * *",    # ADI summarization job
  "0 4 * * *"     # ADI retention cleanup job
]
```

The scheduled handler in index.js will need to branch on the cron schedule string to route to the correct handler function.

---

## 7. Critical Infrastructure Decision: D1/R2 vs. Neon Postgres

### 7.1 The Conflict

`ADAPTIVE_DOCUMENT_INTELLIGENCE.md` specified Cloudflare D1 (SQLite) and R2 (object storage) for the ADI server repository. The existing stack uses **Neon Postgres** with no D1 or R2 provisioned on this account.

### 7.2 Recommendation: Consolidate on Neon Postgres

**Do not introduce D1 and R2.** Use Neon Postgres for all ADI structured data.

Rationale:

- Neon Postgres is already the single source of truth for all server-side data. Splitting ADI into a separate storage tier creates operational complexity with no meaningful benefit at this scale.
- The consensus engine's query patterns (aggregation, grouping, threshold comparison, JSONB feature clustering) are well-served by Postgres and poorly served by SQLite (D1).
- Neon's serverless HTTP driver is already integrated and working. No new driver, no new connection management.
- R2 was specified for raw batch file archival. This can be implemented as a Neon table (`pattern_atom_batches`) with a JSONB payload column for v1, with a migration path to R2 if storage volume justifies it later. At projected v1 scale (see ADI spec section 6 cost estimate) it never will.

**ADAPTIVE_DOCUMENT_INTELLIGENCE.md section 8.1** should be considered superseded by this decision. The table schema in section 4.3 above is the authoritative replacement.

### 7.3 What Still Needs Provisioning

Nothing new needs to be enabled in the Cloudflare dashboard. The ADI tables are added to the existing Neon database via migration. New environment bindings are listed in section 8.

---

## 8. ADI Environment Bindings — To Be Added

```
env.ADI_PHI_PATTERN_BLOCKLIST    Comma-separated regex patterns for server-side PHI strip verification
env.ADI_CONSENSUS_MIN_N          Default minimum observation count for promotion (overrides consensus_config table default during cold start)
env.ADI_BURST_WINDOW_HOURS       Burst detection window in hours (default: 24)
env.ADI_LIBRARY_CACHE_TTL        CDN cache TTL for pattern library delta responses in seconds
env.ADI_LOG_SAMPLE_RATE_CLEAN    Clean run raw output sample rate (default: 0.10)
env.ADI_RAW_VECTOR_RETENTION_DAYS  Hot window for raw_output_log in days (default: 30)
env.ADI_EXTRACTION_ARCHIVE_DAYS  Extraction run Neon→S3 archive threshold in days (default: 180)
env.ADI_ANOMALY_ARCHIVE_DAYS     Resolved anomaly_flag archive threshold in days (default: 365)
env.ADI_S3_LOG_BUCKET            S3 bucket for raw output string storage (raw_model_output_s3_key)
env.ADI_S3_ARCHIVE_BUCKET        S3 bucket for cold archive (extraction_runs, anomaly_flags)
```

These are added to the Cloudflare Worker environment via the dashboard or `wrangler secret put`.

---

## 9. AI Layer — AWS Bedrock

```
Service:    AWS Bedrock
Model:      env.BEDROCK_MODEL_ID (currently claude-sonnet-4-6)
Auth:       SigV4 via aws4fetch library
Response:   Mapped to OpenAI-compatible format at the Worker layer
            (iOS app sends/receives OpenAI schema — no app changes required for model swaps)
Metering:   Token usage tracked per-user in token_usage table
            Grace threshold: 10% below limit before warning surfaced
```

ADI does not interact with the Bedrock layer. Pattern atom processing and consensus computation are pure data operations with no AI inference calls.

---

## 10. Routing Architecture Note

The current Worker uses a **manual if-chain** for routing — no router library. At 688 lines this is manageable. At the end of the ADI build it will be approximately 1,000-1,100 lines with the new routes and handlers.

**Recommendation:** When the ADI routes are added (Phase 3), extract route handlers into separate functions grouped by domain at the top of index.js. Do not split into multiple files yet — the single-file pattern is working and Cloudflare's tooling handles it cleanly. Revisit splitting into a proper router (Hono is the natural choice given the runtime) when the file crosses 1,500 lines or when a second Worker is warranted.

This is a note for future planning, not a blocker for ADI implementation.

---

## 11. Deployment

```
Command:    wrangler deploy
Target:     Production (no staging environment currently)
Process:    Edit src/index.js → wrangler deploy → verify via /health and /health/db
Secrets:    Set via wrangler secret put {KEY} or Cloudflare dashboard
```

**No staging environment is currently configured.** For ADI, consider adding a `[env.staging]` block to wrangler.toml with a separate DATABASE_URL pointing to a Neon branch. Neon supports instant database branching — a staging branch costs nothing and eliminates the current pattern of testing against production. Not a blocker for Phase 1-2 (on-device work), but worth doing before Phase 3 when the Worker starts receiving real atom payloads.

---

## 12. ADI Build Dependency Map

Reference this when scoping implementation sprints:

```
Phase 1 (on-device — no server changes)
└── CorrectionStore, PatternAtomExtractor, BatchUploadService buffer
    No server work. No new bindings.

Phase 3 (server side begins)
├── Prerequisite: Neon migration — add ADI tables (section 4.3)
├── Prerequisite: wrangler.toml — add daily cron trigger (section 6.2)
├── Prerequisite: New env bindings (section 8)
└── New routes: /v1/pattern-atoms, /v1/pattern-library/latest, /v1/pattern-library/delta

Phase 4 (consensus refinement)
└── adiConsensusHandler() — reads candidate_rules, promotes to pattern_library
    Runs on daily cron. No new infrastructure.

Phase 5 (federated learning)
├── New routes: /v1/gradients, /v1/gradients/model/latest
└── Gradient aggregation handler — stateless, reads submissions, writes averaged weights
    Weights stored in pattern_library table as JSONB blob or separate model_versions table

Integration Layer (parallel to Phase 3 server work)
├── raw_output_log table + indexes
├── raw_output_summary table
├── learning_lineage table
├── annotator_variance_log table
├── model_versions table (extended from routing pipeline)
├── consensus_config model-version-keyed threshold rows
└── Integration layer normalization boundary wired into extraction route handler
    See INTEGRATION_LAYER.md for full schema and constraints

Post-Phase 3 (after first training run)
├── adiSummarizationHandler() CRON (daily 3AM)
├── adiRetentionCleanupHandler() CRON (daily 4AM)
└── Shadow evaluation framework for first model swap
    See INTEGRATION_LAYER.md §7 for migration delta methodology
```

---

*End of document.*

*This document describes the current state of recordhealth-api and the infrastructure changes required to support ADI. Implementation prompts should reference both this document and the relevant sections of ADAPTIVE_DOCUMENT_INTELLIGENCE.md. Schema changes require this document to be updated before implementation begins. Document version 1.1 adds: learning_lineage, raw_output_log, raw_output_summary, model_versions, and annotator_variance_log tables to section 4.3; ADI summarization and retention cleanup CRONs to section 6.2; six new env bindings to section 8; integration layer and post-Phase 3 blocks to section 12. See INTEGRATION_LAYER.md for the model abstraction contract and migration delta framework that these tables support.*
