-- ============================================================================
-- vocabulary_misfire_snapshot_version.sql
--
-- Source:       ROADMAP F-NEW-PQ (filed 2026-08-22, when the beacon shipped
--               without a column for the signal), closed by the owner ruling
--               of the same day. Amends `vocabulary_baseline_v6.sql`
--               SECTION A, as already amended by
--               `vocabulary_misfire_dedup_source.sql` (F-NEW-PK).
-- Author date:  2026-08-22
-- Scope:        ONE column and ONE index. Adds
--               `vocabulary_misfire_events.snapshot_version` and puts it in
--               `uq_vocabulary_misfire_events_class`, the misfire log's dedup
--               key. Nothing else in SECTION A is touched.
--
-- ── WHY ─────────────────────────────────────────────────────────────────────
-- `POST /v1/client-drift` (F-NEW-PP) accepts the dictionary version the client
-- HELD when it observed drift — `snapshot_version` on the envelope, the signal
-- OR-19 names as one of the beacon's two populations ("version skew: client
-- snapshot older than server dictionary"). The table had no column for it, so
-- the route validated it, logged it to the tail, and dropped it: the skew
-- signal never reached the NCC read surface it exists for.
--
-- Folding it into `app_version` was rejected outright and stays rejected: that
-- is a dedup-key column whose value domain is the app version, and appending a
-- snapshot marker to it would corrupt the key and fragment every row.
--
-- ── WHY IT IS IN THE KEY, NOT MERELY BESIDE IT (owner ruling 2026-08-22) ─────
-- THE DICTIONARY VERSION THE OBSERVER HELD IS PART OF THE OBSERVATION CLASS.
-- The same unrecognized value seen under snapshot v3 and under v7 is DIFFERENT
-- EVIDENCE, not one observation counted twice:
--
--   under an OLD snapshot  — the term may well be in the dictionary already
--                            and the observer simply had not caught up. That
--                            is APP LAG, and the fix is distribution.
--   under the CURRENT one  — the term is genuinely absent from the dictionary.
--                            That is a CURATION work item, and the fix is the
--                            owner promoting a term.
--
-- Merging them under one row destroys exactly that distinction, and destroys
-- it in the direction that costs the most: a wave of lag sightings would
-- inflate a row the owner then reads as demand for a term that already exists.
-- This is the same argument OR-14 makes for extractor identity and F-NEW-PK
-- made for `source`, one level up again — the log's stated purpose is seeing
-- WHO OBSERVED WHAT, and "what the observer knew at the time" is part of who
-- was observing.
--
-- The server-side sources are keyed on it for the same reason and it is not a
-- courtesy: the ingest census and the ADI feeder validate against the CACHED
-- SNAPSHOT (v7 Phase 1), so a census row also means "off-list AS OF version
-- N". A term promoted at v8 must not have its pre-promotion sightings merged
-- into its post-promotion ones. Those rows carry the version the census
-- actually validated against, or NULL when it fell back to the in-code
-- bootstrap sets — NULL there means "validated against no published
-- snapshot", which is a real and different state, never a stand-in for
-- unknown.
--
-- ── TYPE ────────────────────────────────────────────────────────────────────
-- BIGINT, not the INTEGER the ROADMAP entry sketched. The value domain is
-- `vocabulary_dictionary_version.version`, which is BIGINT
-- (`vocabulary_v7_phase1_dictionary.sql`); narrowing it here would plant a
-- silent overflow between a counter and the column that records it. Nullable
-- by construction — a NULL is "no published snapshot was in hand", the
-- bootstrap-fallback state.
--
-- ── WHAT ELSE MUST CHANGE, AND IN WHAT ORDER ────────────────────────────────
-- The writer's ON CONFLICT target must name the index's column list EXACTLY.
-- `src/vocabulary-misfire.mjs` (`buildMisfireInsert`, `buildMisfireRow`,
-- `MISFIRE_COLUMNS`) and `src/client-drift.mjs` are updated in the same sprint
-- to carry and store the column.
--
-- ORDER: MIGRATION FIRST, THEN DEPLOY (standing rule). Between the two there
-- is a brief window in which the deployed Worker's ON CONFLICT names a column
-- list no unique index matches, and every misfire INSERT in that window
-- errors. That is ACCEPTABLE AND BOUNDED for the two censuses, and it is why
-- the misfire writer is fire-and-forget: `logMisfires` swallows to
-- console.error, nothing branches on its outcome, and the observe-never-gate
-- posture means ingest and the ADI upload are untouched. The BEACON is the one
-- caller that awaits its write, and in that window it would answer 503
-- `misfire_write_failed` — which acknowledges nothing, so the device keeps its
-- backlog un-watermarked and the next flush carries it. Nothing is lost either
-- way. Running the deploy first instead would open the SAME window in the
-- other direction and additionally lose the ordering guarantee, so it is not
-- the safer inversion it looks like.
--
-- ── DATABASE GROUP ──────────────────────────────────────────────────────────
-- USER-FLOW only (`DATABASE_URL`, binding `sql`). The misfire log lives in the
-- user-flow group per baseline authoring decision A1; the ADI group has no
-- `vocabulary_misfire_events` table and MUST NOT be run against here. (Note
-- the dictionary and its version counter DO live in the ADI group — the
-- version travels here as a value on a row, never as a foreign key. There is
-- no cross-database constraint to add and none may be added.)
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
-- Non-destructive. The column is nullable with no default, so the ADD COLUMN
-- is a catalog-only operation that rewrites nothing and every existing row
-- reads NULL — honest, since none of them recorded a held version.
--
-- The index change is strictly WIDENING: adding a column to a unique key can
-- only ever admit rows the old key refused, never refuse a row it admitted. No
-- existing row can violate the new index (they all share NULL in the new
-- position, and every other position is unchanged), so the CREATE cannot fail
-- on data.
--
-- What it does NOT do, deliberately: it does not backfill a version onto
-- existing rows. There is no honest value to backfill — the current dictionary
-- version is what is true NOW, not what the observer held THEN, and stamping
-- it would fabricate exactly the evidence this column exists to record. Pre-
-- migration rows keep NULL and mean "held version not recorded".
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

