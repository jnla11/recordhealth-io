#!/usr/bin/env python3
"""
MIMIC-IV Data Extractor — Step 1 (Complete)
Keeps ALL fields from source data. Nothing dropped.
Runs entirely locally. No network calls. No PHI leaves this machine.

subject_id and hadm_id are hashed but the hashes are consistent,
so the same patient gets the same hash across all output files.
"""

import csv
import gzip
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# ─── Config ───────────────────────────────────────────────
MIMIC_DIR = Path.home() / "Projects/RecordHealth.IO/SeedCorpus/mimic-iv/physionet.org/files/mimiciv/3.1/hosp"
OUTPUT_DIR = Path("data/mimic")
LABS_DIR = OUTPUT_DIR / "labs"
MEDS_DIR = OUTPUT_DIR / "medications"

LAB_LIMIT = 400
MED_LIMIT = 300
HASH_LENGTH = 12

# Consistent salt so same IDs always produce same hashes
HASH_SALT = "recordhealth-seed-v1"


def hash_id(value):
    """Consistent one-way hash. Same input always produces same output."""
    return hashlib.sha256(f"{HASH_SALT}:{value}".encode()).hexdigest()[:HASH_LENGTH]


def read_gz_csv(filepath):
    """Read a gzipped CSV, yield dicts."""
    print(f"  Reading {filepath.name}...", end=" ", flush=True)
    count = 0
    with gzip.open(filepath, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row
            count += 1
    print(f"{count:,} rows")
    return count


# ─── Lab Result Extractor ─────────────────────────────────
def extract_labs():
    print("\n═══ Lab Result Extractor ═══")

    # Load FULL lab item dictionary — every field
    d_labitems_path = MIMIC_DIR / "d_labitems.csv.gz"
    if not d_labitems_path.exists():
        print(f"  ERROR: {d_labitems_path} not found")
        return []

    lab_items = {}
    for row in read_gz_csv(d_labitems_path):
        lab_items[row["itemid"]] = {
            "itemid": row["itemid"],
            "label": row.get("label", ""),
            "fluid": row.get("fluid", ""),
            "category": row.get("category", ""),
            "loinc_code": row.get("loinc_code", ""),
        }
    print(f"  Loaded {len(lab_items):,} lab item definitions")
    loinc_mapped = sum(1 for v in lab_items.values() if v["loinc_code"])
    print(f"  LOINC codes available: {loinc_mapped:,} / {len(lab_items):,}")

    # Read ALL lab event fields, group by hadm_id
    labevents_path = MIMIC_DIR / "labevents.csv.gz"
    if not labevents_path.exists():
        print(f"  ERROR: {labevents_path} not found")
        return []

    # Track subject_id → hadm_id mapping for patient linkage
    patient_encounters = defaultdict(set)
    encounters = defaultdict(lambda: {"subject_hash": None, "results": []})
    row_count = 0

    print(f"  Reading labevents (this may take a minute)...", flush=True)
    with gzip.open(labevents_path, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hadm_id = row.get("hadm_id", "").strip()
            subject_id = row.get("subject_id", "").strip()
            if not hadm_id:
                continue

            itemid = row.get("itemid", "")
            item_info = lab_items.get(itemid, {})

            subject_hash = hash_id(subject_id)
            encounter_hash = hash_id(hadm_id)

            patient_encounters[subject_hash].add(encounter_hash)
            encounters[hadm_id]["subject_hash"] = subject_hash

            result = {
                # Event identity
                "labevent_id": row.get("labevent_id", ""),
                "specimen_id": row.get("specimen_id", ""),
                # Item info (from d_labitems join)
                "itemid": itemid,
                "label": item_info.get("label", f"item_{itemid}"),
                "fluid": item_info.get("fluid", ""),
                "category": item_info.get("category", ""),
                "loinc_code": item_info.get("loinc_code", ""),
                # Values
                "value": row.get("value", ""),
                "valuenum": row.get("valuenum", ""),
                "valueuom": row.get("valueuom", ""),
                # Reference ranges
                "ref_range_lower": row.get("ref_range_lower", ""),
                "ref_range_upper": row.get("ref_range_upper", ""),
                # Flags and status
                "flag": row.get("flag", ""),
                "priority": row.get("priority", ""),
                "comments": row.get("comments", ""),
                # Timestamps
                "charttime": row.get("charttime", ""),
                "storetime": row.get("storetime", ""),
                "order_provider_id": hash_id(row.get("order_provider_id", "")) if row.get("order_provider_id", "").strip() else "",
            }
            encounters[hadm_id]["results"].append(result)

            row_count += 1
            if row_count % 1_000_000 == 0:
                print(f"    ...{row_count:,} rows, {len(encounters):,} encounters", flush=True)

            # Stop early once we have enough qualifying encounters
            qualifying = sum(1 for e in encounters.values() if len(e["results"]) >= 5)
            if qualifying >= LAB_LIMIT * 2:
                break

    print(f"  Total: {row_count:,} rows across {len(encounters):,} encounters")

    # Filter to encounters with at least 5 results
    qualifying = {k: v for k, v in encounters.items() if len(v["results"]) >= 5}
    selected = dict(list(qualifying.items())[:LAB_LIMIT])
    print(f"  Selected {len(selected)} encounters (>= 5 results each)")

    # Write output
    LABS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_entries = []

    for hadm_id, data in selected.items():
        encounter_hash = hash_id(hadm_id)
        subject_hash = data["subject_hash"]

        output = {
            "subject_hash": subject_hash,
            "encounter_hash": encounter_hash,
            "encounter_count_for_patient": len(patient_encounters.get(subject_hash, set())),
            "result_count": len(data["results"]),
            "results": data["results"],
        }

        out_path = LABS_DIR / f"{encounter_hash}.json"
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)

        manifest_entries.append({
            "file": f"labs/{encounter_hash}.json",
            "category": "labReport",
            "subject_hash": subject_hash,
            "encounter_hash": encounter_hash,
            "result_count": len(data["results"]),
        })

    # Patient linkage stats
    multi_encounter = sum(1 for encs in patient_encounters.values() if len(encs) > 1)
    print(f"  Unique patients in selected: {len(set(d['subject_hash'] for d in selected.values()))}")
    print(f"  Patients with multiple encounters: {multi_encounter}")
    print(f"  Wrote {len(manifest_entries)} lab encounter files to {LABS_DIR}/")
    return manifest_entries


# ─── Medication Extractor ─────────────────────────────────
def extract_medications():
    print("\n═══ Medication Extractor ═══")

    prescriptions_path = MIMIC_DIR / "prescriptions.csv.gz"
    if not prescriptions_path.exists():
        print(f"  ERROR: {prescriptions_path} not found")
        return []

    patient_encounters = defaultdict(set)
    encounters = defaultdict(lambda: {"subject_hash": None, "medications": []})
    row_count = 0

    for row in read_gz_csv(prescriptions_path):
        hadm_id = row.get("hadm_id", "").strip()
        subject_id = row.get("subject_id", "").strip()
        if not hadm_id:
            continue

        subject_hash = hash_id(subject_id)
        encounter_hash = hash_id(hadm_id)
        patient_encounters[subject_hash].add(encounter_hash)
        encounters[hadm_id]["subject_hash"] = subject_hash

        med = {
            # Identity
            "pharmacy_id": row.get("pharmacy_id", ""),
            "poe_id": row.get("poe_id", ""),
            "poe_seq": row.get("poe_seq", ""),
            "order_provider_id": hash_id(row.get("order_provider_id", "")) if row.get("order_provider_id", "").strip() else "",
            # Drug info
            "drug": row.get("drug", ""),
            "drug_type": row.get("drug_type", ""),
            "formulary_drug_cd": row.get("formulary_drug_cd", ""),
            "gsn": row.get("gsn", ""),
            "ndc": row.get("ndc", ""),
            "prod_strength": row.get("prod_strength", ""),
            # Dosing
            "dose_val_rx": row.get("dose_val_rx", ""),
            "dose_unit_rx": row.get("dose_unit_rx", ""),
            "form_val_disp": row.get("form_val_disp", ""),
            "form_unit_disp": row.get("form_unit_disp", ""),
            "doses_per_24_hrs": row.get("doses_per_24_hrs", ""),
            "form_rx": row.get("form_rx", ""),
            "route": row.get("route", ""),
            # Timing
            "starttime": row.get("starttime", ""),
            "stoptime": row.get("stoptime", ""),
        }
        encounters[hadm_id]["medications"].append(med)

        row_count += 1
        if row_count % 500_000 == 0:
            print(f"    ...{row_count:,} rows, {len(encounters):,} encounters", flush=True)

        if len(encounters) >= MED_LIMIT * 2:
            break

    print(f"  Total: {row_count:,} rows across {len(encounters):,} encounters")

    selected = dict(list(encounters.items())[:MED_LIMIT])
    print(f"  Selected {len(selected)} encounters")

    # Write output
    MEDS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_entries = []

    for hadm_id, data in selected.items():
        encounter_hash = hash_id(hadm_id)
        subject_hash = data["subject_hash"]

        output = {
            "subject_hash": subject_hash,
            "encounter_hash": encounter_hash,
            "encounter_count_for_patient": len(patient_encounters.get(subject_hash, set())),
            "medication_count": len(data["medications"]),
            "medications": data["medications"],
        }

        out_path = MEDS_DIR / f"{encounter_hash}.json"
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)

        manifest_entries.append({
            "file": f"medications/{encounter_hash}.json",
            "category": "medications",
            "subject_hash": subject_hash,
            "encounter_hash": encounter_hash,
            "medication_count": len(data["medications"]),
        })

    unique_patients = len(set(d["subject_hash"] for d in selected.values()))
    print(f"  Unique patients: {unique_patients}")
    print(f"  Wrote {len(manifest_entries)} medication files to {MEDS_DIR}/")
    return manifest_entries


