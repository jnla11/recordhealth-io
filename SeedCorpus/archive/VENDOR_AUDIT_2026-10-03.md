# Vendor and bakeoff audit against the dictionary series (2026-10-03)

Status: historical (point-in-time audit)
Last verified: 2026-10-03

Read-only audit of `recordhealth-api` on `firstclass` at `910ae79` (after XK was built, before the 2026-10-03 deploy), against `../VENDOR_ABSTRACTION_DESIGN.md` v1.1 and the dictionary series (`../INGEST_VOCABULARY_DESIGN.md` §12.10). No files changed, no SQL run. Recorded, not ruled: the open questions at the end wait on the owner. Line numbers are as of `910ae79`.

## 1. Design state

- `VENDOR_ABSTRACTION_DESIGN.md` v1.1 is current. No v1.2 exists.
- `F-NEW-RY` (configuration registry, opaque configuration id on the manifest) and `F-NEW-RZ` (`parse_vendor_meta` out of the envelope, `errors[]` scrubbed) are filed in ROADMAP with no design text. Both come from `R3_RELATIONSHIPS_SPEC.md` §I, which also filed `F-NEW-RX` and `F-NEW-RT`.
- The 2026-09-07 api audit behind `F-NEW-RY`'s "large" sizing survives only as a one-line session-log entry; no audit document exists.
- `PACKAGE_DESIGN.md` §1 and §7: the manifest's `configuration` is the five-part tuple (parse vendor, parse config bundle version, inference provider, `prompt_variant_set`, `pipeline_version_stamp`); `vocabulary_version` and `schema_version` sit beside it, not in it. The tuple is the report key.

## 2. Built state of V1 to V5

| Item | State |
|---|---|
| Provider registry at `callBedrock` | Not built (`src/pipeline-shared.mjs:84` is a direct Bedrock call) |
| Model id (satellite 1) | Partial (`resolveBedrockModelId` exists; a duplicate env read is still live in `callBedrockWithTools`) |
| Failure classifier, ledger literal (satellite 2) | Not built (`vendor: "bedrock"` literal still in `src/bedrock-retry.mjs`) |
| Harness routing (satellite 3) | Not built (`bedrockRoute` in `test/harness/replay.mjs` hard-wired to Bedrock) |
| Parse adapter | Not built (LlamaCloud calls still `IngestDO.submitParse` / `submitExtract`) |
| Extract config bundle | Partial: `EXTRACT_CONFIG_VERSION` `x2` and `PARSE_CONFIG_VERSION` `p1` pinned; `SYSTEM_PROMPT` and `DATA_SCHEMA` still inline |
| Vendor id in phase and error events | Not built |
| Harness passthrough | Partial (handlers get `init`; the original `input` and a real-fetch path are missing) |
| Scorer, corpus runner, response cache, bakeoff tables | Not built |
| Rate card (`F-NEW-MY`) | Partial (inline Llama constants only) |
| Per-job stamp resolution | Not built (hold release and tombstones compare the global stamp) |

Ground truth is built: the lock writes `corrected_core_hash` and `rebuild_version` (`src/package-lock.mjs`).

## 3. What identifies a configuration today

