# Prompt ID Registry

Authoritative registry of every system prompt in Record Health.

Governed by ARCHITECTURE.md §3.3 (Prompt Identity and Versioning,
RecordHealth_App repo). Storage schema and registration endpoints
defined in GRADING_TOOL_DESIGN.md sprint GT-1.5. Initial
population is sprint GT-1.5a.

## Status

Populated by GT-1.5a on 2026-04-15. 16 prompts registered at v1.
pass2_extraction bumped to v2 on 2026-04-16 (GT-1.6c).
ontology_resolution v1 added on 2026-04-16 (GT-1.6d) — Worker-side,
invoked by POST /v1/admin/lookup with Bedrock tool use.
pass2_extraction bumped to v3 on 2026-04-18 (GT-2e) — staging registered,
production deferred (same ADI_ADMIN_KEY issue as GT-1.6c).
pass1_atomization bumped to v6 on 2026-09-04 (locate-step audit, atom
location by pointer) — deployed to staging only; production pending the
owner's read of the live-proof numbers.
pass1_atomization bumped to v7 on 2026-09-04 (one atom per clinical fact,
never one per line — owner ruling that v6's per-line answers were a bug;
the same series found the word layer rendering wrapped lines short and
fixed that beside it) — staging only (`3e4a10c4`); production pending.

## Registry

