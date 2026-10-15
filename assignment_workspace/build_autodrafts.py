import os
import sys
import json
import re
from datetime import datetime
from erp import erp_book, num, round2
from master_data_matcher import MasterDataMatcher

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

matcher = MasterDataMatcher()
cache_dir = "assignment_workspace/extracted_cache"

def clean_num_str(val):
    if val is None or val == "":
        return ""
    if isinstance(val, (int, float)):
        return f"{val:.2f}"
    s = str(val).strip()
    s = re.sub(r'[€$£¥₹\s]', '', s)
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) in [2, 3]:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    n = num(s)
    return f"{n:.2f}"

def parse_iso_date(s):
    if not s:
        return ""
    s = str(s).strip()
    # Check Buddhist year (e.g. 2569 -> 2026)
    m = re.search(r'(\d{1,2})[./-](\d{1,2})[./-](25\d{2})', s)
    if m:
        d, mth, y = m.groups()
        gy = int(y) - 543
        return f"{gy:04d}-{int(mth):02d}-{int(d):02d}"

    # Standard YYYY-MM-DD
    m = re.search(r'\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b', s)
    if m:
        y, mth, d = m.groups()
        return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"

    # Standard DD.MM.YYYY or DD/MM/YYYY
    m = re.search(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b', s)
    if m:
        d, mth, y = m.groups()
        return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"

    # DD Month YYYY (e.g. 30 Apr 2025)
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    m = re.search(r'\b(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(20\d{2})\b', s)
    if m:
        d, mth_name, y = m.groups()
        mth = months.get(mth_name.lower()[:3], 1)
        return f"{int(y):04d}-{mth:02d}-{int(d):02d}"

    # Month DD, YYYY
    m = re.search(r'\b([A-Za-z]{3})[a-z]*\s+(\d{1,2}),?\s+(20\d{2})\b', s)
    if m:
        mth_name, d, y = m.groups()
        mth = months.get(mth_name.lower()[:3], 1)
        return f"{int(y):04d}-{mth:02d}-{int(d):02d}"

    return ""

print("Extractor modules initialized.")
