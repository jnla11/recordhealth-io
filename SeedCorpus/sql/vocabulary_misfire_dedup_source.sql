-- ============================================================================
-- vocabulary_misfire_dedup_source.sql
--
-- Source:       ROADMAP F-NEW-PK (filed 2026-08-21), owner-ruled to ride the
--               F-NEW-PP beacon-route migration rather than wait for one of
--               its own. Amends `vocabulary_baseline_v6.sql` SECTION A.
-- Author date:  2026-08-22
-- Scope:        ONE index. Adds `source` to
--               `uq_vocabulary_misfire_events_class`, the misfire log's dedup
--               key. Nothing else in SECTION A is touched.
--
-- ── WHY ─────────────────────────────────────────────────────────────────────
-- The baseline's dedup key is (environment, namespace, surface, field,
-- event_class, value_class, value_hash, extractor_vendor, extractor_model,
-- extractor_version, app_version) — `source` is NOT in it. So the same
-- unrecognized value seen by two different detectors collapses into ONE row:
-- the row's `source` column records whichever detector's INSERT won the
-- ON CONFLICT race, and every later sighting from the other detector bumps
-- `occurrence_count` / `last_seen_at` while leaving no record of its own
-- source at all. The log can count those occurrences but cannot attribute
-- them.
--
-- That was a latent, low-severity defect while only ONE detector wrote rows
-- in production (`ingest`, the DO census — `adi` is DEBUG-only). It stops
-- being latent with the beacon: `POST /v1/client-drift` (F-NEW-PP) makes
-- `source='beacon'` a live production writer alongside the census, and the
-- two see DIFFERENT POPULATIONS by construction (OR-18) — the census sees
-- extractor output, the beacon carries the mirror population the census
-- structurally cannot see. Merging them under whichever filed first would
-- destroy exactly the distinction OR-18 draws, on the very first cross-source
-- collision. Hence: this rides the beacon's migration, and runs BEFORE the
-- beacon route deploys.
--
-- The same argument OR-14 makes for extractor identity applies here one level
-- up: the log's stated purpose is seeing WHO OBSERVED WHAT, and a key that
-- cannot separate two observers is a key that lies about attribution. The
-- baseline's own header already treats every other identity axis
-- (environment, app_version, extractor triple) as part of the observation
-- class; `source` was an omission, not a decision.
--
-- ── WHAT ELSE MUST CHANGE, AND IN WHAT ORDER ────────────────────────────────
-- The writer's ON CONFLICT target must name the index's column list EXACTLY.
-- `src/vocabulary-misfire.mjs` (`buildMisfireInsert`) is updated in the same
-- commit to include `source`.
--
-- ORDER: MIGRATION FIRST, THEN DEPLOY (standing rule). Between the two there
-- is a brief window in which the deployed Worker's ON CONFLICT names a column
-- list no unique index matches, and every misfire INSERT in that window
-- errors. That is ACCEPTABLE AND BOUNDED, and it is why the misfire writer is
-- fire-and-forget: `logMisfires` swallows to console.error, nothing branches
-- on its outcome, and the observe-never-gate posture means ingest and the ADI
-- upload are untouched. The cost of the window is a handful of unlogged
-- observations, not a failed job. Running the deploy first instead would open
-- the SAME window in the other direction and additionally lose the ordering
-- guarantee, so it is not the safer inversion it looks like.
--
-- ── DATABASE GROUP ──────────────────────────────────────────────────────────
-- USER-FLOW only (`DATABASE_URL`, binding `sql`). The misfire log lives in the
-- user-flow group per baseline authoring decision A1; the ADI group has no
-- `vocabulary_misfire_events` table and MUST NOT be run against here.
--
--   RUN ON STAGING:  RecordHealth / staging
--                    endpoint ep-long-tooth-ak34xej9, database neondb
--   THEN PRODUCTION: RecordHealth / production
--                    endpoint ep-cold-mountain-akdz6bmv, database neondb
--
-- STAGING FIRST, VERIFY, THEN PRODUCTION — DATABASE_LAYOUT.md § Migration
-- workflow rules, rule 4.
--
-- ── SAFETY ──────────────────────────────────────────────────────────────────
-- Non-destructive and strictly WIDENING: adding a column to a unique key can
-- only ever admit rows the old key refused, never refuse a row it admitted.
-- No existing row can violate the new index, so the CREATE cannot fail on
-- data. No data is read, written, or moved.
--
-- What it does NOT do, deliberately: it does not retroactively split rows
-- that already merged across sources. Those rows are honest about their
-- counts and dishonest only about attribution, and splitting them would
-- require inventing per-source counts that were never recorded — the log
-- would be fabricating observations. They stay as they are; new sightings
-- from here on file under their own source. (At author time the live tables
-- hold only `source='ingest'` rows, so there is nothing merged to split.)
--
-- The endpoint guard rail below follows the baseline's pattern
-- (DATABASE_LAYOUT.md § Migration workflow rules, rule 6). EDIT
-- `expected_endpoint` before each run. The guard block is dollar-quoted: if
-- this file is ever run through a programmatic runner, that runner must be a
-- real Postgres client, never a `split(";")` splitter (rule 5).
-- ============================================================================

BEGIN;

-- Endpoint guard rail — EDIT for the target you are running against RIGHT NOW.
DO $guard$
DECLARE
  expected_endpoint TEXT := 'ep-long-tooth-ak34xej9';  -- <<< EDIT: staging
  -- expected_endpoint TEXT := 'ep-cold-mountain-akdz6bmv';  -- production
  actual_endpoint   TEXT;
