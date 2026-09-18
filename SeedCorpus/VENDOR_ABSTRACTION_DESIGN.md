# Vendor Abstraction + Bakeoff Design

Status: design v1.1 (shape, not spec) — V0 audit findings folded, owner rulings applied; §4.1 amended 2026-09-17 (owner rulings; Fable spec pass); v1.1's retired resolver language struck from §4.1, §5, §6 and §8 on 2026-09-18
Last verified: 2026-09-18
Date: 2026-08-21 (v1 same day; v1.1 supersedes it in place)
Repo home when adopted: `RecordHealth.IO/SeedCorpus/VENDOR_ABSTRACTION_DESIGN.md`

Absorbs the design halves of `F-NEW-MZ` (pluggable parse vendor abstraction) and `F-NEW-AA` (AI provider abstraction), and defines the bakeoff harness neither item names. Leans on shipped machinery: the replay harness (F-NEW-MP), `VendorHealthDO`, the spend ledger, the failure taxonomy, `ingest_phase_events`, and the ADI graded corpus. Hard-depends on F-NEW-MY (rate card) — promoted by owner ruling to a prerequisite for live A/B routing (§5).

**v1.1 provenance.** Two audits ran 2026-08-21: a Worker-side V0 audit (recordhealth-api, 7 questions) and an iOS caller check (recordhealth_app). Their findings are folded throughout; sections changed from v1 are marked ⟲. Owner rulings recorded 2026-08-21: live A/B routing is IN scope (§5); the Extract config gets an explicit version constant (§2.1); F-NEW-MY is a hard prerequisite for A/B and the ledger's cost arithmetic rewires to it (§3.2).

---

## 0. Framing — two boundaries, one scoring surface ⟲

Record Health buys two different things from vendors:

- **The parse boundary** turns document bytes into structure: page text in reading order, word geometry, tables, and structured field extraction. Today: LlamaParse (parse arm) + LlamaExtract (extract arm), wired into `IngestDO`. Candidates: Textract AnalyzeDocument, Landing.ai (checkbox fidelity, F-NEW-MK), Bedrock vision.
- **The inference boundary** turns structure into meaning: the Atom Pass, PHI Pass, record summary, condition-page tailoring, KT synthesis, and `/ai/chat`. Today: Bedrock Claude via the single `callBedrock` in `pipeline-shared.mjs`. Candidates: other Bedrock models, BioMistral (roadmap), any BAA-covered chat-shaped LLM.

**Scope ruling (v1.1, audit-verified).** The abstraction covers the server ingest pipeline (the DO path) only. The audit found two additional parse-shaped code paths — the `/document/parse` sync LlamaParse relay (five bare fetches, `src/index.js:8811–9041`) and the `/document/analyze` Textract relay (`:8403`) — sitting outside every seam, ledger, and error capture. The iOS caller check confirmed **both are fully dead**: no caller anywhere in the app, and the iOS `LlamaParseResponseAdapter` that once consumed `/document/parse` is itself orphaned (zero callers of `makeParsedPages`; the live pipeline decodes `/v1/ingest/result` inline in `RecordIngestPipeline.swift`). They are **deletion candidates, not abstraction targets** — filed in §8, out of scope here.

**Deliberately not an adapter target:** Comprehend Medical and similar NER services. Those replace a pass, not a model behind a pass. They enter only at the bakeoff layer (§4), which scores *pass outputs* — comparable no matter what produced them.

The design's central claim stands: **the bakeoff scores atoms against the reviewer-graded corpus, not raw vendor responses against each other.** And v1.1 sharpens the unit of comparison: the bakeoff never compares bare vendors — it compares **configurations**: (vendor, vendor config bundle version, prompt variant set). That tuple is the run manifest, the cache key, and the report key (§2.1, §4.1).

---

## 1. The parse adapter contract (tiered) ⟲

