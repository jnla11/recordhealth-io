# DICTIONARY_TEXT_DRAFT.md — Dictionary text for owner approval (INGEST_VOCABULARY_DESIGN §12.8)

Status: living, DRAFT for owner approval. Nothing here has entered the dictionary; it goes to staging and then production only after approval (OR-28)
Last verified: 2026-10-01

**Owner rulings applied (2026-10-01):** the plain name of `provider` is "Provider"; the plain name of `labValue` is "Lab result"; the plain name of `encounter` is "Visit"; the plain names and descriptions for reliability are left blank until the reliability audit is ruled on. Everything else below is still a draft.

This is the text drafted for INGEST_VOCABULARY_DESIGN v8 §12 step D1: a plain name, a one-line description, a one-line example and an order for each term. The owner approves it before anything is published. Nothing is built.

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

Proposed namespace: `rh.atom.kind-group`. The nine groups of §12.3, in that order. The codes are the console's current `KIND_GROUPS` ids, kept as they are so the console's switch to the dictionary (C1) changes no id.

| Order | Code | Plain name | Description | Example of a fact in this group |
|---|---|---|---|---|
| 1 | `observation` | Observations | Things measured or seen: lab tests, vital signs and exam or imaging findings. | Glucose 95 mg/dL |
| 2 | `condition` | Clinical findings | Health problems: what the patient reports feeling, ongoing conditions and diagnoses. | Diagnosis: seasonal allergies |
| 3 | `treatment` | Treatments & care | What is done or planned for the patient: medicines, procedures, vaccines, plans, referrals and devices. | Amoxicillin 500 mg capsule |
| 4 | `history` | Patient history | Background that shapes care: allergies, family health history and social history. | Allergy: penicillin |
| 5 | `care_team` | People & places | The clinicians and organisations named in the document, and how to reach them. | Ordering physician: Dr. A. Sample |
| 6 | `temporal` | Document dates | Dates in the document and what each date is for. | Date of service: 03/15/2024 |
| 7 | `administrative` | Administrative | Paperwork facts: insurance, the type of visit, document numbers and the record summary. | Accession number: AB-000000 |
| 8 | `patient` | Patient details | Who the document is about: identity, identifiers, contact details and the people to call for them. | Patient phone: 555-0100 |
| 9 | `other` | Other | Facts that fit no other group. | A line the reader could not place |

**Unsure or disagreeing:**

- **Code collisions across namespaces.** Three proposed group codes are also codes in other namespaces: `condition` (a kind), `observation` (a section kind) and `patient` (a section kind). A namespace keeps them apart (§5.3), so they are allowed. They will read confusingly in logs and tests, though. Renaming them (for example `clinical_finding`, `measurement`, `patient_details`) is a choice for the owner, not drafted here.
- **The phone groups differently.** The phone's six-group `KindCategory` (retired by §12.3) puts `encounter` and `finding` under Clinical, and `referral` and `carePlan` under Administrative. The console puts `encounter` under Administrative, `finding` under Observations, and `referral` and `carePlan` under Treatments & care. This draft follows the console, as §12.3 says to start from its assignment.

---

## 2. Kinds

Namespace `rh.atom.kind`: all 31 live terms. The order within each group follows the order of the console's `KIND_GROUP_HINT`. Today the console sorts kinds alphabetically within a group and the phone uses its own `displayOrder`. For the kinds both cover, the phone's relative order matches this one.

