# Date Rules Design

Status: living (shape, not spec), owner rulings of 2026-09-26 applied (GR-84 through GR-92, recorded in `ADI_GRADING_DESIGN_v1.6.md`); the audit GR-77 called for is §2 here. Repo home: `RecordHealth.IO/SeedCorpus/DATE_RULES_DESIGN.md`.
Last verified: 2026-09-26

Owns the date rules: how a date is read from text, what its normalized form is, how it is displayed, how the vendor's date is kept beside ours, where the one rule set lives, and what the date role requires. `ADI_GRADING_DESIGN_v1.6.md` §7 points here for the date checks on the console and says nothing more about them; `DATA_MODEL.md` §4.7 and `ARCHITECTURE.md` §3.2 in `RecordHealth_App/docs` point here by name for the reading and normalization of a date fact and keep the role list and the edge mapping. Nothing here is built. Anything the owner did not rule is a labeled PROPOSAL, never settled.

**A word on words.** A *date fact* is a fact of kind `dateAtom`. Its *text* is the words on the page the fact points at, or what a reviewer typed over them. Its *normalized date* is the machine form behind the text. The *vendor's date* is the value the extraction vendor returned for the same field. *Needs attention* is the amber box of GR-83.

## 1. The rulings this rests on

Recorded in the owner's register in `ADI_GRADING_DESIGN_v1.6.md`; listed here by number only.

- GR-84. One set of date rules, written once, used by the phone, the backend and the console. No side keeps its own copy.
- GR-85. The import keeps the vendor's normalized date. *Corrected by GR-92: its second sentence, a needs-attention state for a disagreement, is removed.*
- GR-86. Never invent precision. A year, or a month and year, stays that precise everywhere; no day or time is filled in.
- GR-87. A date that arrived as text is shown exactly as written; a normalized date sits behind it; every programmatic use reads the normalized date, never the text.
- GR-88. A date the system produces itself displays in one consistent format everywhere.
- GR-89. The normalized date is the most precise machine form available, carrying only the precision the source has.
- GR-90. The normalized form is ISO 8601 with its partial forms; a date-time carries its offset; never padded.
- GR-91. The display format is the long US form, March 1, 2024; partials display as March 2024 or 2024; no ordinal suffix.
- GR-92. No comparison between the vendor's date and ours, and no amber box for a disagreement. The vendor's date is kept exactly as returned. Every date is normalized through the one rule set and both values are kept. The vendor's value, our normalized value and the reviewer-confirmed value differ as training and scoring signal; the confirmed date is ground truth and the vendor is scored against it. The reviewer sees the printed text with our normalized date beside it and confirms or fixes it; that is the check for ambiguous dates.

Behind them: GR-69 (checks live on screen, the normalized value shown beside the original), GR-73 and GR-82 (an emptied detail saves and the fact needs attention; the date role is required of the pipeline), GR-74 and GR-80 (the backend refuses only what the console cannot make, and otherwise marks the same state the screen shows), GR-75 and GR-76 (the lock refuses while any fact needs attention; amber is the catch-all), GR-83 (the amber box).

## 2. What exists today (the 2026-09-26 date audit, GR-77)

Read from the code to describe it, not to design around it. Named by file, never by line.

**The import discards the vendor's date.** `recordhealth-api/src/llama-extract-adapter.mjs` reads the vendor's four date fields in one loop. The vendor returns each as an ISO day (`1977-01-16`). The loop generates surface forms for that day (`01/16/1977`, `January 16, 1977`, and the rest), finds the first that resolves to a line in the parsed page, and writes that surface form as the fact's `source_text`; the ISO value itself is not written to the fact. When no surface form resolves, the ISO value is tried as the text, and the fact reaches the validator unlocated, the honest outcome the file's own comment names. Either way the vendor's reading is gone once the fact is built: `source_text` is later re-derived as the parser's words at the pointer (`src/result-schema.mjs`, the `source_text` derivation), and no field on the wire holds a normalized date. `result-schema.mjs` declares none.

