import os
import json
import re

sys_cache_dir = "assignment_workspace/extracted_cache"
files = sorted(os.listdir(sys_cache_dir))

print(f"Inspecting {len(files)} cached documents...")

doc_inventory = []

for f in files:
    path = os.path.join(sys_cache_dir, f)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    
    filename = data["file"]
    p_cnt = data["page_count"]
    
    # Check declination indicators
    full_text = " \n ".join([p["text"] for p in data["pages"]])
    lower_full = full_text.lower()
    
    declined_reason = None
    doc_type = None
    
    if "mahnung" in lower_full:
        doc_type = "DUNNING_REMINDER"
        declined_reason = "Payment reminder / dunning notice (Mahnung) is not a payable invoice"
    elif "donations and charitable contributions" in lower_full or "cadence technology form" in lower_full:
        doc_type = "TAX_DISCLOSURE_FORM"
        declined_reason = "Statutory disclosure form is not a bookable payable"
    elif "estimate" in lower_full and "cash customer" in lower_full:
        doc_type = "ESTIMATE"
        declined_reason = "Commercial estimate / price quotation is not a payable obligation"
    
    # Currency search
    currencies = set()
    for curr in ["EUR", "USD", "GBP", "GHS", "ZAR", "KES", "MYR", "THB", "CHF", "SGD", "BRL", "AUD"]:
        if re.search(r"\b" + curr + r"\b", full_text) or (curr == "EUR" and "€" in full_text) or (curr == "GBP" and "£" in full_text) or (curr == "USD" and "$" in full_text):
            currencies.add(curr)

    # Dates
    date_matches = re.findall(r"\b(\d{1,4}[-./]\d{1,2}[-./]\d{2,4})\b", full_text)

    # Amounts
    amounts = re.findall(r"\b(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\b", full_text)

    doc_inventory.append({
        "file": filename,
        "pages": p_cnt,
        "declined": declined_reason is not None,
        "doc_type": doc_type or ("CREDIT_MEMO" if ("credit note" in lower_full or "kreeditarve" in lower_full) else "INVOICE"),
        "declined_reason": declined_reason,
        "currencies": list(currencies)[:3],
        "date_sample": date_matches[:3],
        "amount_sample": amounts[-5:] if amounts else []
    })

print(json.dumps(doc_inventory, indent=2))
