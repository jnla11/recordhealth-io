# Record Health: React Migration Scope
Status: exploratory. Nothing in this doc is decided. No owner rulings exist on this topic.
Last verified: 2026-11-12

> Captures a big-picture scoping conversation on 2026-11-12 about moving the phone app from Swift to a shared codebase that could feed iPhone, Android, web, desktop and an intranet version. Written so the topic can be picked up later. Chat project copy only; not filed in any repo.

---

## 1. What the owner said (intent, not rulings)

- Wants, eventually, one master codebase that can branch into iPhone, Android, web and other versions, including a desktop or intranet web version.
- Most app-side work is tabled while groundtruth and the server are proven.
- Has SOC 2 and similar compliance in mind for later.
- Raised the idea that holding firm on tokenized PHI should limit exposure from outside code.

Everything in sections 4 through 9 marked "proposal" is the chat instance's, not the owner's.

---

## 2. Bottom line

- Moving to a shared codebase is a rewrite of the phone app, not a port. No Swift carries over.
- One React Native codebase builds both the iPhone and Android apps. There is no "port back to iOS" step.
- The server side carries over untouched.
- Size judgment: months, not weeks, to bring the iPhone app back to where it is today. Android adds roughly a quarter to a third on top. This is a judgment from line counts, not a measurement.

---

## 3. Size audit (run 2026-11-12)

Counting audit run in the app repo on Sonnet. Read-only, nothing edited or committed. The commit it ran against was not recorded. Files were sorted by their import lines only.

| Bucket | Files | Lines | Share |
|---|---|---|---|
| Plain logic | 479 | 57,781 | 57.7% |
| Screens | 114 | 20,818 | 20.8% |
| Apple-tied | 45 | 21,513 | 21.5% |
| Total (non-test) | 638 | 100,112 | 100% |

- Tests: 236 files, 49,336 lines.
- Share extension: 1 file, 295 lines.
- Outside packages: one (ZIPFoundation).

Plain logic by folder: Domain 22,061; Data 17,674; AI 6,620; Infrastructure 4,131; Presentation 1,752; Services 1,660; PHI 1,434; UI 1,258.

Hard platform pieces (files / lines; 11 files import more than one framework, so these overlap):

| Piece | Files | Lines |
|---|---|---|
| Apple Health | 5 | 3,474 |
| Audio recording | 7 | 3,180 |
| Photo picker | 2 | 1,275 |
| iCloud backup | 1 | 1,157 |
| Speech | 3 | 842 |
| Photo analysis | 3 | 772 |
| Camera scanner | 1 | 641 |
| Subscriptions | 2 | 529 |
| Photo cleanup | 1 | 357 |
| Sign-in | 2 | 260 |
| Push | 1 | 57 |

Sum is at most about 12,500 lines before removing overlap. Also counted as Apple-tied: PDF handling (8 files, 8,455 lines), encryption and hashing (14 files, 9,767 lines), key storage (4 files, 1,698 lines), the date rules runner (1 file, 220 lines).

**Known weakness of the count (inference, not verified).** A file was marked Apple-tied if it imports any one Apple framework, so large files that look mostly like logic were counted whole: `RecordIngestPipeline.swift` (3,857), `RecordsStore.swift` (1,432), `FHIRRecordMapper.swift` (1,376), `CareGraphBuilder.swift` (936), `PatientPackageImporter.swift` (934). The true Apple-only share is likely well under 21%.

**Unresolved flags from the audit session.** Three files matched "generated" wording and were not opened (`MedicalIDBuilder.swift`, `MedicalIDCard.swift`, `AppointmentPrepContext.swift`). Stray `.DS_Store` files sit in four source folders.

---

## 4. What carries over and what does not

**Untouched:** the Worker (ingest, AI passes, PHI tokens), the ADI console, the databases, the design docs, the wire contracts, the shared date rules file (already JavaScript).

**Rebuilt once in the shared language:** the three layers and their encrypted stores, the import queue and recovery, document packages and rebuild, the archive, patient matching, all screens, the test suite.

**Built per platform, never shared:** Apple Health import (iPhone only; Android needs its own source or goes without), camera scanner and photo cleanup, share-in from other apps, on-device transcription, locked-phone file protection and key storage, subscriptions, sign-in, silent push, iCloud backup (no Android twin), the PDF viewer with tap-to-source highlights.

**The real weight:** re-proving device-verified behavior (locked phone, kept unreadable files, interrupted imports resuming) on each platform. Claude Code cannot do that part.

---

## 5. Routes

| Route | What it is | Cost |
|---|---|---|
| Stay in Swift, build other platforms separately later | Nothing on iPhone is redone | Separate codebases kept in step permanently by one person |
| React Native with web and desktop support | One shared brain, shared phone screens, thin shell per platform | Full phone rewrite; native pieces built per platform; many outside packages |
| Shared brain only, native screens per platform | Swift screens could stay | Brain still rewritten; screens built per platform |

