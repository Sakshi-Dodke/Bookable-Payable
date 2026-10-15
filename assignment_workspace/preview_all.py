import os
import json
import re

cache_dir = r"assignment_workspace/extracted_cache"
cached_files = sorted([f for f in os.listdir(cache_dir) if f.endswith(".json")])

print(f"Total cached files: {len(cached_files)}")
print(f"{'FILE':<12} | {'PAGES':<5} | {'SAMPLE TEXT PREVIEW'}")
print("-" * 80)

for f in cached_files:
    path = os.path.join(cache_dir, f)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    p_cnt = data["page_count"]
    first_page_txt = data["pages"][0]["text"].replace("\n", " ")
    first_page_txt = re.sub(r"\s+", " ", first_page_txt)[:80]
    print(f"{f:<12} | {p_cnt:<5} | {first_page_txt}")
