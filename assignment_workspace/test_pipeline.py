import os
import json
import re
from erp import erp_book, num, round2
from master_data_matcher import MasterDataMatcher

matcher = MasterDataMatcher()
cache_dir = "assignment_workspace/extracted_cache"

print("Building test pipeline across all 42 documents...")
