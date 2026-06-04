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

def check_replica_consistency():
    db1, db2 = get_mongo1(), get_mongo2()
    sci1 = db1["articles"].count_documents({"category": "science"})
    sci2 = db2["articles"].count_documents({"category": "science"})
    br1  = db1["bereads"].count_documents({})
    br2  = db2["bereads"].count_documents({})
    pr1  = db1["popular_rank"].count_documents({})
    pr2  = db2["popular_rank"].count_documents({})
    print(f"\n=== Replica Consistency Check ===")
    print(f"  Science articles: DB1={sci1}, DB2={sci2} → {'✅ MATCH' if sci1==sci2 else '❌ MISMATCH'}")
    print(f"  Be-Read (science): DB1={br1}, DB2 total={br2}")
    print(f"  Popular-Rank: DB1(daily)={pr1}, DB2(weekly/monthly)={pr2}")
    
if __name__ == "__main__":
    monitor()
    check_replica_consistency()