#!/usr/bin/env python3
"""
Document Renderer — Step 2
Takes MIMIC JSON extractions and renders realistic provider-style PDFs.
Each PDF has a companion ground_truth JSON with field coordinates.

Runs locally. No network calls.
"""

import json
import hashlib
import random
import os
import sys
from pathlib import Path
from io import BytesIO
import base64

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
except ImportError:
    print("ERROR: reportlab not installed. Run: pip3 install reportlab")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────
INPUT_DIR = Path("data/mimic")
RENDER_DIR = Path("data/rendered")
GT_DIR = Path("data/ground_truth")
COUNT = 200  # how many to render (override with --count)

LAYOUT_TYPES = ["LabCorpStyle", "QuestStyle"]

# ─── Layout Variations ────────────────────────────────────
def random_variant():
    return {
        "font_size": random.choice([9, 10, 11]),
        "column_spacing": random.choice(["tight", "normal", "wide"]),
        "header_style": random.choice(["full", "compact"]),
        "row_shading": random.choice([True, False]),
    }

def layout_hash(layout_type, variant):
    key = json.dumps({"type": layout_type, **variant}, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:16]

# ─── Coordinate Tracker ──────────────────────────────────
class CoordinateTracker:
    """Tracks where fields are placed on the page for ground truth."""
    def __init__(self, page_width, page_height):
        self.pw = page_width
        self.ph = page_height
        self.fields = []
    
    def add(self, label, value, unit, ref_range, flag, x, y, w, h, canonical_id="", panel=""):
        self.fields.append({
            "fieldType": "numericLabValue",
            "label": label,
            "value": str(value),
            "unit": unit,
            "referenceRange": ref_range,
            "flag": flag,
            "canonicalId": canonical_id,
            "panel": panel,
            "pageIndex": 0,
            "boundingBox": {
                "x": round(x / self.pw, 4),
                "y": round(y / self.ph, 4),
                "w": round(w / self.pw, 4),
                "h": round(h / self.ph, 4),
            }
        })


# ─── LOINC Lookup (best effort) ──────────────────────────
COMMON_LOINC = {
    "glucose": "LOINC:2345-7", "sodium": "LOINC:2951-2",
    "potassium": "LOINC:2823-3", "chloride": "LOINC:2075-0",
    "creatinine": "LOINC:2160-0", "urea nitrogen": "LOINC:3094-0",
    "calcium, total": "LOINC:17861-6", "calcium": "LOINC:17861-6",
    "magnesium": "LOINC:19123-9", "phosphate": "LOINC:2777-1",
    "bicarbonate": "LOINC:2028-9", "co2": "LOINC:2028-9",
    "anion gap": "LOINC:33037-3",
    "white blood cells": "LOINC:6690-2", "wbc": "LOINC:6690-2",
    "red blood cells": "LOINC:789-8", "rbc": "LOINC:789-8",
    "hemoglobin": "LOINC:718-7", "hematocrit": "LOINC:4544-3",
    "platelet count": "LOINC:777-3", "platelets": "LOINC:777-3",
    "mcv": "LOINC:787-2", "mch": "LOINC:785-6", "mchc": "LOINC:786-4",
    "rdw": "LOINC:788-0",
    "alanine aminotransferase (alt)": "LOINC:1742-6",
    "asparate aminotransferase (ast)": "LOINC:1920-8",
    "alkaline phosphatase": "LOINC:6768-6",
    "bilirubin, total": "LOINC:1975-2", "total bilirubin": "LOINC:1975-2",
    "albumin": "LOINC:1751-7", "total protein": "LOINC:2885-2",
    "lactate dehydrogenase (ld)": "LOINC:2532-0",
    "inr(pt)": "LOINC:5902-2", "pt": "LOINC:5902-2",
    "ptt": "LOINC:3173-2",
}

def lookup_loinc(label):
    return COMMON_LOINC.get(label.lower().strip(), "")


