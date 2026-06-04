# scripts/sync_standby.py
import sys
import argparse
sys.path.insert(0, ".")

from src.db.connections import get_mongo1, get_mongo3
from pymongo import ReplaceOne

COLLECTIONS = ["users", "articles", "reads", "bereads", "popular_rank"]

KEY_MAP = {
    "users":        "uid",
    "articles":     "aid",
    "reads":        "id",
    "bereads":      "aid",
    "popular_rank": "temporalGranularity",
}

BATCH_SIZE = 5000  

def sync_standby(full_reset=False):
    src  = get_mongo1()
    dest = get_mongo3()

    mode = "DROP + INSERT (fast)" if full_reset else "UPSERT bulk_write"
    print(f"=== Syncing DB1 → DB3 (Hot Standby) [{mode}] ===\n")

    for col_name in COLLECTIONS:
        src_col  = src[col_name]
        dest_col = dest[col_name]

        total = src_col.count_documents({})
        if total == 0:
            print(f"  {col_name:<15} skipped (empty)")
            continue

        synced = 0

        if full_reset:
            # Fastest: drop collection entirely, then bulk insert
            dest_col.drop()
            batch = []
            for doc in src_col.find({}, {"_id": 0}):
                batch.append(doc)
                if len(batch) >= BATCH_SIZE:
                    dest_col.insert_many(batch, ordered=False)
                    synced += len(batch)
                    batch = []
            if batch:
                dest_col.insert_many(batch, ordered=False)
                synced += len(batch)
        else:
            # Safe incremental upsert — won't lose existing data
            key = KEY_MAP.get(col_name, "id")
            ops = []
            for doc in src_col.find({}, {"_id": 0}):
                ops.append(ReplaceOne({key: doc[key]}, doc, upsert=True))
                if len(ops) >= BATCH_SIZE:
                    dest_col.bulk_write(ops, ordered=False)
                    synced += len(ops)
                    ops = []
            if ops:
                dest_col.bulk_write(ops, ordered=False)
                synced += len(ops)

        dest_count = dest_col.count_documents({})
        print(f"  {col_name:<15} synced {synced:>6} docs → DB3 now has {dest_count}")

    print("\n✅ Sync complete. DB3 is up to date with DB1.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--full", action="store_true",
                   help="Drop and reinsert (fastest — use after reset_and_load.sh)")
    args = p.parse_args()
    sync_standby(full_reset=args.full)