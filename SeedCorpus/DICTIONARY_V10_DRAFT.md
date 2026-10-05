# DICTIONARY_V10_DRAFT.md — Dictionary version 10, drafted for approval

Status: APPROVED by the owner 2026-10-04, with an amendment awaiting approval (2026-10-05): Claude and LlamaExtract texts per term. Not yet published.

This page holds the complete final content of every term that is new, changed or retired in dictionary version 10 (INGEST_VOCABULARY_DESIGN §12.10 pieces b, e and f, plus `phi_default`). Version 10 is published once, with the §12.10 piece h deploy (OR-69). The owner approved this page on 2026-10-04 (OR-28).

**The governing rule (owner, 2026-10-04):** version 10 moves today's behaviour into the dictionary unchanged. Nothing in it may change what the AI is offered or extracts, beyond owner rulings already recorded in INGEST_VOCABULARY_DESIGN §12.10. Anything that would change ingest behaviour belongs to the ingest fidelity series, not here.

## Three texts per term

Owner ruling (2026-10-05, OR-73): each term may carry three separate texts, one per reader: the reviewer text (the description and examples on this page, shown in the console, unchanged), the Claude text (what the Atom Pass and PHI pass are told about the term, carrying today's prompt wording word for word, OR-68), and the LlamaExtract text (the field description LlamaExtract is given for the fields that fill the term, used from piece g). This revises OR-21 and OR-25 (one description per term) and supports the bakeoff's per-vendor wording (`VENDOR_ABSTRACTION_DESIGN.md` §1.1). Sections 14 and 15 hold the Claude and LlamaExtract texts; field names are the build's.

**Sources (read only):** the published version 9 (`recordhealth-api/test/harness/fixtures/dictionary-v9.json`); `ATOM_PASS_GUIDANCE`, `PHI_ELIGIBLE_KINDS` and the two prompts in `src/pipeline-shared.mjs`; `ATOM_KIND_FIELDS` in `src/result-schema.mjs`; the vendor adapter (`src/llama-extract-adapter.mjs`); INGEST_VOCABULARY_DESIGN v8.9.

## How to read this page

- **Unchanged** beside a description means the version 9 text stays word for word. It is repeated so each term can be read whole.
- **Examples** follow OR-46: up to three per term, deliberately varied, each exactly the words a fact should cover and never the printed label. Each example is shown in `code type` so its start and end are exact. Every example is invented. Names, numbers and addresses are fictional.
- **Descriptions** keep the dictionary's existing style: a short definition, as in the approved version 7 text ("A vaccine the patient received."). The certainty and confidence descriptions are full sentences.
- **Lists.** An empty list, written `[]`, means curated with nothing in it. "No value" means not yet curated (OR-65). No list names a retired kind (OR-63). Only the ten kinds `ATOM_KIND_FIELDS` names carry subtypes (OR-60).
- Every question is settled; section 13 records the answers. Nothing on the page is open.

## Counts

| | Version 9 | Version 10 |
|---|---|---|
| Terms | 162 | 165 |
| Live terms | 155 | 150 |
| Retired terms | 7 | 15 |
| Namespaces | 12 | 13 |

Three terms are added (extraction confidence). Eight are retired (five subtypes, three reliability terms).

---

## 1. Kinds (`rh.atom.kind`)

33 terms: 31 live, 2 retired. Every live kind changes: its examples are rewritten and it gains `phi_default`. Five descriptions change. Plain names, groups and order are unchanged.

`phi_default` is filled in version 10, from `PHI_ELIGIBLE_KINDS`, so today's behaviour carries over unchanged. OR-29, which held it empty until the phone release, is superseded by OR-70 (owner, 2026-10-03): the field is filled in version 10, and the phone takes version 10 when P1 ships; until then it keeps version 9. **true** means a fact of this kind can carry PHI, so it is sent to the PHI pass to be judged. **false** means a fact of this kind is never PHI on its own, so it is marked not PHI without asking the AI. It does not mean every fact of the kind is PHI.

| Code | Plain name | Description | Examples | phi_default |
|---|---|---|---|---|
| `labValue` | Lab result | Unchanged: One lab test and its result: value, units and normal range. | `Sodium 140 mmol/L` `Hemoglobin A1c 6.1%` `TSH 2.1 mIU/L (0.4-4.0)` | false |
| `labPanel` | Lab panel | Unchanged: A heading that names a group of lab tests run together. It is not a single test result. | `Basic Metabolic Panel` `CBC With Differential/Platelet` `Urinalysis, Complete` | false |
| `vitalSign` | Vital sign | Unchanged: A basic body measurement such as blood pressure, heart rate, temperature or oxygen level. | `Blood pressure` `HR` `SpO2` | false |
| `finding` | Finding | Unchanged: Something a clinician observed during an exam, on an image or while reading a lab result. A normal finding is still a finding, not a condition. | `Lungs clear on both sides` `mild swelling of the left ankle` `No acute fracture` | false |
| `encounter` | Visit | Unchanged: The type of visit the document records. | `Office visit` `ED visit` `Telehealth` | false |
| `symptom` | Symptom | Unchanged: Something the patient comes in with or describes feeling, such as the main complaint. A symptom the patient denies is not recorded. | `sore throat` `chest pain on exertion` `trouble sleeping` | false |
| `condition` | Condition | Unchanged: An ongoing or past health problem of this patient, often listed under medical history. | `asthma` `type 2 diabetes` `high blood pressure` | false |
| `diagnosis` | Diagnosis | Unchanged: A clinician's formal conclusion from this visit, usually under Assessment or Impression. | `ear infection` `acute bronchitis` `sprained left ankle` | false |
| `medication` | Medication | Unchanged: A medicine by name, brand or generic. A dosage form alone, such as "tablet", is not a medication. | `Ibuprofen 200 mg` `Flonase` `metformin` | false |
| `procedure` | Procedure | Unchanged: A surgery or other hands-on treatment that was performed. | `Knee arthroscopy` `appendectomy` `colonoscopy with biopsy` | false |
| `immunization` | Vaccine | Unchanged: A vaccine the patient received. | `Flu vaccine` `Tdap` `MMR` | false |
| `carePlan` | Care plan item | Unchanged: A planned step or goal of the patient's care. | `Physical therapy twice a week` `follow up in three months` `low-salt diet` | false |
| `referral` | Referral or order | Unchanged: A service requested for the patient, such as a consult or a scan. | `MRI of the lower back` `ENT consult` `referral to cardiology` | false |
| `device` | Medical device | Unchanged: A medical device the patient has or uses, implanted or external. | `Insulin pump` `pacemaker` `CPAP machine` | false |
| `allergy` | Allergy | Unchanged: Something the patient is allergic to: a medicine, a food or something in the environment. "No known allergies" counts too. | `penicillin` `peanuts` `No known drug allergies` | false |
| `familyHistory` | Family history | Unchanged: A health problem of a family member, not of the patient. | `Mother had breast cancer` `father, heart attack at 60` `sister with asthma` | false |
| `socialHistory` | Social history | Unchanged: Lifestyle facts relevant to health, such as smoking or alcohol use. | `Former smoker` `drinks alcohol socially` `lives alone` | false |
| `provider` | Provider | Unchanged: A doctor, nurse practitioner or other provider who treats the patient, orders tests, reads results or signs the document. Lab staff are not included. | `Dr. A. Sample` `Internal Medicine` `1234567893` | true |
| `organization` | Organization | Unchanged (it keeps "insurer", OR-57): A hospital, clinic, lab, imaging center or insurer named in the document. A brand-name medicine is never an organization. | `Example County Hospital` `Department of Radiology` `Example Health Insurance` | true |
| `providerContact` | Provider or organization contact | **Changed** (OR-55): A phone number, fax number, email address or postal address for a provider or an organization. Each part of an address (street, city, state and ZIP code) is a separate fact. | `555-0199` `frontdesk@example.org` `1 Main Road, Suite 200` | true |
| `dateAtom` | Date | **Changed** (the leftover "(see section 4)" is gone): A date in the document. Its date role says what the date is for. A date of birth is a patient detail, not a date. | `03/15/2024` `March 15, 2024` `2019` | true |
| `coverage` | Insurance coverage | **Changed** (OR-57, "payer" dropped): Insurance plan details: the plan, the member number and the plan's dates. The insurer's name is an organization, not coverage. | `Example Choice PPO` `HMO` `000123456` | false |
| `documentReference` | Document number or type | Unchanged: A number or label that identifies the document or the order, such as an accession number, order number or document type. | `AB-000000` `000000` `Discharge Summary` | true |
| `recordSummary` | Record summary | Unchanged (not choosable, OR-51): A short summary of the whole record, written by the system, not read from the document. | `Routine lab panel, all results in range.` `Office visit for a sore throat. Strep test negative.` | false |
| `patientDemographic` | Patient demographic | Unchanged: A personal detail about the patient: name, date of birth, sex, age, race, ethnicity, pronouns or blood type. | `Alex Sample` `01/16/1977` `female` | true |
| `patientIdentifier` | Patient identifier | **Changed** (OR-46, the rule in words): A number or code that identifies the patient, in any length or format, such as a medical record number, member number or Social Security number. | `0000000` `MR-00-12-34` `E0012345` | true |
| `patientContact` | Patient contact | Unchanged: The patient's phone, email or fax. | `555-0100` `(555) 555-0142` `alex.sample@example.com` | true |
| `patientAddress` | Patient address | **Changed** (OR-55): The patient's street, city, state or ZIP code. Each part is a separate fact. | `12 Example Street` `Fairhaven` `97000` | true |
| `guardianInfo` | Guardian | Unchanged: The patient's guardian: name, relationship or contact details. | `Jordan Sample` `mother` `555-0142` | true |
| `emergencyContact` | Emergency contact | Unchanged: The person to call in an emergency: name, relationship or contact details. | `Sam Example` `spouse` `555-0167` | true |
| `uncategorized` | Other | Unchanged: A fact that fits no other kind. | `COPY` `Scanned at front desk` | true |
| `reportDate` | (retired) | Retired in version 9. Unchanged. | no value | no value |
| `visitDate` | (retired) | Retired in version 9. Unchanged. | no value | no value |

### Where `PHI_ELIGIBLE_KINDS` and the dictionary disagree

- **In `PHI_ELIGIBLE_KINDS` but not in the dictionary:** none. All twelve are live kinds: `patientDemographic`, `patientIdentifier`, `patientContact`, `patientAddress`, `guardianInfo`, `emergencyContact`, `provider`, `providerContact`, `organization`, `dateAtom`, `documentReference`, `uncategorized`.
- **In the dictionary but not in `PHI_ELIGIBLE_KINDS`:** nineteen live kinds, all **false**. Sixteen are named in the code as clinical and never PHI on their own: `labValue`, `vitalSign`, `medication`, `condition`, `diagnosis`, `symptom`, `allergy`, `procedure`, `immunization`, `finding`, `device`, `referral`, `carePlan`, `familyHistory`, `socialHistory`, `encounter`. Three are named in neither list and are false only because the code leaves them out: `labPanel`, `coverage` and `recordSummary`. They stay false, as today.
- **Retired kinds:** `reportDate` and `visitDate` are in neither list. They carry no value.

---

## 2. Kind groups (`rh.atom.kind-group`)

10 terms. Examples only. Plain names, descriptions and order are unchanged. Groups are display-only (OR-36).

| Code | Plain name | Examples |
|---|---|---|
| `observations` | Observations | `Glucose 95 mg/dL` `Blood pressure` `Lungs clear on both sides` |
| `visits` | Visits | `Office visit` `ED visit` `Telehealth` |
| `conditions` | Conditions | `sore throat` `asthma` `ear infection` |
| `treatment` | Treatments & care | `Amoxicillin 500 mg` `Knee arthroscopy` `Flu vaccine` |
| `history` | Patient history | `penicillin` `Mother had breast cancer` `Former smoker` |
| `care_team` | People & places | `Dr. A. Sample` `Example County Hospital` `555-0199` |
| `temporal` | Document dates | `03/15/2024` `March 15, 2024` `2019` |
| `administrative` | Administrative | `AB-000000` `Discharge Summary` `Example Choice PPO` |
| `patient_details` | Patient details | `Alex Sample` `0000000` `555-0100` |
| `other` | Other | `COPY` `Scanned at front desk` |

---

## 3. Subtypes (`rh.atom.subtype`)

41 terms: 36 live after version 10, 5 retired by it.

### 3a. Retired in version 10 (piece e, OR-37)

| Code | Why |
|---|---|
| `patientName` | The vendor's spelling. The adapter translates it to `name`. |
| `facility` | The vendor's spelling. The adapter translates it to `facilityName`. |
| `address` | Every address is split into `street`, `city`, `state` and `zip` (OR-55). |
| `formCode` | No such element in a FHIR document reference, and nothing ever produced it. |
| `barcode` | The same. |

None of the five has a plain name, a description or a list in version 9, and none gains one.

### 3b. The address parts (piece e, OR-55)

`street`, `city`, `state` and `zip` already exist in version 9. OR-55 splits every address into these parts, for provider and organization contacts, the patient, a guardian and an emergency contact, and the server links parts printed together into one address. The table below gives each part the four kinds OR-55 names. This is the one place a list departs from today's prompt and adapter. It is settled (S1, section 13): the parts follow OR-55, because the check that found the departure compared against today's code, which predates OR-55.

### 3c. Every live subtype

Every live subtype gains `belongs_to_kinds`, an order, a description (three already have one) and examples. Plain names are unchanged. Each list holds exactly the kinds today's prompt and vendor adapter offer the subtype on, in the prompt's order; the four address parts are the exception (3b). The order is the subtype's place in today's prompt lists.

| Code | Plain name | Description | Examples | belongs_to_kinds | Order |
|---|---|---|---|---|---|
| `accessionNumber` | Accession number | The number a lab or imaging department gives a specimen or study to track it, in any length or format. | `AB-000000` `000123456` `S24-0001234` | `documentReference` | 34 |
| `age` | Age | The patient's age, as printed. | `47` `47 years` `6 months` | `patientDemographic` | 8 |
| `billingAccountNumber` | Billing account number | Unchanged: The patient's account number with the provider's billing office. | `0000123456` `ACCT-00-1234` `B000123` | `patientIdentifier` | 14 |
| `bloodType` | Blood type | The patient's blood type. | `O positive` `A-` `AB+` | `patientDemographic` | 6 |
| `city` | City | The city or town in a postal address. | `Fairhaven` `Port Example` `Mount Sample` | `patientAddress`, `providerContact`, `guardianInfo`, `emergencyContact` | 25 |
| `credentials` | Credentials | The letters after a provider's name that show their qualifications. | `MD` `NP` `DO, FACP` | `provider` | 31 |
| `dateOfBirth` | Date of birth | The patient's date of birth. | `01/16/1977` `January 16, 1977` `1977-01-16` | `patientDemographic` | 2 |
| `departmentName` | Department name | The name of a department or unit within an organization. | `Cardiology` `Department of Radiology` `Emergency Department` | `organization` | 33 |
| `documentType` | Document type | The type of document, in the document's own words. | `Discharge Summary` `Laboratory Report` `Progress Note` | `documentReference` | 36 |
| `email` | Email | An email address. | `alex.sample@example.com` `frontdesk@example.org` | `patientContact`, `patientAddress`, `guardianInfo`, `emergencyContact`, `providerContact` | 20 |
| `encounterNumber` | Visit number | The number a facility gives one visit or hospital stay, in any length or format. | `000456789` `V-0001234` `ENC00098765` | `patientIdentifier` | 17 |
| `ethnicity` | Ethnicity | The patient's ethnicity, as printed. | `Hispanic or Latino` `Not Hispanic or Latino` | `patientDemographic` | 10 |
| `facilityName` | Facility name | The name of a hospital, clinic, lab, imaging center or other place of care. | `Example County Hospital` `Example Labs` `Fairhaven Family Clinic` | `organization` | 32 |
| `fax` | Fax | A fax number. | `555-0199` `(555) 555-0188` | `patientContact`, `patientAddress`, `guardianInfo`, `emergencyContact`, `providerContact` | 21 |
| `genderIdentity` | Gender identity | The patient's gender identity, as printed. | `woman` `nonbinary` `transgender man` | `patientDemographic` | 5 |
| `memberNumber` | Member number | Unchanged: The patient's own ID on the insurance plan. | `000123456` `XEH000123456` `W0001-23456-01` | `patientIdentifier` | 15 |
| `mrn` | Medical record number | The number or code a hospital or clinic uses to identify the patient in its own records, in any length or format. | `0000000` `MR-00-12-34` `E0012345` | `patientIdentifier` | 11 |
| `name` | Name | The name of the patient or of a provider, as printed. | `Alex Sample` `SAMPLE, ALEX J` `Dr. A. Sample` | `patientDemographic`, `provider` | 1 |
| `npi` | National Provider Identifier (NPI) | A provider's ten-digit National Provider Identifier. | `1234567893` | `provider` | 28 |
| `orderNumber` | Order number | The number that identifies an order for a test or service, in any length or format. | `000000` `ORD-0012345` `L0001234` | `documentReference` | 35 |
| `phone` | Phone | A phone number. | `555-0100` `(555) 555-0142` `+1 555 555 0175` | `patientContact`, `patientAddress`, `guardianInfo`, `emergencyContact`, `providerContact` | 19 |
| `pronouns` | Pronouns | The pronouns the patient uses. | `she/her` `they/them` `he/him` | `patientDemographic` | 7 |
| `race` | Race | The patient's race, as printed. | `Asian` `Black or African American` `White` | `patientDemographic` | 9 |
| `relationship` | Relationship | How a guardian or emergency contact is related to the patient. | `mother` `spouse` `legal guardian` | `patientContact`, `patientAddress`, `guardianInfo`, `emergencyContact` | 23 |
| `role` | Role | A provider's role in the patient's care, in the document's own words. | `[]` | `provider` | 29 |
| `sex` | Sex | The patient's sex, as printed. | `female` `M` `Male` | `patientDemographic` | 3 |
| `sexAssignedAtBirth` | Sex assigned at birth | The sex recorded for the patient at birth. | `female` `Male` `F` | `patientDemographic` | 4 |
| `specialty` | Specialty | A provider's field of medicine. | `Internal Medicine` `Cardiology` `Pediatrics` | `provider` | 30 |
| `ssn` | Social Security number | A full Social Security number. | `000-00-0000` `000000000` | `patientIdentifier` | 12 |
| `ssnLastFour` | Last four digits of SSN | The last four digits of a Social Security number. | `0000` `XXX-XX-0000` | `patientIdentifier` | 13 |
| `state` | State | The state in a postal address, spelled out or abbreviated. | `OR` `Oregon` | `patientAddress`, `providerContact`, `guardianInfo`, `emergencyContact` | 26 |
| `street` | Street | The street line of a postal address. | `12 Example Street` `1 Main Road, Suite 200` `PO Box 000` | `patientAddress`, `providerContact`, `guardianInfo`, `emergencyContact` | 24 |
| `subscriberNumber` | Subscriber number | Unchanged: The insurance policy holder's ID. | `000987654` `SUB-0001234` | `patientIdentifier` | 16 |
| `unspecifiedContact` | Other contact | A contact detail that is not a phone number, fax number, email address or postal address. | `Pager 555-0167` | `patientContact`, `patientAddress`, `guardianInfo`, `emergencyContact`, `providerContact` | 22 |
| `unspecifiedIdentifier` | Other identifier | A number or code that identifies the patient and fits no other identifier subtype. | `PT-000123` `0001234` | `patientIdentifier` | 18 |
| `zip` | ZIP code | The ZIP code in a postal address. | `97000` `97000-0001` | `patientAddress`, `providerContact`, `guardianInfo`, `emergencyContact` | 27 |

**Checks.** The lists name exactly the ten kinds `ATOM_KIND_FIELDS` allows, and every one of the ten has at least one subtype. No list names a retired kind. Thirty-two lists match today's prompt and vendor adapter exactly; the four address parts follow OR-55 (S1, settled). The adapter's own spellings, `patientName` and `facility`, are read as `name` and `facilityName` (OR-37). The order keeps every one of today's prompt lists in its own order; the four address parts take the place `address` holds today.

---

## 4. Date roles (`rh.atom.date-role`)

8 terms. Six gain a description. All eight have their examples rewritten. Plain names are unchanged. A date role records the printed label, so the label is named in the description and the example is the date alone.

| Code | Plain name | Description | Examples |
|---|---|---|---|
| `admission` | Admission date | **New:** A date the document labels as the day the patient was admitted to a hospital or other facility, such as 'Admitted' or 'Admission date'. | `03/12/2024` `March 12, 2024` `12-Mar-2024` |
| `collection` | Sample collection date | **New:** A date the document labels as the day a sample was taken for a lab test, such as 'Collected', 'Collection date' or 'Date drawn'. | `03/15/2024` `3/15/24` `2024-03-15` |
| `discharge` | Discharge date | **New:** A date the document labels as the day the patient left the hospital or facility, such as 'Discharged' or 'Discharge date'. | `03/14/2024` `March 14, 2024` `14-Mar-2024` |
| `narrativeReference` | Date mentioned in notes | **New:** A date mentioned in the running text of a clinician's notes with no label saying what it is, usually where the notes describe a past event. | `2019` `March 2021` `03/02` |
| `report` | Report date | **New:** A date the document labels as the day the report was produced, such as 'Reported' or 'Report date'. | `03/18/2024` `March 18, 2024` `2024-03-18` |
| `service` | Date of service | Unchanged: A date the document labels as the date of service, such as 'DOS' or 'Service date'. | `03/15/2024` `3/15/24` `March 15, 2024` |
| `study` | Imaging date | **New:** A date the document labels as the day an imaging study was done, such as 'Study date' or 'Exam date'. | `03/16/2024` `March 16, 2024` `16 Mar 2024` |
| `visit` | Visit date | Unchanged: A date the document labels as the visit or appointment date. | `03/15/2024` `Friday, March 15, 2024` `15 Mar 2024` |

---

## 5. Classification certainty (`rh.certainty`)

3 terms. Each gains a description. Plain names are unchanged.

| Code | Plain name | Description | Examples |
|---|---|---|---|
| `specific` | Sure of kind and detail | **New:** The AI is confident of the fact's kind and, where the kind has subtypes, of its subtype as well. | `[]` |
| `parent_only` | Sure of kind only | **New:** The AI is confident of the fact's kind but not of its subtype. | `[]` |
| `low_confidence` | Unsure of kind | **New:** The AI is not confident even of the fact's kind. | `[]` |

---

## 6. Extraction confidence (new, piece f)

**Approved (owner, 2026-10-04):** the namespace `rh.extraction-confidence`, the field name `extraction_confidence`, and the codes `high`, `medium` and `low` with the plain names below. The codes are the same three the reliability field uses today, so only the namespace and field name move.

High, medium or low is worked out by the server from each reader's own confidence number, with one shared set of cut-offs for the Atom Pass and LlamaExtract (OR-52). A fact whose reader gave no number has no value here: it is left blank and flagged, never set to low.

| Code | Plain name | Description | Examples |
|---|---|---|---|
| `high` | High confidence | **New:** The AI that read this fact gave it a confidence score in the top band. | `[]` |
| `medium` | Medium confidence | **New:** The AI that read this fact gave it a confidence score in the middle band. | `[]` |
| `low` | Low confidence | **New:** The AI that read this fact gave it a confidence score in the bottom band. | `[]` |

**Cut-offs.** They stay at today's: a score of 0.8 or more is high, 0.6 or more is medium, and anything lower is low. The descriptions do not state the numbers.

**Not choosable.** All three are marked not choosable, as "Unrecognized PHI type" is (OR-43). The server computes them, no picker offers them, and the save step refuses a new pick by name (OR-61).

---

## 7. Reliability (`rh.reliability`) — retired (piece f, OR-52, OR-53)

| Code | Version 10 |
|---|---|
| `high` | Retired |
| `medium` | Retired |
| `low` | Retired |

The three never had a plain name or description, and gain none. The Atom Pass's word-precision answer retires with them. In the snapshot's list of fields, the `reliability` entry gives way to the extraction confidence entry; that is build work, not text.

---

## 8. PHI types (`rh.phi.type`)

36 terms. Twenty-seven gain a description; nine already have one. All gain examples. Plain names, token prefixes and token sharing are unchanged.

| Code | Plain name | Description | Examples |
|---|---|---|---|
| `accessionNumber` | Accession number | **New:** The number a lab or imaging department gives a specimen or study to track it. | `AB-000000` `000123456` `S24-0001234` |
| `accountNumber` | Account number | **New:** A billing account number, such as the patient's account with a provider's billing office. | `0000123456` `ACCT-00-1234` |
| `biometric` | Biometric identifier | Unchanged: A biometric identifier, such as a fingerprint or voiceprint. | `[]` |
| `dateOfAdmission` | Admission date | **New:** The date the patient was admitted to a hospital or other facility. | `03/12/2024` `March 12, 2024` |
| `dateOfDischarge` | Discharge date | **New:** The date the patient left the hospital or facility. | `03/14/2024` `14-Mar-2024` |
| `dateOfReport` | Report date | **New:** The date a report or document was produced. | `03/18/2024` `2024-03-18` |
| `dateOfService` | Date of service | **New:** The date of a visit. | `03/15/2024` `3/15/24` |
| `dateSigned` | Date signed | **New:** The date the document was signed. | `03/18/2024` `March 18, 2024` |
| `deviceIdentifier` | Device identifier | Unchanged: A device identifier or serial number, such as an implant's serial number. | `000123456789` `SN-00-12345` |
| `dob` | Date of birth | **New:** The patient's date of birth. | `01/16/1977` `January 16, 1977` |
| `emergencyContactName` | Emergency contact name | **New:** The name of the patient's emergency contact. | `Sam Example` |
| `facilityAddress` | Facility address | **New:** The address of a hospital, clinic, lab or other facility, or any part of it. | `1 Main Road, Suite 200` `Fairhaven` `97000` |
| `facilityName` | Facility name | **New:** The name of a hospital, clinic, lab or other facility. | `Example County Hospital` `Example Labs` |
| `guardianName` | Guardian name | **New:** The name of the patient's guardian. | `Jordan Sample` |
| `ipAddress` | IP address | Unchanged: An internet (IP) address. | `192.0.2.10` `2001:db8::1` |
| `licenseNumber` | License number | Unchanged: A certificate or license number, such as a driver's or professional license. | `D000-0000-0000` `MD000000` |
| `memberNumber` | Member number | **New:** The patient's own ID on an insurance plan. | `000123456` `XEH000123456` |
| `mrn` | Medical record number | **New:** The number or code a hospital or clinic uses to identify the patient in its own records, in any length or format. | `0000000` `MR-00-12-34` `E0012345` |
| `otherIdentifier` | Other identifier | Unchanged: An identifier that fits no other PHI type. | `PT-000123` |
| `patientAddress` | Patient address | **New:** The patient's address, or any part of it. | `12 Example Street` `Fairhaven` `97000` |
| `patientEmail` | Patient email | **New:** The patient's email address. | `alex.sample@example.com` |
| `patientFax` | Patient fax | **New:** The patient's fax number. | `555-0155` |
| `patientName` | Patient name | **New:** The patient's name, in full or in part. | `Alex Sample` `SAMPLE, ALEX J` |
| `patientPhone` | Patient phone | **New:** The patient's phone number. | `555-0100` `(555) 555-0142` |
| `photograph` | Photograph | Unchanged: A full-face photograph or comparable image. | `[]` |
| `providerAddress` | Provider address | **New:** A provider's address, or any part of it. | `1 Main Road, Suite 200` `Fairhaven` |
| `providerEmail` | Provider email | **New:** A provider's email address. | `a.sample@example.org` |
| `providerFax` | Provider fax | **New:** A provider's fax number. | `555-0199` |
| `providerName` | Provider name | **New:** The name of a doctor, nurse practitioner or other provider who treats the patient. | `Dr. A. Sample` `Jordan Example` |
| `providerPhone` | Provider phone | **New:** A provider's phone number. | `555-0123` `(555) 555-0188` |
| `ssn` | Social Security number | **New:** A full Social Security number. | `000-00-0000` `000000000` |
| `ssnLastFour` | Last four digits of SSN | **New:** The last four digits of a Social Security number. | `0000` `XXX-XX-0000` |
| `staffName` | Staff name | **New:** The name of a staff member who is not one of the patient's providers, such as a lab technician or a nurse. | `Casey Sample` `T. Example` |
| `unrecognized` | Unrecognized PHI type | Unchanged (not choosable, OR-43): A value marked as PHI whose type could not be recognized. A reviewer needs to pick the correct type. | `[]` |
| `urlOrHandle` | Web address or online handle | Unchanged: A web address (URL) or online username. | `www.example.org/portal` `@alexsample` |
| `vehicleIdentifier` | Vehicle identifier | Unchanged: A vehicle identifier or serial number, including a license plate. | `00000000000000000` `ABC-0000` |

---

## 9. Column roles (`rh.column-role`)

5 terms. Examples only. Plain names are unchanged, and so are the descriptions: `flag` keeps its description and the other four still have none.

| Code | Plain name | Examples |
|---|---|---|
| `analyte_name` | Test name | `Glucose` `Hemoglobin A1c` `WBC` |
| `value` | Result | `95` `6.1` `Negative` |
| `units` | Units | `mg/dL` `%` `mmol/L` |
| `reference_range` | Normal range | `70-99` `<5.7` `Negative` |
| `flag` | Result flag | `H` `L` `Critical` |

---

## 10. Section kinds (`rh.section.kind`)

15 terms. Each gains `looks_for_kinds`, ordered, taken from today's `ATOM_PASS_GUIDANCE` in the same order. Plain names, descriptions, groups and order are unchanged. Examples stay as they are in version 9.

| Code | Plain name | looks_for_kinds, in order |
|---|---|---|
| `patient` | Patient block | `patientDemographic`, `patientIdentifier`, `patientContact`, `patientAddress`, `guardianInfo`, `emergencyContact`, `dateAtom` |
| `organization` | Organization block | `organization`, `providerContact`, `dateAtom` |
| `practitioner_role` | Clinician block | `provider`, `providerContact`, `organization`, `dateAtom` |
| `service_request` | Order or referral | `provider`, `providerContact`, `organization`, `referral`, `dateAtom`, `documentReference`, `uncategorized` |
| `diagnostic_report` | Diagnostic report | `labValue`, `labPanel`, `documentReference`, `dateAtom`, `provider`, `uncategorized` |
| `observation` | Single result | `labValue`, `labPanel`, `finding`, `dateAtom`, `uncategorized` |
| `medication_request` | Prescription | `medication`, `dateAtom` |
| `provenance` | Signature block | `provider`, `dateAtom`, `documentReference` |
| `narrative` | Clinical notes | The general list below |
| `impression` | Impression or conclusion | The general list below |
| `table_headers` | Table header row | `[]` (the Atom Pass skips this section kind) |
| `header` | Page header | The general list below |
| `footer` | Page footer | The general list below |
| `whitespace` | Blank area | `[]` (the Atom Pass skips this section kind) |
| `unknown` | Unrecognized section | The general list below |

**The general list**, in order (19 kinds): `condition`, `diagnosis`, `symptom`, `allergy`, `medication`, `procedure`, `immunization`, `vitalSign`, `labValue`, `labPanel`, `finding`, `device`, `referral`, `carePlan`, `familyHistory`, `socialHistory`, `encounter`, `dateAtom`, `uncategorized`.

**Checks.** Every listed kind is a live dictionary term. No list names a retired kind (`reportDate`, `visitDate`). `recordSummary` is in no list (not choosable, OR-51). `coverage` is in no list, because producing coverage has moved to the ingest fidelity series (OR-56). `uncategorized` is in some lists and not others, as today.

---

## 11. Not changed in version 10

- `rh.section.kind-group` (3 terms): nothing changes.
- `rh.edge.kind` (2) and `rh.edge.source` (3): all five were retired before version 9 and stay retired.
- On every term outside `rh.atom.subtype`, `belongs_to_kinds` stays at no value. On every term outside `rh.section.kind`, `looks_for_kinds` stays at no value. These fields do not apply there.
- `phi_default` stays at no value on every term outside `rh.atom.kind`.

---

## 12. Can the dictionary record a denied finding?

This section is the record of the check piece b asked for. It is filed separately and is not part of version 10.

**No.** As it stands, the dictionary cannot record that a finding was denied, for example "denies fever".

- Nothing in it says whether a fact is present or denied. A fact carries a kind, a subtype, a date role, a certainty, a confidence and a PHI type. None of them is about presence.
- The dictionary's own rule is to leave a denied symptom out: the symptom description says "A symptom the patient denies is not recorded", and the prompt says the same. When that rule fails, the denied symptom is stored as an ordinary symptom with nothing to mark it. That is what happened on the staging package, where eleven denied symptoms were stored as symptoms.
- The only negatives it can hold are ones whose own words carry the "no": an allergy fact reading "No known drug allergies", or a finding reading "No acute fracture". The "no" lives in the fact's text. No field says it.

**What would be needed** (not designed here):

1. A place to say it: either a new field on a fact, with its own small list of values in the dictionary (for example present and denied), or new kinds. A new field is a server change as well as a dictionary change, because the server declares which fields a kind has.
2. New text for the symptom description and the matching prompt rule, which today say to drop a denied symptom.
3. Every reader taught to treat a denied fact as not present: the phone, the console, the coding step and the record summary.
4. A way for the AI to tie each item to a "Denies" heading printed on another line. That is the routing problem of the ingest fidelity series, not a dictionary matter.

Version 10 leaves the symptom description as it is.

---

## 13. Rulings applied

The owner's answers of 2026-10-04 to the draft's open questions, by question number.

- **Q1.** `phi_default` is filled in version 10. OR-29 is superseded by the owner (2026-10-03).
- **Q2, Q3, Q4.** As drafted: `coverage` false, `recordSummary` false, the two retired kinds no value.
- **Q5.** The extraction confidence namespace, field name, codes and plain names are approved as proposed.
- **Q6.** The cut-offs stay at today's 0.8 and 0.6. Descriptions as drafted.
- **Q7.** The three extraction confidence terms are not choosable. The server computes them.
- **Q8.** Empty example lists are correct.
- **Q9.** Section-kind and section-kind-group examples stay as in version 9.
- **Q10, Q11, Q12.** Today's `looks_for_kinds` lists, unchanged.
- **Q13.** Coverage text as drafted, per OR-57.
- **Q14.** A vital sign covers the name only, as today.
- **Q15.** The narrowing is undone. `phone`, `email`, `fax` and `unspecifiedContact` are on `patientAddress` again, and `relationship` is on `patientContact` and `patientAddress` again, as today's prompt offers them.
- **Q16.** `name` stays on `patientDemographic` and `provider` only. Its description now names those two.
- **Q17.** `role` stays on `provider`, description unchanged. Its examples are an empty list: curated, nothing in it (S2, settled).
- **Q18.** An insurer's name gets no subtype of its own, as today. `facilityName` is unchanged.
- **Q19.** Every live subtype carries an order taken from today's prompt lists.
- **Q20.** No facility phone, fax or email type. `providerPhone`, `providerFax` and `providerEmail` no longer say they cover organizations, because today's PHI pass prompt does not say it.
- **Q21.** No guardian or emergency contact types. The patient types are unchanged.
- **Q22.** Neither `accessionNumber` nor `accountNumber` says which takes an order number, because today's prompt does not. `accountNumber` now says "billing", the prompt's word.
- **Q23.** `dateOfService` names visit dates only, as today's prompt does.
- **Q24.** `policyHolder`, a subscriber number PHI type and the `received` date role do not enter version 10.
- **Q25.** "Or any part of it" stays: today's prompt makes an address PHI even when partial.
- **Q26.** The signature hint stays in the prompt. The `report` description is as drafted.
- **Q27.** The three description changes are approved.
- **Q28, Q29.** The four column-role descriptions stay blank. The `organization` section kind's description is left as it is.
- **Section 12** stays on the page as the record of the check. It is filed separately.

### Settled since (S1 to S3)

- **S1. `street`, `city`, `state`, `zip`: which kinds. Settled.** They belong to `patientAddress`, `providerContact`, `guardianInfo` and `emergencyContact`, per OR-55. The check that raised the question compared against today's code, which predates OR-55. The parts' order (24 to 27, the place `address` holds today) stands.
- **S2. `role`: what the examples show. Settled.** `role` has examples `[]` (curated, nothing in it). OR-46 and OR-65: no fact covers a role's words on its own today, so there is nothing to show.
- **S3. When version 10 is published. Settled.** One publish, per OR-69 (INGEST_VOCABULARY_DESIGN §10). Version 10 is published once, with the §12.10 piece h deploy, staging then production. It replaces piece f's publish-before-the-deploy and retire-right-after steps.

---

## 14. Claude text (amendment awaiting approval, OR-73)

What today's code sends to Claude about each term, copied word for word. Nothing here is new wording, except the one change OR-49 rules (`labValue`, marked).

**How to read this section.**

- The source column gives the line in `recordhealth-api/src/pipeline-shared.mjs`, written `P:` and the line number. Lines are as of the root commit this page was written at.
- **Sent in** names the section kinds whose Atom Pass prompt carries the words. "General list" is the guidance every section kind without its own entry gets (narrative, impression, header, footer, unknown), as in section 10. "All" means the cross-cutting rules every Atom Pass prompt carries. "PHI pass" means the PHI pass prompt.
- Identical words sent in several section kinds are one row.
- A piece cut from a longer line is shown without the comma or full stop that separated it from the next piece. Nothing inside a piece is changed.
- **(none today)**: today's prompts send this term's bare code at most (in the VOCABULARY block, a subtype list or the PHI TYPES block), and no words about it.
- **(shared)**: today's words about this term also name another term in the same breath and cannot be split without rewording. They are listed under "Text that belongs to no single term" below, not copied here.
- Retired terms carry no texts.

### 14a. Kinds (`rh.atom.kind`)

| Code | Sent in | Claude text, today's words | Source |
|---|---|---|---|
| `labValue` | observation | `lab test name spans (e.g. Glucose, Sodium)` | P:273 |
| `labValue` | diagnostic_report | `individual test name spans` | P:376 |
| `labValue` | general list | `lab test name spans referenced in narrative` **Changed by OR-49:** a lab result in note text is recorded like a table row, test name, value and units. | P:405 |
| `labPanel` | observation, diagnostic_report, general list | `panel or section headers that name a group of lab tests (e.g. "General Health Screen", "CBC With Differential/Platelet", "Urinalysis, Complete"). These are NOT individual test results.` | P:267 (sent at P:274, P:377, P:406) |
| `labPanel` | diagnostic_report | `Section header labels ("LABORATORY REPORT", "BASIC METABOLIC PANEL" if it's the report banner) MAY be atoms with kind=labPanel when they name an analyte family, otherwise are NOT atoms.` | P:385 |
| `vitalSign` | general list | `vital type spans (e.g. BP, HR, Temp, SpO2)` | P:404 |
| `finding` | observation, general list | `physical exam observations, imaging findings, lab interpretations stated as observations` | P:268 (sent at P:275, P:407) |
| `finding` | general list | `finding: physical exam observations, imaging findings, lab interpretations. A normal finding is an observation, NEVER a condition or diagnosis.` | P:426 |
| `encounter` | general list | `visit type (Office Visit, ED Visit, Telehealth, etc.)` | P:413 |
| `symptom` | general list | `chief complaint / HPI items the patient presents WITH` | P:399 |
| `symptom` | general list | `Negations are NOT symptoms. "No history of diabetes", "denies chest pain" — do NOT extract.` | P:419 |
| `condition` | general list | `ongoing clinical conditions (e.g. hypertension, diabetes, asthma)` | P:397 |
| `diagnosis` | general list | `formal Assessment/Impression conclusions from THIS visit` | P:398 |
| `medication` | medication_request, general list | `drug names; brand names go here, never under organization` | P:285, P:401 |
| `medication` | medication_request | `Dosage forms alone ("tablet", "capsule", "injection") are NOT medications. Only complete medication names.` | P:289 |
| `medication` | general list | `Dosage forms alone ("tablet", "capsule") are NOT medications. Only complete medication names.` | P:421 |
| `procedure` | general list | `surgical / interventional procedures performed` | P:402 |
| `immunization` | general list | `vaccine name spans` | P:403 |
| `carePlan` | general list | `plan items / goals (e.g. "Physical therapy 2x/week")` | P:410 |
| `referral` | service_request | `the requested service (e.g. ENT consult, MRI lumbar spine)` | P:362 |
| `referral` | general list | `service requests (e.g. ENT consult, MRI lumbar spine)` | P:409 |
| `device` | general list | `medical device names (implant / external / etc.)` | P:408 |
| `allergy` | general list | `allergens, including "No Known Allergies" / "NKA" / "NKDA"` | P:400 |
| `allergy` | general list | `allergy: extract medication, environmental, and food allergies. "NKA" / "NKDA" is itself an atom — emit it.` | P:427 |
| `familyHistory` | general list | `family member medical history (mother / father / sibling)` | P:411 |
| `familyHistory` | general list | `Family history is NOT a patient condition. "Mother had breast cancer" → kind=familyHistory.` | P:420 |
| `socialHistory` | general list | `social history categories (smoking, alcohol use, etc.)` | P:412 |
| `provider` | practitioner_role | `treating physicians (NOT lab techs / phlebotomists / radiology techs)` | P:315 |
| `provider` | practitioner_role | `Lab tech / phlebotomist / radiology tech is NOT a provider; treat staff names as out-of-scope.` | P:321 |
| `provider` | provenance | `signing / attesting physician` | P:345 |
| `provider` | service_request | `ordering / requesting physician` | P:359 |
| `provider` | diagnostic_report | `interpreting / performing physician named on the report banner` | P:380 |
| `organization` | practitioner_role | `healthcare facility, hospital, clinic, lab the practitioner acts for` | P:317 |
| `organization` | organization | `healthcare facility, hospital, clinic, lab, insurance company` | P:331 |
| `organization` | organization | `Brand-name drugs (FLONASE, TYLENOL, ADVIL, etc.) are NEVER organizations.` | P:336 |
| `organization` | service_request | `requesting facility` | P:361 |
| `providerContact` | practitioner_role | `phone / fax / email of a provider` | P:316 |
| `providerContact` | organization | `phone / fax / email associated with the organization` | P:332 |
| `providerContact` | service_request | `phone / fax / email of the requester` | P:360 |
| `dateAtom` | every section kind that offers it | `any date mention` | P:250, P:346, P:363, P:379 |
| `dateAtom` | patient | `Other labeled dates appearing here (e.g. Date of Service, Collection Date) follow the cross-cutting label rule.` | P:306 |
| `dateAtom` | all | `Labeled dates classify by their label.` | P:564 |
| `dateAtom` | all | `dateAtom emission is universal across all section kinds. When a date appears with a label naming what kind of date it is (e.g. "Date of Service: 03/15/2024", "Collection: 03/15/2024", "Reported: 03/18"), classify by the label. Use the role taxonomy: collection, report, visit, service, study, admission, discharge.` (The role list is rendered from the dictionary; this is how it renders today.) | P:580 |
| `coverage` | | (none today) | |
| `documentReference` | provenance | `accession number, order number, document type, etc.` | P:347 |
| `documentReference` | service_request | `order number, accession number` | P:364 |
| `documentReference` | diagnostic_report | `accession number, order number, document type` | P:378 |
| `recordSummary` | | (none today). Not offered to the AI (OR-51). | |
| `patientDemographic` | patient | `name, DOB, sex, blood type, pronouns, age, race, ethnicity` | P:295 |
| `patientIdentifier` | patient | `MRN, SSN, member number, encounter number, etc.` | P:296 |
| `patientIdentifier` | patient | `patientIdentifier subtypes: see the SUBTYPE list below.` | P:305 |
| `patientContact` | patient | `phone, email, fax of the patient` | P:297 |
| `patientAddress` | patient | `street/city/state/zip of the patient` | P:298 |
| `guardianInfo` | patient | `guardian's name / relationship / contact` | P:299 |
| `emergencyContact` | patient | `emergency contact name / relationship / contact` | P:300 |
| `uncategorized` | observation, service_request, diagnostic_report, general list | `atom that doesn't fit any other kind` | P:277, P:365, P:381, P:415 |

### 14b. Subtypes (`rh.atom.subtype`)

| Code | Sent in | Claude text, today's words | Source |
|---|---|---|---|
| `accessionNumber` | | (none today) | |
| `age` | | (none today) | |
| `billingAccountNumber` | | (none today) | |
| `bloodType` | | (none today) | |
| `city` | | (none today) | |
| `credentials` | | (none today) | |
| `dateOfBirth` | patient | `DOB in this section is kind=patientDemographic subtype=dateOfBirth, NOT dateAtom.` | P:306 |
| `dateOfBirth` | all | `DOB is the one exception (patientDemographic, not dateAtom).` | P:564 |
| `dateOfBirth` | all | `Date of birth is the one exception to dateAtom: classify it as kind=patientDemographic with subtype=dateOfBirth, NOT as dateAtom — regardless of how it is labeled or which section it appears in.` | P:581 |
| `departmentName` | | (none today) | |
| `documentType` | | (none today) | |
| `email` | | (none today) | |
| `encounterNumber` | | (none today) | |
| `ethnicity` | | (none today) | |
| `facilityName` | | (none today) | |
| `fax` | | (none today) | |
| `genderIdentity` | | (none today) | |
| `memberNumber` | | (none today) | |
| `mrn` | | (none today) | |
| `name` | | (none today) | |
| `npi` | | (none today) | |
| `orderNumber` | | (none today) | |
| `phone` | | (none today) | |
| `pronouns` | | (none today) | |
| `race` | | (none today) | |
| `relationship` | | (none today) | |
| `role` | | (none today) | |
| `sex` | | (none today) | |
| `sexAssignedAtBirth` | | (none today) | |
| `specialty` | | (none today) | |
| `ssn` | | (none today) | |
| `ssnLastFour` | | (none today) | |
| `state` | | (none today) | |
| `street` | | (none today) | |
| `subscriberNumber` | | (none today) | |
| `unspecifiedContact` | | (none today) | |
| `unspecifiedIdentifier` | | (none today) | |
| `zip` | | (none today) | |

### 14c. Date roles (`rh.atom.date-role`)

| Code | Sent in | Claude text, today's words | Source |
|---|---|---|---|
| `admission` | | (shared) | |
| `collection` | every section kind that offers `dateAtom`, except provenance and service_request | `'collection' for specimen collection/lab draw dates` | P:250, P:379 |
| `discharge` | | (shared) | |
| `narrativeReference` | every section kind that offers `dateAtom`, except provenance | `'narrativeReference' for prose date mentions` | P:250, P:363, P:379 |
| `narrativeReference` | provenance | `'narrativeReference' for dates mentioned in prose without being the date of a current event` | P:346 |
| `narrativeReference` | all | `Unlabeled prose dates inside clinician notes are narrativeReference.` | P:564 |
| `narrativeReference` | all | `narrativeReference is reserved for unlabeled dates inside running prose, such as dates mentioned in clinician notes describing past events ("similar elevation in 2019").` | P:580 |
| `report` | every section kind that offers `dateAtom`, except provenance and service_request | `'report' for report generation dates` | P:250, P:379 |
| `report` | provenance | `'report' for document generation dates` | P:346 |
| `report` | service_request | `'report' for order document generation dates` | P:363 |
| `service` | every section kind that offers `dateAtom`, except provenance | `'service' for billing-legal service dates` | P:250, P:363, P:379 |
| `study` | every section kind that offers `dateAtom`, except provenance and service_request | `'study' for imaging study dates` | P:250, P:379 |
| `visit` | every section kind that offers `dateAtom`, except provenance | `'visit' for clinical visit dates` | P:250, P:363, P:379 |

### 14d. Classification certainty (`rh.certainty`)

| Code | Sent in | Claude text, today's words | Source |
|---|---|---|---|
| `specific` | all | `"specific" = confident in kind+subtype` | P:579 |
| `parent_only` | all | `"parent_only" = confident in kind, uncertain subtype` | P:579 |
| `low_confidence` | all | `"low_confidence" = uncertain even at parent` | P:579 |

### 14e. PHI types (`rh.phi.type`)

| Code | Sent in | Claude text, today's words | Source |
|---|---|---|---|
| `accessionNumber` | | (shared) | |
| `accountNumber` | | (shared) | |
| `biometric` | | (none today) | |
| `dateOfAdmission` | | (none today) | |
| `dateOfDischarge` | | (none today) | |
| `dateOfReport` | | (shared) | |
| `dateOfService` | | (shared) | |
| `dateSigned` | | (none today) | |
| `deviceIdentifier` | | (none today) | |
| `dob` | | (none today) | |
| `emergencyContactName` | | (none today) | |
| `facilityAddress` | | (none today) | |
| `facilityName` | | (none today) | |
| `guardianName` | | (none today) | |
| `ipAddress` | | (none today) | |
| `licenseNumber` | | (none today) | |
| `memberNumber` | | (none today) | |
| `mrn` | | (none today) | |
| `otherIdentifier` | | (none today) | |
| `patientAddress` | | (none today) | |
| `patientEmail` | | (none today) | |
| `patientFax` | | (none today) | |
| `patientName` | | (none today) | |
| `patientPhone` | | (none today) | |
| `photograph` | | (none today) | |
| `providerAddress` | | (none today) | |
| `providerEmail` | | (none today) | |
| `providerFax` | | (none today) | |
| `providerName` | | (none today) | |
| `providerPhone` | | (none today) | |
| `ssn` | | (none today) | |
| `ssnLastFour` | | (none today) | |
| `staffName` | PHI pass | `Staff names (techs, nurses, signing physicians) are PHI under staffName when they don't fit providerName.` (two source lines, joined by one space) | P:1115-1116 |
| `unrecognized` | | (none today). Not offered to the AI (OR-43). | |
| `urlOrHandle` | | (none today) | |
| `vehicleIdentifier` | | (none today) | |

### 14f. Namespaces today's prompts do not describe

- `rh.section.kind`: the Atom Pass prompt names section kinds by bare code only (the tentative classification at P:567 and the nine-kind routing list beside it; the PHI pass's section list at P:1127). No words about any section kind.
- `rh.atom.kind-group`, `rh.section.kind-group`, `rh.column-role` and `rh.extraction-confidence`: not sent to Claude at all.
- `rh.reliability`: retired in version 10 (section 7). Today's words are listed below so nothing is lost.

### 14g. Text that belongs to no single term (not copied above)

Listed for the owner, not carried by any term.

**Two or more terms in one breath**

| Today's words | Terms named | Source |
|---|---|---|
| `'admission'/'discharge' for inpatient encounter bounds` | `admission`, `discharge` | P:250, P:379 |
| `ORG vs MEDICATION: a word in all-caps is NOT automatically an organization. Brand-name drugs are kind=medication, never organization.` | `organization`, `medication` | P:290 |
| `"Electronically signed by X on date" → provider atom (the name) + dateAtom atom with date_role='report' (the date).` | `provider`, `dateAtom`, `report` | P:350 |
| `(Date roles are NOT documentReference subtypes — emit kind=dateAtom with the appropriate date_role above.)` | `documentReference`, `dateAtom` | P:390 |
| General list rule 5, condition vs diagnosis vs symptom, with its three cue lines | `condition`, `diagnosis`, `symptom` | P:422-425 |
| General list rule 8, generic educational or boilerplate text | `condition`, `symptom`, `socialHistory`, `familyHistory` | P:428 |
| General list rule 9, labPanel vs labValue | `labPanel`, `labValue` | P:429 |
| The worked date example's three output lines | `patientDemographic`, `dateOfBirth`, `dateAtom`, `service`, `narrativeReference` | P:559-562 |
| PHI pass rule 2, direct identifiers always PHI even when partial | several PHI types | P:1110-1111 |
| PHI pass rule 3, clinical content not PHI on its own | several kinds | P:1112-1113 |
| PHI pass rule 4, provider and facility names are PHI | `providerName`, `facilityName` by implication | P:1114 |
| PHI pass rule 7, visit and report dates are PHI | `dateOfService`, `dateOfReport` | P:1119-1120 |
| PHI pass rule 8, accession, order and billing account numbers | `accessionNumber`, `accountNumber` | P:1121-1122 |
| The subtype lists per kind group, and the open-vocabulary line for provider | bare codes per kind | P:308-310, P:324-326, P:339-340, P:353-354, P:370-371, P:387-388, P:489 |

**No term at all**

| Today's words | Source |
|---|---|
| The prompt header, input format, how to point, one atom per clinical fact, and the four-atom example | P:510-550 |
| The section classification preamble and the nine-kind routing list (OR-50) | P:566-569 |
| `Emit atoms over distinct verbatim spans only. Tabular lab cells are emitted deterministically by the CELL walker before this pass — do not re-emit them.` (observation) | P:280 |
| Section header labels are NOT atoms (patient, practitioner_role, organization, provenance, service_request, general list rule 1) | P:304, P:322, P:337, P:351, P:368, P:418 |
| `Individual lab analyte rows are NOT extracted here — they belong to nested observation children. This section's atoms cover the report banner, collection date, accession number, etc.` (diagnostic_report) | P:384 |
| The lead-ins `Set date_role:` and `Set date_role accordingly:` inside the `dateAtom` hints | P:250, P:346, P:363, P:379 |
| The cross-cutting rules on one atom per fact, one line per pointer, and word_end; the `classification_certainty:` lead-in | P:575-577, P:579 |
| The return format, including `date_role: required when kind="dateAtom", otherwise null.` | P:585-613 |
| The PHI pass opening, return format, PHI TYPES heading, the rules heading, rules 1 and 6, section list and closing | P:1088-1106, P:1108-1109, P:1117-1118, P:1124-1135 |
| Every field and tool description in `recordhealth-api/src/extractor-vocabulary.mjs` (field-level, never per term), and the VOCABULARY and PHI TYPES block headings | extractor-vocabulary.mjs:241-256, 299, 324, 340, 346, 401, 425 |

**Words about terms version 10 retires**

| Today's words | Terms | Source |
|---|---|---|
| `reliability: "high" = the word range captures exactly the value; "medium" = the range includes a label or punctuation you could not leave out; "low" = uncertain which words carry the value.` | `rh.reliability` `high`, `medium`, `low` (retired, section 7) | P:578 |

---

## 15. LlamaExtract text (amendment awaiting approval, OR-73)

Each field description LlamaExtract is given today, copied word for word from `DATA_SCHEMA` in `recordhealth-api/src/ingest-do.mjs` (written `D:`), with the dictionary term the adapter fills from it (`recordhealth-api/src/llama-extract-adapter.mjs`, written `A:`). Used from piece g. The adapter's own spellings `patientName` and `facility` are read as `name` and `facilityName` (OR-37).

### 15a. Fields that fill a dictionary term

| Field | LlamaExtract text, today's words | Fills | Source |
|---|---|---|---|
| `patient.name` | `Patient full name` | kind `patientDemographic`, subtype `name` | D:489, A:1142 |
| `patient.date_of_birth` | `Patient date of birth` | kind `patientDemographic`, subtype `dateOfBirth` | D:490, A:1143 |
| `patient.sex` | `Patient sex/gender` | kind `patientDemographic`, subtype `sex` | D:491, A:1144 |
| `patient.street_address` | `Patient street address, usually on the line labeled 'Address:' in the patient demographics section (e.g. 2676 S Redondo Blvd)` | kind `patientAddress`, subtype `street` | D:492, A:1145 |
| `patient.city` | `Patient city, usually on the line labeled 'City, ST Zip' or 'City/State/Zip' in the patient demographics section (e.g. Los Angeles)` | kind `patientAddress`, subtype `city` | D:493, A:1146 |
| `patient.state` | `Patient US state abbreviation, usually on the same line as city and zip code (e.g. CA)` | kind `patientAddress`, subtype `state` | D:494, A:1147 |
| `patient.zip_code` | `Patient zip or postal code, usually on the same line as city and state (e.g. 90016)` | kind `patientAddress`, subtype `zip` | D:495, A:1148 |
| `patient.phone` | `Patient phone number` | kind `patientContact`, subtype `phone` | D:496, A:1149 |
| `patient.medical_record_number` | `MRN or patient identifier` | kind `patientIdentifier`, subtype `mrn` | D:497, A:1150 |
| `providers[].name` | `Provider name` | kind `provider`; its subtype is the role's own words when a role is given, else none (open for `provider`) | D:506, A:1215-1220 |
| `providers[].npi` | `NPI number` | kind `provider`, subtype `npi` | D:507, A:1225-1230 |
| `providers[].organization` | `Organization or facility name` | kind `organization`, no subtype | D:508, A:1235-1240 |
| `lab_results[].panel_name` | `The panel, section, or test group header this lab result belongs to. Look for bold or larger-font headers above groups of test rows (e.g. 'General Health Screen', 'CBC With Differential/Platelet', 'Urinalysis, Complete', 'Lipid Panel'). Every lab result that falls under a visible group header must have that header as its panel_name. Do not leave null if a group header is visible above the test.` | kind `labPanel` | D:519, A:1044-1047 |
| `lab_results[].test_name` | `Analyte or test name` | kind `labValue` | D:520, A:1106-1109 |
| `dates.collection_date` | `Specimen collection date` | kind `dateAtom`, date role `collection` | D:533, A:1263 |
| `dates.report_date` | `Report or result date` | kind `dateAtom`, date role `report` | D:534, A:1264 |
| `dates.received_date` | `Specimen received date` | kind `dateAtom`, date role `narrativeReference` | D:535, A:1265 |
| `dates.service_date` | `Date of service or encounter date, as labeled on the document. Not the same as specimen collection date.` | kind `dateAtom`, date role `service` | D:536, A:1266 |
| `facility` | `The facility, institution, hospital, clinic, or laboratory where the service was performed or the document originated` | kind `organization`, subtype `facilityName` | D:541, A:1248-1253 |

When two date fields carry the same value, the adapter makes one fact, with the date role of the first field in the order above (A:1268-1277).

### 15b. Fields that fill no dictionary term

| Field | LlamaExtract text, today's words | What the adapter does with it | Source |
|---|---|---|---|
| `patient` | `Patient demographics` | Container for the patient fields | D:487 |
| `providers` | `All healthcare providers mentioned` | Container for the provider fields | D:502 |
| `providers[].role` | `Provider role (ordering, performing, etc.)` | No fact of its own: its words become the subtype of the provider name fact | D:509, A:1213-1220 |
| `lab_results` | `Every lab test result in the document` | Container for the lab fields | D:515 |
| `lab_results[].value` | `Result value` | No fact of its own: carried in the `labValue` fact's lab payload | D:521, A:619-633 |
| `lab_results[].units` | `Unit of measurement` | The same | D:522, A:619-633 |
| `lab_results[].reference_range` | `Normal reference range` | The same | D:523, A:619-633 |
| `lab_results[].flag` | `Abnormal flag (high, low, critical, etc.)` | The same | D:524, A:619-633 |
| `lab_results[].page` | `Page number where this result appears` | Location only, a fallback page for the row | D:525, A:1096-1097 |
| `dates` | `Key dates in the document` | Container for the date fields | D:531 |

The adapter also holds a table naming `test_name`, `value`, `units`, `reference_range` and `flag` as the column roles `analyte_name`, `value`, `units`, `reference_range` and `flag` (A:55-61), but nothing reads it: every lab fact it makes has no column role.

`SYSTEM_PROMPT` (D:480) is one instruction for the whole document and belongs to no field or term.