# ─── Renderers ────────────────────────────────────────────
def render_labcorp(results, variant, encounter_hash):
    """LabCorp-style: single column table, alternating rows."""
    buf = BytesIO()
    pw, ph = letter
    doc = SimpleDocTemplate(buf, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.6*inch, bottomMargin=0.6*inch)
    
    fs = variant["font_size"]
    styles = getSampleStyleSheet()
    tracker = CoordinateTracker(pw, ph)
    elements = []
    
    # Header
    hstyle = ParagraphStyle('H', parent=styles['Heading1'], fontSize=14,
        spaceAfter=4, textColor=HexColor('#1a1a1a'))
    sub = ParagraphStyle('S', parent=styles['Normal'], fontSize=8,
        textColor=HexColor('#666666'), spaceAfter=10)
    
    elements.append(Paragraph("LABORATORY REPORT", hstyle))
    if variant["header_style"] == "full":
        elements.append(Paragraph(
            f"Sample Medical Laboratory — Report ID: {encounter_hash}", sub))
    elements.append(Spacer(1, 8))
    
    # Group results by category
    categories = {}
    for r in results:
        cat = r.get("category", "General")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)
    
    col_widths_map = {
        "tight": [150, 70, 90, 100, 40],
        "normal": [160, 80, 100, 110, 50],
        "wide": [170, 90, 110, 120, 50],
    }
    col_widths = col_widths_map[variant["column_spacing"]]
    
    for cat_name, cat_results in categories.items():
        # Section header
        sec = ParagraphStyle('Sec', parent=styles['Heading2'], fontSize=fs + 1,
            spaceBefore=12, spaceAfter=6, textColor=HexColor('#333333'))
        elements.append(Paragraph(cat_name.upper(), sec))
        
        # Table
        data = [["Test", "Result", "Units", "Ref Range", "Flag"]]
        for r in cat_results:
            value = r.get("value", r.get("valuenum", ""))
            unit = r.get("valueuom", "")
            flag = r.get("flag", "")
            label = r.get("label", "Unknown")
            
            ref_lower = r.get("ref_range_lower", "")
            ref_upper = r.get("ref_range_upper", "")
            ref_range = ""
            if ref_lower and ref_upper:
                ref_range = f"{ref_lower}-{ref_upper}"
            elif ref_lower:
                ref_range = f">{ref_lower}"
            elif ref_upper:
                ref_range = f"<{ref_upper}"
            
            data.append([label, str(value), unit, ref_range, flag])
            
            # Track coordinates (approximate)
            row_idx = len(data) - 1
            row_y = 140 + (row_idx * 18)  # approximate
            tracker.add(
                label=label, value=value, unit=unit,
                ref_range=ref_range, flag=flag,
                x=54, y=row_y, w=sum(col_widths), h=16,
                canonical_id=lookup_loinc(label),
                panel=cat_name,
            )
        
        t = Table(data, colWidths=col_widths)
        style_cmds = [
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), fs),
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#e8e8e8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#333333')),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (-1, 0), (-1, -1), 'CENTER'),
        ]
        if variant["row_shading"]:
            style_cmds.append(
                ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                 [HexColor('#ffffff'), HexColor('#f5f5f5')])
            )
        # Flag coloring
        for i, row in enumerate(data[1:], 1):
            if row[4] and row[4].strip().lower() in ('abnormal', 'delta', 'h', 'l', 'hh', 'll'):
                style_cmds.append(('TEXTCOLOR', (1, i), (1, i), HexColor('#cc0000')))
                style_cmds.append(('TEXTCOLOR', (-1, i), (-1, i), HexColor('#cc0000')))
        
        t.setStyle(TableStyle(style_cmds))
        elements.append(t)
    
    # Footer
    elements.append(Spacer(1, 20))
    footer = ParagraphStyle('F', parent=styles['Normal'], fontSize=7,
        textColor=HexColor('#999999'))
    elements.append(Paragraph(f"Report ID: {encounter_hash} | Page 1", footer))
    
    doc.build(elements)
    return buf.getvalue(), tracker.fields