ALTER TABLE vocabulary_misfire_events
  ADD COLUMN IF NOT EXISTS snapshot_version BIGINT;

-- Defence in depth against a negative version reaching the column. The writer
-- normalizes before binding (a non-integer, a negative, or a value outside the
-- JS safe-integer range becomes NULL rather than a fabricated number), so this
-- CHECK should never fire — and it must never fire, because the beacon writes
-- its whole batch in ONE transaction and a CHECK violation there would refuse
-- the batch rather than one row. It is here so a future writer that forgets
-- the normalizer fails loudly at the boundary instead of storing nonsense on
-- a key column. Added conditionally: ALTER TABLE has no ADD CONSTRAINT IF NOT
-- EXISTS, and this file must be re-runnable.
DO $c$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'vocabulary_misfire_events'::regclass
      AND conname  = 'vocabulary_misfire_events_snapshot_version_check'
  ) THEN
    ALTER TABLE vocabulary_misfire_events
      ADD CONSTRAINT vocabulary_misfire_events_snapshot_version_check
      CHECK (snapshot_version IS NULL OR snapshot_version >= 0);
  END IF;
END
$c$;

-- Drop-and-recreate under the SAME NAME rather than adding a second index:
-- the old key must stop binding, or it would keep refusing exactly the
-- cross-version rows this migration exists to admit. The name is preserved so
-- the baseline's verify block, and the writer's documented ON CONFLICT
-- reference, both still find it.
DROP INDEX IF EXISTS uq_vocabulary_misfire_events_class;

-- `snapshot_version` sits immediately after `app_version`: the two are the
-- OBSERVER-STATE axis of the key, and they belong together — "which build saw
-- it, holding which dictionary". The key now reads as "one observation class,
-- per environment, per DETECTOR, per namespace/surface/field, per value, per
-- extractor identity, per app version, PER HELD DICTIONARY VERSION".
--
-- NULLS NOT DISTINCT is load-bearing and unchanged, and it is what makes the
-- new column safe to add here: extractor identity is legitimately NULL on
-- lifecycle surfaces (and on every beacon row), and `snapshot_version` is
-- legitimately NULL on every pre-migration row, on every bootstrap-fallback
-- census row, and on any beacon row whose client sent no version. Two NULLs
-- are the same observation class — without NULLS NOT DISTINCT, every such row
-- would be unique and the log would stop deduping entirely. Requires
-- PostgreSQL 15+; both targets are 17.11.
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
    app_version,
    snapshot_version
  ) NULLS NOT DISTINCT;

