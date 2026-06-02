#derive_beread.py

import sys
from datetime import datetime
sys.path.insert(0, ".")

from src.db.connections import get_mongo1, get_mongo2
from src.db.router import route_beread

def derive_beread():
    # Gather all reads from both DBs
    all_reads = []
    for db in [get_mongo1(), get_mongo2()]:
        all_reads.extend(list(db["reads"].find({})))
    print(f"Total read records collected: {len(all_reads)}")

    # Build aid -> category map
    cat_map = {}
    for db in [get_mongo1(), get_mongo2()]:
        for art in db["articles"].find({}, {"aid": 1, "category": 1, "_id": 0}):
            cat_map[art["aid"]] = art.get("category", "technology")

    # Aggregate reads per article
    aggregated = {}
    for read in all_reads:
        aid = read["aid"]
        if aid not in aggregated:
            aggregated[aid] = {
                "aid": aid,
                "timestamp": datetime.utcnow().isoformat(),
                "readNum": 0, "readUidList": [],
                "commentNum": 0, "commentUidList": [],
                "agreeNum": 0, "agreeUidList": [],
                "shareNum": 0, "shareUidList": [],
            }
        rec = aggregated[aid]
        uid = read["uid"]
        rec["readNum"] += 1
        rec["readUidList"].append(uid)
        # Values are "1"/"0" strings — NOT booleans
        if read.get("commentOrNot") == "1":
            rec["commentNum"] += 1
            rec["commentUidList"].append(uid)
        if read.get("agreeOrNot") == "1":    # single g — agreeOrNot
            rec["agreeNum"] += 1
            rec["agreeUidList"].append(uid)
        if read.get("shareOrNot") == "1":
            rec["shareNum"] += 1
            rec["shareUidList"].append(uid)

    # Insert into correct DBs
    count = 0
    for aid, beread in aggregated.items():
        category = cat_map.get(aid, "technology")
        collections = route_beread(category)
        for col in collections:
            col.update_one({"aid": aid}, {"$set": beread}, upsert=True)
        count += 1

    print(f"Be-Read derivation complete: {count} records inserted")

if __name__ == "__main__":
    derive_beread()