def render_quest(results, variant, encounter_hash):
    """Quest-style: slightly different layout, flags as symbols."""
    buf = BytesIO()
    pw, ph = letter
    doc = SimpleDocTemplate(buf, pagesize=letter,
        leftMargin=0.7*inch, rightMargin=0.7*inch,
        topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    fs = variant["font_size"]
    styles = getSampleStyleSheet()
    tracker = CoordinateTracker(pw, ph)
    elements = []
    
    # Header - Quest uses different styling
    hstyle = ParagraphStyle('H', parent=styles['Heading1'], fontSize=12,
        spaceAfter=2, textColor=HexColor('#003366'))
    sub = ParagraphStyle('S', parent=styles['Normal'], fontSize=8,
        textColor=HexColor('#666666'), spaceAfter=8)
    
    elements.append(Paragraph("Quest Diagnostics — Laboratory Results", hstyle))
    elements.append(Paragraph(f"Accession: QD-{encounter_hash[:8].upper()}", sub))
    elements.append(Spacer(1, 6))
    
    # Quest uses 6 columns with tighter spacing
    col_widths = [140, 70, 70, 90, 70, 40]
    
    data = [["Test Name", "Result", "Units", "Reference", "Status", ""]]
    for r in results:
        value = r.get("value", r.get("valuenum", ""))
        unit = r.get("valueuom", "")
        flag = r.get("flag", "")
        label = r.get("label", "Unknown")
        
        ref_lower = r.get("ref_range_lower", "")
        ref_upper = r.get("ref_range_upper", "")
        ref_range = ""
        if ref_lower and ref_upper:
            ref_range = f"{ref_lower}-{ref_upper}"
        elif ref_lower:
            ref_range = f">{ref_lower}"
        elif ref_upper:
            ref_range = f"<{ref_upper}"
        
        # Quest uses H/L/C symbols
        flag_symbol = ""
        if flag and flag.strip().lower() in ('abnormal', 'h', 'hh'):
            flag_symbol = "H"
        elif flag and flag.strip().lower() in ('l', 'll'):
            flag_symbol = "L"
        elif flag and flag.strip().lower() == 'delta':
            flag_symbol = "C"
        
        status = "Final"
        data.append([label, str(value), unit, ref_range, status, flag_symbol])
        
        row_idx = len(data) - 1
        row_y = 120 + (row_idx * 16)
        tracker.add(
            label=label, value=value, unit=unit,
            ref_range=ref_range, flag=flag_symbol,
            x=50, y=row_y, w=sum(col_widths), h=14,
            canonical_id=lookup_loinc(label),
            panel=r.get("category", "General"),
        )
    
    t = Table(data, colWidths=col_widths)
    style_cmds = [
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), fs),
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#999999')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (-2, 0), (-2, -1), 'CENTER'),
    ]
    if variant["row_shading"]:
        style_cmds.append(
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [HexColor('#ffffff'), HexColor('#f0f4f8')])
        )
    for i, row in enumerate(data[1:], 1):
        if row[5] in ('H', 'L', 'C'):
            style_cmds.append(('TEXTCOLOR', (-1, i), (-1, i), HexColor('#cc0000')))
            style_cmds.append(('FONTNAME', (-1, i), (-1, i), 'Helvetica-Bold'))
    
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)
    
    elements.append(Spacer(1, 16))
    footer = ParagraphStyle('F', parent=styles['Normal'], fontSize=7,
        textColor=HexColor('#999999'))
    elements.append(Paragraph(
        f"QD-{encounter_hash[:8].upper()} | Electronically verified | Page 1", footer))
    
    doc.build(elements)
    return buf.getvalue(), tracker.fields