| prompt_id | current_version | type | location | notes |
|-----------|-----------------|------|----------|-------|
| pass1_document_read | v1 | core | RecordHealth/AI/Pipeline/DocumentReadService.swift | Pass 1 document classification and context extraction |
| pass2_extraction | v3 | core | RecordHealth/AI/Pipeline/AIExtractionService.swift | Pass 2 structured entity extraction, JSON output. v1 (GT-1.5a): initial 12 extraction-target kinds (symptom, condition, diagnosis, medication, allergy, provider, organization, labValue, vitalSign, procedure, visitDate, reportDate). v2 (GT-1.6c): +7 kinds (familyHistory, immunization, socialHistory, device, referral, carePlan, coverage); rule #3 rewritten to extract family history as familyHistory; rules 23-28 added. v3 (GT-2e): +2 kinds (finding, encounter); rules 29-30 added. Finding covers exam/imaging observations and normal findings previously misclassified as conditions. Encounter captures visit type distinct from visitDate. Current: v3 (staging registered; production pending ADI_ADMIN_KEY). |
| ask_ai_single_record | v1 | core | RecordHealth/AI/Pipeline/AIContextBuilder.swift | Ask AI base system prompt for single-record Q&A |
| ask_ai_structured_summary | v1 | modifier | RecordHealth/AI/Pipeline/AIContextBuilder.swift | Structured-card response modifier layered on ask_ai_single_record |
| appointment_prep_summary | v1 | synthesis | RecordHealth/AI/Prompts/AppointmentPrepPrompt.swift | Appointment prep system prompt — tokenized context assembly |
| appointment_prep_user_trigger | v1 | synthesis | RecordHealth/AI/Prompts/AppointmentPrepPrompt.swift | Appointment prep user-role trigger message |
| ask_ai_button_explain_report | v1 | button | RecordHealth/Domain/Models/ConversationModels.swift | Suggested-question button: "Explain this report" |
| ask_ai_button_explain_abnormal | v1 | button | RecordHealth/Domain/Models/ConversationModels.swift | Suggested-question button: "Explain abnormal values" (lab) |
| ask_ai_button_explain_findings_imaging | v1 | button | RecordHealth/Domain/Models/ConversationModels.swift | Suggested-question button: "Explain the findings" (imaging) |
| ask_ai_button_explain_findings_pathology | v1 | button | RecordHealth/Domain/Models/ConversationModels.swift | Suggested-question button: "Explain the findings" (pathology/surgical) |
| ask_ai_button_explain_medication | v1 | button | RecordHealth/Domain/Models/ConversationModels.swift | Suggested-question button: "Explain this medication" |
| ask_ai_button_translate_terminology | v1 | button | RecordHealth/Domain/Models/ConversationModels.swift | Suggested-question button: "Translate into plain English" |
| ask_ai_button_doctor_questions | v1 | button | RecordHealth/Domain/Models/ConversationModels.swift | Suggested-question button: "What should I ask my doctor?" |
| ask_ai_button_what_was_decided | v1 | button | RecordHealth/Domain/Models/ConversationModels.swift | Suggested-question button: "What was decided?" (visit notes) |
| ask_ai_button_key_findings_default | v1 | button | RecordHealth/Domain/Models/ConversationModels.swift | Suggested-question button: "Explain key findings" (default category) |
| ask_ai_button_key_findings_followup | v1 | button | RecordHealth/Domain/Models/ConversationModels.swift | Suggested-question button: "Explain key findings" (follow-up) |
| pass1_atomization | v7 | core | recordhealth-api/src/pipeline-shared.mjs | Worker-side Atom Pass (server port of SegmentedAtomExtractionService). v4: kind/subtype vocabulary as prose, free-text JSON answer. v5 (2026-08-22, vocabulary v7 Phase 2): kind / subtype / date_role / classification_certainty / reliability wording generated from the dictionary snapshot; answer forced through the strict `emit_atoms` tool carrying the same enumerations (`src/extractor-vocabulary.mjs`). v6 (2026-09-04, locate-step audit — atom location by pointer): the section is rendered with `<i>` word markers from the codex word layer and the answer is a POINTER (`page`, `line`, inclusive `word_start`/`word_end`, copied from the markers); `line_start` / `line_end` / `source_text` are removed from the tool; the contradictory "DO NOT RESTATE VALUES" header and every copy-the-text instruction are deleted; the model is told to copy markers, never count, never quote. Classification instructions unchanged. Bump rule: any edit to the prompt, the pointer contract or `atomItemProperties` bumps this version in the same commit. v7 (2026-09-04, recordhealth-api `baa100d`): the atomization unit is made explicit — ONE ATOM PER CLINICAL FACT, never a line and never a marker; several facts on a line yield several atoms with distinct, often adjacent, word ranges; a list on one line yields one atom per item; a worked example shows one long line producing four atoms. v6's "One atom per distinct span (one pointer)" is deleted. Classification rules, pointer mechanics, tool schema and wire unchanged. Compared on a PINNED parse (`docs/WORKER_ARCHITECTURE.md § Prompt v7`): the long-line loss the audit attributed to v6 was the word layer rendering one visual row of a wrapped line (`9ecc2d4`); v7 adds on top of that fix (69/64 atoms on two runs vs 61 for v6 on the fixed layer, 50 on the one-row layer). |
| pass2_phi_classification | v3 | core | recordhealth-api/src/pipeline-shared.mjs | Worker-side PHI pass (server port of PHIClassificationService). v2: HIPAA phi_type list as prose, free-text JSON answer. v3 (2026-08-22, vocabulary v7 Phase 2): phi_type list generated from the dictionary snapshot; answer forced through the strict `emit_phi_classifications` tool enumerating it. |
| ontology_resolution | v1 | resolution | recordhealth-api/src/index.js | Worker-side. AI-led canonical-code resolution with Bedrock tool use. Tools: rxnav_search (RxNorm), nppes_search (NPI), clinical_tables_search (SNOMED, ICD-10-CM, LOINC, CPT). Invoked by POST /v1/admin/lookup. Full agent trace stored in ontology_traces; output shape matches CLINICAL_SHAPE_DESIGN.md §5.6. Added GT-1.6d (2026-04-16). |

## Discipline

- Adding a prompt → add a registry row in the same commit that
  introduces the prompt. Register the prompt_text in
  prompt_versions (Worker) in the same PR.
- Changing a prompt's text → bump the version in both the code
  location and this registry, and register the new
  (prompt_id, version) in prompt_versions. Same commit.
- Removing a prompt → mark deprecated in notes. Do not delete the
  row. Do not reuse the prompt_id.
- Renaming a prompt_id is forbidden. If the purpose changes,
  assign a new prompt_id and deprecate the old one.

## Invariants

- prompt_id is permanent from first commit.
- (prompt_id, version) is append-only in prompt_versions. Text
  cannot change for an existing pair — bump the version instead.
- Every audit_fields row and grading record references a
  (prompt_id, version) pair that exists in this registry.
