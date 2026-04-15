#!/usr/bin/env python3
"""
Document Renderer v4 — Template Drift Architecture
5 base layouts with controlled element perturbation.
Deterministic synthetic names. MIMIC provenance on every page.
"""

import json
import hashlib
import random
import sys
from pathlib import Path
from io import BytesIO
import base64

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                     Paragraph, Spacer, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
except ImportError:
    print("ERROR: pip3 install reportlab --break-system-packages")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────
INPUT_DIR = Path("data/mimic")
RENDER_DIR = Path("data/rendered")
GT_DIR = Path("data/ground_truth")
COUNT = 200

# Drift ratio: 0.0 = exact template, 1.0 = maximum perturbation
DRIFT_RATIO = 0.6

# ─── Deterministic Identity System ────────────────────────
# These caches ensure the same hash ALWAYS produces the same identity
# across every document in every run.
_patient_cache = {}
_provider_cache = {}
_facility_cache = {}

FIRST_NAMES_F = ["Mary","Patricia","Jennifer","Linda","Elizabeth","Barbara",
    "Susan","Jessica","Sarah","Karen","Lisa","Nancy","Betty","Margaret",
    "Sandra","Ashley","Dorothy","Kimberly","Emily","Donna","Michelle",
    "Carol","Amanda","Melissa","Deborah","Stephanie","Rebecca","Sharon",
    "Cynthia","Kathleen","Amy","Angela","Helen","Anna","Brenda","Pamela"]
FIRST_NAMES_M = ["James","Robert","John","Michael","David","William",
    "Richard","Joseph","Thomas","Charles","Daniel","Christopher","Matthew",
    "Anthony","Mark","Donald","Steven","Andrew","Paul","Joshua","Kenneth",
    "Kevin","Brian","George","Timothy","Ronald","Edward","Jason","Jeffrey","Ryan"]
LAST_NAMES = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller",
    "Davis","Rodriguez","Martinez","Hernandez","Lopez","Wilson","Anderson",
    "Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson",
    "White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker",
    "Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill",
    "Flores","Green","Adams","Nelson","Baker","Hall","Rivera","Campbell",
    "Mitchell","Carter","Roberts","Gomez","Phillips","Evans","Turner","Diaz"]

PROVIDER_TITLES = ["MD","DO","MD, PhD","MD, FACP","MD, FACEP","DO, FACOI"]
PROVIDER_FIRST = ["Alan","Beth","Carlos","Diana","Eric","Fatima","Gregory",
    "Helen","Ivan","Julia","Keith","Laura","Miguel","Nina","Oscar","Priya",
    "Raj","Sandra","Tomoko","Uma","Victor","Wendy","Xavier","Yuki","Zara",
    "Ahmed","Brigitte","Dmitri","Elena","Franklin","Gabriela","Hiroshi",
    "Ingrid","Jean-Pierre","Keiko","Leonard","Maria","Nolan","Olga","Patrick"]
PROVIDER_LAST = ["Chen","Patel","Kim","Nakamura","Singh","Okafor","Petrov",
    "Gutierrez","Johannsen","Al-Rashid","Cohen","Fernandez","Takahashi",
    "Muller","Svensson","Adebayo","Moreau","Volkov","Santos","Andersen",
    "Yamamoto","O'Brien","Krishnamurthy","DeSilva","Hoffman","Reeves",
    "Marchetti","Bjornsson","Chakraborty","Fitzgerald"]

FACILITIES = [
    {"name":"Riverside Medical Center","addr":"4200 River Rd, Sacramento, CA 95814","pfx":"RMC","clia_base":5100000},
    {"name":"St. Luke's Hospital Laboratory","addr":"1100 Church St, San Francisco, CA 94114","pfx":"SLH","clia_base":5200000},
    {"name":"Memorial Hermann Health System","addr":"6411 Fannin St, Houston, TX 77030","pfx":"MHH","clia_base":4500000},
    {"name":"Cedar Ridge Medical Group","addr":"850 Oak Blvd, Portland, OR 97205","pfx":"CRM","clia_base":3800000},
    {"name":"Atlantic Coast Clinical Laboratory","addr":"220 Beach Ave, Miami, FL 33139","pfx":"ACL","clia_base":1000000},
    {"name":"Midwest Regional Lab Services","addr":"3300 State St, Chicago, IL 60616","pfx":"MRL","clia_base":1400000},
    {"name":"Pacific Diagnostics Inc.","addr":"1500 Sunset Blvd, Los Angeles, CA 90028","pfx":"PDI","clia_base":5000000},
    {"name":"Northern Valley Health System","addr":"775 Pine St, Denver, CO 80203","pfx":"NVH","clia_base":6000000},
    {"name":"Bayview Clinical Laboratory","addr":"400 Harbor Dr, San Diego, CA 92101","pfx":"BCL","clia_base":5300000},
    {"name":"Summit Health Partners Lab","addr":"900 Summit Ave, Seattle, WA 98101","pfx":"SHP","clia_base":9100000},
    {"name":"University Hospital Lab","addr":"500 University Ave, Madison, WI 53706","pfx":"UHL","clia_base":4900000},
    {"name":"Lakeside Pathology Associates","addr":"1200 Lake Shore Dr, Cleveland, OH 44114","pfx":"LPA","clia_base":3400000},
]


