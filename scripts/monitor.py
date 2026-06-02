#monitor.py - Monitor MongoDB databases for document counts, 
# collection sizes, and connection stats.

import sys
sys.path.insert(0, ".")

from src.db.connections import get_mongo1, get_mongo2

def monitor():
    for db, label in [(get_mongo1(), "MongoDB1 (mongo1 — port 27017)"),
                      (get_mongo2(), "MongoDB2 (mongo2 — port 27018)")]:
        print(f"\n=== {label} ===")
        for col_name in ["users", "articles", "reads", "bereads", "popular_rank"]:
            count = db[col_name].count_documents({})
            try:
                stats = db.command("collstats", col_name)
                size_mb = round(stats.get("size", 0) / 1024 / 1024, 2)
            except Exception:
                size_mb = 0
            print(f"  {col_name:<15} docs={count:<8} size={size_mb} MB")

        info = db.command("serverStatus")
        conns = info.get("connections", {})
        print(f"  Connections: current={conns.get('current')} available={conns.get('available')}")

if __name__ == "__main__":
    monitor()