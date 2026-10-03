# DICTIONARY_TEXT_DRAFT.md — Dictionary text (INGEST_VOCABULARY_DESIGN §12.8)

Status: historical. Published as dictionary version 7 (2026-10-02). From now on the dictionary is the text's one home; this file is not edited again. A later text change is a dictionary edit, approved by the owner, published as the next version (INGEST_VOCABULARY_DESIGN §12.8). Approved by the owner 2026-10-02, except the reliability text, which stayed blank.
Last verified: 2026-10-02

**Owner rulings applied (2026-10-01):** the plain name of `provider` is "Provider"; the plain name of `labValue` is "Lab result"; the plain name of `encounter` is "Visit"; the plain names and descriptions for reliability are left blank until the reliability audit is ruled on. The rulings of 2026-10-02 below approve the rest, with the changes they name.

**Owner rulings applied (2026-10-02):** the text below is approved. The kind groups are ten, with the codes given, and `encounter` sits in a new Visits group; the owner rejected the console's grouping for Visit (INGEST_VOCABULARY_DESIGN OR-34). `provider` and `providerContact` and `labValue` have the descriptions below. Section kinds get three display groups (OR-35). Groups are display-only (OR-36). The subtype, PHI type, date role and column role rulings are in section 4 (OR-37 to OR-39). Reliability stays blank (OR-30). The matching "unsure" notes are removed; the ones left are about terms the rulings did not touch.

This is the text drafted for INGEST_VOCABULARY_DESIGN v8 §12 step D1: a plain name, a one-line description, a one-line example and an order for each term. The owner approved it (2026-10-02) and it was loaded as dictionary version 7 (D1, `83dbf4e`).

**Sources drafted from (all read only, 2026-10-01):**

- The staging dictionary: `vocabulary_terms` on `ADI_STAGING`, dictionary version 6. Live terms only. The two retired kinds (`reportDate`, `visitDate`) and the retired `rh.edge.kind` and `rh.edge.source` terms are left out.
- `recordhealth-api/adi-console/vocabulary.mjs`: `KIND_GROUPS` and `KIND_GROUP_HINT`.
- `recordhealth-api/src/pipeline-shared.mjs`: `ATOM_PASS_GUIDANCE`, the per-kind hints, and the certainty and reliability definitions.
- `recordhealth-api/src/result-schema.mjs`: `SECTION_KINDS`.
- `recordhealth-api/src/index.js`: the unused section prompts, which hold the one-line section-kind descriptions.
- `RecordHealth_App`: `AtomKind+Display.swift` and `SectionKindMapping.swift`. The phone's `DateRole.swift`, `ClassificationCertainty.swift`, `ReliabilityTier.swift`, `PHIType.swift`, `AtomSubtype.swift`, `CoveragePayload.swift` and `FHIRPHIClassifier.swift` were read only where a term had no description in the named sources.

**Rules for the text.** Plain language a reviewer who is not a clinician can follow. Every example is generic and invented. None comes from a real document, and none carries a real name, date of birth, address or ID. Phone numbers use the fictional 555-01xx range. Nothing here is medical advice. A meaning the sources do not support is marked, never invented.

**Plain names are singular.** A term names one fact ("Medication"). The phone's current labels are plural list headings ("Medications"), so a list heading is the app's own choice and not a dictionary field. This applies throughout and is not repeated under each table.

---

## 1. Kind groups

Namespace `rh.atom.kind-group`. The ten groups of INGEST_VOCABULARY_DESIGN §12.3 (OR-34), in that order. Where a code matches a console `KIND_GROUPS` id it is kept; `visits` is new, `conditions` replaces `condition` and `patient_details` replaces `patient`, so the console's switch to the dictionary (C1) reads the new codes. Groups are display-only: the AI is not shown them (OR-36).