| Group | Order | Code | Plain name | Description | Example |
|---|---|---|---|---|---|
| Observations | 1 | `labValue` | Lab result | One lab test named in the document, such as a blood or urine test. | Sodium |
| Observations | 2 | `labPanel` | Lab panel | A heading that names a group of lab tests run together. It is not a single test result. | Basic Metabolic Panel |
| Observations | 3 | `vitalSign` | Vital sign | A basic body measurement such as blood pressure, heart rate, temperature or oxygen level. | Blood pressure |
| Observations | 4 | `finding` | Finding | Something a clinician observed in an exam, on an image or in reading a lab result. A normal finding is still a finding, not a condition. | Lungs clear on both sides |
| Clinical findings | 1 | `symptom` | Symptom | Something the patient comes in with or describes feeling, such as the main complaint. A symptom the patient denies is not recorded. | Patient presents with a sore throat |
| Clinical findings | 2 | `condition` | Condition | An ongoing or past health problem of this patient, often listed under medical history. | History of asthma |
| Clinical findings | 3 | `diagnosis` | Diagnosis | A clinician's formal conclusion from this visit, usually under Assessment or Impression. | Assessment: ear infection |
| Treatments & care | 1 | `medication` | Medication | A medicine by name, brand or generic. A dosage form alone, such as "tablet", is not a medication. | Ibuprofen 200 mg |
| Treatments & care | 2 | `procedure` | Procedure | A surgery or other hands-on treatment that was performed. | Knee arthroscopy |
| Treatments & care | 3 | `immunization` | Vaccine | A vaccine the patient received. | Flu vaccine |
| Treatments & care | 4 | `carePlan` | Care plan item | A planned step or goal of the patient's care. | Physical therapy twice a week |
| Treatments & care | 5 | `referral` | Referral or order | A service requested for the patient, such as a consult or a scan. | MRI of the lower back |
| Treatments & care | 6 | `device` | Medical device | A medical device the patient has or uses, implanted or external. | Insulin pump |
| Patient history | 1 | `allergy` | Allergy | Something the patient is allergic to: a medicine, a food or something in the environment. "No known allergies" counts too. | No known drug allergies |
| Patient history | 2 | `familyHistory` | Family history | A health problem of a family member, not of the patient. | Mother: high blood pressure |
| Patient history | 3 | `socialHistory` | Social history | Lifestyle facts relevant to health, such as smoking or alcohol use. | Former smoker |
| People & places | 1 | `provider` | Provider | A treating, ordering, interpreting or signing clinician named in the document. Lab technicians and other staff are not included. | Dr. A. Sample, MD |
| People & places | 2 | `organization` | Organization | A hospital, clinic, lab, imaging centre or insurer named in the document. A brand-name medicine is never an organization. | Example County Hospital |
| People & places | 3 | `providerContact` | Clinician or organization contact | A phone, fax, email or address for a clinician or an organization. | Clinic fax: 555-0199 |
| Document dates | 1 | `dateAtom` | Date | A date in the document. Its date role says what the date is for (see section 4). A date of birth is a patient detail, not a date. | Collected: 03/15/2024 |
| Administrative | 1 | `coverage` | Insurance coverage | Insurance plan details: the payer, the plan type and its dates. **Unsure, see below.** | Plan: Example Health PPO |
| Administrative | 2 | `encounter` | Visit | The type of visit the document records. | Office visit |
| Administrative | 3 | `documentReference` | Document number or type | A number or label that identifies the document or the order, such as an accession number, order number or document type. | Order #000000 |
| Administrative | 4 | `recordSummary` | Record summary | A short summary of the whole record, written by the system, not read from the document. | Summary: routine lab panel, all results in range |
| Patient details | 1 | `patientDemographic` | Patient demographic | A personal detail about the patient: name, date of birth, sex, age, race, ethnicity, pronouns or blood type. | Sex: female |
| Patient details | 2 | `patientIdentifier` | Patient identifier | A number that identifies the patient, such as a medical record number, member number or Social Security number. | MRN: 0000000 |
| Patient details | 3 | `patientContact` | Patient contact | The patient's phone, email or fax. | Phone: 555-0100 |
| Patient details | 4 | `patientAddress` | Patient address | The patient's street, city, state or ZIP code. | 12 Example Street |
| Patient details | 5 | `guardianInfo` | Guardian | The patient's guardian: name, relationship or contact details. | Guardian: parent |
| Patient details | 6 | `emergencyContact` | Emergency contact | The person to call in an emergency: name, relationship or contact details. | Emergency contact: spouse, 555-0142 |
| Other | 1 | `uncategorized` | Other | A fact that fits no other kind. | A stamp reading "Copy" |

**Unsure or disagreeing:**