def _seed(hash_str):
    return int(hashlib.sha256(f"rh-seed-v4:{hash_str}".encode()).hexdigest()[:8], 16)


def get_patient(subject_hash):
    if subject_hash in _patient_cache:
        return _patient_cache[subject_hash]
    s = _seed(subject_hash)
    is_female = (s % 2) == 0
    if is_female:
        first = FIRST_NAMES_F[s % len(FIRST_NAMES_F)]
    else:
        first = FIRST_NAMES_M[s % len(FIRST_NAMES_M)]
    last = LAST_NAMES[(s // 3) % len(LAST_NAMES)]
    p = {
        "name": f"{last.upper()}, {first.upper()}",
        "display": f"{first} {last}",
        "gender": "F" if is_female else "M",
        "dob": f"{(s%12)+1:02d}/{(s%28)+1:02d}/{1940+(s%60)}",
        "mrn": f"MRN-{subject_hash[:8].upper()}",
        "ssn4": f"{s%10000:04d}",
        "subject_hash": subject_hash,
    }
    _patient_cache[subject_hash] = p
    return p


def get_provider(provider_hash):
    if not provider_hash or provider_hash == "":
        provider_hash = "default-provider"
    if provider_hash in _provider_cache:
        return _provider_cache[provider_hash]
    s = _seed(provider_hash)
    first = PROVIDER_FIRST[s % len(PROVIDER_FIRST)]
    last = PROVIDER_LAST[(s // 7) % len(PROVIDER_LAST)]
    title = PROVIDER_TITLES[s % len(PROVIDER_TITLES)]
    p = {
        "full": f"{first} {last}, {title}",
        "short": f"Dr. {last}",
        "npi": f"{1000000000 + s % 900000000}",
        "id_hash": provider_hash,
    }
    _provider_cache[provider_hash] = p
    return p


def get_facility(encounter_hash):
    if encounter_hash in _facility_cache:
        return _facility_cache[encounter_hash]
    s = _seed(encounter_hash)
    base = FACILITIES[s % len(FACILITIES)]
    f = {
        "name": base["name"],
        "address": base["addr"],
        "id": f"{base['pfx']}-{encounter_hash[:6].upper()}",
        "phone": f"({200+s%800:03d}) {200+s%800:03d}-{1000+s%9000:04d}",
        "clia": f"05D{base['clia_base']+s%1000000:07d}",
    }
    _facility_cache[encounter_hash] = f
    return f


def charttime_display(ct, show_time=True):
    if not ct or len(ct) < 10:
        return "—"
    if show_time and len(ct) >= 16:
        return ct[:16]
    return ct[:10]


# ─── 5 Base Layout Templates ─────────────────────────────
# Each template defines the structural skeleton.
# Drift perturbs numeric parameters within bounds.

TEMPLATES = {
    "labcorp_classic": {
        "description": "LabCorp-style: formal header block, grouped by category, full grid",
        "font_body": "Helvetica",
        "font_header": "Helvetica-Bold",
        "font_size": 9,
        "header_color": "#1a1a1a",
        "accent_color": "#cc0000",
        "margins": (0.75, 0.75, 0.6, 0.6),
        "col_widths": [155, 75, 80, 95, 45],
        "header_layout": "full_block",
        "section_style": "grouped",
        "grid_style": "full",
        "row_shading": True,
        "ref_style": "dash",       # "70-100"
        "flag_style": "letter",     # H, L
        "date_style": "us",         # MM/DD/YYYY
        "footer_style": "full",
        "show_time": False,
        "show_loinc_col": False,
    },
    "quest_modern": {
        "description": "Quest-style: blue header, flat list, horizontal lines",
        "font_body": "Helvetica",
        "font_header": "Helvetica-Bold",
        "font_size": 9,
        "header_color": "#003366",
        "accent_color": "#b30000",
        "margins": (0.7, 0.7, 0.5, 0.5),
        "col_widths": [140, 70, 70, 85, 55, 40],
        "header_layout": "compact_line",
        "section_style": "flat",
        "grid_style": "horizontal",
        "row_shading": False,
        "ref_style": "spaced",      # "70 - 100"
        "flag_style": "letter",
        "date_style": "us",
        "footer_style": "minimal",
        "show_time": False,
        "show_loinc_col": False,
        "extra_status_col": True,
    },
    "hospital_formal": {
        "description": "Hospital discharge style: two-column header, numbered, serif font",
        "font_body": "Times-Roman",
        "font_header": "Times-Bold",
        "font_size": 10,
        "header_color": "#2d5016",
        "accent_color": "#c41e3a",
        "margins": (1.0, 1.0, 0.75, 0.75),
        "col_widths": [170, 85, 85, 105, 45],
        "header_layout": "two_column",
        "section_style": "numbered",
        "grid_style": "minimal",
        "row_shading": True,
        "ref_style": "bracket",     # "[70-100]"
        "flag_style": "word",       # HIGH, LOW
        "date_style": "long",       # January 15, 2024
        "footer_style": "detailed",
        "show_time": True,
        "show_loinc_col": False,
    },
    "regional_clinic": {
        "description": "Regional clinic: minimal header, grouped, full grid, compact",
        "font_body": "Helvetica",
        "font_header": "Helvetica-Bold",
        "font_size": 8,
        "header_color": "#4a1942",
        "accent_color": "#d4380d",
        "margins": (0.5, 0.5, 0.5, 0.5),
        "col_widths": [145, 70, 70, 85, 40],
        "header_layout": "minimal",
        "section_style": "grouped",
        "grid_style": "full",
        "row_shading": False,
        "ref_style": "paren",       # "(70-100)"
        "flag_style": "arrow",      # ↑, ↓
        "date_style": "iso",        # 2024-01-15
        "footer_style": "minimal",
        "show_time": False,
        "show_loinc_col": False,
    },
    "urgent_care": {
        "description": "Urgent care: courier font, flat list, bold flags, clinical feel",
        "font_body": "Courier",
        "font_header": "Courier-Bold",
        "font_size": 9,
        "header_color": "#333333",
        "accent_color": "#8b0000",
        "margins": (0.6, 0.6, 0.5, 0.5),
        "col_widths": [150, 75, 75, 90, 45],
        "header_layout": "compact_line",
        "section_style": "flat",
        "grid_style": "full",
        "row_shading": True,
        "ref_style": "dash",
        "flag_style": "bang",       # H!, L!
        "date_style": "mil",        # 15-Jan-2024
        "footer_style": "full",
        "show_time": True,
        "show_loinc_col": False,
    },
}

TEMPLATE_NAMES = list(TEMPLATES.keys())


def drift_value(base, max_delta, drift_ratio):
    """Perturb a numeric value within bounds."""
    delta = random.uniform(-max_delta, max_delta) * drift_ratio
    return base + delta


def drift_int(base, max_delta, drift_ratio):
    return int(round(drift_value(base, max_delta, drift_ratio)))


def apply_drift(template, drift_ratio):
    """Create a drifted copy of a template."""
    t = dict(template)
    # Drift font size ±1
    t["font_size"] = max(7, min(12, drift_int(t["font_size"], 1, drift_ratio)))
    # Drift margins ±0.15in
    m = t["margins"]
    t["margins"] = tuple(max(0.3, round(drift_value(v, 0.15, drift_ratio), 2)) for v in m)
    # Drift column widths ±15px
    t["col_widths"] = [max(30, drift_int(w, 15, drift_ratio)) for w in t["col_widths"]]
    # Occasionally flip row shading
    if random.random() < 0.3 * drift_ratio:
        t["row_shading"] = not t["row_shading"]
    # Occasionally flip show_time
    if random.random() < 0.2 * drift_ratio:
        t["show_time"] = not t["show_time"]
    return t


# ─── Formatting Functions ─────────────────────────────────
def fmt_date(date_parts_or_str, style):
    """Format a date. Accepts (m,d,y) tuple or charttime string."""
    if isinstance(date_parts_or_str, tuple):
        m, d, y = date_parts_or_str
    elif isinstance(date_parts_or_str, str) and len(date_parts_or_str) >= 10:
        try:
            y, m, d = int(date_parts_or_str[:4]), int(date_parts_or_str[5:7]), int(date_parts_or_str[8:10])
        except:
            return date_parts_or_str[:10]
    else:
        return "—"

    months = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    months_long = ["","January","February","March","April","May","June","July",
                   "August","September","October","November","December"]
    if style == "us":
        return f"{m:02d}/{d:02d}/{y}"
    elif style == "iso":
        return f"{y}-{m:02d}-{d:02d}"
    elif style == "long":
        return f"{months_long[m]} {d}, {y}"
    elif style == "mil":
        return f"{d:02d}-{months[m]}-{y}"
    return f"{m:02d}/{d:02d}/{y}"


def fmt_ref(lo, hi, style):
    lo = str(lo).strip() if lo else ""
    hi = str(hi).strip() if hi else ""
    if not lo and not hi:
        return ""
    if style == "dash":
        return f"{lo}-{hi}" if lo and hi else f">{lo}" if lo else f"<{hi}"
    elif style == "spaced":
        return f"{lo} - {hi}" if lo and hi else f"> {lo}" if lo else f"< {hi}"
    elif style == "bracket":
        return f"[{lo}-{hi}]" if lo and hi else f"[>{lo}]" if lo else f"[<{hi}]"
    elif style == "paren":
        return f"({lo}-{hi})" if lo and hi else f"(>{lo})" if lo else f"(<{hi})"
    return f"{lo}-{hi}" if lo and hi else f">{lo}" if lo else f"<{hi}"


def fmt_flag(raw, style):
    if not raw:
        return ""
    f = raw.strip().lower()
    flags = {
        "letter": {"h":"H","l":"L","hh":"HH","ll":"LL","abnormal":"A","delta":"D"},
        "word": {"h":"HIGH","l":"LOW","hh":"CRIT HIGH","ll":"CRIT LOW","abnormal":"ABNORMAL","delta":"DELTA"},
        "arrow": {"h":"↑","l":"↓","hh":"↑↑","ll":"↓↓","abnormal":"*","delta":"Δ"},
        "bang": {"h":"H!","l":"L!","hh":"H!!","ll":"L!!","abnormal":"**","delta":"D!"},
    }
    mapping = flags.get(style, flags["letter"])
    return mapping.get(f, raw)


# ─── Coordinate Tracker ──────────────────────────────────
class Tracker:
    def __init__(self, pw, ph):
        self.pw, self.ph = pw, ph
        self.fields = []

    def add(self, x, y, w, h, **kw):
        kw["boundingBox"] = {
            "x": round(x/self.pw, 4), "y": round(y/self.ph, 4),
            "w": round(w/self.pw, 4), "h": round(h/self.ph, 4),
        }
        kw["pageIndex"] = 0
        self.fields.append(kw)


# ─── Render Engine ────────────────────────────────────────
def render(data, template_name, config, encounter_hash):
    buf = BytesIO()
    pw, ph = letter
    ml, mr, mt, mb = config["margins"]
    doc = SimpleDocTemplate(buf, pagesize=letter,
        leftMargin=ml*inch, rightMargin=mr*inch,
        topMargin=mt*inch, bottomMargin=mb*inch)

    fs = config["font_size"]
    fb = config["font_body"]
    fh = config["font_header"]
    hc = config["header_color"]
    ac = config["accent_color"]
    styles = getSampleStyleSheet()
    tracker = Tracker(pw, ph)
    elements = []

    subject_hash = data.get("subject_hash", "unknown")
    results = data.get("results", [])
    enc_count = data.get("encounter_count_for_patient", 1)

    patient = get_patient(subject_hash)
    first_prov_hash = next((r.get("order_provider_id","") for r in results if r.get("order_provider_id")), "")
    provider = get_provider(first_prov_hash)
    facility = get_facility(encounter_hash)

    first_ct = next((r["charttime"] for r in results if r.get("charttime")), "")
    first_st = next((r["storetime"] for r in results if r.get("storetime")), "")
    first_r = results[0] if results else {}

    ds = config["date_style"]

    # ═══ MIMIC PROVENANCE BANNER ═══
    mimic_style = ParagraphStyle('MIMIC', fontName='Courier', fontSize=6,
        textColor=HexColor('#999999'), spaceAfter=4)
    elements.append(Paragraph(
        f"MIMIC-IV SEED DOCUMENT  |  Subject: {subject_hash}  |  "
        f"Encounter: {encounter_hash}  |  Template: {template_name}", mimic_style))
    elements.append(HRFlowable(width="100%", thickness=0.3, color=HexColor('#dddddd')))
    elements.append(Spacer(1, 4))

    # ═══ HEADER ═══
    hl = config["header_layout"]

    if hl == "full_block":
        h1 = ParagraphStyle('H1', fontName=fh, fontSize=14, spaceAfter=2, textColor=HexColor(hc))
        elements.append(Paragraph(facility["name"].upper(), h1))
        sub = ParagraphStyle('S', fontName=fb, fontSize=7, textColor=HexColor('#666'), spaceAfter=1)
        elements.append(Paragraph(f"{facility['address']}  |  {facility['phone']}  |  CLIA# {facility['clia']}", sub))
        elements.append(Paragraph(f"Facility ID: {facility['id']}", sub))
        elements.append(Spacer(1, 6))
        rows = [
            ["Patient:", patient["name"], "DOB:", fmt_date(patient["dob"], ds) if isinstance(patient["dob"], str) else patient["dob"],
             "Gender:", patient["gender"]],
            ["MRN:", patient["mrn"], "SSN(last 4):", patient["ssn4"],
             "Acct#:", f"{facility['id'][:3]}-{encounter_hash[:8].upper()}"],
            ["Ordering:", provider["full"], "NPI:", provider["npi"],
             "Provider ID:", provider["id_hash"][:12]],
            ["Collected:", charttime_display(first_ct, config["show_time"]),
             "Reported:", charttime_display(first_st, config["show_time"]),
             "Visit:", f"#{enc_count} for patient"],
            ["Specimen:", first_r.get("fluid","—"),
             "Priority:", first_r.get("priority","Routine"),
             "Specimen ID:", first_r.get("specimen_id","—")],
        ]
        pt = Table(rows, colWidths=[58, 148, 62, 108, 62, 105])
        pt.setStyle(TableStyle([
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('FONTNAME', (0,0), (0,-1), fh), ('FONTNAME', (2,0), (2,-1), fh), ('FONTNAME', (4,0), (4,-1), fh),
            ('TEXTCOLOR', (0,0), (-1,-1), HexColor('#333')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2), ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(pt)

    elif hl == "compact_line":
        h1 = ParagraphStyle('H1', fontName=fh, fontSize=11, spaceAfter=3, textColor=HexColor(hc))
        elements.append(Paragraph(f"{facility['name']} — LABORATORY REPORT", h1))
        p = ParagraphStyle('P', fontName=fb, fontSize=7, textColor=HexColor('#444'), spaceAfter=1)
        elements.append(Paragraph(
            f"<b>Patient:</b> {patient['name']} ({patient['gender']})  "
            f"<b>DOB:</b> {patient['dob']}  <b>MRN:</b> {patient['mrn']}  "
            f"<b>SSN4:</b> {patient['ssn4']}", p))
        elements.append(Paragraph(
            f"<b>Provider:</b> {provider['full']} (NPI: {provider['npi']}, ID: {provider['id_hash'][:12]})  "
            f"<b>Facility:</b> {facility['id']} (CLIA# {facility['clia']})", p))
        elements.append(Paragraph(
            f"<b>Collected:</b> {charttime_display(first_ct, config['show_time'])}  "
            f"<b>Reported:</b> {charttime_display(first_st, config['show_time'])}  "
            f"<b>Specimen:</b> {first_r.get('fluid','—')}  "
            f"<b>Priority:</b> {first_r.get('priority','Routine')}  "
            f"<b>Specimen ID:</b> {first_r.get('specimen_id','—')}  "
            f"<b>Visit:</b> #{enc_count}", p))

    elif hl == "two_column":
        h1 = ParagraphStyle('H1', fontName=fh, fontSize=12, spaceAfter=3, textColor=HexColor(hc))
        elements.append(Paragraph(facility["name"], h1))
        sub = ParagraphStyle('S', fontName=fb, fontSize=7, textColor=HexColor('#666'), spaceAfter=1)
        elements.append(Paragraph(f"{facility['address']}  |  CLIA# {facility['clia']}  |  {facility['id']}", sub))
        elements.append(Spacer(1, 4))
        ps = ParagraphStyle('PI', fontName=fb, fontSize=7, textColor=HexColor('#333'), leading=10)
        left = (f"Patient: {patient['name']} ({patient['gender']})<br/>"
                f"DOB: {patient['dob']}<br/>"
                f"MRN: {patient['mrn']}  |  SSN4: {patient['ssn4']}<br/>"
                f"Visit #{enc_count} for this patient")
        right = (f"Provider: {provider['full']}<br/>"
                 f"NPI: {provider['npi']}  |  ID: {provider['id_hash'][:12]}<br/>"
                 f"Collected: {charttime_display(first_ct, config['show_time'])}<br/>"
                 f"Specimen: {first_r.get('fluid','—')}  |  Priority: {first_r.get('priority','Routine')}<br/>"
                 f"Specimen ID: {first_r.get('specimen_id','—')}")
        tc = Table([[Paragraph(left, ps), Paragraph(right, ps)]], colWidths=[240, 280])
        tc.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4)]))
        elements.append(tc)

    else:  # minimal
        h1 = ParagraphStyle('H1', fontName=fh, fontSize=10, spaceAfter=2, textColor=HexColor(hc))
        elements.append(Paragraph("LAB RESULTS", h1))
        p = ParagraphStyle('P', fontName=fb, fontSize=7, textColor=HexColor('#555'), spaceAfter=1)
        elements.append(Paragraph(
            f"{patient['name']} | MRN: {patient['mrn']} | DOB: {patient['dob']} | "
            f"{provider['short']} | {facility['name']} ({facility['id']})", p))
        elements.append(Paragraph(
            f"Collected: {charttime_display(first_ct)} | Specimen: {first_r.get('fluid','—')} | "
            f"Priority: {first_r.get('priority','Routine')} | Visit #{enc_count}", p))

    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=HexColor(hc)))
    elements.append(Spacer(1, 6))

    # ═══ RESULTS ═══
    col_w = config["col_widths"]
    has_status = config.get("extra_status_col", False)
    total_w = sum(col_w)
    rs = config["ref_style"]
    fls = config["flag_style"]
    section_y = 220

    def make_row(r):
        value = r.get("value", "") or r.get("valuenum", "") or "—"
        if value == "___":
            value = r.get("valuenum", "—") or "—"
        unit = r.get("valueuom", "")
        label = r.get("label", "Unknown")
        ref = fmt_ref(r.get("ref_range_lower",""), r.get("ref_range_upper",""), rs)
        flag = fmt_flag(r.get("flag",""), fls)

        if config["show_time"] and r.get("charttime") and len(r["charttime"]) >= 16:
            label = f"{label}  [{r['charttime'][11:16]}]"

        if has_status:
            status = "STAT" if r.get("priority","").strip().upper() == "STAT" else "Final"
            return [label, str(value), unit, ref, status, flag]
        return [label, str(value), unit, ref, flag]

    def track(r, y):
        value = r.get("value","") or r.get("valuenum","") or "—"
        tracker.add(x=54, y=y, w=total_w, h=13,
            fieldType="numericLabValue",
            label=r.get("label",""), value=str(value),
            unit=r.get("valueuom",""),
            referenceRange=fmt_ref(r.get("ref_range_lower",""),r.get("ref_range_upper",""),rs),
            flag=fmt_flag(r.get("flag",""),fls),
            loincCode=r.get("loinc_code",""),
            panel=r.get("category",""),
            priority=r.get("priority",""),
            specimenId=r.get("specimen_id",""),
            comments=r.get("comments",""),
            charttime=r.get("charttime",""),
            storetime=r.get("storetime",""),
            labeventId=r.get("labevent_id",""),
            fluid=r.get("fluid",""),
            orderProviderId=r.get("order_provider_id",""),
        )

    ss = config["section_style"]

    if ss == "grouped":
        cats = {}
        for r in results:
            cats.setdefault(r.get("category","General"), []).append(r)
        for cat, cat_r in cats.items():
            sec = ParagraphStyle('Sec', fontName=fh, fontSize=fs+1,
                spaceBefore=8, spaceAfter=3, textColor=HexColor(hc))
            elements.append(Paragraph(cat.upper(), sec))
            section_y += 18
            if has_status:
                header = ["Test", "Result", "Units", "Reference", "Status", ""]
            else:
                header = ["Test", "Result", "Units", "Reference", "Flag"]
            rows = [header]
            for r in cat_r:
                rows.append(make_row(r))
                section_y += 13
                track(r, section_y)
            elements.append(build_table(rows, col_w, config))

    elif ss == "numbered":
        if has_status:
            header = ["#  Test", "Result", "Units", "Reference", "Status", ""]
        else:
            header = ["#  Test", "Result", "Units", "Reference", "Flag"]
        rows = [header]
        for i, r in enumerate(results, 1):
            row = make_row(r)
            row[0] = f"{i}. {row[0]}"
            rows.append(row)
            section_y += 13
            track(r, section_y)
        elements.append(build_table(rows, col_w, config))

    else:  # flat
        if has_status:
            header = ["Test", "Result", "Units", "Reference", "Status", ""]
        else:
            header = ["Test", "Result", "Units", "Reference", "Flag"]
        rows = [header]
        for r in results:
            rows.append(make_row(r))
            section_y += 13
            track(r, section_y)
        elements.append(build_table(rows, col_w, config))

    # ═══ COMMENTS ═══
    coms = [r for r in results if r.get("comments","").strip()]
    if coms:
        elements.append(Spacer(1, 8))
        csec = ParagraphStyle('CS', fontName=fh, fontSize=fs, spaceBefore=4, spaceAfter=3, textColor=HexColor(hc))
        elements.append(Paragraph("COMMENTS", csec))
        cs = ParagraphStyle('C', fontName=fb, fontSize=fs-1, textColor=HexColor('#555'), leading=fs+3)
        for r in coms[:8]:
            txt = r['comments'][:300].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            elements.append(Paragraph(f"<b>{r['label']}:</b> {txt}", cs))

    # ═══ FOOTER ═══
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#ccc')))
    ft = ParagraphStyle('F', fontName=fb, fontSize=6, textColor=HexColor('#999'), spaceBefore=2)

    if config["footer_style"] == "full":
        elements.append(Paragraph(
            f"Patient: {patient['mrn']} ({patient['name']})  |  "
            f"Provider: {provider['full']} (NPI: {provider['npi']})  |  "
            f"Facility: {facility['name']} ({facility['id']}, CLIA# {facility['clia']})", ft))
        elements.append(Paragraph(
            f"MIMIC-IV Seed  |  Subject: {subject_hash}  |  Encounter: {encounter_hash}  |  "
            f"Provider ID: {provider['id_hash'][:12]}  |  Template: {template_name}  |  Page 1", ft))
    elif config["footer_style"] == "detailed":
        elements.append(Paragraph(f"{facility['name']} — {facility['address']} — {facility['phone']}", ft))
        elements.append(Paragraph(
            f"CLIA# {facility['clia']} | {patient['mrn']} | {provider['short']} | "
            f"MIMIC Sub:{subject_hash} Enc:{encounter_hash} | Page 1", ft))
    else:
        elements.append(Paragraph(
            f"{patient['mrn']} | {facility['id']} | MIMIC:{subject_hash}/{encounter_hash} | Page 1", ft))

    doc.build(elements)
    return buf.getvalue(), tracker.fields


def build_table(rows, col_w, config):
    fs = config["font_size"]
    fb = config["font_body"]
    fh = config["font_header"]
    hc = config["header_color"]
    ac = config["accent_color"]

    t = Table(rows, colWidths=col_w)
    cmds = [
        ('FONTNAME', (0,0), (-1,0), fh),
        ('FONTNAME', (0,1), (-1,-1), fb),
        ('FONTSIZE', (0,0), (-1,-1), fs),
        ('BACKGROUND', (0,0), (-1,0), HexColor(hc)),
        ('TEXTCOLOR', (0,0), (-1,0), HexColor('#fff')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (1,1), (1,-1), 'CENTER'),
        ('ALIGN', (-1,0), (-1,-1), 'CENTER'),
    ]
    gs = config["grid_style"]
    if gs == "full":
        cmds.append(('GRID', (0,0), (-1,-1), 0.5, HexColor('#ccc')))
    elif gs == "horizontal":
        cmds.append(('LINEBELOW', (0,0), (-1,-1), 0.3, HexColor('#ddd')))
        cmds.append(('LINEBELOW', (0,0), (-1,0), 1, HexColor(hc)))
    else:
        cmds.append(('LINEBELOW', (0,0), (-1,0), 1, HexColor(hc)))

    if config["row_shading"]:
        cmds.append(('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#fff'), HexColor('#f5f5f5')]))

    for i, row in enumerate(rows[1:], 1):
        flag_val = row[-1] if row else ""
        if flag_val and flag_val.strip():
            cmds.append(('TEXTCOLOR', (1,i), (1,i), HexColor(ac)))
            cmds.append(('TEXTCOLOR', (-1,i), (-1,i), HexColor(ac)))
            cmds.append(('FONTNAME', (-1,i), (-1,i), fh))

    t.setStyle(TableStyle(cmds))
    return t


