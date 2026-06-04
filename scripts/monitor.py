#monitor.py - Monitor MongoDB databases for document counts, 
# collection sizes, and connection stats.

import sys
sys.path.insert(0, ".")

from pymongo import MongoClient
from src.db.connections import get_mongo1, get_mongo2, get_mongo3

def _sep(title=""):
    width = 60
    if title:
        print(f"\n{'═' * 4} {title} {'═' * max(0, width - len(title) - 6)}")
    else:
        print("═" * width)

def monitor():
    nodes = [
        (get_mongo1, "MongoDB1 (mongo1 — port 27017)"),
        (get_mongo2, "MongoDB2 (mongo2 — port 27018)"),
        (get_mongo3, "MongoDB3 (mongo3 — port 27019)  [Hot Standby]"),
    ]
    for getter, label in nodes:
        try:
            db = getter()
            db.client.admin.command("ping")
        except Exception as e:
            _sep(label)
            print(f"  ❌ Unreachable: {e}")
            continue

        _sep(label)
        for col_name in ["users", "articles", "reads", "bereads", "popular_rank"]:
            count = db[col_name].count_documents({})
            try:
                stats = db.command("collstats", col_name)
                size_mb = round(stats.get("size", 0) / 1024 / 1024, 2)
            except Exception:
                size_mb = 0
            print(f"  {col_name:<15} docs={count:<8} size={size_mb} MB")

        try:
            info = db.command("serverStatus")
            conns = info.get("connections", {})
            print(f"  Connections: current={conns.get('current')} available={conns.get('available')}")
        except Exception:
            print("  Connections: (unavailable)")

def check_replica_consistency():
    _sep("Replica Consistency Check")
    try:
        db1, db2 = get_mongo1(), get_mongo2()
        sci1 = db1["articles"].count_documents({"category": "science"})
        sci2 = db2["articles"].count_documents({"category": "science"})
        br1  = db1["bereads"].count_documents({})
        br2  = db2["bereads"].count_documents({})
        pr1  = db1["popular_rank"].count_documents({})
        pr2  = db2["popular_rank"].count_documents({})
        print(f"  Science articles : DB1={sci1}, DB2={sci2} → {'✅ MATCH' if sci1==sci2 else '❌ MISMATCH'}")
        print(f"  Be-Read records  : DB1={br1} (science), DB2={br2} (science+tech)")
        print(f"  Popular-Rank     : DB1={pr1} (daily), DB2={pr2} (weekly+monthly)")
    except Exception as e:
        print(f"  ❌ Could not check DB1/DB2: {e}")

def check_standby_sync():
    _sep("DB3 Hot-Standby Sync Check (DB1 vs DB3)")
    try:
        db1 = get_mongo1()
        db1.client.admin.command("ping")
    except Exception:
        print("  ⚠ MongoDB1 offline — skipping sync check")
        return
    try:
        db3 = get_mongo3()
        db3.client.admin.command("ping")
    except Exception:
        print("  ❌ MongoDB3 offline")
        return

    all_match = True
    for col in ["users", "articles", "reads", "bereads", "popular_rank"]:
        c1 = db1[col].count_documents({})
        c3 = db3[col].count_documents({})
        match = c1 == c3
        if not match:
            all_match = False
        icon = "✅" if match else "❌"
        print(f"  {icon} {col:<15} DB1={c1:<8} DB3={c3}")
    print(f"\n  {'✅ DB3 fully in sync with DB1' if all_match else '❌ DB3 out of sync — run: python scripts/sync_standby.py --full'}")
    
if __name__ == "__main__":
    monitor()
    check_replica_consistency()