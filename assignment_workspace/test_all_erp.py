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

# Helper for dot-decimal conversion
def parse_amount(s):
    if not s:
        return 0.0
    s = str(s).strip()
    s = re.sub(r'[€$£¥₹\s]', '', s)
    # Check if comma is decimal separator (e.g. 1.234,56 or 123,45)
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            # European: 1.234,56 -> 1234.56
            s = s.replace('.', '').replace(',', '.')
        else:
            # US: 1,234.56 -> 1234.56
            s = s.replace(',', '')
    elif ',' in s:
        # Check if single comma is decimal: e.g. 438,00 or 12,50
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) in [2, 3]:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    return num(s)

print("Starting deep document inspection...")
