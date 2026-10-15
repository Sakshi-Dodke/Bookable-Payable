import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

cache_dir = "assignment_workspace/extracted_cache"

files = sys.argv[1:] if len(sys.argv) > 1 else ["INV-01.json"]

for f in files:
    if not f.endswith(".json"):
        f += ".json"
    path = os.path.join(cache_dir, f)
    if not os.path.exists(path):
        print(f"Not found: {path}")
        continue
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    print("=" * 70)
    print(f"FILE: {f} (Pages: {data['page_count']})")
    print("=" * 70)
    for p in data['pages']:
        print(f"--- Page {p['page_num']} ---")
        for line in p['text'].split('\n'):
            line = line.strip()
            if line:
                print("  ", line)
