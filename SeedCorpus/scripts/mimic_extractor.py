#!/usr/bin/env python3
"""
MIMIC-IV Data Extractor — Step 1 (Labs + Medications)
Runs entirely locally. No network calls. No PHI leaves this machine.

Reads from ~/mimic-iv/ and produces structured JSON at data/mimic/
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

LAB_LIMIT = 400        # encounters with at least 5 results
MED_LIMIT = 300        # encounters
HASH_LENGTH = 12       # truncated SHA-256 for IDs


def hash_id(value):
    """One-way hash for patient/encounter identifiers."""
    return hashlib.sha256(str(value).encode()).hexdigest()[:HASH_LENGTH]


def read_gz_csv(filepath, limit=None):
    """Read a gzipped CSV, yield dicts."""
    print(f"  Reading {filepath.name}...", end=" ", flush=True)
    count = 0
    with gzip.open(filepath, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row
            count += 1
            if limit and count >= limit:
                break
    print(f"{count:,} rows")


# ─── Lab Result Extractor ─────────────────────────────────
def extract_labs():
    print("\n═══ Lab Result Extractor ═══")
    
    # Load lab item dictionary
    d_labitems_path = MIMIC_DIR / "d_labitems.csv.gz"
    if not d_labitems_path.exists():
        print(f"  ERROR: {d_labitems_path} not found")
        return
    
    lab_items = {}
    for row in read_gz_csv(d_labitems_path):
        lab_items[row["itemid"]] = {
            "label": row.get("label", ""),
            "fluid": row.get("fluid", ""),
            "category": row.get("category", ""),
        }
    print(f"  Loaded {len(lab_items):,} lab item definitions")
    
    # Read lab events, group by hadm_id
    labevents_path = MIMIC_DIR / "labevents.csv.gz"
    if not labevents_path.exists():
        print(f"  ERROR: {labevents_path} not found")
        return
    
    encounters = defaultdict(list)
    row_count = 0
    
    print(f"  Reading labevents (this may take a minute)...", flush=True)
    with gzip.open(labevents_path, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hadm_id = row.get("hadm_id", "").strip()
            if not hadm_id:
                continue
            
            itemid = row.get("itemid", "")
            item_info = lab_items.get(itemid, {})
            
            result = {
                "label": item_info.get("label", f"item_{itemid}"),
                "fluid": item_info.get("fluid", ""),
                "category": item_info.get("category", ""),
                "value": row.get("value", ""),
                "valuenum": row.get("valuenum", ""),
                "valueuom": row.get("valueuom", ""),
                "ref_range_lower": row.get("ref_range_lower", ""),
                "ref_range_upper": row.get("ref_range_upper", ""),
                "flag": row.get("flag", ""),
                "charttime": row.get("charttime", ""),
            }
            encounters[hadm_id].append(result)
            
            row_count += 1
            if row_count % 1_000_000 == 0:
                print(f"    ...{row_count:,} rows, {len(encounters):,} encounters", flush=True)
            
            # Stop early if we have enough encounters with 5+ results
            if len([e for e in encounters.values() if len(e) >= 5]) >= LAB_LIMIT * 2:
                break
    
    print(f"  Total: {row_count:,} rows across {len(encounters):,} encounters")
    
    # Filter to encounters with at least 5 results
    qualifying = {k: v for k, v in encounters.items() if len(v) >= 5}
    selected = dict(list(qualifying.items())[:LAB_LIMIT])
    print(f"  Selected {len(selected)} encounters (>= 5 results each)")
    
    # Write output
    LABS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_entries = []
    
    for hadm_id, results in selected.items():
        hadm_hash = hash_id(hadm_id)
        output = {
            "encounter_hash": hadm_hash,
            "result_count": len(results),
            "results": results,
        }
        
        out_path = LABS_DIR / f"{hadm_hash}.json"
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        
        manifest_entries.append({
            "file": f"labs/{hadm_hash}.json",
            "category": "labReport",
            "result_count": len(results),
            "hash": hadm_hash,
        })
    
    print(f"  Wrote {len(manifest_entries)} lab encounter files to {LABS_DIR}/")
    return manifest_entries


# ─── Medication Extractor ─────────────────────────────────
def extract_medications():
    print("\n═══ Medication Extractor ═══")
    
    prescriptions_path = MIMIC_DIR / "prescriptions.csv.gz"
    if not prescriptions_path.exists():
        print(f"  ERROR: {prescriptions_path} not found")
        return
    
    encounters = defaultdict(list)
    row_count = 0
    
    for row in read_gz_csv(prescriptions_path):
        hadm_id = row.get("hadm_id", "").strip()
        if not hadm_id:
            continue
        
        med = {
            "drug": row.get("drug", ""),
            "drug_type": row.get("drug_type", ""),
            "formulary_drug_cd": row.get("formulary_drug_cd", ""),
            "gsn": row.get("gsn", ""),
            "ndc": row.get("ndc", ""),
            "prod_strength": row.get("prod_strength", ""),
            "dose_val_rx": row.get("dose_val_rx", ""),
            "dose_unit_rx": row.get("dose_unit_rx", ""),
            "route": row.get("route", ""),
            "starttime": row.get("starttime", ""),
            "stoptime": row.get("stoptime", ""),
        }
        encounters[hadm_id].append(med)
        
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
    
    for hadm_id, meds in selected.items():
        hadm_hash = hash_id(hadm_id)
        output = {
            "encounter_hash": hadm_hash,
            "medication_count": len(meds),
            "medications": meds,
        }
        
        out_path = MEDS_DIR / f"{hadm_hash}.json"
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        
        manifest_entries.append({
            "file": f"medications/{hadm_hash}.json",
            "category": "medications",
            "medication_count": len(meds),
            "hash": hadm_hash,
        })
    
    print(f"  Wrote {len(manifest_entries)} medication files to {MEDS_DIR}/")
    return manifest_entries


# ─── PHI Validation ───────────────────────────────────────
def validate_no_phi(directory):
    """Scan output files for obvious PHI patterns."""
    import re
    
    phi_patterns = [
        (re.compile(r"\d{2}/\d{2}/\d{4}"), "date MM/DD/YYYY"),
        (re.compile(r"\d{3}-\d{2}-\d{4}"), "SSN pattern"),
        (re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}"), "phone number"),
        (re.compile(r"[A-Z][a-z]+\s[A-Z][a-z]+"), "possible name"),
    ]
    
    issues = []
    for json_file in Path(directory).rglob("*.json"):
        content = json_file.read_text()
        for pattern, label in phi_patterns:
            matches = pattern.findall(content)
            if matches and label == "possible name":
                # Filter out common medical terms
                medical_terms = {"Blood Gas", "Red Blood", "White Blood", "Total Cholesterol",
                                "Uric Acid", "Folic Acid", "Free Calcium", "Direct Bilirubin",
                                "Urine Culture", "Chest Pain", "Blood Pressure", "Heart Rate"}
                matches = [m for m in matches if m not in medical_terms]
            if matches:
                issues.append(f"  {json_file.name}: {label} ({len(matches)} matches)")
    
    return issues


# ─── Main ─────────────────────────────────────────────────
def main():
    print("╔═══════════════════════════════════════╗")
    print("║  MIMIC-IV Extractor — Labs + Meds     ║")
    print("║  All processing is LOCAL. No network.  ║")
    print("╚═══════════════════════════════════════╝")
    
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
    
    # Write manifest
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "1.0",
        "source": "mimic-iv",
        "extractors_run": ["LabResultExtractor", "MedicationExtractor"],
        "total_files": len(all_manifest),
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
        print("  Review these before proceeding.")
    else:
        print("  ✓ No obvious PHI patterns detected")
    
    print(f"\n═══ Done ═══")
    print(f"  {len(all_manifest)} files written to {OUTPUT_DIR}/")
    print(f"  Next step: python scripts/document_renderer.py")


if __name__ == "__main__":
    main()