**The import produces four of the eight roles.** The same loop maps `collection_date` to `collection`, `report_date` to `report`, `service_date` to `service`, and `received_date` to `narrativeReference`. The last is a misuse by `DATA_MODEL.md` §4.7's own definition, which reserves `narrativeReference` for prose mentions. The Atom Pass prompt (`src/pipeline-shared.mjs`) offers all eight roles on narrative dates, but when the extract copy and a narrative copy carry the same calendar day, dedup keeps the extract copy (`src/ingest-dedup.mjs`), so the extract's four roles are what most lab documents get. The eight roles are a closed list in `src/ingest-vocab.mjs` (`DATE_ROLES`), published through the dictionary; the file notes "no server enforcement, prompt prose only".

**The phone is the only date reader, and it invents precision.** `RecordHealth_App/RecordHealth/AI/Pipeline/DateParser.swift` is the app's date-format authority: a fixed list of formats (US numeric with two- and four-digit years, ISO, dotted, month-name forms in several orders, month-and-year, and date-time forms with and without an offset), ordinal suffixes stripped, month names case-folded, two-digit years windowed at 1930 (00 to 29 read as 2000 to 2029, 30 to 99 as 1930 to 1999), a round-trip check so a mismatched separator does not match. Every match returns a Swift `Date`, which is an instant: a date-only match is shifted to noon UTC, and the two month-and-year formats fabricate day 1 (the file says so; `parseCalendarDate` exists to refuse them, and the atom path does not use it). `Domain/Services/Parsers/DateAtomParser.swift` wraps it for date facts. `Domain/Services/ContextLayerBuilder.swift` parses each date fact's text at Layer 2 rebuild, keeps the fact's payload as `.text` when the parse fails (quietly; nothing is marked), and, when the fact carries no role, defaults it to `report` with a console print and nothing else. A second, purpose-built partial reader exists for the profile date of birth alone (`Domain/Services/DOBPartialDate.swift`, `DOBNormalizer.swift`), which knows that `DateParser` has no partial-component parse. Apple Health dates go through `Data/Import/FHIRDateText.swift`: internet date-time or `yyyy-MM-dd`, printed as `yyyy-MM-dd` wherever the text can reach the AI, year-only exempt from minting, year-month printed as written (`ARCHITECTURE.md` §3.4.4).

**The backend checks nothing about a date.** The write route (`src/package-amendments.mjs`) checks that `date_role` is carried by the fact's kind (GR-33) and that a corrected role is a live term of the dictionary's closed list; it reads the date's text as any other text. Nothing checks that a date fact's text is a date, nothing normalizes it, nothing compares it with anything, and an empty role on a correction is whatever the value check makes of an empty string, unaudited (§9 item 28 of the grading design puts that in the item 23 audit). The receive route validates the package boundary and records PHI findings; it looks at no date.

**The console checks nothing about a date.** `adi-console/app.js` renders `date_role` as a dropdown from the published declaration and the fact's text as text. No format check, no normalized value beside the original, no amber.

**The token reads the text.** A PHI date's token is an HMAC over the PHI type and the trimmed text (`src/result-schema.mjs`, the token derivation). The normalized date and the display form play no part in it, and must not: changing either must not move a token. A reviewer's text correction moves the token by the shipped rule (PACKAGE_DESIGN OR-18 i).

**Display today.** The phone formats dates in some sixty places with its own formatters; the console shows a date fact's text as written and formats no date of its own.

## 3. The normalized form (GR-86, GR-89, GR-90)

The normalized date is a string in one of these shapes, and its length is its precision:

- `2024`
- `2024-03`
- `2024-03-01`
- `2024-03-01T14:30` or `2024-03-01T14:30:00`, a local time with no offset (PROPOSAL 1 below)
- `2024-03-01T14:30:00-08:00`, an instant with its offset

Nothing is padded. A text that names a month and a year produces `2024-03` and nothing longer, anywhere, on any side. A text that names a day and no time produces `2024-03-01` and never a time. A time is kept only when the source states one.

**PROPOSAL 1: a date-time with no offset in the source.** A printed "03/01/2024 14:30" says nothing about its zone. Recommended: the normalized form keeps the time and carries no offset (`2024-03-01T14:30`), which ISO 8601 allows as a local time. Programmatic use treats it as the wall time at the place the document came from; a comparison or sort against an offset-bearing instant is done at day precision. Rejected: filling in UTC or the device's zone, which invents an offset the source does not have (GR-86); dropping the time, which discards precision the source has (GR-89).