- **`coverage`.** Neither the console nor any prompt describes it, and no section's guidance offers it to the extractor, so nothing produces it today. The description comes from the phone's `CoveragePayload` (payer name, plan type, group number, subscriber ID, start and end dates) and its PHI classifier comment ("plan-level metadata"). Whether this is the meaning the owner intends, and whether the kind should stay, is for the owner.
- **`labValue`.** The name says "value", but the prompt hint is "lab test name spans (e.g. Glucose, Sodium)": the fact points at the test's name, and the result, units and range arrive as table columns (the column roles, section 4). This draft described the test, not the number, and proposed "Lab test". **Owner ruling 2026-10-01: the plain name is "Lab result".** The description still describes the test, not the number, and may need rewording to match the name.
- **`vitalSign`, `immunization`.** The same pattern: the hints say "vital type spans" and "vaccine name spans". The descriptions follow the hints (the type of measurement, the vaccine's name).
- **`encounter`.** The hint says "visit type (Office Visit, ED Visit, Telehealth, etc.)", and the description says that. The draft proposed "Visit type". **Owner ruling 2026-10-01: the plain name is "Visit".** The description still says "the type of visit", which matches the hint.
- **`provider` plain name.** The code says provider. The section prompts say "clinician" and "physician". The draft proposed "Clinician". **Owner ruling 2026-10-01: the plain name is "Provider".** The description still says "clinician", and `providerContact` is still named "Clinician or organization contact". Whether those follow is not ruled.
- **`providerContact`.** The kind's own hint covers only phone, fax and email, but its subtype list also includes `address`, and in the organization section it is a contact "associated with the organization". The description and plain name cover both clinician and organization, and address. The phone's label "Provider Contacts" leaves organizations out.
- **`recordSummary`.** Synthesized, not extracted (result-schema, `ATOM_SYNTHESIZED`). It sits under Administrative in the console and the phone. The example is invented.

---

## 3. Section kinds

Namespace `rh.section.kind`: all 15 values of `SECTION_KINDS`. The order is the phone's `SectionKindMapping.all`, which matches the order of the section prompts. Descriptions come from the section prompts in `src/index.js`, put into plain words.

| Order | Code | Plain name | Description | Example of such a section in a document |
|---|---|---|---|---|
| 1 | `patient` | Patient block | The block that says who the document is about: name, date of birth, record number and address. | A box at the top labelled "Patient Information" |
| 2 | `organization` | Organization block | A block about a hospital, clinic, lab or imaging centre: its name, address and phone. | "Performing lab: Example Labs, 1 Main Road, 555-0123" |
| 3 | `practitioner_role` | Clinician block | A block about one clinician: name, role, specialty, credentials and, when stated, where they work. | "Ordering physician: Dr. A. Sample, Internal Medicine" |
| 4 | `service_request` | Order or referral | An order or referral for a service not yet performed: who ordered it, when, and what was ordered. | "Order: chest X-ray, ordered by Dr. A. Sample on 03/15/2024" |
| 5 | `diagnostic_report` | Diagnostic report | A complete test report, such as a lab panel, imaging study or pathology report, that holds its results together. | A "Complete Blood Count" report with its table of results |
| 6 | `observation` | Single result | One measurement or finding, such as one lab result row, a vital-signs row or one imaging finding. Usually sits inside a diagnostic report. | The row "Glucose 95 mg/dL 70-99" |
| 7 | `medication_request` | Prescription | A prescription or medication order: the medicine's name, dose, how it is taken and how often. | "Ibuprofen 200 mg, by mouth, every 6 hours as needed" |
| 8 | `provenance` | Signature block | The signing block: who finalised the document, when, and on whose authority. | "Electronically signed by Dr. A. Sample on 03/18/2024" |
| 9 | `narrative` | Clinical notes | Free-text notes by a clinician, such as the history of the illness, exam, assessment or plan. | A paragraph under "History of Present Illness" |
| 10 | `impression` | Impression or conclusion | A section headed Impression, Conclusion or Interpretation that states the clinician's summary. | "Impression: no acute findings" |
| 11 | `table_headers` | Table header row | The row of column titles at the top of a table, apart from the data rows below it. | "Test   Result   Units   Reference" |
| 12 | `header` | Page header | The banner at the top of a page. | A clinic logo and name across the top of each page |
| 13 | `footer` | Page footer | The strip at the bottom of a page: page number, document stamp or legal text. | "Page 2 of 3 — Confidential" |
| 14 | `whitespace` | Blank area | An area of the page with no text. | An empty band between two sections |
| 15 | `unknown` | Unrecognised section | A part of the page that matches none of the other section kinds. | A block of scanner noise or an unreadable stamp |

**Grouping, a PROPOSAL.** The sources support a two-way split. Both the section prompts in `src/index.js` and the phone's `SectionKindMapping` divide the 15 kinds into the same two sets:

| Order | Proposed group code | Plain name | Description | Members |
|---|---|---|---|---|
| 1 | `composite` | Information blocks | Sections that describe one thing (a person, a place, an order, a report) and can be turned into structured data. | `patient`, `organization`, `practitioner_role`, `service_request`, `diagnostic_report`, `observation`, `medication_request`, `provenance` |
| 2 | `structural` | Text and page layout | Free text and parts of the page's layout, with no structured record behind them. | `narrative`, `impression`, `table_headers`, `header`, `footer`, `whitespace`, `unknown` |

Whether section kinds get a group field and namespace at all is not ruled: §12.2 says "Kinds only for now". This table is offered only because the brief asked whether the sources support one.

**Unsure or disagreeing:**

- **"Structural" holds clinical text.** The source label for the second set is "structural (no FHIR resource)", yet `narrative` and `impression` hold some of the most important clinical text. The plain name "Text and page layout" is proposed to avoid saying they are mere layout. The split itself is the sources' and is not changed.
- **`observation` versus the classifier.** The live section classifier is told never to assign `observation`, `table_headers` or `whitespace`, because they are set from the page's structure (table detection), not its content. The meaning is the same in both places. Only how each is assigned differs, so this is noted, not marked unsure.
- **`unknown` example.** The sources describe it only as "not matching any of the above". The example is invented.

---

## 4. Plain names for every other live term

Code and plain name only, as the brief asks. Where a source gives a meaning that bears on the name, it is noted under the table.

### 4a. Subtypes (`rh.atom.subtype`, 41)

| Code | Plain name |
|---|---|
| `accessionNumber` | Accession number |
| `address` | Address |
| `age` | Age |
| `barcode` | Barcode |
| `billingAccountNumber` | Billing account number |
| `bloodType` | Blood type |
| `city` | City |
| `credentials` | Credentials |
| `dateOfBirth` | Date of birth |
| `departmentName` | Department name |
| `documentType` | Document type |
| `email` | Email |
| `encounterNumber` | Visit number |
| `ethnicity` | Ethnicity |
| `facility` | Facility |
| `facilityName` | Facility name |
| `fax` | Fax |
| `formCode` | Form code |
| `genderIdentity` | Gender identity |
| `memberNumber` | Member number |
| `mrn` | Medical record number |
| `name` | Name |
| `npi` | National Provider Identifier (NPI) |
| `orderNumber` | Order number |
| `patientName` | Patient name |
| `phone` | Phone |
| `pronouns` | Pronouns |
| `race` | Race |
| `relationship` | Relationship |
| `role` | Role |
| `sex` | Sex |
| `sexAssignedAtBirth` | Sex assigned at birth |
| `specialty` | Specialty |
| `ssn` | Social Security number |
| `ssnLastFour` | Last four digits of SSN |
| `state` | State |
| `street` | Street |
| `subscriberNumber` | Subscriber number |
| `unspecifiedContact` | Other contact |
| `unspecifiedIdentifier` | Other identifier |
| `zip` | ZIP code |

**Unsure or disagreeing:**

- **Duplicate pairs.** `name` and `patientName`, and `facilityName` and `facility`, look like the same meaning written twice. The Worker's `ingest-vocab.mjs` says the prompt uses `name`, `facilityName` and `address`, while the LlamaExtract adapter mints `patientName`, `facility` and `street`/`city`/`state`/`zip`, and keeps both spellings on purpose. The phone folds `patientName` into `name` ("patientName is a phi_type, not a subtype") and `facility` into `facilityName`. Each is given its own plain name here. Whether one of each pair should be retired is the owner's call, not this draft's.
- **`address` versus `street`, `city`, `state`, `zip`.** The same split: the prompt asks for one whole address, the adapter for its parts. Both are kept.
- **`formCode`.** No source says what a form code is beyond the name, in the list of document-reference subtypes. Probably the printed form's own number. **Meaning not confirmed.**
- **`barcode`.** In the same list, with no description. The plain name is literal.
- **`subscriberNumber` versus `memberNumber` versus `billingAccountNumber`.** All three are patient identifiers with no description in any source. A subscriber number is presumably the insurance policy holder's ID and a member number the patient's own plan ID, but no source says so. **Distinction not confirmed.**
- **`role`.** Open vocabulary for clinicians: the extractor copies the role as written ("Ordering Physician"), so many off-list values are expected (owner ruling 2026-08-21). The plain name names the term, not its values.
- **`encounterNumber`.** "Visit number" is proposed because "encounter" is clinical jargon. The code is unchanged.

### 4b. Date roles (`rh.atom.date-role`, 8)

| Code | Plain name |
|---|---|
| `admission` | Admission date |
| `collection` | Sample collection date |
| `discharge` | Discharge date |
| `narrativeReference` | Date mentioned in notes |
| `report` | Report date |
| `service` | Date of service |
| `study` | Imaging date |
| `visit` | Visit date |

**Unsure or disagreeing:**

- **`service` versus `visit`.** The prompt says `service` is the "billing-legal service date" and `visit` the "clinical visit date". On most documents they are the same day, and a non-clinician reviewer may not know when to pick which. The names follow the sources. A one-line description would help when date roles get descriptions.
- **`study`.** The prompt says "imaging study dates" and the phone "imaging study start". "Imaging date" follows both.

### 4c. PHI types (`rh.phi.type`, 34)

Two already carry a plain name in the dictionary (`patientFax` "Patient fax", `providerEmail` "Provider email"). They are kept as they are, and the rest follow the same pattern.

| Code | Plain name |
|---|---|
| `accessionNumber` | Accession number |
| `accountNumber` | Account number |
| `biometric` | Biometric identifier |
| `dateOfAdmission` | Admission date |
| `dateOfDischarge` | Discharge date |
| `dateOfReport` | Report date |
| `dateOfService` | Date of service |
| `dateSigned` | Date signed |
| `deviceIdentifier` | Device identifier |
| `dob` | Date of birth |
| `emergencyContactName` | Emergency contact name |
| `facilityAddress` | Facility address |
| `facilityName` | Facility name |
| `guardianName` | Guardian name |
| `ipAddress` | IP address |
| `licenseNumber` | License number |
| `memberNumber` | Member number |
| `mrn` | Medical record number |
| `otherIdentifier` | Other identifier |
| `patientAddress` | Patient address |
| `patientEmail` | Patient email |
| `patientFax` | Patient fax |
| `patientName` | Patient name |
| `patientPhone` | Patient phone |
| `photograph` | Photograph |
| `providerAddress` | Provider address |
| `providerEmail` | Provider email |
| `providerFax` | Provider fax |
| `providerName` | Provider name |
| `providerPhone` | Provider phone |
| `ssn` | Social Security number |
| `ssnLastFour` | Last four digits of SSN |
| `staffName` | Staff name |
| `urlOrHandle` | Web address or online handle |

**Unsure or disagreeing:**

- **"Provider" here and in section 2.** The PHI type names keep "Provider" to match the two plain names already in the dictionary (`providerEmail`). With the 2026-10-01 ruling naming the `provider` kind "Provider", the two now agree.
- **`otherIdentifier`.** Besides its plain meaning, the Worker also uses it as the slot for any PHI type it does not recognise (PACKAGE_DESIGN OR-18 n, per the phone's `PHIType.swift`). The plain name does not mention this.
- **`biometric`, `photograph`, `ipAddress`, `urlOrHandle`, `licenseNumber`, `deviceIdentifier`.** These follow the HIPAA identifier list the phone's `PHIType` cites. No source in this sweep describes them further. The names are literal.

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

| Code | Plain name |
|---|---|
| `analyte_name` | Test name |
| `value` | Result |
| `units` | Units |
| `reference_range` | Normal range |
| `flag` | High or low flag |

These are the five roles the LlamaExtract adapter gives the cells of a lab table (`ingest-vocab.mjs`, `COLUMN_ROLES`). No source describes `flag` beyond its name. "High or low flag" assumes the usual lab-report marker (H, L, or abnormal), and the owner should confirm it.

---

## Counts

| Section | Terms |
|---|---|
| 1. Kind groups | 9 |
| 2. Kinds | 31 |
| 3. Section kinds | 15 (plus 2 proposed section-kind groups) |
| 4. Plain names | 94: subtypes 41, date roles 8, PHI types 34, certainty 3, reliability 3, column roles 5 |

Live terms in the staging dictionary (version 6): 125, that is 31 kinds plus the 94 in section 4. The kind groups and section kinds are new terms proposed by D1.