F-NEW-MZ's hard question — is a common contract achievable — is answered with a **tiered contract**: a small mandatory core plus declared optional capabilities. The V0 audit's Textract check (§1.2) confirms the core tier survives contact with a real second vendor, with named adapter obligations.

**The canonical shape already exists.** It is what `buildCodexFromParsedPages` and `llama-extract-adapter.mjs` already produce: the codex (per-page lines with `lineProvenance` bboxes), parsed pages (text elements, tables, words), and extract atoms. The LlamaCloud adapter IS adapter #1; this design formalizes what it implicitly promises.

**Core tier (mandatory):**
- Per-page text lines in reading order, with page dimensions.
- Per-line bounding geometry (line-level minimum; may be adapter-synthesized — see Textract note).
- A job identity the poll loop can watch — native async job id, OR a sync result adapted to an instantly-completed arm.

**Capability tiers (declared per adapter):** `word_geometry`, `tables`, `cell_geometry`, `panel_headers`, `checkbox_state`, `grounding_boxes`, `structured_extract`. An adapter may fulfill the parse arm, the extract arm, or both.

**An adapter exports:** `submit(bytes, opts)`, `pollStatus(jobId)`, `fetchResult(jobId)` → canonical shape, `classifyFailure(err)` → the existing `FAILURE_CLASS` taxonomy, `capabilities`, `rateEntry` (F-NEW-MY hook), and its **vendor config bundle** (§1.1). The `IngestDO` two-arm state machine does not change; arm vendor calls route through the adapter the job's config names. Degradation is explicit: a stage wanting an absent capability takes its documented fallback or logs a capability gap — never silently produces garbage geometry.

### 1.1 Vendor config carveout (new in v1.1, owner-confirmed)

Vendor-specific material lives inside the adapter, never in the DO or passes:

- **Parse side.** LlamaExtract's `SYSTEM_PROMPT` + `DATA_SCHEMA` currently sit inline in `src/ingest-do.mjs:297+` with **no version constant at all** (audit finding; acknowledged in-code at `:2216–2221`). They move into the adapter as a versioned config bundle. **Owner ruling: the bundle gets an explicit version constant** (same convention as the existing prompt versions — not a derived hash). Textract's config is its FeatureTypes; Landing.ai's is its schema shape. The bundle version joins the stamp composition (§3.1) and the bakeoff cache key (§4.1), so a schema tweak invalidates stale shards and stale cache entries the same way a vendor swap does.
- **Inference side.** Prompts stay pass-owned — the Atom Pass prompt is the pipeline's, not Bedrock's. But a Claude-tuned prompt handed raw to another model scores artificially badly, so each pass allows optional **per-provider prompt variants**, each versioned. The bakeoff's one-variable rule treats provider + its refit as ONE named configuration: comparisons are tuned-vs-tuned, and the run manifest records exactly which variant ran.

### 1.2 Textract adapter obligations (audit-verified) ⟲

Against the core tier, AnalyzeDocument's block tree: reading-order lines only via the LAYOUT child walk (a LINE unparented by any LAYOUT block is invisible — adapter must also walk bare LINEs); **per-line geometry is absent from the current walker** (Textract emits it; the relay dropped it) and must be synthesized as the union of word bboxes; no job identity (sync, stateless, block ids unstable across calls) — the adapter mints its own and lands the arm through the existing rung-6a pattern (WAITING arm, `jobId: null`, alarm synthesizes COMPLETED; that pattern shipped and is test-pinned). Capabilities provided: `word_geometry`, `tables`, `cell_geometry`. Lacks: `structured_extract` entirely, `panel_headers` (raw TABLE_TITLE / COLUMN_HEADER signals only). Sync-per-page means the adapter owns page fan-out and partial-page failure semantics, and the Llama-credit `pages_estimate` ceiling math is meaningless for a per-page dollar vendor — the ceiling reads the vendor's own `rateEntry` (§3.2).

