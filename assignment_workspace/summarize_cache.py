import os
import json

cache_dir = r"assignment_workspace/extracted_cache"
files = sorted(os.listdir(cache_dir))
print(f"Total cached files: {len(files)}")
total_pages = 0
for f in files:
    with open(os.path.join(cache_dir, f), "r", encoding="utf-8") as fh:
        data = json.load(fh)
    p_cnt = data["page_count"]
    total_pages += p_cnt
    chars = sum(len(p["text"]) for p in data["pages"])
    first_line = data["pages"][0]["text"].replace("\n", " ")[:60]
    print(f"{f:16} | pages: {p_cnt:2} | chars: {chars:5} | snippet: {first_line}")

print(f"Total pages across all files: {total_pages}")