**PROPOSAL 2: the phone's value type.** A Swift `Date` cannot hold a partial date without inventing the rest, so the phone's `.dateAtom(role:date:)` payload takes a value that carries exactly the components the normalized string names (year, optional month, optional day, optional time, optional offset), with an ordering over it. Sorting: lexical order of the normalized string sorts dates of one shape correctly, and a partial sorts before every fuller form of the same span (`2024` before `2024-03` before `2024-03-01`); across shapes the comparison is at the coarser precision, and an instant with an offset is compared as a day in its own offset. A longitudinal view places a partial at the start of its span and draws it as a span, never as a day. Matching (dedup, the walker's date edges) compares at the coarser precision as well. The record-level `serviceDate` and `reportDate` on `RecordV2` are out of scope here until the owner says otherwise; they are system-held dates today.

## 4. Reading text (GR-87)

A date fact's text is read whole: trimmed, ordinals stripped, month names read in any case, and the whole must be one date or one date-time. The reader recognizes:

- Numeric US order: `3/1/2024`, `03/01/2024`, `03-01-2024`, `03/01/24`, `3-1-24`
- ISO: `2024-03-01`, `2024-03`, `2024`, `2024/03/01`
- Month-name forms: `March 1, 2024`, `Mar 1, 2024`, `Mar. 1, 2024`, `1 March 2024`, `01-Mar-2024`, `March 1st, 2024`
- Month and year: `March 2024`, `Mar 2024`, `03/2024`
- Dotted: `01.03.2024` (PROPOSAL 3 says how it is read)
- Date-time: any of the day forms followed by a time, with or without seconds, with or without an offset or a `Z`

The exact list is the rule set's, not this document's, and it is published with the rule set so the console, the backend and the phone read the same one (§5). This document says what family it covers and how the hard cases go.

**PROPOSAL 3: ambiguous numeric dates.** `03/04/2024` is March 4 in US order and April 3 in day-first order. Recommended: the rule set reads slash and dash numeric dates in US order, always, and does not mark a fact amber for the ambiguity alone; the check for the cases that matter is the reviewer's: the printed text is shown with our normalized date beside it, and the reviewer confirms or fixes it (GR-92, §6). A numeric date whose first number exceeds 12 is read day-first only when that makes a valid day, and the fact needs attention, since the document has told us its order is not the one we assume. The dotted form reads the same way. Rejected: reading day-first when both readings are valid days, which guesses; refusing every ambiguous text, which would mark most US lab headers.

**PROPOSAL 4: two-digit years.** Recommended: a fixed window stated once in the rule set, 00 to 29 read as 2000 to 2029 and 30 to 99 as 1930 to 1999, the window the phone applies today, chosen so a birth year in the 1930s and a service date in the 2020s both read. The date-of-birth rule that flips a future year back a century (`DOBNormalizer`) stays a rule of that one field, downstream of the rule set, not part of it. Rejected: a sliding window relative to today, which makes the same text normalize differently in different years and breaks the fixture.

**A text that cannot be read.** The fact keeps its text, has no normalized date, and needs attention (GR-76, GR-83). Nothing is substituted, nothing falls back to plain text quietly, and the lock refuses while it stands (GR-75). This holds on import, on the reviewer's save of a typed text, and on the phone. The reviewer's way out is to fix the text, move the fact's words, change its kind, or delete it. The screen shows the reader's result as the reviewer types: the normalized date beside the text when it reads, and "not a date" when it does not (GR-69).

**PROPOSAL 5: a label inside the fact's words.** A fact whose words are "Collected: 03/15/2024" is not a date under the whole-text rule. Recommended: it needs attention like any unreadable text, and the fix is to move the fact's words (GR-53), because the fact's position is ground truth and a reader that hunts inside the text would make the position lie. Rejected: a lenient reader that finds the date inside the text, which hides a position defect.

**Out of scope.** The reader is applied to date facts (kind `dateAtom`) and to any other field the schema declares as a date. A date-shaped text on a fact of another kind is not read and is not marked.

## 5. Where the one rule set lives (GR-84)

The rule set is: the reader of §4, the normalized form of §3 with its ordering, the display of §7, and the fixture that pins them. Three consumers need it: the backend at import and at the write route, the console live as the reviewer types (GR-69), and the phone.

**Option A. One JavaScript module, and the phone runs it through JavaScriptCore.** `recordhealth-api/src/date-rules.mjs` is the rule set; the backend imports it, the console is served the same file (the console already runs as modules from the same repo), and the phone evaluates it in a JavaScriptCore context at Layer 2 rebuild and wherever it formats a date. Cost: a JavaScript runtime on the phone's rebuild path, a bridge to marshal strings both ways, one more thing to start up and to debug on device, and the phone's build no longer stands alone. Truest to the ruling: there is one file.

**Option B. A declarative rule table plus a small interpreter per language.** The formats, the two-digit window, the display forms and the comparison rule are data, in one JSON file shipped with the schema; Swift and JavaScript each hold an interpreter of that table, and the fixture pins the two interpreters equal. Cost: two interpreters are two hand-kept copies of the part that is hardest to get right (the matching), and the table's expressiveness decides the whole design. Drift is confined to interpreter bugs, which the fixture catches.

**Option C. Two implementations pinned equal by one shared fixture.** Swift and JavaScript each implement the rules; `test/harness/fixtures/date-rules.json` holds the vectors (text in, normalized form or "unreadable" out, display form out, ordering verdicts), and both suites run it. This is the repo's existing pattern for the fold and for the package hash. Cost: it is exactly two hand-kept copies, which GR-84 rules out, unless the fixture is read as the rule set and the two implementations as its executors.

**Option D. The backend computes, the phone reads.** The normalized date is a field on the core atom, written by the backend from the text at import and rewritten by the write route whenever the text is corrected. The console runs the same module the backend runs. The phone never reads a date fact's text: Layer 2 reads the stored normalized date. Cost: the phone still formats the normalized form for display (§7), a small piece of Swift; and the phone's own dates (profile date of birth, Apple Health, record dates) are outside the rule set until the owner brings them in. The phone's rebuild loses a parse and gains nothing to keep in sync for facts.

**PROPOSAL 6: D, with C's fixture for the display piece.** Recommended: the rule set is one JavaScript module in `recordhealth-api`, used by the backend and served unchanged to the console. The normalized date and the vendor's date are fields on the core atom (§8), so the phone reads them and parses nothing for a date fact. The one thing the phone keeps in Swift is the display of a normalized string (GR-91), pinned to the module's display function by a shared vector fixture. The phone's `DateParser` stops being used for date facts; its other uses (profile date of birth, Apple Health, record dates, chat digests) are named in §10 as open. Rejected for now: A, because a JavaScript runtime on the phone is a larger change than the rules deserve; B, because the interpreter is where the rules actually are.

## 6. The vendor's date and ours (GR-85, GR-92)

There is no comparison between the vendor's date and ours, and no amber box for a disagreement (GR-92). PROPOSAL 7, which built one, is removed; the other PROPOSALs keep their numbers.

**What the import keeps.** The vendor's value goes on the fact as its own field (PROPOSAL 11 names it), exactly as the vendor returned it, alongside the text the pointer resolves to. Nothing is discarded, and nothing reads it to decide anything about the fact: not the fact's state, not its normalized date, not the lock.

**What is normalized.** Every date fact goes through the one rule set (GR-84), whether the vendor extracted it, the AI extracted it or a reviewer typed it. The normalized date is the rule set's reading of the fact's text, as §3 and §4 say. So each date fact holds both the vendor's value, where the vendor gave one, and our normalized value.

**The signal.** Three values can differ on one date: the vendor's value, our normalized value, and the value the reviewer confirmed. The differences between them are training and scoring signal. The reviewer-confirmed date is ground truth; the vendor is scored against it.

**The check for an ambiguous date.** The reviewer sees the printed text with our normalized date beside it (GR-69, §7) and confirms or fixes it. That is the whole check. A text that cannot be read at all still needs attention (§4); a date that reads is not marked for its ambiguity alone (PROPOSAL 3), and the reviewer's confirmation is what settles it. The reviewer confirms by vetting the fact (GR-28) or fixes it by correcting the text (§8 recomputes the normalized date).

**Dedup.** `src/ingest-dedup.mjs` merges a narrative date with an extract date on the same calendar day. Under this design it compares normalized dates at the coarser precision (§3) instead of its own reading of the text. That is dedup's matching and has nothing to do with the vendor's value.

## 7. Display (GR-88, GR-91)

A date that arrived as text is shown as its text, exactly as written, wherever the fact is shown: the console's list row and panel, the phone's tap-to-source, any view that shows the fact itself. The normalized date is shown beside it where the reviewer is checking it (GR-69) and is what every derived view sorts and plots by (GR-87).

A date the system produces itself (a record's date on the dashboard, an axis label, a header, a date resolved through an edge and shown on a lab result) displays in one format, from the normalized form:

- `2024-03-01` displays as March 1, 2024
- `2024-03` displays as March 2024
- `2024` displays as 2024
- No ordinal suffix, no leading zero, the month spelled out

**PROPOSAL 8: the device's locale outside the US.** Recommended: the display form does not follow the device locale; it is March 1, 2024 on every device and on the console. A printed date shows as printed anyway, so the locale question only touches system-produced dates, and one fixed form is what GR-88 asks for. Rejected: the platform's long style, which gives "1 March 2024" on a UK device and would make the phone and the console disagree; recorded as parked, to revisit if the product ships outside the US.

**PROPOSAL 9: a date-time.** Recommended: March 1, 2024, 2:30 PM, the time in the source's own offset when it has one and as the local time it states when it has none; the offset is not shown. Seconds are not shown. Rejected: converting to the device's zone, which shows a lab drawn at 2:30 PM as an evening draw to a traveler.

**Apple Health.** `FHIRDateText` prints an Apple Health date as `yyyy-MM-dd` wherever the text can reach the AI, so the minted text and the vault entry match (`ARCHITECTURE.md` §3.4.4). That is the AI-facing form and it stays. PROPOSAL 10: what a person sees for the same date (a Health record's header, title and body on screen) is the display form above; the two surfaces are different and the vault matches the AI-facing one. This is a conflict with the file's own comment that every place a Health record prints a date goes through it, opened for the owner in §11.

## 8. The date on the wire

**PROPOSAL 11: two fields on the core atom, published in the schema.** A date fact carries `date_normalized` (the rule set's reading of the text, nullable when unreadable) and `date_vendor` (the vendor's value as given, nullable when the vendor gave none). Both are declared in `src/result-schema.mjs` on the atom shapes and bump `SCHEMA_VERSION`; the phone's drift beacon sees the bump. `date_normalized` is a derivation of the text and is graded as the text is: it is never corrected on its own, it is recomputed by the write route whenever the text is corrected, and it is recomputed by the rebuild at lock from the corrected text. `date_vendor` is never corrected and is not a field the console edits. The names are proposals.

**Why this does not break sacred rule 8.** `ARCHITECTURE.md` §3.2 and `DATA_MODEL.md` §3.3 say a storage atom never holds an AI-restated value. `date_normalized` is a deterministic function of the text, regenerable from it, and no AI wrote it; that is the same standing as `source_text`, which is the parser's words at the pointer. `date_vendor` is an AI's value, and it is kept as evidence and as scoring signal (GR-92), not as a value any consumer reads for the date. The owner should confirm that reading (§11).

**The token.** Neither field enters the token. The token is over the trimmed text, as today.

**The amber state's carrier.** How "needs attention" is stored and served is §10 step 7's build in `ADI_GRADING_DESIGN_v1.6.md`; the date states of §9 ride whatever that step builds.

## 9. The date role

The role is required of the pipeline's output (GR-82). The Atom Pass emits it on every date it emits; the import's four mappings stand as the roles they name, except `received_date` (PROPOSAL 12). A date fact that arrives with no role, from either path, needs attention at import; the receive marks it, the console shows it amber, and the lock refuses it (GR-75, GR-76). A reviewer who empties the role is not refused; the fact needs attention (GR-82). A reviewer's role must be a live term of the closed list; the console's dropdown cannot produce anything else, so the backend's refusal of an off-list role stands under GR-74.

**The phone's silent default retires.** `ContextLayerBuilder` today reads a missing role as `report` with a print. Under GR-84 and GR-76 that is a second rule set and a silent fallback both. A date fact with no role produces no date edge and is not read as a report date; it stays a fact that needs attention, and the phone's build summary names it as it names an inert custom-kind fact. Nothing is substituted.

**PROPOSAL 12: `received_date`.** The import maps it to `narrativeReference`, which `DATA_MODEL.md` §4.7 reserves for prose mentions. Recommended: the closed list gains `received` (the day a specimen or document was received), walker-ignored like `study`, `admission` and `discharge`, and the import maps `received_date` to it. Rejected: emitting it with no role, which would mark a fact amber on most lab documents; dropping the field, which discards a real date. This changes the list in `DATA_MODEL.md` §4.7 and `src/ingest-vocab.mjs`, opened in §11.

## 10. Open, and where this builds

- **PROPOSAL 13: placement.** The build order of `ADI_GRADING_DESIGN_v1.6.md` §10 (GR-64) has no date step. Recommended: one step of its own, after step 7 (the amber box has to exist before a date can need attention) and before step 8, shipping whole (GR-41): the rule module and its fixture, the two wire fields with the schema bump, the import keeping the vendor's date, the write route recomputing the normalized date on a text correction, the console's live check with the normalized value beside the text, the role required on import, and the phone reading the stored fields with its default retired. The owner places it.
- **The phone's other dates.** `DateParser` is used by the chat digest, the dashboard, the record ingest pipeline, the exporter, the profile date of birth (`DOBNormalizer`, `DOBPartialDate`) and the emergency card. GR-84 says no side keeps its own copy; PROPOSAL 6 leaves these outside the rule set until the owner says which of them are facts. Open.
- **Record dates.** `RecordV2.serviceDate` and `reportDate`, and the chart fallback to them when a lab has no date edge (`ARCHITECTURE.md` §3.2), are system-held dates. Whether they become normalized strings under §3 or stay `Date` values is open; the display rule of §7 applies to them either way.
- **Keeping the three values apart.** §8 recomputes `date_normalized` when a reviewer corrects the text, and GR-92 makes the vendor's value, our normalized value and the confirmed value the scoring signal. Where our import-time normalized value is held once a correction has overwritten it is not settled here. Open, for the owner and for the build step of PROPOSAL 13.
- **The eight roles' walker mapping** stays `DATA_MODEL.md` §4.7's and is not changed here.
- **The fixture** is the contract between the module and the phone's display formatter, and between today's reader and any later one: every format of §4, every partial, every ambiguous case of PROPOSAL 3, every unreadable case, and every display case of §7.

## 11. Conflicts opened for the owner

- **`ARCHITECTURE.md` §3.2, `DATA_MODEL.md` §3.3, sacred rule 8** against §8: a normalized date and the vendor's date stored on the core atom. §8 argues the normalized date is a deterministic derivation like `source_text` and the vendor's date is evidence and scoring signal (GR-92), not a value. Needs the owner's confirmation.
- **`ARCHITECTURE.md` §3.2** says the walker parses each date fact's text at Layer 2 through `DateAtomParser`. Under PROPOSAL 6 the phone reads the stored normalized date and parses nothing; the section's description of emission changes when this builds.
- **`ARCHITECTURE.md` §3.2** and the phone's `.dateAtom(role:date:)` payload hold a Swift `Date`, an instant, which cannot carry a partial without inventing the rest. GR-86 requires PROPOSAL 2's value type.
- **`ARCHITECTURE.md` §3.4.4 and `FHIRDateText`** print an Apple Health date as `yyyy-MM-dd` everywhere a Health record prints a date. GR-88 and GR-91 require the long US form for what a person sees. PROPOSAL 10 splits the AI-facing form from the display form.
- **`DATA_MODEL.md` §4.7's role list** against PROPOSAL 12: a ninth role, `received`.
- **GR-46 and GR-33** (the console holds no list of its own, structure declared by the server): the console running the served rule module is not a list of its own, and the date format list is not per-kind structure; recorded so the two readings are not confused.
- **GR-71 as originally written** (refuse out loud on any input a check depends on) would refuse an unreadable date; GR-79 and GR-80 already superseded that to needs attention, and §4 follows them. No conflict remains; recorded because the older text still reads as a refusal.
- **GR-77** is done by §2; §9 item 30 of the grading design closes against GR-84 through GR-91; GR-92 corrects GR-85.
