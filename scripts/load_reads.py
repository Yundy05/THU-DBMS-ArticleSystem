# load_reads.py

import sys, json
sys.path.insert(0, '.')

from src.db.router import route_read
from src.db.connections import get_mongo1, get_mongo2

def load_reads(filepath: str):
    uid_map = {}
    for db in [get_mongo1(), get_mongo2()]:
        for user in db["users"].find({}, {"uid": 1, "region": 1, "_id": 0}):
            uid_map[user["uid"]] = user.get("region", "Hong Kong")

    print(f"Loaded {len(uid_map)} users into uid->region map")

    batch1, batch2 = [], []
    counts = {"Beijing": 0, "Hong Kong": 0}
    BATCH_SIZE = 5000

    def flush(b1, b2):
        if b1:
            get_mongo1()["reads"].insert_many(b1, ordered=False)
        if b2:
            get_mongo2()["reads"].insert_many(b2, ordered=False)

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            read = json.loads(line)
            region = uid_map.get(read["uid"], "Hong Kong")
            if region == "Beijing":
                batch1.append(read)
                counts["Beijing"] += 1
            else:
                batch2.append(read)
                counts["Hong Kong"] += 1

            if len(batch1) + len(batch2) >= BATCH_SIZE:
                flush(batch1, batch2)
                batch1, batch2 = [], []

    flush(batch1, batch2)  # flush remaining

    print(f"Loaded {counts.get('Beijing', 0)} reads -> MongoDB1 (Beijing)")
    print(f"Loaded {counts.get('Hong Kong', 0)} reads -> MongoDB2 (Hong Kong)")
    print(f"Loaded Successfully!")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "db-generation/read.dat"
    load_reads(path)