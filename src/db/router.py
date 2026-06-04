# router.py - Implements fragmentation rules

from src.db.connections import get_mongo1, get_mongo2

def route_user(user: dict):
    """
    User Table fragmented by region:
    
    - Beijing users go to MongoDB1
    - Hong Kong users go to MongoDB2
    """
    db = get_mongo1() if user.get("region") == "Beijing" else get_mongo2()
    return db["users"]

def route_article(article: dict):
    """
    Article Table fragmented by category:

    - Science articles go to MongoDB1 & MongoDB2 (replication)
    - Technology articles go to MongoDB2 only
    """
    targets = []
    category = article.get("category", "")
    if category == "science":
        targets = [get_mongo1()["articles"], get_mongo2()["articles"]]
    elif category == "technology":
        targets = [get_mongo2()["articles"]]
    return targets
    
def route_read(read: dict, user_region: str):
    """
    Read Table follows User table fragmentation (no replication)
    
    - Beijing users go to MongoDB1
    - Hong Kong users go to MongoDB2
    """
    
    db = get_mongo1() if user_region == "Beijing" else get_mongo2()
    return db["reads"]
    
def route_beread(article_category: str): 
    """
    Be-Read Table follows Article table fragmentation with replication
    
    - Science articles go to MongoDB1 & MongoDB2 (replication)
    - Technology articles go to MongoDB2 only
    """
    targets = []
    if article_category == "science":
        targets = [get_mongo1()["bereads"], get_mongo2()["bereads"]]
    elif article_category == "technology":
        targets = [get_mongo2()["bereads"]]
    return targets
    
def route_popular_rank(granularity: str):
    """
    Popular Rank Table fragmented by granularity:
    
    - Daily ranks go to MongoDB1
    - Weekly/Monthly ranks go to MongoDB2
    """
    if granularity == "daily":
        return [get_mongo1()["popular_rank"]]
    else:
        return [get_mongo2()["popular_rank"]]

def read_article(aid: str) -> dict | None:
    """Read-side routing: check DB2 first (has all), fall back to DB1."""
    return get_mongo2()["articles"].find_one({"aid": aid}, {"_id": 0}) or \
           get_mongo1()["articles"].find_one({"aid": aid}, {"_id": 0})

def read_user(uid: str) -> dict | None:
    """Try both nodes — don't assume region without a lookup."""
    return get_mongo1()["users"].find_one({"uid": uid}, {"_id": 0}) or \
           get_mongo2()["users"].find_one({"uid": uid}, {"_id": 0})

def read_beread(aid: str, category: str) -> dict | None:
    if category == "science":
        return get_mongo1()["bereads"].find_one({"aid": aid}, {"_id": 0}) or \
               get_mongo2()["bereads"].find_one({"aid": aid}, {"_id": 0})
    return get_mongo2()["bereads"].find_one({"aid": aid}, {"_id": 0})

def read_popular_rank(granularity: str) -> dict | None:
    col = get_mongo1() if granularity == "daily" else get_mongo2()
    return col["popular_rank"].find_one({"temporalGranularity": granularity}, {"_id": 0})