-- Fallback if the target is somehow pre-PG15 — same key, COALESCE'd. If you
-- use this, the writer's ON CONFLICT target must name the expression list
-- exactly. (Carried forward from the baseline, with `source` and
-- `snapshot_version` added; not used on either live target.)
-- CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_misfire_events_class
--   ON vocabulary_misfire_events (
--     environment, source, namespace, surface,
--     COALESCE(field, ''), event_class, value_class, COALESCE(value_hash, ''),
--     COALESCE(extractor_vendor, ''), COALESCE(extractor_model, ''),
--     COALESCE(extractor_version, ''), COALESCE(app_version, ''),
--     COALESCE(snapshot_version, -1)
--   );

COMMENT ON COLUMN vocabulary_misfire_events.snapshot_version IS
  'The dictionary snapshot version the OBSERVER HELD when it saw this value, '
  'and PART OF THE DEDUP KEY since '
  'migrations/vocabulary_misfire_snapshot_version.sql (F-NEW-PQ, owner ruling '
  '2026-08-22) — the same drift under an old snapshot and under the current '
  'one is different evidence (app lag vs genuinely new vocabulary), never one '
  'row. Value domain is vocabulary_dictionary_version.version (ADI group), '
  'carried here as a value; there is no cross-database constraint and none may '
  'be added. NULL means NO PUBLISHED SNAPSHOT WAS IN HAND — for '
  'source=''ingest''/''adi'' that is the bootstrap-fallback path of '
  'loadVocabularyKnownSets (KV unbound, unreadable, or empty); for '
  'source=''beacon'' it is a client that sent no version, or one that sent an '
  'unusable one. It is never a stand-in for a version we simply did not '
  'record. Rows predating this migration are all NULL and are not backfilled: '
  'the current version is what is true now, not what the observer held then, '
  'and stamping it would fabricate the very evidence this column records.';

-- Ledger — DATABASE_LAYOUT.md § Migration workflow rules, rule 3.
INSERT INTO schema_migrations (filename, applied_by)
VALUES ('vocabulary_misfire_snapshot_version.sql', 'vocabulary-v7-phase4')
ON CONFLICT (filename) DO NOTHING;

COMMIT;


-- ── Verify (run after COMMIT, on an independent reconnect) ──────────────────
-- DATABASE_LAYOUT.md § Migration workflow rules, rule 7.
--
-- -- Expect one row: snapshot_version, bigint, is_nullable = YES.
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'vocabulary_misfire_events'
--   AND column_name = 'snapshot_version';
--
-- -- Expect ONE row whose definition ends with `snapshot_version` immediately
-- -- after `app_version`, and still says NULLS NOT DISTINCT.
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
-- -- TEN constraints now — the nine the baseline authored plus
-- -- vocabulary_misfire_events_snapshot_version_check.
-- SELECT conname FROM pg_constraint
-- WHERE conrelid = 'vocabulary_misfire_events'::regclass ORDER BY conname;
--
-- SELECT filename, applied_at, applied_by FROM schema_migrations
-- WHERE filename = 'vocabulary_misfire_snapshot_version.sql';


-- ── Rollback ────────────────────────────────────────────────────────────────
-- Safe ONLY while no two rows differ solely by `snapshot_version`; the
-- narrowed unique index is validated on creation and will refuse if any pair
-- does. That is the correct behavior — collapsing an app-lag sighting and a
-- genuine-new-vocabulary sighting to fit an index would be the log lying.
-- Deploy the matching writer (no `snapshot_version` in the row or the ON
-- CONFLICT target) alongside any rollback.
--
-- BEGIN;
-- DROP INDEX IF EXISTS uq_vocabulary_misfire_events_class;
-- CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_misfire_events_class
--   ON vocabulary_misfire_events (
--     environment, source, namespace, surface, field, event_class,
--     value_class, value_hash, extractor_vendor, extractor_model,
--     extractor_version, app_version
--   ) NULLS NOT DISTINCT;
-- ALTER TABLE vocabulary_misfire_events
--   DROP CONSTRAINT IF EXISTS vocabulary_misfire_events_snapshot_version_check;
-- ALTER TABLE vocabulary_misfire_events DROP COLUMN IF EXISTS snapshot_version;
-- DELETE FROM schema_migrations
-- WHERE filename = 'vocabulary_misfire_snapshot_version.sql';
-- COMMIT;
