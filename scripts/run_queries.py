# run_queries.py

import sys
from pathlib import Path
sys.path.insert(0, ".")

from pymongo import MongoClient
from src.db.connections import get_mongo1, get_mongo2, get_mongo3

ROOT = Path(__file__).resolve().parents[1]


def _db1_or_standby(label=False):
    """get_mongo1() already handles DB3 fallback internally in connections.py."""
    try:
        client = MongoClient(os.getenv("MONGO1_URI"), serverSelectionTimeoutMS=1500)
        client.admin.command("ping")
        if label:
            print("  [Node: MongoDB1]")
        return get_mongo1(), "MongoDB1"
    except Exception:
        if label:
            print("  [MongoDB1 unreachable → failing over to MongoDB3 (hot standby)]")
        return get_mongo3(), "MongoDB3 (failover)"

def _text_preview(article, max_chars=80):
    aid = str(article.get("aid", "")).lstrip("0") or "0"
    text_file = article.get("text", "")
    if not text_file:
        return "(no text)"
    p = ROOT / "db-generation" / "articles" / f"article{aid}" / text_file
    try:
        return p.read_text(errors="ignore").strip()[:max_chars] + "..." if p.exists() else "(file missing)"
    except Exception:
        return "(read error)"

def _video_exists(article):
    aid = str(article.get("aid", "")).lstrip("0") or "0"
    video_file = article.get("video", "")
    if not video_file:
        return False
    p = ROOT / "db-generation" / "articles" / f"article{aid}" / video_file
    return p.exists()

def _sep(title=""):
    width = 60
    if title:
        print(f"\n{'─' * 4} {title} {'─' * max(0, width - len(title) - 6)}")
    else:
        print("─" * width)

# ── query 1: users by region

def query_users(region=None):
    if region == "Beijing":
        db, node = _db1_or_standby()
    else:
        db, node = get_mongo2(), "MongoDB2"
    filter_ = {"region": region} if region else {}
    results = list(db["users"].find(filter_).limit(5))
    _sep(f"Users (region={region}) → {node}")
    for u in results:
        print(f"  uid={u.get('uid'):<6} name={u.get('name'):<20} "
              f"region={u.get('region'):<12} lang={u.get('language')}")

# ── query 2: articles by category 

def query_articles(category=None):
    db = get_mongo2()
    filter_ = {"category": category} if category else {}
    results = list(db["articles"].find(filter_).limit(5))
    _sep(f"Articles (category={category}) → MongoDB2")
    for a in results:
        print(f"  aid={a.get('aid'):<6} category={a.get('category'):<14} "
              f"title={a.get('title','')[:35]}")

# ── query 3: distributed join — user ⋈ reads ⋈ article

def query_user_reads(uid: str):
    """Distributed join: User (fragmented) ⋈ Read (fragmented) ⋈ Article (DB2)."""
    user = (get_mongo1()["users"].find_one({"uid": uid}) or
            get_mongo2()["users"].find_one({"uid": uid}))
    if not user:
        print(f"  User {uid} not found")
        return

    region = user.get("region", "Hong Kong")
    reads_db, reads_node = (_db1_or_standby() if region == "Beijing"
                            else (get_mongo2(), "MongoDB2"))
    reads = list(reads_db["reads"].find({"uid": uid}).limit(5))

    user_node = "MongoDB1" if region == "Beijing" else "MongoDB2"
    _sep(f"Read history: uid={uid} (region={region})")
    print(f"  [Join: User({user_node}) ⋈ Read({reads_node}) ⋈ Article(MongoDB2)]")
    for r in reads:
        art = get_mongo2()["articles"].find_one({"aid": r.get("aid")}, {"title": 1, "category": 1})
        title = (art or {}).get("title", "?")
        print(f"  aid={r.get('aid'):<6} title={str(title):<22} "
              f"agree={r.get('agreeOrNot')} comment={r.get('commentOrNot')} share={r.get('shareOrNot')}")

# ── query 4: top-5 popular articles 

def query_top5_popular(granularity="daily"):
    """Top-5 popular articles with full details: text preview, images, video."""
    if granularity == "daily":
        db, node = _db1_or_standby()
    else:
        db, node = get_mongo2(), "MongoDB2"

    rank = db["popular_rank"].find_one({"temporalGranularity": granularity})
    if not rank:
        print(f"\n  No popular-rank data for {granularity} — run derive_popular_rank.py")
        return

    _sep(f"Top-5 Popular ({granularity}) → {node}")
    print(f"  [Join: PopularRank({node}) ⋈ Article(MongoDB2)]")

    for i, aid in enumerate(rank.get("articleAidList", [])[:5], 1):
        art = get_mongo2()["articles"].find_one({"aid": aid})
        if not art:
            print(f"  {i}. aid={aid} — article not found")
            continue

        images = [f.strip() for f in str(art.get("image", "")).split(",") if f.strip()]
        image_str = f"{len(images)} image(s): {images[0]}" if images else "no images"

        video_file = art.get("video", "")
        if video_file and _video_exists(art):
            video_str = f"✅ {video_file}"
        elif video_file:
            video_str = f"⚠ {video_file} (file missing)"
        else:
            video_str = "none"

        print(f"\n  #{i} aid={aid} [{art.get('category','').upper()}]")
        print(f"     Title   : {art.get('title', '')}")
        print(f"     Authors : {art.get('authors', '')}")
        print(f"     Images  : {image_str}")
        print(f"     Video   : {video_str}")
        print(f"     Text    : {_text_preview(art)}")

# ── query 5: DB3 hot-standby failover demo

def query_standby_failover():
    """
    Demo query: attempt DB1, fall back to DB3 if unreachable.
    Shows the hot-standby takeover visibly in the terminal.
    """
    _sep("Hot-Standby Failover Demo")
    print("  Attempting to reach MongoDB1...")
    db, node = _db1_or_standby(label=True)

    user_count = db["users"].count_documents({})
    read_count  = db["reads"].count_documents({})
    rank = db["popular_rank"].find_one({"temporalGranularity": "daily"})
    top_aid = (rank or {}).get("articleAidList", [None])[0]

    print(f"  Users   : {user_count}")
    print(f"  Reads   : {read_count}")
    print(f"  Top daily article AID : {top_aid}")
    print(f"  ✅ Query served by: {node}")

if __name__ == "__main__":
    query_users(region="Beijing")
    query_users(region="Hong Kong")
    query_articles(category="science")
    query_articles(category="technology")
    query_user_reads("0")
    query_top5_popular("daily")
    query_top5_popular("weekly")
    query_top5_popular("monthly")
    query_standby_failover()
