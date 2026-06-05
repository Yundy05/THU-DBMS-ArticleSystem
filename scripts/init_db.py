# init_db.py - Initializes the databases with sample data for testing. 

import sys
sys.path.insert(0, '.')

from src.db.connections import get_mongo1, get_mongo2, get_mongo3, get_mongo4

def init():
    nodes = [
        (get_mongo1(), "MongoDB1"),
        (get_mongo2(), "MongoDB2"),
    ]

    # DB3 (hot standby) and DB4 (expansion/cold standby) are optional:
    for getter, name in [(get_mongo3, "MongoDB3"), (get_mongo4, "MongoDB4")]:
        try:
            db = getter()
            nodes.append((db, name))
        except Exception:
            print(f"{name}: skipped (not configured or offline).")

    for db, name in nodes:
        db["users"].create_index("uid", unique=True)
        db["articles"].create_index("aid")
        db["reads"].create_index([("uid", 1), ("aid", 1)])
        db["bereads"].create_index("aid")
        db["popular_rank"].create_index(
            [("temporalGranularity", 1), ("timestamp", -1)]
        )
        print(f"{name}: all indexes created successfully.")
        
if __name__ == "__main__":
    init()
    print("Database initialisation completed.")
    
