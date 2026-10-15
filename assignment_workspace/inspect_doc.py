import sys
import json
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

doc_names = sys.argv[1:] if len(sys.argv) > 1 else ["INV-01.json"]

for fname in doc_names:
    path = os.path.join("assignment_workspace/extracted_cache", fname)
    if not os.path.exists(path):
        print(f"File not found: {path}")
        continue
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    print("=" * 60)
    print(f"FILE: {fname} (pages: {data['page_count']})")
    print("=" * 60)
    for p in data['pages']:
        print(f"--- Page {p['page_num']} ---")
        print(p['text'])