# ─── Patient Index ────────────────────────────────────────
def build_patient_index(manifest_entries):
    """Build a patient-level index showing which encounters belong to which patient."""
    print("\n═══ Patient Index ═══")

    patients = defaultdict(lambda: {"encounters": [], "categories": set()})

    for entry in manifest_entries:
        sh = entry.get("subject_hash", "")
        if not sh:
            continue
        patients[sh]["encounters"].append({
            "encounter_hash": entry["encounter_hash"],
            "category": entry["category"],
            "file": entry["file"],
        })
        patients[sh]["categories"].add(entry["category"])

    # Convert sets to lists for JSON
    patient_index = {}
    for sh, data in patients.items():
        patient_index[sh] = {
            "subject_hash": sh,
            "encounter_count": len(data["encounters"]),
            "categories": sorted(data["categories"]),
            "encounters": data["encounters"],
            "has_labs_and_meds": "labReport" in data["categories"] and "medications" in data["categories"],
        }

    index_path = OUTPUT_DIR / "patient_index.json"
    with open(index_path, "w") as f:
        json.dump(patient_index, f, indent=2)

    multi = sum(1 for p in patient_index.values() if p["encounter_count"] > 1)
    both = sum(1 for p in patient_index.values() if p["has_labs_and_meds"])
    print(f"  Total unique patients: {len(patient_index)}")
    print(f"  Patients with multiple encounters: {multi}")
    print(f"  Patients with both labs and meds: {both}")
    print(f"  Index written to {index_path}")


