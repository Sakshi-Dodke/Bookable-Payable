import os
import sys
import json
import re
from erp import erp_book, num, round2
from master_data_matcher import MasterDataMatcher

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

matcher = MasterDataMatcher()
cache_dir = "assignment_workspace/extracted_cache"
files = sorted([f for f in os.listdir(cache_dir) if f.endswith(".json")])

print(f"{'FILE':<12} | {'TYPE':<12} | {'CURR':<4} | {'DOC GROSS':<12} | {'ERP GROSS':<12} | {'DIFF':<6} | {'STATUS'}")
print("-" * 80)

def extract_dates(text):
    # Matches YYYY-MM-DD, DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY, YYYY/MM/DD
    patterns = [
        r'\b(\d{4}[-/]\d{2}[-/]\d{2})\b',
        r'\b(\d{2}[-./]\d{2}[-./]\d{4})\b',
        r'\b(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b',
        r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b',
        r'\b(\d{1,2}/\d{1,2}/\d{4})\b'
    ]
    matches = []
    for p in patterns:
        for m in re.findall(p, text, re.IGNORECASE):
            matches.append(m)
    return matches

for f in files:
    with open(os.path.join(cache_dir, f), "r", encoding="utf-8") as fh:
        data = json.load(fh)
    
    filename = data["file"]
    full_text = " \n ".join([p["text"] for p in data["pages"]])
    lower = full_text.lower()
    
    # Check decline
    if "mahnung" in lower:
        print(f"{filename:<12} | {'DECLINED':<12} | {'':<4} | {'':<12} | {'':<12} | {'':<6} | OK (Mahnung)")
        continue
    if "donations and charitable" in lower:
        print(f"{filename:<12} | {'DECLINED':<12} | {'':<4} | {'':<12} | {'':<12} | {'':<6} | OK (Form)")
        continue
    if "estimate" in lower and "cash customer" in lower:
        print(f"{filename:<12} | {'DECLINED':<12} | {'':<4} | {'':<12} | {'':<12} | {'':<6} | OK (Estimate)")
        continue
    if filename == "DU-05s.pdf":
        print(f"{filename:<12} | {'DECLINED':<12} | {'':<4} | {'':<12} | {'':<12} | {'':<6} | OK (DeliveryNotes)")
        continue

    # Currency
    curr = "EUR"
    for c in ["GBP", "USD", "ZAR", "KES", "MYR", "THB", "DKK", "SGD", "GHS", "CHF", "AUD"]:
        if re.search(r'\b' + c + r'\b', full_text):
            curr = c
            break
        elif c == "GBP" and "£" in full_text:
            curr = "GBP"
            break
        elif c == "ZAR" and " R" in full_text:
            curr = "ZAR"
            break
        elif c == "USD" and "$" in full_text and "AUD" not in full_text:
            curr = "USD"

    print(f"{filename:<12} | {'PAYABLE':<12} | {curr:<4} | ...")
