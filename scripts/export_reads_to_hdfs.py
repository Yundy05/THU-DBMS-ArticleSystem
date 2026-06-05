#export_reads_to_hdfs.py

"""
Exports read logs from MongoDB (DB1 + DB2) to HDFS as JSONL files.

Architecture role:
  MongoDB  → live OLTP queries   (hot data)
  HDFS     → historical archive  (cold data, batch analytics)

Usage:
  python scripts/export_reads_to_hdfs.py              # export all
  python scripts/export_reads_to_hdfs.py --limit 5000 # export sample
"""

import sys
import json
import argparse
from datetime import datetime, UTC
from pathlib import Path

sys.path.insert(0, ".")

from src.db.connections import get_mongo1, get_mongo2
from hdfs import InsecureClient
import os
from dotenv import load_dotenv
import re


load_dotenv()

HDFS_URL  = os.getenv("HDFS_URL",  "http://localhost:9870")
HDFS_USER = os.getenv("HDFS_USER", "hadoop")
HDFS_BASE = "/project/distrib_db"


def get_hdfs_client() -> InsecureClient:
    user = os.getenv("HDFS_USER", "root")
    client = InsecureClient(HDFS_URL, user=user)
    
    # Patch session to rewrite datanode hostname → localhost
    # Needed when running outside Docker network on Mac
    original_request = client._session.request

    def patched_request(method, url, **kwargs):
        # Rewrite internal Docker hostnames to localhost
        url = re.sub(r'http://datanode:\d+', 
                     lambda m: m.group(0).replace('datanode', 'localhost'), 
                     url)
        url = re.sub(r'http://namenode:\d+',
                     lambda m: m.group(0).replace('namenode', 'localhost'),
                     url)
        return original_request(method, url, **kwargs)

    client._session.request = patched_request
    return client


def ensure_hdfs_dirs(client: InsecureClient):
    for path in [
        HDFS_BASE,
        f"{HDFS_BASE}/reads",
        f"{HDFS_BASE}/users",
        f"{HDFS_BASE}/articles",
    ]:
        try:
            client.makedirs(path, permission=777)
        except Exception as e:
            # Directory may already exist — not an error
            if "already exists" not in str(e).lower():
                print(f"  Warning: could not create {path}: {e}")


def export_collection(client, mongo_db, col_name: str, hdfs_path: str, limit: int):
    """Export one MongoDB collection to HDFS as JSONL."""
    cursor = mongo_db[col_name].find({}, {"_id": 0})
    if limit:
        cursor = cursor.limit(limit)

    docs = list(cursor)
    if not docs:
        print(f"  [{col_name}] empty — skipping.")
        return 0

    jsonl = "\n".join(json.dumps(d, default=str) for d in docs)

    client.write(hdfs_path, data=jsonl.encode("utf-8"), overwrite=True)
    print(f"  [{col_name}] {len(docs):,} docs → {hdfs_path}")
    return len(docs)


def export_all(limit: int = 0):
    client = get_hdfs_client()
    ensure_hdfs_dirs(client)

    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    mongo1 = get_mongo1()
    mongo2 = get_mongo2()

    print(f"\n{'='*55}")
    print(f"  Exporting MongoDB → HDFS  ({ts})")
    print(f"  HDFS: {HDFS_URL}{HDFS_BASE}")
    print(f"{'='*55}\n")

    total = 0

    # Reads — fragmented across DB1 (Beijing) and DB2 (Hong Kong)
    print("Reads (fragmented by region):")
    total += export_collection(
        client, mongo1, "reads",
        f"{HDFS_BASE}/reads/beijing_reads_{ts}.jsonl", limit
    )
    total += export_collection(
        client, mongo2, "reads",
        f"{HDFS_BASE}/reads/hongkong_reads_{ts}.jsonl", limit
    )

    # Users — fragmented by region
    print("\nUsers (fragmented by region):")
    total += export_collection(
        client, mongo1, "users",
        f"{HDFS_BASE}/users/beijing_users_{ts}.jsonl", limit
    )
    total += export_collection(
        client, mongo2, "users",
        f"{HDFS_BASE}/users/hongkong_users_{ts}.jsonl", limit
    )

    # Articles — from DB2 (has all categories)
    print("\nArticles (full — from DB2):")
    total += export_collection(
        client, mongo2, "articles",
        f"{HDFS_BASE}/articles/articles_{ts}.jsonl", limit
    )

    print(f"\n{'='*55}")
    print(f"  Total exported: {total:,} documents")
    print(f"  HDFS Web UI:    http://localhost:9870")
    print(f"{'='*55}\n")


def list_hdfs_files():
    """List what's already in HDFS — useful for verifying exports."""
    client = get_hdfs_client()
    print(f"\nHDFS contents under {HDFS_BASE}:\n")
    try:
        for root, dirs, files in client.walk(HDFS_BASE):
            for f in files:
                path = f"{root}/{f}"
                status = client.status(path)
                size_kb = status["length"] // 1024
                print(f"  {path}  ({size_kb} KB)")
    except Exception as e:
        print(f"  Could not list HDFS: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export MongoDB reads to HDFS.")
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max documents per collection (0 = all)"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List existing HDFS exports instead of exporting"
    )
    args = parser.parse_args()

    if args.list:
        list_hdfs_files()
    else:
        export_all(limit=args.limit)