# ─── PHI Validation ───────────────────────────────────────
def validate_no_phi(directory):
    """Scan output files for obvious PHI patterns."""
    import re

    phi_patterns = [
        (re.compile(r"\d{3}-\d{2}-\d{4}"), "SSN pattern"),
        (re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}"), "phone number"),
    ]

    issues = []
    for json_file in Path(directory).rglob("*.json"):
        content = json_file.read_text()
        for pattern, label in phi_patterns:
            matches = pattern.findall(content)
            if matches:
                issues.append(f"  {json_file.name}: {label} ({len(matches)} matches)")

    return issues


# ─── Main ─────────────────────────────────────────────────
def main():
    print("╔═══════════════════════════════════════════╗")
    print("║  MIMIC-IV Extractor — Complete (v2)        ║")
    print("║  ALL fields preserved. Patient linkage.    ║")
    print("║  All processing is LOCAL. No network.      ║")
    print("╚═══════════════════════════════════════════╝")

    # Verify source files exist
    required = ["labevents.csv.gz", "d_labitems.csv.gz", "prescriptions.csv.gz"]
    missing = [f for f in required if not (MIMIC_DIR / f).exists()]
    if missing:
        print(f"\nERROR: Missing files in {MIMIC_DIR}:")
        for f in missing:
            print(f"  - {f}")
        sys.exit(1)

    print(f"\nSource: {MIMIC_DIR}")
    print(f"Output: {OUTPUT_DIR}")

    # Run extractors
    all_manifest = []

    lab_entries = extract_labs()
    if lab_entries:
        all_manifest.extend(lab_entries)

    med_entries = extract_medications()
    if med_entries:
        all_manifest.extend(med_entries)

    # Build patient index
    build_patient_index(all_manifest)

    # Write manifest
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "2.0",
        "source": "mimic-iv",
        "extractors_run": ["LabResultExtractor", "MedicationExtractor"],
        "total_files": len(all_manifest),
        "fields_preserved": "ALL — no fields dropped from source",
        "patient_linkage": "subject_hash consistent across labs and meds",
        "loinc_source": "d_labitems.loinc_code (native MIMIC mapping)",
        "files": all_manifest,
    }

    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest written to {manifest_path}")

    # Validate
    print("\n═══ PHI Validation ═══")
    issues = validate_no_phi(OUTPUT_DIR)
    if issues:
        print(f"  ⚠️  {len(issues)} potential PHI patterns found:")
        for issue in issues[:20]:
            print(issue)
    else:
        print("  ✓ No PHI patterns detected")

    print(f"\n═══ Done ═══")
    print(f"  {len(all_manifest)} files written to {OUTPUT_DIR}/")
    print(f"  Next step: python3 scripts/document_renderer.py")


if __name__ == "__main__":
    main()