# ─── Main ─────────────────────────────────────────────────
def main():
    count = COUNT
    if "--count" in sys.argv:
        idx = sys.argv.index("--count")
        count = int(sys.argv[idx + 1])
    
    print("╔═══════════════════════════════════════╗")
    print("║  Document Renderer — Step 2            ║")
    print("║  MIMIC JSON → Realistic Lab PDFs       ║")
    print("╚═══════════════════════════════════════╝")
    
    # Load manifest
    manifest_path = INPUT_DIR / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found. Run mimic_extractor.py first.")
        sys.exit(1)
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    # Filter to lab files only (medications rendered differently later)
    lab_files = [e for e in manifest["files"] if e["category"] == "labReport"]
    print(f"\nSource: {INPUT_DIR}")
    print(f"Lab encounters available: {len(lab_files)}")
    print(f"Rendering: {min(count, len(lab_files))} documents")
    
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    GT_DIR.mkdir(parents=True, exist_ok=True)
    
    rendered = 0
    gt_manifest = []
    
    for entry in lab_files[:count]:
        source_path = INPUT_DIR / entry["file"]
        if not source_path.exists():
            continue
        
        with open(source_path) as f:
            data = json.load(f)
        
        results = data.get("results", [])
        if len(results) < 3:
            continue
        
        encounter_hash = data["encounter_hash"]
        
        # Pick random layout and variant
        layout_type = random.choice(LAYOUT_TYPES)
        variant = random_variant()
        lhash = layout_hash(layout_type, variant)
        
        # Render
        if layout_type == "LabCorpStyle":
            pdf_bytes, gt_fields = render_labcorp(results, variant, encounter_hash)
        else:
            pdf_bytes, gt_fields = render_quest(results, variant, encounter_hash)
        
        # Save PDF
        pdf_name = f"{encounter_hash}_{layout_type}.pdf"
        pdf_path = RENDER_DIR / pdf_name
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        
        # Save ground truth
        gt = {
            "sourceFile": str(source_path),
            "layoutType": layout_type,
            "layoutVariant": variant,
            "providerLayoutHash": lhash,
            "documentCategory": "labReport",
            "encounterHash": encounter_hash,
            "groundTruth": gt_fields,
            "renderPath": str(pdf_path),
            "renderDataB64Size": len(base64.b64encode(pdf_bytes)),
        }
        
        gt_path = GT_DIR / f"{encounter_hash}_{layout_type}.json"
        with open(gt_path, "w") as f:
            json.dump(gt, f, indent=2)
        
        gt_manifest.append({
            "file": pdf_name,
            "groundTruth": f"{encounter_hash}_{layout_type}.json",
            "layoutType": layout_type,
            "providerLayoutHash": lhash,
            "fieldCount": len(gt_fields),
            "encounterHash": encounter_hash,
        })
        
        rendered += 1
        if rendered % 50 == 0:
            print(f"  ...rendered {rendered}/{min(count, len(lab_files))}")
    
    # Write render manifest
    render_manifest = {
        "version": "1.0",
        "source": "mimic-iv via document_renderer",
        "total_rendered": rendered,
        "layout_types": LAYOUT_TYPES,
        "documents": gt_manifest,
    }
    
    manifest_path = RENDER_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(render_manifest, f, indent=2)
    
    # Stats
    lc = sum(1 for d in gt_manifest if d["layoutType"] == "LabCorpStyle")
    qs = sum(1 for d in gt_manifest if d["layoutType"] == "QuestStyle")
    total_fields = sum(d["fieldCount"] for d in gt_manifest)
    unique_hashes = len(set(d["providerLayoutHash"] for d in gt_manifest))
    
    print(f"\n═══ Done ═══")
    print(f"  {rendered} PDFs rendered to {RENDER_DIR}/")
    print(f"  {rendered} ground truth files to {GT_DIR}/")
    print(f"  LabCorpStyle: {lc} | QuestStyle: {qs}")
    print(f"  Unique layout hashes: {unique_hashes}")
    print(f"  Total ground truth fields: {total_fields:,}")
    print(f"  Manifest: {manifest_path}")
    print(f"\n  Next: ingest these into the SEED API for annotation")


if __name__ == "__main__":
    main()