## 2. The inference provider contract ⟲

Audit verdict: **one clean move, plus three satellites.** Every Bedrock invocation in the repo funnels through the single `callBedrock` (`pipeline-shared.mjs:104` is the only `bedrock-runtime` URL composition in the codebase) — the three ingest passes via `callBedrockWithRetry`'s injection, and `/ai/chat`, `/ai/query`, `/ai/test`, condition-page tailoring, KT synthesis, and the admin tool-use driver directly. A provider registry installed at `callBedrock` misses nothing.

- A provider is `{ id, modelId, invoke(messages, opts) → { content, usage, stop_reason }, classifyFailure(err), rateEntry, capabilities }`.
- `bedrock-claude` = today's `callBedrock` + `classifyBedrockFailure`, moved behind the interface, zero behavior change.
- **Satellite 1 — model identity.** Two sites read model identity outside the call path (`resolveBedrockModelId` at `ingest-do.mjs:2222`; a duplicate env read at `index.js:971`). The interface exposes `modelId`; both sites read it from the provider.
- **Satellite 2 — per-provider failure classification.** `classifyBedrockFailure` keys on AWS-shaped signals. Each provider ships its own classifier behind the SAME shared error-class vocabulary. The deliberately hardcoded `vendor: "bedrock"` ledger literal (`bedrock-retry.mjs:258`, test-pinned) becomes threaded from the provider id — the pinning test updates with it, on purpose.
- **Satellite 3 — harness routing.** The replay harness recognizes Bedrock by URL + system-prompt sniffing (`bedrockRoute`); a new provider's URL/body shape means extending the route matcher.
- Per-pass provider selection: Atom Pass, PHI Pass, and summary may each name a provider — routing config, not code.

F-NEW-AA's iOS-side protocol stays filed separately; this design is Worker-side.

## 3. Vendor identity threading ⟲

### 3.1 The version stamp

Audit-verified: `PIPELINE_VERSION_STAMP` is composed at `pipeline-shared.mjs:1266` from three prompt/method versions; every consumer compares it as an opaque string. **Appending vendor + config-bundle versions is mechanically purely additive**, and the bump's side effects (memos reset, prior-generation shards unadoptable, version-gated holds release, tombstones lift) are exactly the intended "vendor change = version change" semantics.

**The constraint the audit surfaced, and the owner ruling that overrides deferral:** the stamp is a module-load global, so per-job vendor selection inside one deploy breaks the model — `versionReleasesHold` and `tombstoneBlocks` compare a job's stamped version against ONE global running value. **Owner ruling 2026-08-21: live A/B routing is wanted.** Therefore the stamp rework is committed scope (in V5, §6): stamp resolution becomes per-job — `resolveStampFor(routingConfig)` computed at dispatch and stamped on meta — and the global-comparison consumers change to compare a hold's/tombstone's stamped config against the stamp its key would resolve to under CURRENT routing. Deploy-scoped vendor config (V4) needs none of this; the rework unlocks split routing only.

### 3.2 Ledger, spend protection, and the rate card (owner-ruled)

The ledger already carries `vendor` as a first-class field — new vendor rows store with no migration. But the audit found the **cost arithmetic vendor-hardwired**: `llamaCreditsSpent`, `checkLlamaSpend`, `countBilledSubmitIntents`, and `rollupLedger` filter on `vendor === "llamacloud"` and the inline Llama rate constants. A new vendor's spend is telemetry, not protection — invisible to ceilings, submit caps, and rollups.

**Owner ruling:** this generalizes through F-NEW-MY, which already specifies nearly verbatim what was asked for — per-vendor/model/tier rate conversion, a configurable margin applied at the boundary and **updatable without code change**, a rate-change path that doesn't reprice user tiers, and observed-spend drift tracking feeding rate validation (covering same-vendor rate fluctuation). The audit adds MY's wiring target: the ledger's ceilings/caps/rollups become rate-card-driven, so any vendor with a card entry gets spend protection automatically. **MY is a hard prerequisite for live A/B (V5)** — no vendor is ever live-routed while the ceilings can't see its spend. MY's own design doc is separate work, sequenced in §6.