# ─── Main ─────────────────────────────────────────────────
def main():
    count = COUNT
    if "--count" in sys.argv:
        idx = sys.argv.index("--count")
        count = int(sys.argv[idx + 1])

    print("╔═══════════════════════════════════════════════════╗")
    print("║  Document Renderer v4 — Template Drift             ║")
    print("║  5 templates, controlled perturbation, MIMIC IDs   ║")
    print("╚═══════════════════════════════════════════════════╝")
    print(f"  Drift ratio: {DRIFT_RATIO}")
    print(f"  Templates: {', '.join(TEMPLATE_NAMES)}")

    manifest_path = INPUT_DIR / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    lab_files = [e for e in manifest["files"] if e["category"] == "labReport"]
    print(f"\n  Lab encounters: {len(lab_files)}")
    print(f"  Rendering: {min(count, len(lab_files))}")

    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    GT_DIR.mkdir(parents=True, exist_ok=True)

    rendered = 0
    failed = 0
    gt_manifest = []
    template_counts = {n: 0 for n in TEMPLATE_NAMES}

    for entry in lab_files[:count]:
        source_path = INPUT_DIR / entry["file"]
        if not source_path.exists():
            continue

        with open(source_path) as f:
            data = json.load(f)

        if len(data.get("results", [])) < 3:
            continue

        enc_hash = data["encounter_hash"]
        sub_hash = data.get("subject_hash", "unknown")

        # Deterministic template assignment based on encounter hash
        tname = TEMPLATE_NAMES[_seed(enc_hash) % len(TEMPLATE_NAMES)]
        base = TEMPLATES[tname]
        config = apply_drift(dict(base), DRIFT_RATIO)

        lhash = hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()[:16]

        try:
            pdf_bytes, gt_fields = render(data, tname, config, enc_hash)
        except Exception as e:
            print(f"  WARN: {enc_hash}: {e}")
            failed += 1
            continue

        pdf_name = f"{enc_hash}.pdf"
        with open(RENDER_DIR / pdf_name, "wb") as f:
            f.write(pdf_bytes)

        gt = {
            "sourceFile": str(source_path),
            "subjectHash": sub_hash,
            "encounterHash": enc_hash,
            "encounterCountForPatient": data.get("encounter_count_for_patient", 1),
            "templateName": tname,
            "layoutConfig": config,
            "providerLayoutHash": lhash,
            "documentCategory": "labReport",
            "groundTruth": gt_fields,
            "renderPath": str(RENDER_DIR / pdf_name),
            "mimicSource": True,
        }
        with open(GT_DIR / f"{enc_hash}.json", "w") as f:
            json.dump(gt, f, indent=2)

        gt_manifest.append({
            "file": pdf_name,
            "groundTruth": f"{enc_hash}.json",
            "templateName": tname,
            "providerLayoutHash": lhash,
            "fieldCount": len(gt_fields),
            "encounterHash": enc_hash,
            "subjectHash": sub_hash,
        })

        template_counts[tname] += 1
        rendered += 1
        if rendered % 50 == 0:
            print(f"  ...rendered {rendered}")

    with open(RENDER_DIR / "manifest.json", "w") as f:
        json.dump({
            "version": "4.0",
            "drift_ratio": DRIFT_RATIO,
            "total_rendered": rendered,
            "total_failed": failed,
            "template_distribution": template_counts,
            "unique_layouts": len(set(d["providerLayoutHash"] for d in gt_manifest)),
            "unique_patients": len(set(d["subjectHash"] for d in gt_manifest)),
            "total_fields": sum(d["fieldCount"] for d in gt_manifest),
            "documents": gt_manifest,
        }, f, indent=2)

    print(f"\n═══ Done ═══")
    print(f"  Rendered: {rendered} | Failed: {failed}")
    print(f"  Template distribution:")
    for n, c in template_counts.items():
        print(f"    {n}: {c}")
    print(f"  Unique layouts: {len(set(d['providerLayoutHash'] for d in gt_manifest))}")
    print(f"  Unique patients: {len(set(d['subjectHash'] for d in gt_manifest))}")
    print(f"  Total fields: {sum(d['fieldCount'] for d in gt_manifest):,}")
    print(f"\n  Next: python3 scripts/batch_ingest.py")


if __name__ == "__main__":
    main()