**Chat proposal:** the React Native route is the better long-term fit for a solo owner who wants several versions, because the server is already JavaScript and one language would span everything. It is the wrong pick if Android and web stay "someday" for years, or if the iPhone launch date outranks the multi-version goal.

---

## 6. Modular port (proposal)

It can go piece by piece with the iPhone app working throughout. The date rules file is the precedent: shared JavaScript that the Swift app loads and runs.

- **Logic first:** move one logic module at a time into shared code the Swift app calls, then delete the Swift version. Screens and platform pieces move last.
- **Good first candidates:** patient name and birth-date matching, retry timing and import decision rules, the parsers that build lab values, medications and vitals. These are described in `ARCHITECTURE.md` as pure decision logic with their own tests.
- **Does not move in modules:** encrypted storage, locked-phone handling, the platform pieces.
- **Must respect the no-cohabitation principle** (`ARCHITECTURE.md` section 1): each Swift module is deleted when its shared twin lands. No running both as a safety net.
- **Costs:** connector plumbing that is thrown away at the end; two languages to debug during the transition; tangled files such as the import pipeline must be pulled apart before they can move.

---

## 7. Dev ops effects

**Gains:** logic tests run without Xcode or a phone, so Claude Code can run them itself; the hand-kept Swift mirror copies of server lists and rules go away; logic fixes can ship over the air without store review (within Apple's rules, and only when they match the installed native build); one fix lands on every platform; rules can move between server and phone without a rewrite.

**Costs:** hundreds of outside packages instead of one, each needing vetting next to PHI; framework upgrades become a recurring chore; more build machinery and two store release processes; over-the-air updates need an owner ruling on what may ship that way; doubled toolchain overhead during a modular port.

---

## 8. PHI boundary (proposal, would need its own design doc)

Tokenizing limits exposure from outside code only if the shared code never sees real values. Today it does not work that way: tokens protect what goes to the AI, while the phone holds the original documents, the page text and the token lookup, and screens show real names and dates. Outside packages that contain native code run with the app's full access regardless.

A firm boundary would mean:
- The token lookup, encryption key and original documents live in a small owner-written native core with no outside code.
- The shared brain receives tokenized data only.
- Real values are swapped in at the last step before the screen, inside the native core.
- Patient matching stays in the native core or moves to the server.
- Packages containing native code are kept to a short vetted list.

Costs: the native core is built per platform; display, search and sort by name get harder; it is a larger change than a straight port. Side benefit: a web or intranet version could run the brain without holding identities.

---

## 9. Compliance notes (general knowledge, not audit advice)

- SOC 2 audits how the company runs its systems, not the app's language. Either route can pass.
- The biggest lever is where records live. On-device keeps the audited footprint small. Records on the owner's server (a synced web version) bring storage, access, backups and breach response into scope.
- Outside packages need an inventory, vetting, scanning and pinned versions.
- Over-the-air updates need a written release process.
- An intranet version run by an organization puts records on their systems, but enterprise buyers will ask for the owner's SOC 2 first.
- Selling to clinics or health systems would likely make the company a business associate under HIPAA. `ARCHITECTURE.md` states it is not a covered entity today.
- A one-person company must show substitute controls for change review and access. Neither route changes that.

---

## 10. Open decisions (all the owner's)

1. Whether to pursue a shared codebase at all, and when. Natural decision point: when app-side work resumes.
2. Where records live for a web version: in the browser, or on a server. This also decides whether devices sync.
3. Whether to adopt the firm tokenized boundary in section 8.
4. Which route in section 5.
5. All at once or modular (section 6).
6. What "intranet version" means as a product: who runs it and who holds the records.

Proposed order: decisions 2 and 3 first, because they carry the privacy and compliance weight; the route follows from them.

---

## 11. Timing

- The rewrite is cheapest before launch, while everything on the phone is dev data and can be wiped.
- With app work tabled, the cost is not growing much. It grows again with each phone-side sprint in Swift.
- Until a decision is made, new rules that could live on the server or in the shared rules file cost nothing extra to place there (proposal).

---

## 12. Suggested next steps when picked up

1. Audit the 45 Apple-tied files to count how many lines in each actually touch an Apple framework. Replaces the inference in section 3.
2. Check what Android offers in place of Apple Health clinical records, on-device transcription and device backup.
3. Draft a design doc for the tokenized boundary if decision 3 is yes.
4. Trial one module from section 6 as a proof before committing to any route.

---

## Sources

- React Native 0.86 release notes (latest stable as of June 2026): https://reactnative.dev/blog/2026/06/11/react-native-0.86
- The State of React Native in 2026: https://ditto.com/blog/the-state-of-react-native-in-2026
- `ARCHITECTURE.md` (Last verified 2026-11-10) for all statements about the current app.
