# migrate_to_mongo4.py - Example data migration to an expansion node 

import sys
sys.path.insert(0, ".")

from src.db.connections import get_mongo1, get_mongo2, get_mongo4


def migrate_basic():
    src1 = get_mongo1()
    src2 = get_mongo2()
    dest = get_mongo4()

    # Example: users and articles only
    collections = ["users", "articles"]

    for col in collections:
        dest_col = dest[col]
        dest_col.drop()  # reset for demo
        print(f"MongoDB4: cleared '{col}' collection.")

    # Copy all users from DB1 and DB2 into DB4
    for src, name in [(src1, "MongoDB1"), (src2, "MongoDB2")]:
        for col in collections:
            src_col = src[col]
            dest_col = dest[col]
            docs = list(src_col.find({}, {"_id": 0}))
            if docs:
                dest_col.insert_many(docs)
            print(f"Copied {len(docs)} documents from {name}.{col} to MongoDB4.{col}.")

    print("Migration to MongoDB4 completed.")


if __name__ == "__main__":
    migrate_basic()