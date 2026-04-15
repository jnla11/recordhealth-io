#!/usr/bin/env python3
"""
Batch Ingest — Push rendered PDFs + ground truth to SEED API.
Reads from data/rendered/ and data/ground_truth/, POSTs to the Worker.

Requires: SEED_API_KEY environment variable
"""

import json
import base64
import sys
import os
import time
import hashlib
from pathlib import Path

try:
    import urllib.request
    import urllib.error
except ImportError:
    print("ERROR: urllib not available")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────
RENDER_DIR = Path("data/rendered")
GT_DIR = Path("data/ground_truth")
API_BASE = "https://recordhealth-api.jason-nolte.workers.dev"
BATCH_PAUSE = 0.1  # seconds between requests to avoid rate limits
MAX_RENDER_SIZE = 5 * 1024 * 1024  # 5MB cap for render_data


def api_post(path, body, api_key):
    """POST JSON to the API."""
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "RecordHealth-SeedIngest/1.0")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return json.loads(body), e.code
        except:
            return {"error": body}, e.code


def main():
    print("╔═══════════════════════════════════════╗")
    print("║  Batch Ingest — PDFs → SEED API        ║")
    print("╚═══════════════════════════════════════╝")
    
    # Get API key
    api_key = os.environ.get("SEED_API_KEY")
    if not api_key:
        print("\nERROR: Set SEED_API_KEY environment variable")
        print("  export SEED_API_KEY=your_admin_key_here")
        sys.exit(1)
    
    # Load render manifest
    manifest_path = RENDER_DIR / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found. Run document_renderer.py first.")
        sys.exit(1)
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    docs = manifest.get("documents", [])
    print(f"\nDocuments to ingest: {len(docs)}")
    
    # Optional limit
    limit = len(docs)
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        limit = int(sys.argv[idx + 1])
        print(f"Limiting to: {limit}")
    
    # Optional skip for resume
    skip = 0
    if "--skip" in sys.argv:
        idx = sys.argv.index("--skip")
        skip = int(sys.argv[idx + 1])
        print(f"Skipping first: {skip}")
    
    success = 0
    failed = 0
    skipped = 0
    
    for i, entry in enumerate(docs[skip:skip+limit]):
        pdf_path = RENDER_DIR / entry["file"]
        gt_path = GT_DIR / entry["groundTruth"]
        
        if not pdf_path.exists() or not gt_path.exists():
            print(f"  SKIP {entry['file']} — files missing")
            skipped += 1
            continue
        
        # Load ground truth
        with open(gt_path) as f:
            gt = json.load(f)
        
        # Load and encode PDF
        pdf_bytes = pdf_path.read_bytes()
        if len(pdf_bytes) > MAX_RENDER_SIZE:
            print(f"  SKIP {entry['file']} — PDF too large ({len(pdf_bytes):,} bytes)")
            skipped += 1
            continue
        
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        
        # Build ingest payload
        doc_id = f"mimic-{entry['encounterHash']}-{entry['layoutType']}"
        
        payload = {
            "id": doc_id,
            "sourceFile": gt.get("sourceFile", ""),
            "layoutType": gt.get("layoutType", "unknown"),
            "layoutVariant": gt.get("layoutVariant"),
            "providerLayoutHash": gt.get("providerLayoutHash", "unknown"),
            "documentCategory": gt.get("documentCategory", "labReport"),
            "corpusSplit": "training",
            "sourceType": "mimic_rendered",
            "groundTruth": gt.get("groundTruth", []),
            "renderData": pdf_b64,
        }
        
        # POST
        resp, status = api_post("/v1/seed/ingest-document", payload, api_key)
        
        if status == 201 or resp.get("success"):
            success += 1
        else:
            error = resp.get("error", resp.get("detail", "unknown"))
            if "duplicate" in str(error).lower() or "unique" in str(error).lower():
                skipped += 1
            else:
                print(f"  FAIL {doc_id}: {error}")
                failed += 1
        
        if (i + 1) % 25 == 0:
            print(f"  ...{i + 1}/{limit} ({success} ok, {failed} fail, {skipped} skip)")
        
        time.sleep(BATCH_PAUSE)
    
    print(f"\n═══ Done ═══")
    print(f"  Ingested: {success}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Total: {success + failed + skipped}")
    print(f"\n  Open SEED Console to see documents in the queue")


if __name__ == "__main__":
    main()