### 3.3 Telemetry columns

Phase events: `vendor` id needs a `PHASE_EVENT_COLUMNS` entry, an INSERT column, and a migration on `ingest_phase_events` — additive, sanitizer-compatible. `error_events`: a vendor column needs a migration + `insertErrorEvent` change under the table's strict-allowlist rule (today vendor detail reaches it only mangled into strings). Both migrations run via the Neon browser editor per standing rule. `vendor_errors[]` and hold records already carry vendor / `failure_version` — free. `VendorHealthDO` is already addressed by vendor id — new vendors get breaker coverage by enum membership.

## 4. The bakeoff harness ⟲

### 4.1 Offline corpus bakeoff — the primary mode

(v1.1's opening paragraph — ground truth as a resolved grading submission — is deleted as of 2026-09-18; the amendment below stands alone and is the whole of §4.1's ground-truth rule.)

### §4.1 amended 2026-09-17 (owner rulings; Fable spec pass)

**Ground truth is the corrected package (PACKAGE_DESIGN §7; ADI_GRADING v1.4 §6, GR-16/17).** The resolver of v1.1 is retired: it folded grading_submissions and data_atoms, which the lock's rebuild replaces. Ground truth for a source document is the newest locked corrected core for its `source_hash`, identified by `corrected_core_hash` and `rebuild_version`. Every report binds to that pair; a re-lock is a new truth version and cross-version comparison is flagged (§4.3).

**A candidate is any core with the same `source_hash`,** keyed by its manifest's configuration tuple: a re-ingest package, a bakeoff run's output, or the graded package's own original core (candidate zero, the incumbent baseline, free). Nobody scores the reviewer; the reviewer makes truth.

**The scorer compares one candidate core against one truth core and emits records.** One record per truth instance and one per unmatched candidate instance, for atoms, relationships and sections (rows when step 5 lands). A record carries every dimension known: class, kind on each side, page, truth section, match tier, pointer span overlap, box overlap, normalized value equality, PHI mark on each side and its type, table and row, configuration tuple, truth hash, candidate hash, scorer version. Records are computed on request and stored nowhere; reports persisted by the runner (append-only, `bakeoff_runs` / `bakeoff_scores`) carry records with values stripped (§4.3 allowlist). Same inputs, same records; no clock.

