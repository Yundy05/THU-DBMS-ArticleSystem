#run_queries.py

import sys
sys.path.insert(0, ".")

from src.db.connections import get_mongo1, get_mongo2

def query_users(region=None):
    db = get_mongo1() if region == "Beijing" else get_mongo2()
    filter_ = {"region": region} if region else {}
    results = list(db["users"].find(filter_).limit(5))
    print(f"\n--- Users (region={region}) ---")
    for u in results:
        print(f"  uid={u.get('uid')} name={u.get('name')} region={u.get('region')}")

def query_articles(category=None):
    db = get_mongo2()  # DBMS2 has ALL articles
    filter_ = {"category": category} if category else {}
    results = list(db["articles"].find(filter_).limit(5))
    print(f"\n--- Articles (category={category}) ---")
    for a in results:
        print(f"  aid={a.get('aid')} title={a.get('title')} category={a.get('category')}")

def query_user_reads(uid: str):
    """Join User + Read for a given uid."""
    # Find user in correct DB
    user = get_mongo1()["users"].find_one({"uid": uid}) or \
           get_mongo2()["users"].find_one({"uid": uid})
    if not user:
        print(f"User {uid} not found")
        return
    region = user.get("region", "Hong Kong")
    db = get_mongo1() if region == "Beijing" else get_mongo2()
    reads = list(db["reads"].find({"uid": uid}).limit(5))
    print(f"\n--- Read history for uid={uid} (region={region}) ---")
    for r in reads:
        print(f"  aid={r.get('aid')} agree={r.get('agreeOrNot')} comment={r.get('commentOrNot')}")

def query_top5_popular(granularity="daily"):
    """Top-5 popular articles with article details."""
    db = get_mongo1() if granularity == "daily" else get_mongo2()
    rank = db["popular_rank"].find_one({"temporalGranularity": granularity})
    if not rank:
        print(f"No popular-rank data for {granularity}")
        return
    aids = rank.get("articleAidList", [])
    print(f"\n--- Top-5 Popular Articles ({granularity}) ---")
    for aid in aids:
        art = get_mongo2()["articles"].find_one({"aid": aid})
        if art:
            print(f"  aid={aid} title={art.get('title')} category={art.get('category')} image={art.get('image','')[:30]}")

if __name__ == "__main__":
    query_users(region="Beijing")
    query_users(region="Hong Kong")
    query_articles(category="science")
    query_articles(category="technology")
    query_user_reads("0")
    query_top5_popular("daily")
    query_top5_popular("weekly")
    query_top5_popular("monthly")