- The manifest tuple holds no dictionary. `prompt_variant_set` and the pipeline stamp name pass versions only.
- `vocabulary_version` sits beside the tuple and records only the Atom Pass's copy of the dictionary.
- The PHI pass loads its own copy at assembly; its version reaches a log line only, never the result.
- `vocabulary_version` is null when only Extract ran, though the PHI pass still ran against a dictionary.
- It is mixed on partial retries: a retry that re-runs some sections labels the result with the re-run's version.
- Each pass caches its copy for 5 minutes per instance, so a publish between passes yields a result whose PHI pass saw the new dictionary while the manifest names the old one.
- A dictionary publish moves no version and no stamp: the pins hash template source, not the rendered prompt.
- The rendered prompt prints the snapshot version (`dictionary snapshot v{N}`), so every publish, even a display-only edit, changes what the AI reads (against OR-26's intent).

## 4. Gaps between the vendor design and the build order

1. The configuration does not capture dictionary-driven AI input. This matters now: closed lists and PHI types already reach the AI. Before W3 it needs the dictionary version per pass; from W3, the AI-facing fingerprint.
2. The design's response-cache key (vendor, config version, document hash), taken literally, would replay an answer across dictionary versions.
3. One-variable-per-run cannot be checked from the manifest: the dictionary is a second axis that changes across publishes with no code change.
4. `F-NEW-RY`'s opaque id and the design's tuple are unreconciled, and no doc owns v1.2.
5. Truth has no dictionary version, and there is no translation path (`F-NEW-SV`) to score across versions.

## 5. Conflicts

- VENDOR §1.1's "explicit version constant, not a derived hash" against the 2026-09-07 version-constant convention (`../RELATIONSHIP_DESIGN.md`: a constant may stay explicit only if a test guards it). The VENDOR doc was never updated.
- The tuple (VENDOR §0, §4.1: run manifest, cache key, report key) against `F-NEW-RY`'s opaque id. Neither doc says which wins.
- Neither the tuple nor the opaque id includes the dictionary.

## 6. Scoring effects of the remaining steps

| Step | Effect |
|---|---|
| W3 | Prompts change; prompt pins bump, so the stamp and `prompt_variant_set` move. Before-W3 and after-W3 candidates are different configurations. The fingerprint helps only if it enters the configuration. |
| XH to XJ | Subtype values change: `patientName` → `name`, `facility` → `facilityName` (1:1 renames); `address` splits into street, city, state and zip (one fact becomes up to four, so counts and matching change); `formCode` and `barcode` removed. |
| XA | `reliability` changes meaning and possibly name; old and new candidates do not compare on it. |
| 7a | Adds `date_normalized`, the vendor date fields and the `received` role: a better date equality test, but truth locked before 7a has no normalized dates. |

Truth from one dictionary version can score a candidate from another only partly: kind, page, span and box compare; PHI type, subtype and reliability need translation. The lock records no dictionary version, and reviewer picks come from whatever dictionary was live, so one truth core can mix versions. 1:1 renames translate mechanically once `F-NEW-SV` exists; the `address` split needs a re-grade or a known-mismatch rule.

## 7. Open questions, with the audit's recommendation

1. **Does the dictionary belong in the configuration?** Recommendation: yes; the version per pass now, the AI-facing fingerprint from W3; it then enters the report key and the cache key.
2. **Tuple or opaque id?** Recommendation: keep the tuple as the identity and add the dictionary; defer the registry until a second vendor exists.
3. **Should the prompt print the dictionary version?** Recommendation: no; remove it at W3, so only AI-facing changes alter the AI's input.
4. **Does the lock record the dictionary?** Recommendation: yes, the version live at lock time.
5. **Is `F-NEW-SV` a scorer prerequisite?** Recommendation: yes for the 1:1 renames; re-grade the `address` split instead of translating it.
6. **When is the truth corpus locked for the bakeoff?** Recommendation: after the dates step (7a), matching GR-173's one wipe and re-ingest; the scorer can be built before then against throwaway truth.
7. **XK's deploy order?** Recommendation: migration and the version 8 publish first on staging, then the code, then the same for production; never XK's code alone.

**Note on question 7 (recorded at the 2026-10-03 deploy).** The publish-before-code recommendation was not followed: the old Worker's publish would have written a version 8 without the choosable setting. The XK order was used instead (migration, Worker, console, then publish), on staging then production, and it worked; the hold gaps between the Worker and the publish were 14 s and 1 s. See `recordhealth-api/docs/archive/SESSION_LOG.md`, 2026-10-03.

Placement the audit proposed, recorded not ruled: a small piece recording the dictionary in each run's identity (per-pass version, and the lock's version) before W3, for a clean "before W3" baseline; V1 waits for a second provider; scorer stages S1 and S2 can start any time; V2, V4 and V5 stay after V3.