| Order | Code | Plain name | Description | Example of a fact in this group |
|---|---|---|---|---|
| 1 | `observations` | Observations | Things measured or seen: lab tests, vital signs and exam or imaging findings. | Glucose 95 mg/dL |
| 2 | `visits` | Visits | What type of visit this was: an office visit, an ER visit, a hospital stay or a telehealth appointment. | Office visit |
| 3 | `conditions` | Conditions | Symptoms the patient reports, ongoing or past conditions, and diagnoses. | Diagnosis: seasonal allergies |
| 4 | `treatment` | Treatments & care | What is done or planned for the patient: medicines, procedures, vaccines, plans, referrals and devices. | Amoxicillin 500 mg capsule |
| 5 | `history` | Patient history | Background that shapes care: allergies, family health history and social history. | Allergy: penicillin |
| 6 | `care_team` | People & places | The clinicians and organizations named in the document, and how to reach them. | Ordering physician: Dr. A. Sample |
| 7 | `temporal` | Document dates | Dates in the document and what each date is for. | Date of service: 03/15/2024 |
| 8 | `administrative` | Administrative | Paperwork facts: insurance, document numbers and the record summary. | Accession number: AB-000000 |
| 9 | `patient_details` | Patient details | The patient's identity, ID numbers and contact details, plus their guardian and emergency contact. | Patient phone: 555-0100 |
| 10 | `other` | Other | Facts that fit no other group. | A line the reader could not place |

**Recorded:** the owner rejected the console's grouping for Visit (`encounter` under Administrative) and ruled the Visits group above. The code-collision note (three group codes shared with kinds and section kinds) and the phone-grouping note are removed: the new codes settle the first, and the phone's `KindCategory` is retired.

---

## 2. Kinds

Namespace `rh.atom.kind`: all 31 live terms. The order within each group follows the order of the console's `KIND_GROUP_HINT`, with `encounter` as the one kind in Visits. Today the console sorts kinds alphabetically within a group and the phone uses its own `displayOrder`. For the kinds both cover, the phone's relative order matches this one.

| Group | Order | Code | Plain name | Description | Example |
|---|---|---|---|---|---|
| Observations | 1 | `labValue` | Lab result | One lab test and its result: value, units and normal range. | Sodium 140 mmol/L |
| Observations | 2 | `labPanel` | Lab panel | A heading that names a group of lab tests run together. It is not a single test result. | Basic Metabolic Panel |
| Observations | 3 | `vitalSign` | Vital sign | A basic body measurement such as blood pressure, heart rate, temperature or oxygen level. | Blood pressure |
| Observations | 4 | `finding` | Finding | Something a clinician observed during an exam, on an image or while reading a lab result. A normal finding is still a finding, not a condition. | Lungs clear on both sides |
| Visits | 1 | `encounter` | Visit | The type of visit the document records. | Office visit |
| Conditions | 1 | `symptom` | Symptom | Something the patient comes in with or describes feeling, such as the main complaint. A symptom the patient denies is not recorded. | Patient presents with a sore throat |
| Conditions | 2 | `condition` | Condition | An ongoing or past health problem of this patient, often listed under medical history. | History of asthma |
| Conditions | 3 | `diagnosis` | Diagnosis | A clinician's formal conclusion from this visit, usually under Assessment or Impression. | Assessment: ear infection |
| Treatments & care | 1 | `medication` | Medication | A medicine by name, brand or generic. A dosage form alone, such as "tablet", is not a medication. | Ibuprofen 200 mg |
| Treatments & care | 2 | `procedure` | Procedure | A surgery or other hands-on treatment that was performed. | Knee arthroscopy |
| Treatments & care | 3 | `immunization` | Vaccine | A vaccine the patient received. | Flu vaccine |
| Treatments & care | 4 | `carePlan` | Care plan item | A planned step or goal of the patient's care. | Physical therapy twice a week |
| Treatments & care | 5 | `referral` | Referral or order | A service requested for the patient, such as a consult or a scan. | MRI of the lower back |
| Treatments & care | 6 | `device` | Medical device | A medical device the patient has or uses, implanted or external. | Insulin pump |
| Patient history | 1 | `allergy` | Allergy | Something the patient is allergic to: a medicine, a food or something in the environment. "No known allergies" counts too. | No known drug allergies |
| Patient history | 2 | `familyHistory` | Family history | A health problem of a family member, not of the patient. | Mother: high blood pressure |
| Patient history | 3 | `socialHistory` | Social history | Lifestyle facts relevant to health, such as smoking or alcohol use. | Former smoker |
| People & places | 1 | `provider` | Provider | A doctor, nurse practitioner or other provider who treats the patient, orders tests, reads results or signs the document. Lab staff are not included. | Dr. A. Sample, MD |
| People & places | 2 | `organization` | Organization | A hospital, clinic, lab, imaging center or insurer named in the document. A brand-name medicine is never an organization. | Example County Hospital |
| People & places | 3 | `providerContact` | Provider or organization contact | A phone, fax, email or address for a provider or an organization. | Clinic fax: 555-0199 |
| Document dates | 1 | `dateAtom` | Date | A date in the document. Its date role says what the date is for (see section 4). A date of birth is a patient detail, not a date. | Collected: 03/15/2024 |
| Administrative | 1 | `coverage` | Insurance coverage | Insurance plan details: the payer, the plan type and its dates. | Plan: Example Health PPO |
| Administrative | 2 | `documentReference` | Document number or type | A number or label that identifies the document or the order, such as an accession number, order number or document type. | Order #000000 |
| Administrative | 3 | `recordSummary` | Record summary | A short summary of the whole record, written by the system, not read from the document. | Summary: routine lab panel, all results in range |
| Patient details | 1 | `patientDemographic` | Patient demographic | A personal detail about the patient: name, date of birth, sex, age, race, ethnicity, pronouns or blood type. | Sex: female |
| Patient details | 2 | `patientIdentifier` | Patient identifier | A number that identifies the patient, such as a medical record number, member number or Social Security number. | MRN: 0000000 |
| Patient details | 3 | `patientContact` | Patient contact | The patient's phone, email or fax. | Phone: 555-0100 |
| Patient details | 4 | `patientAddress` | Patient address | The patient's street, city, state or ZIP code. | 12 Example Street |
| Patient details | 5 | `guardianInfo` | Guardian | The patient's guardian: name, relationship or contact details. | Guardian: parent |
| Patient details | 6 | `emergencyContact` | Emergency contact | The person to call in an emergency: name, relationship or contact details. | Emergency contact: spouse, 555-0142 |
| Other | 1 | `uncategorized` | Other | A fact that fits no other kind. | A stamp reading "Copy" |

