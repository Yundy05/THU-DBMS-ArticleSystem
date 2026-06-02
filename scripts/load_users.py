#load_users.py

import sys, json
sys.path.insert(0, '.')

from src.db.router import route_user

def load_users(filepath: str):
    counts = {"Beijing": 0, "Hong Kong": 0}
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            user = json.loads(line)
            collection = route_user(user)
            collection.update_one({"uid": user["uid"]}, {"$set": user}, upsert=True)
            counts[user.get("region", "Hong Kong")] += 1

    print(f"Loaded {counts['Beijing']} users into MongoDB1 (Beijing) and {counts['Hong Kong']} users into MongoDB2 (Hong Kong).")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "db-generation/user.dat"
    load_users(path)
