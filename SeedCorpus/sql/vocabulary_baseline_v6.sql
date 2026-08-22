-- ============================================================================
-- vocabulary_baseline_v6.sql
--
-- Source:       SeedCorpus/INGEST_VOCABULARY_DESIGN.md — DRAFT v6 (2026-08-20),
--               §5.0, §5.3, §6, §8 rung 4 / rung 6, §9 items 6/9/10/12,
--               rulings OR-12, OR-13, OR-14, OR-15, OR-16.
-- Author date:  2026-08-20
-- Scope:        Fresh-baseline DDL for the v6 vocabulary work. Two database
--               groups, two independent sections:
--                 SECTION A — USER-FLOW group (`DATABASE_URL`):
--                             new table `vocabulary_misfire_events` (the
--                             misfire log, §6 / OR-15).
--                 SECTION B — ADI group (`ADI_DATABASE_URL`):
--                             dev-corpus wipe, new table `vocabulary_terms`
--                             (the dictionary, §8 rung 6 item 1), and the
--                             `data_atoms` atom-side changes (raw kind column,
--                             nullable term reference, certainty default kill).
--
--               NOT in scope, deliberately: `column_role`'s own optional term
--               reference (§8 rung 6 item 2 leaves it to the implementation);
--               the misfire log's row cap and retention policy (§9 item 12 —
--               un-ruled, to be set alongside L7's sweeper as one policy pass);
--               any L7 table (INGEST_LIVENESS_DESIGN §4 owns those).
--
-- OWNER-RUN, BY HAND, IN THE NEON BROWSER SQL EDITOR.
--
-- ── HOW TO RUN ──────────────────────────────────────────────────────────────
-- 1. Sections A and B target DIFFERENT Neon projects. Run them separately.
--    Do not paste the whole file into one editor tab.
-- 2. Each section runs FOUR times in total: staging first, verify, then
--    production (DATABASE_LAYOUT.md § Migration workflow rules, rule 4).
-- 3. Each section opens with a `DO $$ ... $$` endpoint guard rail (rule 6).
--    EDIT the `expected_endpoint` literal before each run. The guard exists
--    because of the Neon-editor database-dropdown footgun documented under
--    DATABASE_LAYOUT.md § Known schema footguns — a query silently scoped to
--    the wrong database inside the right branch.
-- 4. The guard blocks are dollar-quoted. If this file is ever run through a
--    programmatic runner instead of the browser editor, that runner must be a
--    real Postgres client, never a `split(";")` splitter (rule 5).
-- 5. Each section ends with a `schema_migrations` ledger insert (rule 3) and a
--    trailing verify block to run on an independent reconnect (rule 7).
--
-- ── POSTGRES VERSION REQUIREMENT ────────────────────────────────────────────
-- SECTION A's dedup index uses `UNIQUE NULLS NOT DISTINCT` (PostgreSQL 15+).
-- Extractor identity is legitimately NULL on lifecycle surfaces (§6), and the
-- merge key must treat two NULL extractors as the same observation class. If
-- the target Neon branch is somehow pre-15 the CREATE will error loudly rather
-- than silently create a key that never merges; a COALESCE-expression fallback
-- is given, commented out, beside it.
--
-- ── PROCESS DIVERGENCE, STATED ──────────────────────────────────────────────
-- DATABASE_LAYOUT.md § Migration workflow rules, rule 1 requires a committed
-- migration file under `recordhealth-api/migrations/` before any DDL runs. This
-- file lives at `SeedCorpus/sql/` in the parent repo, at the owner's explicit
-- instruction, and `recordhealth-api` is a submodule. RESOLVED 2026-08-21: this
-- copy is the mirror committed under `recordhealth-api/migrations/`, satisfying
-- rule 1. It diverges from the SeedCorpus original only by the owner-confirmed
-- edits of 2026-08-21 (full Section B wipe enabled; A6 retirement enabled),
-- each marked inline.
--
-- ── AUTHORING DECISIONS (design delegates these; flagged for owner review) ───
-- The design explicitly hands the baseline DDL itself — table shapes, seed
-- content, indexes — to the `recordhealth-api` review ("What this doc
-- deliberately does not own"). Every choice below that the design did not make
-- is marked `AUTHORED:` inline. The load-bearing ones:
--   A1. The misfire log lives in the USER-FLOW group, not the ADI group. The
--       §6 seam requires `environment` / `job_id` / vendor-identity conventions
--       shared with L7 "so a misfire row's exemplar joins against phase events
--       ad hoc" — an ad-hoc join needs one database, and `ingest_phase_events`
--       / `ingest_spend_events` / `error_events` are all user-flow tables. The
--       ADI feeder (§8 rung 6 item 3) therefore writes cross-binding, which is
--       already required: it is out-of-transaction and observe-never-gated.
--   A2. The atom's raw kind column keeps the name `entity_kind`, retyped from
--       `entity_kind_enum` to plain `TEXT NOT NULL`. `data_atoms.verbatim_value`
--       already exists and is the atom's clinical value, NOT the vocabulary raw
--       string; the two must not be conflated. Keeping the name means existing
--       corpus `GROUP BY entity_kind` queries now group on the raw column,
--       which is exactly §8 rung 6's reader instruction ("group on the raw
--       column as ground truth, with the reference as enrichment").
--   A3. [OWNER-CONFIRMED 2026-08-21 — stands as authored.]
--       `classification_certainty` loses NOT NULL as well as its DEFAULT.
--       OR-16 requires absence to be "persisted *as absent*" so §5.2 property
--       2's three-way distinguishability survives in the encoding. Dropping
--       only the DEFAULT while keeping NOT NULL would make an omitted certainty
--       an INSERT error, which is a refusal — the exact posture OR-12/OR-13
--       delete. Confirmed intended.
--   A4. Extractor identity columns are `extractor_vendor` / `extractor_model` /
--       `extractor_version`. `extractor_vendor` carries the SAME value domain
--       as `ingest_spend_events.vendor` ('llamacloud' | 'bedrock' | successors)
--       per OR-14, so `ON m.extractor_vendor = s.vendor` is the ad-hoc join;
--       the prefix disambiguates it from the misfire row's own provenance.
--   A5. `vocabulary_terms.display_name` and `.notes` are curation metadata the
--       design does not name. A hand-authored dictionary needs a human label.
--       Both nullable; delete them if unwanted.
--   A6. [OWNER-CONFIRMED 2026-08-21 — retirement ENABLED.] `visitDate` and
--       `reportDate` are seeded because the design says "the 33 values", full
--       stop, then retired by the UPDATE immediately below the seed. They are
--       dead in practice (DATABASE_LAYOUT § Drift: rejected by the Worker
--       validator, rows backfilled to `dateAtom`), so the dictionary carries
--       all 33 rows with those two carrying a non-null `retired_at`.
-- ============================================================================


-- ############################################################################
-- ############################################################################
-- ##                                                                        ##
-- ##  SECTION A — MISFIRE LOG                                               ##
-- ##                                                                        ##
-- ##  DATABASE GROUP:  user-flow  (`DATABASE_URL`, binding `sql`)           ##
-- ##  RUN ON STAGING:  RecordHealth / staging                               ##
-- ##                   branch br-fancy-darkness-ak68ea0o                    ##
-- ##                   endpoint ep-long-tooth-ak34xej9, database neondb     ##
-- ##  THEN PRODUCTION: RecordHealth / production                            ##
-- ##                   branch br-rapid-scene-aky6zg2q                       ##
-- ##                   endpoint ep-cold-mountain-akdz6bmv, database neondb  ##
-- ##                                                                        ##
-- ##  BOTH ENVIRONMENTS, STAGING FIRST. Production is not optional here:    ##
-- ##  OR-15 pins the log durable-in-Neon in the first build, and §6's        ##
-- ##  stated purpose is that the owner sees PRODUCTION behavior (ADI is     ##
-- ##  DEBUG-only and superuser-gated, so a corpus-side-only log would see   ##
-- ##  no production data at all). Same both-environments posture as         ##
-- ##  `error_events` (ncc1_error_events.sql) and the two L7 tables.         ##
-- ##                                                                        ##
-- ##  NO WIPE IN THIS SECTION. Nothing here is destructive; the table is    ##
-- ##  new in both environments.                                            ##
-- ##                                                                        ##
-- ############################################################################
-- ############################################################################

BEGIN;

-- Endpoint guard rail — DATABASE_LAYOUT.md § Migration workflow rules, rule 6.
-- EDIT `expected_endpoint` for the target you are running against RIGHT NOW.
DO $guard$
DECLARE
  expected_endpoint TEXT := 'ep-long-tooth-ak34xej9';  -- <<< EDIT: staging
  -- expected_endpoint TEXT := 'ep-cold-mountain-akdz6bmv';  -- production
  actual_endpoint   TEXT;
BEGIN
  actual_endpoint := current_setting('neon.endpoint_id', true);
  IF actual_endpoint IS DISTINCT FROM expected_endpoint THEN
    RAISE EXCEPTION
      'ENDPOINT GUARD: expected %, connected to %. Aborting Section A.',
      expected_endpoint, COALESCE(actual_endpoint, '<null>');
  END IF;
END
$guard$;


-- ── The misfire log (§6, OR-12 storage role 2; OR-15 first-build durable) ───
--
-- NOT an L7 table and must never become one (§6, the L7 seam). Opposite write
-- semantics (L7 appends per occurrence; this table upserts over observation
-- classes), opposite PHI posture (L7 is ids/enums/counts/durations only; this
-- table's whole purpose is a gated verbatim value column), different feeders,
-- different lifecycle.
--
-- NO FOREIGN KEYS to `ingest_phase_events`, `ingest_spend_events`,
-- `ingest_jobs`, `error_events`, or any future observability table, in either
-- direction. Correlation is by id only (`job_id`, `atom_id`), so neither
-- surface's absence or failure can gate the other. This is OR-15, stated as
-- structure rather than convention.
--
-- Standing rules, inherited verbatim from `error_events` (ncc1_error_events.sql)
-- and binding here:
--   1. Strict column allowlist. No free-form JSONB, ever. A new field is a new
--      named, explicitly-classified column via a new migration.
--   2. Writes are fire-and-forget from both feeders. Observe-never-gate: a
--      failed or slow write to this table must never block, delay, or fail
--      ingest, the beacon, or an ADI submission.
--   3. This table observes but never gates. No code path may branch on the
--      presence, absence, or content of a row here.
-- Plus one rule that is this table's alone:
--   4. THE VERBATIM VALUE EXCEPTION. `value_verbatim` is the ONLY verbatim
--      value column permitted in any NCC table (§6, the seam). It is admitted
--      solely through the §9 item 6 vocabulary-shape gate AND the OR-9 length
--      threshold, both applied by the WRITER before the row is built. No L7
--      table inherits this permission by analogy; the column must stay
--      structurally unreachable from every phase / spend / error writer, which
--      is one reason it lives in its own table.

CREATE TABLE IF NOT EXISTS vocabulary_misfire_events (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  -- ── Classification ──────────────────────────────────────────────────────
  event_class         TEXT NOT NULL,      -- 'drift' | 'anomaly' (§6: two event
                                          -- classes, one route, one table, one
                                          -- NCC posture — never one payload
                                          -- shape. A drift row is a dictionary
                                          -- work item; an anomaly row is an
                                          -- upstream-breakage report. One must
                                          -- never be triaged as the other.)
  source              TEXT NOT NULL,      -- 'beacon' | 'adi' — which of §6's
                                          -- two feeders wrote the row. The
                                          -- beacon is the ONLY production-facing
                                          -- detector (§9 item 7).
                                          -- [2026-08-21, OR-18, v7-era
                                          -- annotation: a third source,
                                          -- 'ingest', was added by
                                          -- migrations/vocabulary_misfire_
                                          -- source_ingest.sql and is now the
                                          -- PRIMARY detector (IngestDO.
                                          -- assemble() sees 100% of extraction
                                          -- traffic); the beacon named above
                                          -- is deferred, not built. The CHECK
                                          -- below is left exactly as
                                          -- originally authored/executed —
                                          -- see the widening migration for
                                          -- the structural change.]
  namespace           TEXT NOT NULL,      -- §5.3 invariant 1: a term's identity
                                          -- is namespace plus code, never a bare
                                          -- string. Field position assigns the
                                          -- namespace; this column records
                                          -- explicitly what position implies.
                                          -- e.g. rh.atom.kind, rh.column-role,
                                          -- rh.certainty, rh.job.state,
                                          -- rh.hold.reason, rh.phi.type
                                          -- (§5.3's scheme is illustrative,
                                          -- not final — AUTHORED as free text
                                          -- rather than a constrained set for
                                          -- exactly that reason).
  surface             TEXT NOT NULL,      -- the classifier that fired (§6):
                                          -- jobState | holdReason | armState |
                                          -- atomKind | columnRole | edgeKind |
                                          -- edgeSetBy | phiType | certainty |
                                          -- decodeFailure
  field               TEXT,               -- wire field position, where the
                                          -- surface carries one. Nullable.

  -- ── The observed value (§6 PHI rule, governing BOTH feeders and BOTH
  --    event classes; = §9 item 6 applied to the log) ────────────────────────
  value_class         TEXT NOT NULL,      -- 'verbatim'  — passed the §9.6 shape
                                          --               gate AND sits under
                                          --               the OR-9 length
                                          --               threshold
                                          -- 'suppressed'— failed either gate;
                                          --               hash + length only,
                                          --               never the value. The
                                          --               verbatim string
                                          --               survives on-device
                                          --               (the atom itself, and
                                          --               the IngestEventLog
                                          --               ring) and, for the ADI
                                          --               feeder, in the corpus
                                          --               atom row. A reviewer
                                          --               who needs it walks the
                                          --               exemplar identity back.
                                          -- 'absent'    — OR-16's distinguished
                                          --               absent marker. NEVER a
                                          --               fabricated string.
  value_verbatim      TEXT,               -- THE VERBATIM VALUE EXCEPTION — see
                                          -- standing rule 4 above. Populated
                                          -- ONLY when value_class='verbatim'.
                                          -- Byte-exact: no trimming, no
                                          -- case-folding, no normalization
                                          -- (§5.2 property 1 applied to
                                          -- observation).
  value_hash          TEXT,               -- SHA-256 hex of the verbatim value.
                                          -- Present for 'verbatim' and
                                          -- 'suppressed'; NULL for 'absent'.
  value_length        INTEGER,            -- character length of the verbatim
                                          -- value. NULL for 'absent'. This plus
                                          -- value_hash plus identity IS the
                                          -- OR-9 anomaly shape.

  -- ── Extractor identity (OR-14: vendor-agnostic, attribution required) ────
  -- Owner-defined strings. `extractor_vendor` carries the SAME value domain as
  -- `ingest_spend_events.vendor`, so a misfire row joins that ledger ad hoc.
  -- NULL on lifecycle surfaces, where no extractor is in play (§6).
  -- These are part of the dedup key: drift produced by vendor A and drift
  -- produced by vendor B must NEVER merge. A vendor swap is precisely the
  -- event that reads as a drift wave whose attribution matters (§5.0: a
  -- swapped vendor is a fifth copy of the vocabulary trying to be born, and
  -- this log is what catches it).
  extractor_vendor    TEXT,
  extractor_model     TEXT,
  extractor_version   TEXT,

  -- ── Client / environment identity ───────────────────────────────────────
  app_version         TEXT,               -- part of the dedup key. Drives the
                                          -- §6 NCC panel row: "app 1.4.2 saw
                                          -- jobState=converging x41".
                                          -- NULL for server-side (ADI) rows.
  environment         TEXT NOT NULL,      -- shared L7 convention ('staging' |
                                          -- 'production').

  -- ── Exemplar identity, from the FIRST occurrence (§6) ────────────────────
  -- Correlation by id only. NO FOREIGN KEYS. `job_id` is the ad-hoc join key
  -- into `ingest_phase_events` / `ingest_spend_events` (same database, same
  -- convention). `atom_id` points into the ADI database's `data_atoms` and is
  -- therefore a cross-database id by construction — never a constraint.
  job_id              TEXT,
  atom_id             UUID,

  -- ── Merge bookkeeping (§6 / OR-12: a row is an observation class, never one
  --    row per atom) ──────────────────────────────────────────────────────────
  occurrence_count    BIGINT NOT NULL DEFAULT 1,
  first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- ── Structural constraints ──────────────────────────────────────────────
  CONSTRAINT vocabulary_misfire_events_event_class_check
    CHECK (event_class IN ('drift', 'anomaly')),

  CONSTRAINT vocabulary_misfire_events_source_check
    CHECK (source IN ('beacon', 'adi')),

  CONSTRAINT vocabulary_misfire_events_value_class_check
    CHECK (value_class IN ('verbatim', 'suppressed', 'absent')),

  -- OR-9 / §9 item 9, enforced structurally rather than by convention: the
  -- anomaly shape has NO rawValue field at all. §9 item 9's erosion argument
  -- applies at column scale here and at table scale at the L7 seam.
  CONSTRAINT vocabulary_misfire_events_anomaly_never_verbatim_check
    CHECK (event_class <> 'anomaly' OR value_verbatim IS NULL),

  -- value_class and the value columns agree, in both directions.
  CONSTRAINT vocabulary_misfire_events_value_shape_check
    CHECK (
      (value_class = 'verbatim'
         AND value_verbatim IS NOT NULL
         AND value_hash     IS NOT NULL
         AND value_length   IS NOT NULL)
      OR
      (value_class = 'suppressed'
         AND value_verbatim IS NULL
         AND value_hash     IS NOT NULL
         AND value_length   IS NOT NULL)
      OR
      (value_class = 'absent'
         AND value_verbatim IS NULL
         AND value_hash     IS NULL
         AND value_length   IS NULL)
    ),

  -- §5.3 invariant 4 / §9 item 10: the reserved per-user namespace is a PRIVACY
  -- BOUNDARY, not a naming convention. A per-user term landing in an NCC-read
  -- surface is content egress. Structurally refused here, in the same shape as
  -- `vocabulary_terms` refuses it (Section B). Case-insensitive so a 'User.'
  -- variant cannot slip past.
  CONSTRAINT vocabulary_misfire_events_no_user_namespace_check
    CHECK (lower(namespace) <> 'user' AND lower(namespace) NOT LIKE 'user.%'),

  CONSTRAINT vocabulary_misfire_events_count_check
    CHECK (occurrence_count > 0),

  CONSTRAINT vocabulary_misfire_events_seen_order_check
    CHECK (last_seen_at >= first_seen_at)
);


-- ── The dedup key (§6: a row is an observation class) ───────────────────────
-- Rows collapse on byte-exact value within a namespace, per extractor identity,
-- per app version, per environment. NO case-folding, trimming, or normalization
-- in the key: a normalized key merges strings the extractor actually emits
-- distinctly, destroying the signal the log exists to capture. The same string
-- arriving in `column_role` and in `entity_kind` is TWO rows, deliberately —
-- cross-field co-occurrence is itself tuning signal (§6).
--
-- NULLS NOT DISTINCT is load-bearing: extractor identity is NULL on lifecycle
-- surfaces, and two NULL extractors are the same observation class. Requires
-- PostgreSQL 15+.
CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_misfire_events_class
  ON vocabulary_misfire_events (
    environment,
    namespace,
    surface,
    field,
    event_class,
    value_class,
    value_hash,
    extractor_vendor,
    extractor_model,
    extractor_version,
    app_version
  ) NULLS NOT DISTINCT;

-- Fallback if the target is somehow pre-PG15 — same key, COALESCE'd. If you use
-- this, the writer's ON CONFLICT target must name the expression list exactly.
-- CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_misfire_events_class
--   ON vocabulary_misfire_events (
--     environment, namespace, surface,
--     COALESCE(field, ''), event_class, value_class, COALESCE(value_hash, ''),
--     COALESCE(extractor_vendor, ''), COALESCE(extractor_model, ''),
--     COALESCE(extractor_version, ''), COALESCE(app_version, '')
--   );

-- Read indexes. The fifth NCC panel (§6) is a curation WORK-SURFACE the owner
-- works through, not a health dashboard — it reads by recency, by namespace,
-- and by count.
CREATE INDEX IF NOT EXISTS idx_vocabulary_misfire_events_environment_last_seen
  ON vocabulary_misfire_events (environment, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_vocabulary_misfire_events_namespace_last_seen
  ON vocabulary_misfire_events (namespace, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_vocabulary_misfire_events_event_class_last_seen
  ON vocabulary_misfire_events (event_class, last_seen_at DESC);

-- Ad-hoc correlation into L7's phase / spend events. Not a constraint.
CREATE INDEX IF NOT EXISTS idx_vocabulary_misfire_events_job_id
  ON vocabulary_misfire_events (job_id);


COMMENT ON TABLE vocabulary_misfire_events IS
  'Misfire log (INGEST_VOCABULARY_DESIGN v6 §6, OR-12 storage role 2, OR-15). '
  'Append-only observation surface over unrecognized vocabulary: NOT a data '
  'store (the atom is) and NOT a queue of pending vocabulary (nothing here is '
  'pending anything — promotion into vocabulary_terms is the owner''s '
  'deliberate act). Two feeders (the /v1/client-drift beacon; the ADI submit '
  'route), two event classes (drift, anomaly), one table. Deliberately NOT an '
  'L7 table: no foreign keys to ingest_phase_events / ingest_spend_events / '
  'ingest_jobs in either direction, correlation by id only. '
  '[2026-08-21, OR-18, v7-era annotation: the "two feeders" line above is as '
  'originally authored and executed, and is left unedited for history''s '
  'sake. A third source now exists — ingest, added by migrations/'
  'vocabulary_misfire_source_ingest.sql — and per owner ruling it is the '
  'PRIMARY detector, not the beacon: IngestDO.assemble() sees 100% of '
  'extraction traffic and carries real per-arm extractor identity, where the '
  'beacon named above remains deferred, not built. Current state: '
  'docs/WORKER_ARCHITECTURE.md § Vocabulary misfire log.]';

COMMENT ON COLUMN vocabulary_misfire_events.value_verbatim IS
  'THE VERBATIM VALUE EXCEPTION (v6 §6, the L7 seam). This is the ONLY '
  'verbatim value column permitted in any NCC table, admitted solely through '
  'the §9 item 6 vocabulary-shape gate (single token, no whitespace runs, '
  'bounded charset) AND the OR-9 length threshold. Both gates are applied by '
  'the writer, are specified against ANY extractor''s failure modes, and are '
  'never tuned to the current vendor (OR-14: no upstream vendor bound is ever '
  'load-bearing). No L7 table inherits this permission by analogy.';

COMMENT ON COLUMN vocabulary_misfire_events.extractor_vendor IS
  'OR-14 extractor identity. Same value domain as ingest_spend_events.vendor, '
  'so a misfire row joins the spend ledger ad hoc. Part of the dedup key: '
  'drift from vendor A and drift from vendor B must never merge.';

COMMENT ON COLUMN vocabulary_misfire_events.atom_id IS
  'Exemplar atom from the first occurrence. Points into the ADI database''s '
  'data_atoms — a cross-database id by construction, never a constraint.';


-- Ledger — DATABASE_LAYOUT.md § Migration workflow rules, rule 3.
INSERT INTO schema_migrations (filename, applied_by)
VALUES ('vocabulary_baseline_v6.sql', 'vocabulary-v6')
ON CONFLICT (filename) DO NOTHING;

COMMIT;


-- ── SECTION A verify (run after COMMIT, on an independent reconnect) ────────
-- DATABASE_LAYOUT.md § Migration workflow rules, rule 7.
--
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'vocabulary_misfire_events'
-- ORDER BY ordinal_position;
--
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conrelid = 'vocabulary_misfire_events'::regclass
-- ORDER BY conname;
--
-- -- Must return ZERO rows. If it does not, the no-FK rule of OR-15 is broken.
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE contype = 'f'
--   AND (conrelid = 'vocabulary_misfire_events'::regclass
--        OR confrelid = 'vocabulary_misfire_events'::regclass);
--
-- SELECT indexname, indexdef FROM pg_indexes
-- WHERE tablename = 'vocabulary_misfire_events';
--
-- SELECT filename, applied_at, applied_by FROM schema_migrations
-- WHERE filename = 'vocabulary_baseline_v6.sql';


-- ── SECTION A rollback ──────────────────────────────────────────────────────
-- Safe and complete: brand-new table, nothing reads or writes it until the
-- beacon route and the ADI feeder ship. Non-destructive in both directions.
--
-- BEGIN;
-- DROP TABLE IF EXISTS vocabulary_misfire_events;
-- DELETE FROM schema_migrations WHERE filename = 'vocabulary_baseline_v6.sql';
-- COMMIT;



-- ############################################################################
-- ############################################################################
-- ##                                                                        ##
-- ##  SECTION B — DEV-CORPUS WIPE + DICTIONARY + ATOM-SIDE CHANGES          ##
-- ##                                                                        ##
-- ##  DATABASE GROUP:  ADI review  (`ADI_DATABASE_URL`, binding `adiSql`)   ##
-- ##  RUN ON STAGING:  RecordHealth-ADI / staging                           ##
-- ##                   branch br-soft-frost-am6dmaw1                        ##
-- ##                   endpoint ep-long-silence-ampu7eor, database neondb   ##
-- ##  THEN PRODUCTION: RecordHealth-ADI / production                        ##
-- ##                   branch br-shy-darkness-amun5peq                      ##
-- ##                   endpoint ep-quiet-union-amsm4lqz, database neondb    ##
-- ##                                                                        ##
-- ##  BOTH BRANCHES, STAGING FIRST. Staging is where the dev corpus         ##
-- ##  actually lives: ADI review submission is a DEBUG-only, superuser-      ##
-- ##  gated iOS feature and even DEBUG builds route to the STAGING Worker,   ##
-- ##  so no live user traffic ever reaches ADI production                    ##
-- ##  (DATABASE_LAYOUT § iOS Worker routing; recordhealth-api/CLAUDE.md:     ##
-- ##  "The production Worker does NOT write data_atoms").                    ##
-- ##                                                                        ##
-- ##  ADI PRODUCTION STILL GETS THE FULL SECTION. Its wipe is expected to    ##
-- ##  be a no-op (zero rows), but the SCHEMA change is not optional: the     ##
-- ##  two ADI branches have run identical schema since the DB-separation     ##
-- ##  sprint (DATABASE_LAYOUT § ADI review pipeline: "applied identically    ##
-- ##  to both ADI branches ... so the schema is uniform"). Letting them      ##
-- ##  diverge here re-creates exactly the class of drift this design exists  ##
-- ##  to end.                                                               ##
-- ##                                                                        ##
-- ############################################################################
-- ############################################################################

BEGIN;

-- Endpoint guard rail — DATABASE_LAYOUT.md § Migration workflow rules, rule 6.
-- EDIT `expected_endpoint` for the target you are running against RIGHT NOW.
-- This guard matters more in Section B than anywhere else in the file: the next
-- statement is destructive.
DO $guard$
DECLARE
  expected_endpoint TEXT := 'ep-long-silence-ampu7eor';  -- <<< EDIT: ADI staging
  -- expected_endpoint TEXT := 'ep-quiet-union-amsm4lqz';  -- ADI production
  actual_endpoint   TEXT;
BEGIN
  actual_endpoint := current_setting('neon.endpoint_id', true);
  IF actual_endpoint IS DISTINCT FROM expected_endpoint THEN
    RAISE EXCEPTION
      'ENDPOINT GUARD: expected %, connected to %. Aborting Section B.',
      expected_endpoint, COALESCE(actual_endpoint, '<null>');
  END IF;
END
$guard$;


-- ===========================================================================
-- ==  B.1 — THE WIPE.  OWNER-EXECUTED, DESTRUCTIVE, IRREVERSIBLE.          ==
-- ==                                                                       ==
-- ==  THIS DELETES THE ENTIRE DEV REVIEW CORPUS. THERE IS NO UNDO AND NO   ==
-- ==  BACKUP TAKEN BY THIS FILE. READ THE NEXT THIRTY LINES BEFORE RUNNING.==
-- ===========================================================================
--
-- WHY IT EXISTS: OR-13 (100% dev — no users, no legacy data, reingest is free)
-- plus OR-12 and the wipe-anything sacred rule. §8 rung 6: "There is no data
-- worth converting, so nothing is converted: the table, the NOT NULL verbatim
-- raw column, and the nullable term reference land as FRESH BASELINE DDL — the
-- enum simply never exists in the new baseline — the dev corpus is wiped, and
-- anything wanted back is reingested." Exactly ZERO Neon migrations remain
-- (OR-13, superseding v5's "exactly one").
--
-- WHY IT RUNS FIRST, AND WHY IT IS NOT OPTIONAL: step B.3 adds
-- `data_atoms.entity_kind` as `TEXT NOT NULL` with NO default. Postgres refuses
-- that on a non-empty table. The ordering here is a hard requirement of the
-- fresh-baseline shape, not a stylistic preference.
--
-- SCOPE: the ingestion-derived review corpus and its full foreign-key closure.
-- Every dependent table is named explicitly rather than relying on CASCADE, so
-- nothing is destroyed silently. Verified against baseline_001_adi.sql's
-- constraint list:
--     data_atoms        <- atom_region_links, ontology_traces (both CASCADE),
--                          data_atoms.supersedes (self)
--     source_regions    <- atom_region_links (CASCADE)
--     review_documents  <- grading_submissions, review_phi_detections
--     knowledge_gaps    <- (no inbound FK)
--
-- WHAT SURVIVES: `prompt_versions` only. The human-review artifact trees —
-- `audit_*`, `grading_sessions`, `document_grades`, `grading_exports`,
-- `annotations` — are ALSO wiped, by owner ruling 2026-08-21 (the second
-- TRUNCATE below, originally authored as commented-out and optional). None of
-- them is reproduced by reingest; the owner ruled there is no hand-authored
-- grading data worth preserving, and recovery for the whole wipe is reingest.
-- NONE of them holds a foreign key into the first TRUNCATE's tables, so the two
-- statements are independent.

TRUNCATE TABLE
  atom_region_links,
  ontology_traces,
  data_atoms,
  source_regions,
  knowledge_gaps,
  review_phi_detections,
  grading_submissions,
  review_documents;

-- OWNER-RULED ON, 2026-08-21: RUN IT. The wipe includes the grading and audit
-- trees. There is no hand-authored grading data worth preserving in the dev
-- corpus, so the "reingest does not bring it back" cost is accepted as zero.
-- Separately irreversible, same as B.1 above.
TRUNCATE TABLE
  annotations,
  document_grades,
  grading_exports,
  grading_sessions,
  audit_fields,
  audit_negative_space,
  audit_phi_detections,
  audit_session_summary,
  audit_documents,
  audit_sessions;

-- ===========================================================================
-- ==  END OF THE WIPE. Everything below is schema.                         ==
-- ===========================================================================


-- ===========================================================================
-- ==  B.2 — THE DICTIONARY:  vocabulary_terms                              ==
-- ==  §8 rung 6 item 1; OR-10 (table), OR-11 (identity), OR-12 (who writes)==
-- ===========================================================================
--
-- CURATED, HUMAN-AUTHORED ONLY. A term exists because someone decided it
-- should. Nothing arrives by ingestion (OR-12: THE EXTRACTOR NEVER WRITES TO
-- THE DICTIONARY — the AI does not author vocabulary).
--
-- NO STATUS LIFECYCLE. With no arrival path, every term is canonical by
-- construction, so OR-10's provisional/canonical statuses and the v4
-- rejected-tombstone need are all DELETED (OR-12). `retired_at` is optional
-- curation metadata for owner-authoring mistakes, not machinery — a referenced
-- term still cannot be deleted (the FK from data_atoms holds it).
--
-- THIS IS NOT THE CANONICAL-CODE TABLE (§9 item 11). A standard code on a
-- vocabulary TERM identifies a classification, not a clinical entity. The
-- cross-source matching work (ROADMAP F-NEW-DR / F-NEW-O / F-NEW-P, and
-- F-NEW-OT's kt_coding capture) operates on codes attached to individual atom
-- VALUES and consumes nothing from this table. The mapping columns below are
-- carried because §5.3 invariant 3 rules them cheap and correct; POPULATING
-- THEM IS NOT A WORKSTREAM.

CREATE TABLE IF NOT EXISTS vocabulary_terms (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- §5.3 invariant 1: identity is namespace PLUS code, never a bare string,
  -- and it lands from the start — retrofitting namespaces later is the
  -- expensive path. This changes no wire contract: a string still arrives bare
  -- on the wire, but it is never bare in IDENTITY, because the field it arrives
  -- in assigns its namespace. This table records explicitly what field position
  -- implies.
  namespace           TEXT NOT NULL,
  code                TEXT NOT NULL,

  -- AUTHORED (A5): curation metadata the design does not name. A hand-authored
  -- dictionary needs a human label. Both nullable; delete if unwanted.
  display_name        TEXT,
  notes               TEXT,

  -- §5.3 invariant 3: a term may carry more than one code — the app's internal
  -- code (namespace + code above) plus optional mappings to standard systems.
  -- Nullable, cheap, correct under the namespace-first frame. See the
  -- §9-item-11 warning above before using them for anything.
  loinc_code          TEXT,
  snomedct_code       TEXT,
  rxnorm_code         TEXT,

  -- Curation metadata, not machinery (OR-12).
  retired_at          TIMESTAMPTZ,

  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by          TEXT NOT NULL,      -- ADI convention (data_atoms.created_by).
                                          -- Records the human curation act — the
                                          -- only way a row gets here.

  -- §5.3 invariant 4 / §9 item 10: THE RESERVED PER-USER NAMESPACE IS A PRIVACY
  -- BOUNDARY, NOT A NAMING CONVENTION. User-defined vocabulary is user content,
  -- PHI-adjacent by nature; a per-user term landing in this table lands in a
  -- Neon table with an NCC review surface, where a reviewer SEEING it is content
  -- egress and a reviewer canonicalizing it would launder a private term into
  -- system vocabulary. The refusal is structural NOW, while the table is being
  -- created, even though nothing user-defined is being built — because the
  -- failure mode if it lands as convention is that the first "sync my custom
  -- categories" request routes user terms through the path of least resistance
  -- and the boundary is gone before anyone rules on it. Case-insensitive so a
  -- 'User.' variant cannot slip past.
  CONSTRAINT vocabulary_terms_no_user_namespace_check
    CHECK (lower(namespace) <> 'user' AND lower(namespace) NOT LIKE 'user.%'),

  CONSTRAINT vocabulary_terms_namespace_nonempty_check
    CHECK (namespace <> ''),

  CONSTRAINT vocabulary_terms_code_nonempty_check
    CHECK (code <> '')
);

-- §5.3 invariant 1, as a constraint: (namespace, code) IS the identity.
CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_terms_namespace_code
  ON vocabulary_terms (namespace, code);

CREATE INDEX IF NOT EXISTS idx_vocabulary_terms_namespace
  ON vocabulary_terms (namespace);

COMMENT ON TABLE vocabulary_terms IS
  'The vocabulary dictionary (INGEST_VOCABULARY_DESIGN v6 §8 rung 6 item 1; '
  'OR-10 table, OR-11 identity, OR-12 authorship). Human-authored ONLY — the '
  'extractor never writes here. No status lifecycle: every term is canonical '
  'by construction. NOT the canonical-code table (§9 item 11): a code here '
  'identifies a classification, not a clinical entity.';


-- ── Structural enforcement of OR-12, at the grant level ─────────────────────
-- §8 rung 6 item 1: "no ingest or ADI code path holds an INSERT against this
-- table — and the runtime DB role should lack the privilege at the grant level
-- if Neon's role setup allows, because hand-kept convention is how the
-- four-copies problem was born."
--
-- LEFT COMMENTED because the runtime role name is not recorded in
-- DATABASE_LAYOUT.md and must not be guessed (§ Column-name rule, applied to
-- roles). Read the role from the ADI connection string, then run:
--
-- REVOKE INSERT, UPDATE, DELETE ON vocabulary_terms FROM <runtime_role>;
--
-- Note the ceiling: if the Worker connects as the Neon project owner, no
-- REVOKE will bite and the enforcement stays conventional. Say so out loud
-- rather than recording an enforcement that does not exist.


-- ── Initial dictionary content: the 33 entity_kind_enum values ──────────────
-- §5.0 / §8 rung 6 / OR-13: "The 33 entity_kind_enum values are carried over as
-- INITIAL DICTIONARY CONTENT: owner-adopted canonical terms seeded under the
-- kind namespace in the baseline, A CURATION ACT, NOT A MIGRATION STEP." There
-- is no conversion migration for them to ride — none exists any more.
--
-- Source of truth for the list: recordhealth-api/migrations/baseline_001_adi.sql
-- lines 11-45, the captured `entity_kind_enum` type, in its declared order.
-- (DATABASE_LAYOUT.md § ADI table column schemas prose-enumerates only 29 of
-- them; its own "33 values" count in § Table groups and its stated
-- source-of-truth rule both point at the migration file, which is what was
-- used here. See the report accompanying this file.)
--
-- Namespace `rh.atom.kind` follows §5.3's ILLUSTRATIVE scheme — the design says
-- "illustrative, not final". Changing it later means one UPDATE here and one
-- against data_atoms; it is not load-bearing anywhere yet.

INSERT INTO vocabulary_terms (namespace, code, created_by) VALUES
  ('rh.atom.kind', 'provider',           'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'organization',       'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'visitDate',          'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'reportDate',         'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'coverage',           'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'labValue',           'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'vitalSign',          'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'socialHistory',      'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'immunization',       'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'symptom',            'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'condition',          'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'diagnosis',          'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'medication',         'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'allergy',            'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'procedure',          'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'familyHistory',      'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'device',             'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'referral',           'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'carePlan',           'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'uncategorized',      'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'finding',            'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'encounter',          'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'patientDemographic', 'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'patientIdentifier',  'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'patientContact',     'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'patientAddress',     'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'guardianInfo',       'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'emergencyContact',   'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'providerContact',    'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'documentReference',  'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'dateAtom',           'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'labPanel',           'vocabulary-v6-baseline'),
  ('rh.atom.kind', 'recordSummary',      'vocabulary-v6-baseline')
ON CONFLICT (namespace, code) DO NOTHING;

-- CURATION, OWNER-CONFIRMED 2026-08-21 (authoring decision A6 CONFIRMED).
-- `visitDate` and `reportDate` are dead in practice: DATABASE_LAYOUT § Drift
-- records them as "dead-but-unremovable" enum values, rejected by the Worker
-- validator, with their rows already backfilled to `dateAtom` by
-- fneweh_entity_kind_backfill.sql. They are seeded live above because the design
-- says "the 33 values", full stop — and retired immediately after, so the
-- dictionary carries all 33 while telling the truth about which two are dead.

UPDATE vocabulary_terms
   SET retired_at = NOW(),
       notes = 'Dead since the dateAtom consolidation; rejected by the Worker validator.'
 WHERE namespace = 'rh.atom.kind'
   AND code IN ('visitDate', 'reportDate');


-- ===========================================================================
-- ==  B.3 — THE ATOM SIDE:  data_atoms                                     ==
-- ==  §8 rung 6 (OR-12 storage role 3, OR-13 fresh baseline), OR-16        ==
-- ===========================================================================
--
-- Three storage roles, joined by a NULLABLE reference (OR-12):
--   the DICTIONARY (B.2)  — curated, human-authored only
--   the MISFIRE LOG (A)   — append-only observation of everything unrecognized
--   the ATOM (here)       — the raw value verbatim, ALWAYS, term or no term
-- An unrecognized value is a NULL reference plus the preserved raw string.
-- Nothing is refused, nothing is discarded, nothing is minted.

-- B.3.1 — The enum, and the index over it, cease to exist.
-- OR-13: "the enum simply never exists in the new baseline". This is the fourth
-- copy of the vocabulary (§5.0) — the one nobody counted, the only one that
-- could not be widened by editing a list, and the one whose disagreement threw
-- INSIDE the batched ADI transaction and rolled back whole documents with an
-- HTTP 500, leaving the R2 PDF orphaned. Dropping the column drops
-- idx_data_atoms_kind with it; it is recreated in B.3.2.
ALTER TABLE data_atoms DROP COLUMN entity_kind;

-- `entity_kind_enum` is used by exactly one column across the whole ADI
-- baseline — the one just dropped. (`annotations.entity_kind` and
-- `audit_fields.entity_kind` are and always were plain `text`.) So the type
-- goes too.
DROP TYPE entity_kind_enum;

-- B.3.2 — The NOT NULL verbatim raw column (OR-12 storage role 3).
-- AUTHORED (A2): the column keeps the name `entity_kind` and is retyped to
-- plain TEXT. `data_atoms.verbatim_value` already exists and is the atom's
-- CLINICAL VALUE, not the vocabulary raw string — the two must never be
-- conflated. Keeping the name means corpus `GROUP BY entity_kind` now groups on
-- the raw column, which is exactly §8 rung 6's reader instruction: "corpus
-- GROUP BYs group on the raw column as ground truth, with the reference as
-- enrichment."
--
-- NO CHECK CONSTRAINT beyond NOT NULL, deliberately. A `<> ''` guard would make
-- an empty kind a REFUSAL — an HTTP 400 or a rolled-back transaction — which is
-- the exact posture OR-7 / OR-12 / OR-13 delete. Nothing is refused.
--
-- This statement is why the wipe in B.1 had to run first: Postgres refuses a
-- NOT NULL column with no default on a non-empty table.
ALTER TABLE data_atoms ADD COLUMN entity_kind TEXT NOT NULL;

CREATE INDEX idx_data_atoms_kind ON data_atoms (entity_kind);

-- B.3.3 — The NULLABLE term reference (OR-12).
-- Nullable is the ruling, not a default: "the atom->term foreign key is
-- NULLABLE — unrecognized means null reference plus preserved raw string".
-- What this gives up is stated bluntly in §9 item 7: OR-10's total referential
-- integrity narrows to raw-NOT-NULL + valid-when-present + a
-- provably-clean-dictionary. The FK below is the "valid-when-present" half.
--
-- This FK is INSIDE the ADI database and is entirely proper. The no-foreign-key
-- rule of OR-15 governs the MISFIRE LOG's relationship to L7 tables, nothing
-- here.
--
-- ON DELETE is deliberately omitted (i.e. NO ACTION): a referenced term must
-- not be deletable. That is why `retired_at` exists instead of a delete path.
ALTER TABLE data_atoms
  ADD COLUMN entity_kind_term_id UUID REFERENCES vocabulary_terms(id);

-- Serves both the read-side join and the promotion backfill's
-- `WHERE ... AND entity_kind_term_id IS NULL` scan.
CREATE INDEX idx_data_atoms_entity_kind_term_id
  ON data_atoms (entity_kind_term_id);

-- B.3.4 — OR-16: the certainty default dies.
-- "ABSENT IS DRIFT — owner ruling, v6, killing the ?? 'specific' default."
-- The v5 justification (absence means an older all-specific server) was legacy
-- reasoning with no legacy to serve under OR-13.
--
-- AUTHORED (A3), AND THE ONE DECISION IN THIS FILE MOST WORTH CONFIRMING:
-- NOT NULL is dropped along with the DEFAULT. OR-16 requires absence to be
-- "persisted AS ABSENT, so §5.2 property 2's three-way distinguishability
-- (known / unknown-string / absent) is preserved in the encoding." A column
-- that is NOT NULL with no default cannot persist absence — an INSERT omitting
-- certainty would ERROR, which is a refusal, the posture OR-12/OR-13 delete.
-- Dropping only the DEFAULT would therefore convert a silent lie into a loud
-- crash rather than into a recorded observation. If the owner wants NOT NULL
-- kept, OR-16 needs re-reading first, because the ruling and the constraint
-- cannot both stand.
--
-- Absence is now: NULL here, a `value_class='absent'` row in the misfire log
-- under the certainty namespace (never a fabricated string), and an explicit
-- unknown on-device. Consumers treat absent exactly as unrecognized: the weak
-- side.
ALTER TABLE data_atoms ALTER COLUMN classification_certainty DROP DEFAULT;
ALTER TABLE data_atoms ALTER COLUMN classification_certainty DROP NOT NULL;

COMMENT ON COLUMN data_atoms.entity_kind IS
  'Verbatim raw vocabulary string as it arrived, byte-exact — no trimming, '
  'case-folding, or normalization (§5.2 property 1). NOT the atom''s clinical '
  'value; that is verbatim_value. Was entity_kind_enum until the v6 fresh '
  'baseline (OR-13). Ground truth for corpus GROUP BYs.';

COMMENT ON COLUMN data_atoms.entity_kind_term_id IS
  'Nullable reference into vocabulary_terms (OR-12). NULL means the raw string '
  'resolved no curated term — preserved, logged to the misfire log, refused '
  'nowhere. Populated at ingest only when a term already exists, and later by '
  'the owner''s batch promotion backfill.';

COMMENT ON COLUMN data_atoms.classification_certainty IS
  'NULL means ABSENT, and absent is drift (OR-16) — never a silent promotion '
  'to ''specific''. Three-way distinguishable: known value / unrecognized '
  'string / NULL.';


-- Ledger — DATABASE_LAYOUT.md § Migration workflow rules, rule 3.
INSERT INTO schema_migrations (filename, applied_by)
VALUES ('vocabulary_baseline_v6.sql', 'vocabulary-v6')
ON CONFLICT (filename) DO NOTHING;

COMMIT;


-- ── SECTION B verify (run after COMMIT, on an independent reconnect) ────────
-- DATABASE_LAYOUT.md § Migration workflow rules, rule 7.
--
-- -- Corpus is empty.
-- SELECT 'data_atoms' t, count(*) FROM data_atoms
-- UNION ALL SELECT 'review_documents', count(*) FROM review_documents
-- UNION ALL SELECT 'source_regions',   count(*) FROM source_regions
-- UNION ALL SELECT 'atom_region_links',count(*) FROM atom_region_links
-- UNION ALL SELECT 'ontology_traces',  count(*) FROM ontology_traces
-- UNION ALL SELECT 'knowledge_gaps',   count(*) FROM knowledge_gaps;
--
-- -- 33 seed terms, all under rh.atom.kind.
-- SELECT namespace, count(*) FROM vocabulary_terms GROUP BY namespace;
--
-- -- entity_kind is text NOT NULL; entity_kind_term_id is uuid nullable;
-- -- classification_certainty is nullable with NO default.
-- SELECT column_name, data_type, udt_name, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'data_atoms'
--   AND column_name IN ('entity_kind','entity_kind_term_id',
--                       'classification_certainty','verbatim_value')
-- ORDER BY column_name;
--
-- -- Must return ZERO rows: the enum type is gone.
-- SELECT typname FROM pg_type WHERE typname = 'entity_kind_enum';
--
-- -- The user. refusal actually bites (expect an error, not a row):
-- -- INSERT INTO vocabulary_terms (namespace, code, created_by)
-- -- VALUES ('user.mine', 'x', 'guard-test');
--
-- SELECT indexname, indexdef FROM pg_indexes
-- WHERE tablename IN ('data_atoms','vocabulary_terms')
-- ORDER BY tablename, indexname;
--
-- SELECT filename, applied_at, applied_by FROM schema_migrations
-- WHERE filename = 'vocabulary_baseline_v6.sql';


-- ── SECTION B rollback ──────────────────────────────────────────────────────
-- HONEST STATEMENT: THE SCHEMA IS REVERSIBLE. THE WIPE IS NOT. Nothing below
-- restores a single corpus row; recovery is reingest, which OR-13 makes free
-- and which is the whole reason the wipe was sanctioned. Do not read this block
-- as an undo.
--
-- The schema revert also cannot restore the enum's rows even if you recreate
-- the type, and recreating it re-installs copy 4 of the vocabulary — the thing
-- this change exists to delete. Prefer forward fixes.
--
-- BEGIN;
-- ALTER TABLE data_atoms DROP COLUMN entity_kind_term_id;
-- ALTER TABLE data_atoms DROP COLUMN entity_kind;
-- DROP TABLE IF EXISTS vocabulary_terms;
-- CREATE TYPE entity_kind_enum AS ENUM (
--   'provider','organization','visitDate','reportDate','coverage','labValue',
--   'vitalSign','socialHistory','immunization','symptom','condition','diagnosis',
--   'medication','allergy','procedure','familyHistory','device','referral',
--   'carePlan','uncategorized','finding','encounter','patientDemographic',
--   'patientIdentifier','patientContact','patientAddress','guardianInfo',
--   'emergencyContact','providerContact','documentReference','dateAtom',
--   'labPanel','recordSummary');
-- ALTER TABLE data_atoms ADD COLUMN entity_kind entity_kind_enum NOT NULL;
-- CREATE INDEX idx_data_atoms_kind ON data_atoms (entity_kind);
-- ALTER TABLE data_atoms ALTER COLUMN classification_certainty SET NOT NULL;
-- ALTER TABLE data_atoms
--   ALTER COLUMN classification_certainty SET DEFAULT 'specific'::text;
-- DELETE FROM schema_migrations WHERE filename = 'vocabulary_baseline_v6.sql';
-- COMMIT;


-- ============================================================================
-- ==  APPENDIX — THE PROMOTION LOOP (NOT RUN BY THIS FILE)                  ==
-- ============================================================================
-- Recorded here because it is the mechanism the seed above exists to serve,
-- and because it is the ONLY sanctioned write of its kind.
--
-- §8 rung 6, promotion mechanics: the owner reads the misfire log, decides a
-- string is real vocabulary, AUTHORS the term, then links:
--
--   INSERT INTO vocabulary_terms (namespace, code, created_by)
--   VALUES ('rh.atom.kind', '<the string>', '<owner>');
--
--   UPDATE data_atoms
--      SET entity_kind_term_id = (SELECT id FROM vocabulary_terms
--                                  WHERE namespace = 'rh.atom.kind'
--                                    AND code = '<the string>')
--    WHERE entity_kind = '<the string>'
--      AND entity_kind_term_id IS NULL;
--
-- This UPDATE is a NAMED CARVE-OUT against data_atoms' append-only doctrine
-- (sacred rule 7), sanctioned on the same grounds as flagAsPHI: a term link is
-- a classification flag ABOUT a value, never the value itself. Exact precedent:
-- migrations/fneweh_entity_kind_backfill.sql, the owner-executed 77-row kind
-- rewrite.
--
-- THE CARVE-OUT'S BOUNDARY: linking stays owner-initiated and batch. The moment
-- it happens inline at ingest, it is OR-12's rejected provisional insert by
-- another name.
--
-- v6 / OR-13: this is the PRODUCTION-ERA path. While the corpus is dev data,
-- WIPE + REINGEST IS A SANCTIONED, EQUAL PICKUP — the carve-out is exercised by
-- choice, not necessity, and nothing should lean on it as the only way to link
-- already-ingested atoms until real data exists.
-- ============================================================================