**Matching (proposal, Fable 2026-09-17; thresholds are scorer configuration, versioned `rh.score/1`, pinned by a fixture beside the rebuild's).** Atoms match one-to-one, greedy by best tier, within a page: tier 1 same kind, overlapping pointer span, equal normalized value; tier 2 same kind and overlapping span; tier 3 same kind and equal value; tier 4 overlapping span only. Box overlap (IoU) substitutes for span overlap when either side has no pointer. Relationships match by matched endpoints plus kind; sections by kind plus line-range overlap; PHI is a field on the matched atom, never a separate stream. Unmatched truth is a miss; unmatched candidate is an extra. Pointer-first matching is an unverified proposal: whether line and word positions are comparable across parses is an open audit question, and box overlap may turn out to be the primary measure.

**Scoring is a count over records, grouped by any set of dimensions (owner ruling 2026-09-17: axes are open; no instance may cite a list here to refuse an axis).** Per group: precision, recall, F1, with tier 1 a clean hit and tiers 2 to 4 hits carrying derived error labels (wrong value, wrong kind, wrong box, wrong home, wrong PHI mark) read off the record's fields, never stored as categories. Per-kind, per-page, per-document, per-error, per-configuration and any combination are the same call.

**Report** (unchanged in intent): one PHI-free report per run keyed by the configuration tuple: the group table requested, totals, cost and failure rows from the runner's ledger joined on the tuple, and the unmatched lists as ids (disputes must be findable; a candidate consistently missing truth artifacts is a re-grade trigger).

**Build order (proposal):** S1 the scorer module, pure, with fixture and version pin (api, Opus 5; Fable reviews the matching rules first). S2 a scoring route taking two package ids and a group_by list, proven live on candidate zero of staging package 9e16cb41. S3 a re-ingest candidate on staging, same source, scored. S4 the V3 runner and response cache plug in above it. ROADMAP F-NEW-TT tracks it.

**Runner.** A separate entry point on the F-NEW-MP replay harness — never production DOs, never `ingest_jobs`. Scripted fetch serves every route EXCEPT the vendor under test, which goes live through the **response cache**, content-addressed by `(vendor, config_bundle_version, document_hash)`. A vendor pays for each corpus document at most once, ever; every later run replays free. **Audit-verified prerequisite:** the scripted-fetch route table supports a passthrough route as-is (ordered, first-match-wins), but the handler ctx must be extended to thread the original `(input, init)` — today headers are dropped and FormData bodies degrade, so the Llama upload could not be forwarded. One-line seam change, done first in V3. A live Bedrock lane additionally needs real credentials in the harness env (the injected branch already hands over a fully signed request, forwardable as-is).

**One variable per run.** A run varies exactly one configuration element and pins the rest; the manifest names the full configuration tuple; the report is keyed by it.

### 4.2 Live A/B routing (owner-ruled IN scope; supersedes v1's deferred shadow mode)

**Owner ruling 2026-08-21: live A/B is wanted.** It is real scope with three hard prerequisites, in order:

1. **F-NEW-MY-driven spend generalization (§3.2)** — no vendor is live-routed while ceilings can't see its spend.
2. **The per-job stamp rework (§3.1)** — split routing inside one deploy is incoherent without it.
3. **The BAA rule, stated once:** live user documents route only to BAA-covered vendors. Non-BAA candidates (LlamaCloud itself has no BAA today — F-NEW-GT; Landing.ai below its BAA tier) are evaluated on seed-corpus/synthetic documents via the offline bakeoff only. This rule is a guardrail, not a preference.

Mechanics: percentage-split config consulted at the coordinator's dispatch path; the routing decision stamps the job's meta (vendor + config versions → the job's resolved stamp); results flow through the normal pipeline — an A/B'd job IS a production job, fully metered, fully protected. **Shadow mode becomes a special case of A/B** (route the candidate, serve nothing from it: candidate result written to bakeoff storage keyed by document hash, production result served from the incumbent arm) rather than a separate mechanism. Offline bakeoff still lands first (owner-confirmed sequencing); A/B is V5.

### 4.3 Bakeoff guardrails

- Bakeoff spend: own ledger scope, own ceiling, fully separate from user metering; a runaway bakeoff halts at its own cap.
- Reports are PHI-free by allowlist discipline: kinds, counts, scores, hashes, enum members. Never atom values.
- The corpus is versioned; reports bind to the corpus version scored against; cross-version comparison is flagged, never silently mixed.

## 5. Hard questions and tradeoffs (updated) ⟲

1. ~~Core-tier feasibility~~ — **resolved by V0**: survives, with the §1.2 Textract obligations named.
2. **Attribution vs. realism** — prompts tuned for the incumbent understate a new vendor's ceiling on first pass. Accepted; a per-provider refit (§1.1) is just another configuration under the one-variable rule.
3. **Ground-truth drift** — corpus embodies LlamaParse-era sectioning/geometry. Tolerance matching + findable disputes (unmatched-atom lists) mitigate; consistent artifact-losses trigger re-grades.
4. **Corpus size vs. cost** — each candidate pays the corpus once; size is both the price knob and the statistical-power knob. Owner call once MY yields real per-page rates.
5. **Extract-arm coverage** — Textract has no structured-extract analog; a parse-only vendor bakes off with the incumbent extract arm held constant, and the report says which arm combination ran.
6. **Stamp rework delicacy (new)** — per-job stamp resolution touches hold release, tombstones, and the memo, all liveness-critical. It gets its own pre-implementation review inside V5, same posture as the liveness rungs.

## 6. Phasing ⟲

- **V0 — audits. DONE 2026-08-21.** Worker-side 7-question audit + iOS caller check; findings folded into this v1.1.
- **V1 — inference provider registry.** The `callBedrock` move + the three satellites (§2) + telemetry threading (§3.3: ledger vendor literal, phase-events column + migration, error_events column + migration). Zero behavior change; suite is the proof. ~1 sprint.
- **V2 — parse adapter formalization + config carveout.** LlamaCloud code becomes adapter #1; Extract's prompt/schema move into the bundle and gain their first explicit version constant; capabilities declared; vendor id threaded. Zero behavior change. ~1–2 sprints (delicate file, big suite).
- **V3 — bakeoff harness, offline mode.** The harness ctx `(input, init)` extension first; then corpus runner + response cache; ground-truth selection: the newest locked corrected core per `source_hash`, which does not exist as code yet; the scorer; report storage. Deliverable: the incumbent baseline score. ~3 sprints.
- **V4 — second adapter + deploy-scoped routing.** Textract-family parse adapter per §1.2 obligations; deploy-scoped vendor selection config (staging-first, env-gated per the force-fresh precedent — needs NO stamp rework); first true bakeoff: incumbent vs. candidate, same corpus. ~1–2 sprints.
- **V5 — live A/B routing.** In order: F-NEW-MY design + rate-card wiring of the ledger arithmetic (§3.2); the per-job stamp rework (§3.1, own pre-implementation review); coordinator percentage-split + BAA gate (§4.2). Sized after MY's design lands; the stamp rework alone is ~1 sprint plus review.

Model routing per project convention: V1/V2 refactors → Opus 5; V3 → Opus 5 with Fable on ground-truth selection and scorer matching; V4 adapter → Opus 5; V5 stamp rework review → Fable.

Roughly 6–9 sprints through V4 + first bakeoff; V5 sized after MY.

## 7. What this design deliberately does not do

No per-document *intelligent* routing (A/B is random split; smart routing needs F-NEW-MX document metrics and real bakeoff data — filed, not designed). No auto-promotion of a bakeoff winner — vendor selection is an owner decision reading a report. No iOS-side changes. No new production wire shapes before V5. No Comprehend-style pass-replacement design — when real, it plugs into the bakeoff as a scored configuration and gets its own doc.

## 8. Side findings filed out of this design (to land as F-items at next ROADMAP pass) ⟲

1. **Dead vendor code deletion (cleanup item).** Worker: the `/document/parse` sync relay (five bare fetches) and the `/document/analyze` Textract relay + its AwsClient — both caller-less, confirmed by the iOS audit; the inert `AWS_TEXTRACT_*` / `AWS_ANALYZEDOC_*` secrets and IAM users join the item as operator cleanup. iOS: `LlamaParseResponseAdapter` (orphaned, zero callers of `makeParsedPages`) + the stale comments in `FileTextExtractor.swift:161` and the adapter's own header. Deleting `/document/parse` also closes an untracked exposure: it shipped PHI to LlamaCloud with zero ledger/error capture while it lived.
2. ~~**Grading metrics verdict-drift defect.**~~ **Retired 2026-09-18.** It described a stored grading summary being undercounted by `computeMetrics`; scores computed from the log are retired entirely (ADI_GRADING_DESIGN v1.4 §5, GR-27), so there is no summary left to fix or re-derive.
3. **Doc staleness.** `WORKER_ARCHITECTURE.md`'s `/document/analyze` section describes a retired route as current — restamp at next sprint close alongside this design's adoption.
