"""
Writes meta.json into each opening database directory.
Skips .pgn files entirely — only touches meta.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opening_data import OPENINGS

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database")

written, skipped, missing = 0, 0, []

for dir_name, data in OPENINGS.items():
    dir_path = os.path.join(BASE_DIR, dir_name)
    if not os.path.isdir(dir_path):
        missing.append(dir_name)
        continue
    meta_path = os.path.join(dir_path, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    written += 1

# Report dirs that exist but have no entry in OPENINGS
all_dirs = [d for d in os.listdir(BASE_DIR)
            if os.path.isdir(os.path.join(BASE_DIR, d))]
no_entry = [d for d in all_dirs if d not in OPENINGS]

print(f"✅ Written : {written}")
print(f"❓ Missing dirs (key in OPENINGS but no folder): {missing}")
print(f"📂 Dirs with no OPENINGS entry yet : {no_entry}")
