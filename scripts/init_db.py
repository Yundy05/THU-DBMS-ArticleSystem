# init_db.py - Initializes the databases with sample data for testing. 

import sys
sys.path.insert(0, '.')

from src.db.connections import get_mongo1, get_mongo2

def init():
    for db, name in [(get_mongo1(), "MongoDB1"), (get_mongo2(), "MongoDB2")]:
        db["users"].create_index("uid", unique=True)
        db["articles"].create_index("aid")
        db["reads"].create_index([("uid", 1), ("aid", 1)])
        db["bereads"].create_index("aid")
        db["popular_ranks"].create_index([("granularity", 1), ("timestamp", -1)])
        print(f"{name} All indexes created successfully.")
        
if __name__ == "__main__":
    init()
    print("Database initialization completed.")
    
