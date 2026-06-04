# run_queries.py

import sys
from pathlib import Path
sys.path.insert(0, ".")

from src.db.connections import get_mongo1, get_mongo2

ROOT = Path(__file__).resolve().parents[1]


def _text_preview(article, max_chars=80):
    """Read first N chars of article text file from disk."""
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
    """Check if video file exists on disk."""
    aid = str(article.get("aid", "")).lstrip("0") or "0"
    video_file = article.get("video", "")
    if not video_file:
        return False
    p = ROOT / "db-generation" / "articles" / f"article{aid}" / video_file
    return p.exists()


def query_users(region=None):
    db = get_mongo1() if region == "Beijing" else get_mongo2()
    filter_ = {"region": region} if region else {}
    results = list(db["users"].find(filter_).limit(5))
    node = "MongoDB1" if region == "Beijing" else "MongoDB2"
    print(f"\n--- Users (region={region}) → {node} ---")
    for u in results:
        print(f"  uid={u.get('uid')} name={u.get('name')} "
              f"region={u.get('region')} lang={u.get('language')}")


def query_articles(category=None):
    db = get_mongo2()  # DB2 has ALL articles
    filter_ = {"category": category} if category else {}
    results = list(db["articles"].find(filter_).limit(5))
    print(f"\n--- Articles (category={category}) → MongoDB2 ---")
    for a in results:
        print(f"  aid={a.get('aid')} title={a.get('title')} "
              f"category={a.get('category')} authors={a.get('authors','')[:30]}")


def query_user_reads(uid: str):
    """Distributed join: User (fragmented) ⋈ Read (fragmented) ⋈ Article (DB2)."""
    user = (get_mongo1()["users"].find_one({"uid": uid}) or
            get_mongo2()["users"].find_one({"uid": uid}))
    if not user:
        print(f"User {uid} not found")
        return

    region = user.get("region", "Hong Kong")
    reads_db = get_mongo1() if region == "Beijing" else get_mongo2()
    reads = list(reads_db["reads"].find({"uid": uid}).limit(5))

    print(f"\n--- Read history: uid={uid} (region={region}) ---")
    print(f"  [Join: User from {'MongoDB1' if region == 'Beijing' else 'MongoDB2'}"
          f" ⋈ Read from {'MongoDB1' if region == 'Beijing' else 'MongoDB2'}"
          f" ⋈ Article from MongoDB2]")
    for r in reads:
        art = get_mongo2()["articles"].find_one({"aid": r.get("aid")}, {"title": 1, "category": 1})
        print(f"  aid={r.get('aid'):<6} "
              f"title={str(art.get('title','?')):<20} "
              f"agree={r.get('agreeOrNot')} "
              f"comment={r.get('commentOrNot')} "
              f"share={r.get('shareOrNot')}")


def query_top5_popular(granularity="daily"):
    """Top-5 popular articles with full details: text preview, images, video."""
    db = get_mongo1() if granularity == "daily" else get_mongo2()
    node = "MongoDB1" if granularity == "daily" else "MongoDB2"
    rank = db["popular_rank"].find_one({"temporalGranularity": granularity})
    if not rank:
        print(f"\nNo popular-rank data for {granularity} — run derive_popular_rank.py")
        return

    print(f"\n--- Top-5 Popular Articles ({granularity}) → {node} ---")
    print(f"  [Join: PopularRank from {node} ⋈ Article from MongoDB2]")

    for i, aid in enumerate(rank.get("articleAidList", [])[:5], 1):
        art = get_mongo2()["articles"].find_one({"aid": aid})
        if not art:
            print(f"  {i}. aid={aid} — article not found")
            continue

        # Images
        images = [f.strip() for f in str(art.get("image", "")).split(",") if f.strip()]
        image_str = f"{len(images)} image(s): {images[0]}" if images else "no images"

        # Video
        video_file = art.get("video", "")
        if video_file and _video_exists(art):
            video_str = f"✅ {video_file}"
        elif video_file:
            video_str = f"⚠ {video_file} (file missing)"
        else:
            video_str = "none"

        # Text preview
        text_preview = _text_preview(art)

        print(f"\n  #{i} aid={aid} [{art.get('category','').upper()}]")
        print(f"     Title   : {art.get('title', '')}")
        print(f"     Authors : {art.get('authors', '')}")
        print(f"     Images  : {image_str}")
        print(f"     Video   : {video_str}")
        print(f"     Text    : {text_preview}")


if __name__ == "__main__":
    query_users(region="Beijing")
    query_users(region="Hong Kong")
    query_articles(category="science")
    query_articles(category="technology")
    query_user_reads("0")
    query_top5_popular("daily")
    query_top5_popular("weekly")
    query_top5_popular("monthly")