**Unsure or disagreeing:**

- **`coverage`.** Approved as drafted (2026-10-02). Recorded for the build: nothing produces it today (neither the console nor any prompt describes it, and no section's guidance offers it to the extractor). ROADMAP `F-NEW-XG` teaches the AI read to produce it.
- **`recordSummary`.** Synthesized, not extracted (result-schema, `ATOM_SYNTHESIZED`). It sits under Administrative in the console and the phone. The example is invented.

**Ruled and removed from this list (2026-10-02):** `labValue` "Lab result" (description and example above); `provider` "Provider" and `providerContact` "Provider or organization contact" (descriptions above); `encounter` "Visit", in the new Visits group; `coverage`, `vitalSign` and `immunization` as drafted.

---

## 3. Section kinds

Namespace `rh.section.kind`: all 15 values of `SECTION_KINDS`. The order is the phone's `SectionKindMapping.all`, which matches the order of the section prompts. Descriptions come from the section prompts in `src/index.js`, put into plain words.

| Order | Code | Plain name | Description | Example of such a section in a document |
|---|---|---|---|---|
| 1 | `patient` | Patient block | The block that says who the document is about: name, date of birth, record number and address. | A box at the top labeled "Patient Information" |
| 2 | `organization` | Organization block | A block about a hospital, clinic, lab or imaging center: its name, address and phone. | "Performing lab: Example Labs, 1 Main Road, 555-0123" |
| 3 | `practitioner_role` | Clinician block | A block about one clinician: name, role, specialty, credentials and, when stated, where they work. | "Ordering physician: Dr. A. Sample, Internal Medicine" |
| 4 | `service_request` | Order or referral | An order or referral for a service not yet performed: who ordered it, when, and what was ordered. | "Order: chest X-ray, ordered by Dr. A. Sample on 03/15/2024" |
| 5 | `diagnostic_report` | Diagnostic report | A complete test report, such as a lab panel, imaging study or pathology report, that holds its results together. | A "Complete Blood Count" report with its table of results |
| 6 | `observation` | Single result | One measurement or finding, such as one lab result row, a vital-signs row or one imaging finding. Usually sits inside a diagnostic report. | The row "Glucose 95 mg/dL 70-99" |
| 7 | `medication_request` | Prescription | A prescription or medication order: the medicine's name, dose, how it is taken and how often. | "Ibuprofen 200 mg, by mouth, every 6 hours as needed" |
| 8 | `provenance` | Signature block | The signing block: who finalized the document, when, and on whose authority. | "Electronically signed by Dr. A. Sample on 03/18/2024" |
| 9 | `narrative` | Clinical notes | Free-text notes by a clinician, such as the history of the illness, exam, assessment or plan. | A paragraph under "History of Present Illness" |
| 10 | `impression` | Impression or conclusion | A section headed Impression, Conclusion or Interpretation that states the clinician's summary. | "Impression: no acute findings" |
| 11 | `table_headers` | Table header row | The row of column titles at the top of a table, apart from the data rows below it. | "Test   Result   Units   Reference" |
| 12 | `header` | Page header | The banner at the top of a page. | A clinic logo and name across the top of each page |
| 13 | `footer` | Page footer | The strip at the bottom of a page: page number, document stamp or legal text. | "Page 2 of 3 — Confidential" |
| 14 | `whitespace` | Blank area | An area of the page with no text. | An empty band between two sections |
| 15 | `unknown` | Unrecognized section | A part of the page that matches none of the other section kinds. | A block of scanner noise or an unreadable stamp |

**Section kind groups (approved 2026-10-02, OR-35).** Namespace `rh.section.kind-group`: three display groups, in this order. They are display-only (OR-36). Each group has an example (owner-approved 2026-10-02).

| Order | Code | Plain name | Description | Example of a section in this group | Members |
|---|---|---|---|---|---|
| 1 | `information_blocks` | Information blocks | Sections that describe one thing, such as a person, a place, an order or a report. | Patient Information box | `patient`, `organization`, `practitioner_role`, `service_request`, `diagnostic_report`, `observation`, `medication_request`, `provenance` |
| 2 | `clinical_text` | Clinical text | Free-text notes and conclusions written by a clinician. | History of Present Illness | `narrative`, `impression` |
| 3 | `page_layout` | Page layout | Parts of the page layout with no clinical content. | Page 2 of 3 | `table_headers`, `header`, `footer`, `whitespace`, `unknown` |

**Unsure or disagreeing:**

- **`observation` versus the classifier.** The live section classifier is told never to assign `observation`, `table_headers` or `whitespace`, because they are set from the page's structure (table detection), not its content. The meaning is the same in both places. Only how each is assigned differs, so this is noted, not marked unsure.
- **`unknown` example.** The sources describe it only as "not matching any of the above". The example is invented.

---

## 4. Plain names for every other live term

These sections now carry plain names, descriptions and examples where ruled. Where a source gives a meaning that bears on the name, it is noted under the table.

### 4a. Subtypes (`rh.atom.subtype`, 36)

Code and plain name; three also carry a description (owner ruling 2026-10-02, OR-37).

| Code | Plain name | Description |
|---|---|---|
| `accessionNumber` | Accession number | |
| `age` | Age | |
| `billingAccountNumber` | Billing account number | The patient's account number with the provider's billing office. |
| `bloodType` | Blood type | |
| `city` | City | |
| `credentials` | Credentials | |
| `dateOfBirth` | Date of birth | |
| `departmentName` | Department name | |
| `documentType` | Document type | |
| `email` | Email | |
| `encounterNumber` | Visit number | |
| `ethnicity` | Ethnicity | |
| `facilityName` | Facility name | |
| `fax` | Fax | |
| `genderIdentity` | Gender identity | |
| `memberNumber` | Member number | The patient's own ID on the insurance plan. |
| `mrn` | Medical record number | |
| `name` | Name | |
| `npi` | National Provider Identifier (NPI) | |
| `orderNumber` | Order number | |
| `phone` | Phone | |
| `pronouns` | Pronouns | |
| `race` | Race | |
| `relationship` | Relationship | |
| `role` | Role | |
| `sex` | Sex | |
| `sexAssignedAtBirth` | Sex assigned at birth | |
| `specialty` | Specialty | |
| `ssn` | Social Security number | |
| `ssnLastFour` | Last four digits of SSN | |
| `state` | State | |
| `street` | Street | |
| `subscriberNumber` | Subscriber number | The insurance policy holder's ID. |
| `unspecifiedContact` | Other contact | |
| `unspecifiedIdentifier` | Other identifier | |
| `zip` | ZIP code | |

**Ruled (2026-10-02, OR-37), retired from the list above:** `patientName` and `facility` (the vendor adapter translates its spellings to `name` and `facilityName`; ROADMAP `F-NEW-XH`); `address` (the AI read emits `street`, `city`, `state` and `zip`; `F-NEW-XI`); `formCode` and `barcode` (no such elements in the FHIR R4 DocumentReference, and nothing ever produced them; `F-NEW-XJ`). The terms stay in the dictionary until those builds land.

**Unsure or disagreeing:**

- **`role`.** Open vocabulary for clinicians: the extractor copies the role as written ("Ordering Physician"), so many off-list values are expected (owner ruling 2026-08-21). The plain name names the term, not its values.
- **`encounterNumber`.** "Visit number" is proposed because "encounter" is clinical jargon. The code is unchanged.

### 4b. Date roles (`rh.atom.date-role`, 9)

| Code | Plain name | Description | Example |
|---|---|---|---|
| `admission` | Admission date | | |
| `collection` | Sample collection date | | |
| `discharge` | Discharge date | | |
| `narrativeReference` | Date mentioned in notes | | |
| `received` | Received date | A date the document labels as the day a specimen or document was received. | Received: 03/16/2024 |
| `report` | Report date | | |
| `service` | Date of service | A date the document labels as the date of service, such as 'DOS' or 'Service date'. | DOS: 03/15/2024 |
| `study` | Imaging date | | |
| `visit` | Visit date | A date the document labels as the visit or appointment date. | Visit date: 03/15/2024 |

**Ruled (2026-10-02, OR-39):** `service` and `visit` are both kept. A date role records the printed label (labeled dates classify by label), not what the date means downstream. `received` is new (ruled earlier as GR-105) and enters the dictionary with the date work.

**Unsure or disagreeing:**

- **`study`.** The prompt says "imaging study dates" and the phone "imaging study start". "Imaging date" follows both.

### 4c. PHI types (`rh.phi.type`, 36)

Two already carry a plain name in the dictionary (`patientFax` "Patient fax", `providerEmail` "Provider email"). They are kept as they are, and the rest follow the same pattern. Descriptions are from the owner's ruling of 2026-10-02 (OR-38).

| Code | Plain name | Description |
|---|---|---|
| `accessionNumber` | Accession number | |
| `accountNumber` | Account number | |
| `biometric` | Biometric identifier | A biometric identifier, such as a fingerprint or voiceprint. |
| `dateOfAdmission` | Admission date | |
| `dateOfDischarge` | Discharge date | |
| `dateOfReport` | Report date | |
| `dateOfService` | Date of service | |
| `dateSigned` | Date signed | |
| `deviceIdentifier` | Device identifier | A device identifier or serial number, such as an implant's serial number. |
| `dob` | Date of birth | |
| `emergencyContactName` | Emergency contact name | |
| `facilityAddress` | Facility address | |
| `facilityName` | Facility name | |
| `guardianName` | Guardian name | |
| `ipAddress` | IP address | An internet (IP) address. |
| `licenseNumber` | License number | A certificate or license number, such as a driver's or professional license. |
| `memberNumber` | Member number | |
| `mrn` | Medical record number | |
| `otherIdentifier` | Other identifier | An identifier that fits no other PHI type. |
| `patientAddress` | Patient address | |
| `patientEmail` | Patient email | |
| `patientFax` | Patient fax | |
| `patientName` | Patient name | |
| `patientPhone` | Patient phone | |
| `photograph` | Photograph | A full-face photograph or comparable image. |
| `providerAddress` | Provider address | |
| `providerEmail` | Provider email | |
| `providerFax` | Provider fax | |
| `providerName` | Provider name | |
| `providerPhone` | Provider phone | |
| `ssn` | Social Security number | |
| `ssnLastFour` | Last four digits of SSN | |
| `staffName` | Staff name | |
| `urlOrHandle` | Web address or online handle | A web address (URL) or online username. |
| *(code is the build's)* | Unrecognized PHI type | The AI marked this as PHI but gave a type the system doesn't recognize. Pick the right PHI type. Shows the amber needs-attention box. |
| *(code is the build's)* | Vehicle identifier | A vehicle identifier or serial number, including a license plate. |

The last two are new (OR-38; ROADMAP `F-NEW-XK`). The `photograph` description is the HIPAA Safe Harbor wording (hhs.gov).

**Unsure or disagreeing:**

- **"Provider" here and in section 2.** The PHI type names keep "Provider" to match the two plain names already in the dictionary (`providerEmail`) and the `provider` kind's plain name.
- **`subscriberNumber` and `memberNumber`.** Distinct as PHI types (ruled 2026-10-02). The phone's `FHIRPHIClassifier` still collapses the first into the second; ROADMAP `F-NEW-VE`.

### 4d. Classification certainty (`rh.certainty`, 3)

| Code | Plain name |
|---|---|
| `specific` | Sure of kind and detail |
| `parent_only` | Sure of kind only |
| `low_confidence` | Unsure of kind |

The sources agree. The Worker prompt says `specific` is "confident in kind+subtype", `parent_only` "confident in kind, uncertain subtype" and `low_confidence` "uncertain even at parent". The phone's `ClassificationCertainty.swift` says the same.

### 4e. Reliability (`rh.reliability`, 3)

| Code | Plain name |
|---|---|
| `high` | *(blank, pending the reliability audit)* |
| `medium` | *(blank, pending the reliability audit)* |
| `low` | *(blank, pending the reliability audit)* |

**Unsure or disagreeing. The sources give two different meanings:**

- **The Worker prompt** (`pipeline-shared.mjs`, cross-cutting rules) defines reliability as how exactly the pointed-at words capture the value. `high`: the word range captures exactly the value. `medium`: the range includes a label or punctuation that could not be left out. `low`: unsure which words carry the value.
- **The phone** (`ReliabilityTier.swift`) defines it as confidence in the date attached to a fact. `high`: the date is in the same row or section. `medium`: the document's visit date was inherited. `low`: the date was inferred with real doubt. The phone also has a fourth value, `unverified`, that the dictionary does not carry.

The extractor writes the field under the Worker's meaning today, so the phone's comment is probably stale. **Owner ruling 2026-10-01: the plain names and descriptions are left blank until the reliability audit is ruled on.** (The draft had proposed the neutral names High, Medium and Low.) The phone's `unverified` is a P1 question: §12.10 already has `ReliabilityTier` stop silently dropping unknown values.

### 4f. Column roles (`rh.column-role`, 5)

| Code | Plain name | Description |
|---|---|---|
| `analyte_name` | Test name | |
| `value` | Result | |
| `units` | Units | |
| `reference_range` | Normal range | |
| `flag` | Result flag | The lab's own marker on a result, as printed, such as H, L, Critical or Abnormal. |

These are the five roles the LlamaExtract adapter gives the cells of a lab table (`ingest-vocab.mjs`, `COLUMN_ROLES`). The `flag` text follows the lab pill vocabulary in `DESIGN_SYSTEM.md` (ruled 2026-10-02).

---

## Counts

| Section | Terms |
|---|---|
| 1. Kind groups | 10 |
| 2. Kinds | 31 |
| 3. Section kinds | 15 (plus 3 section-kind groups) |
| 4. Plain names | 92 once the retirements land: subtypes 36, date roles 9, PHI types 36, certainty 3, reliability 3, column roles 5 |

Live terms in the staging dictionary (version 6) when this was drafted: 125, that is 31 kinds plus 94 others. The 2026-10-02 rulings retire 5 subtypes and add 1 date role and 2 PHI types, so 92 after the builds. The kind groups, the section-kind groups and the section kinds are new terms proposed by D1.
