import os
import sys
import json
import re
from erp import erp_book, num, round2
from master_data_matcher import MasterDataMatcher

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

matcher = MasterDataMatcher()
cache_dir = "assignment_workspace/extracted_cache"

print("Evaluating all documents...")