BEGIN
  actual_endpoint := current_setting('neon.endpoint_id', true);
  IF actual_endpoint IS DISTINCT FROM expected_endpoint THEN
    RAISE EXCEPTION
      'ENDPOINT GUARD: expected %, connected to %. Aborting.',
      expected_endpoint, COALESCE(actual_endpoint, '<null>');
  END IF;
END
$guard$;

-- Drop-and-recreate under the SAME NAME rather than adding a second index:
-- the old key must stop binding, or it would keep refusing exactly the
-- cross-source rows this migration exists to admit. The name is preserved so
-- the baseline's verify block, and the writer's documented ON CONFLICT
-- reference, both still find it.
DROP INDEX IF EXISTS uq_vocabulary_misfire_events_class;

-- `source` sits immediately after `environment`: the key reads as "one
-- observation class, per environment, per DETECTOR, per namespace/surface/
-- field, per value, per extractor identity, per app version".
--
-- NULLS NOT DISTINCT is load-bearing and unchanged: extractor identity is
-- legitimately NULL on lifecycle surfaces (and on every beacon row — no
-- client-visible wire carries vendor attribution), and two NULL extractors are
-- the same observation class. Requires PostgreSQL 15+; both targets are 17.11.
--
-- `source` itself is NOT NULL in the table definition, so it contributes no
-- NULL semantics of its own.
CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_misfire_events_class
  ON vocabulary_misfire_events (
    environment,
    source,
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

-- Fallback if the target is somehow pre-PG15 — same key, COALESCE'd. If you
-- use this, the writer's ON CONFLICT target must name the expression list
-- exactly. (Carried forward from the baseline, with `source` added; not used
-- on either live target.)
-- CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_misfire_events_class
--   ON vocabulary_misfire_events (
--     environment, source, namespace, surface,
--     COALESCE(field, ''), event_class, value_class, COALESCE(value_hash, ''),
--     COALESCE(extractor_vendor, ''), COALESCE(extractor_model, ''),
--     COALESCE(extractor_version, ''), COALESCE(app_version, '')
--   );

COMMENT ON COLUMN vocabulary_misfire_events.source IS
  'Which detector wrote the row, and PART OF THE DEDUP KEY since '
  'migrations/vocabulary_misfire_dedup_source.sql (F-NEW-PK) — two detectors '
  'observing the same value are two observation classes, never one row whose '
  'attribution went to whoever filed first. ''ingest'' — IngestDO.assemble(), '
  'the user-flow extraction pipeline and the PRIMARY detector (owner ruling '
  '2026-08-21): it sees 100% of extraction traffic and is the only site '
  'carrying real per-arm extractor identity (OR-14). ''adi'' — the ADI submit '
  'route at dev-submission time (v6 §8 rung 6 item 3). ''beacon'' — '
  'POST /v1/client-drift (F-NEW-PP, v7 §6 / OR-19): production clients, '
  'carrying the MIRROR population (server vocabulary the app could not '
  'classify) that the ingest census structurally cannot see, plus the '
  'version-skew signal.';

-- Ledger — DATABASE_LAYOUT.md § Migration workflow rules, rule 3.
INSERT INTO schema_migrations (filename, applied_by)
VALUES ('vocabulary_misfire_dedup_source.sql', 'vocabulary-v7-phase4')
ON CONFLICT (filename) DO NOTHING;

COMMIT;


-- ── Verify (run after COMMIT, on an independent reconnect) ──────────────────
-- DATABASE_LAYOUT.md § Migration workflow rules, rule 7.
--
-- -- Expect ONE row whose definition lists `source` second, right after
-- -- `environment`, and still says NULLS NOT DISTINCT.
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'vocabulary_misfire_events'
--   AND indexname = 'uq_vocabulary_misfire_events_class';
--
-- -- The four read indexes must be untouched: six rows in total, the four
-- -- plus this unique index plus vocabulary_misfire_events_pkey.
-- SELECT indexname FROM pg_indexes
-- WHERE tablename = 'vocabulary_misfire_events' ORDER BY indexname;
--
-- -- The nine constraints must be untouched.
-- SELECT conname FROM pg_constraint
-- WHERE conrelid = 'vocabulary_misfire_events'::regclass ORDER BY conname;
--
-- SELECT filename, applied_at, applied_by FROM schema_migrations
-- WHERE filename = 'vocabulary_misfire_dedup_source.sql';


-- ── Rollback ────────────────────────────────────────────────────────────────
-- Safe ONLY while no two rows differ solely by `source`; the narrowed unique
-- index is validated on creation and will refuse if any pair does. That is the
-- correct behavior — collapsing two detectors' distinct observations to fit an
-- index would be the log lying. Deploy the matching writer (ON CONFLICT
-- without `source`) alongside any rollback.
--
-- BEGIN;
-- DROP INDEX IF EXISTS uq_vocabulary_misfire_events_class;
-- CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_misfire_events_class
--   ON vocabulary_misfire_events (
--     environment, namespace, surface, field, event_class, value_class,
--     value_hash, extractor_vendor, extractor_model, extractor_version,
--     app_version
--   ) NULLS NOT DISTINCT;
-- DELETE FROM schema_migrations
-- WHERE filename = 'vocabulary_misfire_dedup_source.sql';
-- COMMIT;
