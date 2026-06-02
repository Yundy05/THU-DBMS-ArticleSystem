#derive_popular_rank.py

import sys
from datetime import datetime, timedelta
from collections import defaultdict
sys.path.insert(0, ".")

from src.db.connections import get_mongo1, get_mongo2
from src.db.router import route_popular_rank

def derive_popular_rank():
    all_reads = []
    for db in [get_mongo1(), get_mongo2()]:
        all_reads.extend(list(db["reads"].find({}, {"aid": 1, "timestamp": 1, "_id": 0})))

    now = datetime.utcnow()
    buckets = {
        "daily":   defaultdict(int),
        "weekly":  defaultdict(int),
        "monthly": defaultdict(int),
    }

    for read in all_reads:
        aid = read["aid"]
        try:
            # Generator timestamps are milliseconds since epoch stored as strings
            ts = datetime.utcfromtimestamp(int(read.get("timestamp", "0")) / 1000)
        except Exception:
            ts = now

        if ts >= now - timedelta(days=1):
            buckets["daily"][aid] += 1
        if ts >= now - timedelta(weeks=1):
            buckets["weekly"][aid] += 1
        if ts >= now - timedelta(days=30):
            buckets["monthly"][aid] += 1

    for granularity, counts in buckets.items():
        # Fallback: if no reads fall in the window, rank by total read count
        if not counts:
            counts = defaultdict(int)
            for read in all_reads:
                counts[read["aid"]] += 1

        top5 = sorted(counts.items(), key=lambda x: -x[1])[:5]
        record = {
            "timestamp": now.isoformat(),
            "temporalGranularity": granularity,
            "articleAidList": [aid for aid, _ in top5]
        }
        for col in route_popular_rank(granularity):
            col.update_one(
                {"temporalGranularity": granularity},
                {"$set": record},
                upsert=True
            )
        print(f"  {granularity}: top-5 = {record['articleAidList']}")

    print("Popular-Rank derivation complete")

if __name__ == "__main__":
    derive_popular_rank()