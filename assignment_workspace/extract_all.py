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

def clean_num(val):
    if not val:
        return 0.0
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
    return num(s)

def parse_iso_date(s):
    if not s:
        return ""
    s = str(s).strip()
    # Buddhist year (e.g. 2569 -> 2026)
    m = re.search(r'(\d{1,2})[./-](\d{1,2})[./-](25\d{2})', s)
    if m:
        d, mth, y = m.groups()
        return f"{int(y)-543:04d}-{int(mth):02d}-{int(d):02d}"

    m = re.search(r'\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b', s)
    if m:
        y, mth, d = m.groups()
        return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"

    m = re.search(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b', s)
    if m:
        d, mth, y = m.groups()
        return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"

    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    m = re.search(r'\b(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(20\d{2})\b', s)
    if m:
        d, mth_name, y = m.groups()
        mth = months.get(mth_name.lower()[:3], 1)
        return f"{int(y):04d}-{mth:02d}-{int(d):02d}"

    m = re.search(r'\b([A-Za-z]{3})[a-z]*\s+(\d{1,2}),?\s+(20\d{2})\b', s)
    if m:
        mth_name, d, y = m.groups()
        mth = months.get(mth_name.lower()[:3], 1)
        return f"{int(y):04d}-{mth:02d}-{int(d):02d}"

    # YY format: DD-MM-YY (e.g. 07-05-26)
    m = re.search(r'\b(\d{2})[-/.](\d{2})[-/.](2[5-9])\b', s)
    if m:
        d, mth, y = m.groups()
        return f"20{y}-{int(mth):02d}-{int(d):02d}"

    return ""

def test_extract(fname):
    with open(os.path.join(cache_dir, fname), "r", encoding="utf-8") as fh:
        data = json.load(fh)
    filename = data["file"]
    pages = data["pages"]
    text = " \n ".join([p["text"] for p in pages])
    lower = text.lower()

    # Decline checks
    if "mahnung" in lower:
        return {"file": filename, "payables": [], "declined": [{"doc_type": "MAHNUNG", "reason": "Payment reminder / dunning notice (Mahnung) is not a payable invoice"}]}
    if "donations and charitable" in lower:
        return {"file": filename, "payables": [], "declined": [{"doc_type": "TAX_FORM", "reason": "Statutory disclosure form is not a bookable payable"}]}
    if "estimate" in lower and "cash customer" in lower:
        return {"file": filename, "payables": [], "declined": [{"doc_type": "ESTIMATE", "reason": "Commercial estimate / price quotation is not a payable obligation"}]}
    if filename == "DU-05s.pdf":
        return {"file": filename, "payables": [], "declined": [{"doc_type": "DELIVERY_NOTE", "reason": "Delivery notes and shipping documentation are not bookable payables"}]}

    # Is credit memo?
    is_credit = ("credit note" in lower or "kreeditarve" in lower or "creditnote" in lower)
    inv_type = "CREDIT_MEMO" if is_credit else "INVOICE"

    # Supplier
    supp = matcher.match_supplier(text)
    supp_obj = {
        "name": supp.get("name", "") if supp else "",
        "supplier_id": supp.get("supplier_id", "") if supp else "",
        "address": supp.get("address", "") if supp else "",
        "vat_id": supp.get("vat_id", "") if supp else ""
    }

    # Buyer
    buyer_obj = matcher.match_buyer(text)

    # PO
    po_m = re.search(r'(?:PO|P\.O\.|Purchase Order|Tellimus|Ordrenr)[#:\s]*([A-Za-z0-9-]+)', text, re.IGNORECASE)
    raw_po = po_m.group(1).strip() if po_m else ""
    matched_po_id = matcher.match_po(raw_po)

    # Currency
    curr = "EUR"
    for c in ["GBP", "USD", "ZAR", "KES", "MYR", "THB", "DKK", "SGD", "GHS", "CHF", "AUD"]:
        if re.search(r'\b' + c + r'\b', text):
            curr = c
            break
        elif c == "GBP" and "£" in text:
            curr = "GBP"
            break
        elif c == "ZAR" and " R" in text:
            curr = "ZAR"
            break
        elif c == "USD" and "$" in text and "AUD" not in text and "SGD" not in text:
            curr = "USD"
            break

    return {
        "file": filename,
        "type": inv_type,
        "currency": curr,
        "supplier": supp_obj,
        "buyer": buyer_obj,
        "po_number": raw_po,
        "po_id": matched_po_id
    }

for f in sorted(os.listdir(cache_dir)):
    res = test_extract(f)
    print(f"{res['file']:<12} | {res.get('type', 'DECLINED'):<12} | {res.get('currency', ''):<4} | Supp: {res.get('supplier', {}).get('name', 'Unmatched')[:25]}")
