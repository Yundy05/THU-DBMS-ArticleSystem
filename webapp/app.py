from flask import Flask, render_template, request, abort, send_from_directory, jsonify
from pathlib import Path
import math
import re
import sys
from datetime import datetime, UTC
import time
import uuid
from pymongo import MongoClient
import os
import json
import redis as redis_lib

# - Redis Cahce -
CACHE_TTL = int(os.getenv("CACHE_TTL", 60))

def _get_redis() -> redis_lib.Redis:
    return redis_lib.from_url(
        os.getenv("REDIS_URI", "redis://localhost:6379"),
        decode_responses=True,
    )

def _cache_get(key: str):
    try:
        raw = _get_redis().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None  # Redis down → degrade gracefully, hit MongoDB

def _cache_set(key: str, value):
    try:
        _get_redis().setex(key, CACHE_TTL, json.dumps(value))
    except Exception:
        pass  # Redis down → still return value, just uncached
    return value

def cache_clear():
    """Flush all cached keys — call after any write."""
    try:
        _get_redis().flushdb()
    except Exception:
        pass

def cache_stats() -> dict:
    try:
        r = _get_redis()
        info = r.info("stats")
        keyspace = r.info("keyspace")
        db_info = keyspace.get("db0", {})
        return {
            "status":       "online",
            "live_keys":    db_info.get("keys", 0),
            "ttl_seconds":  CACHE_TTL,
            "hits":         info.get("keyspace_hits", 0),
            "misses":       info.get("keyspace_misses", 0),
            "evictions":    info.get("evicted_keys", 0),
        }
    except Exception:
        return {"status": "offline", "live_keys": 0, "ttl_seconds": CACHE_TTL,
                "hits": 0, "misses": 0, "evictions": 0}
        
# - MongoDB Connections and App Setup -

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from src.db.connections import get_mongo1, get_mongo2, get_mongo3, get_mongo4,node_status
    
except Exception as e:
    raise RuntimeError(
        "Could not import src.db.connections. Check your repo structure and connections.py"
    ) from e

app = Flask(__name__)
ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "db-generation" / "image"
TEXT_ROOT = ROOT / "db-generation" / "bbc_news_texts"


def db1_or_standby():
        return  get_mongo1()

def db2():
    return get_mongo2()
    

def db3():
    return get_mongo3()

def db4():
    return get_mongo4()

def parse_csv(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(",") if v.strip()]


def article_lookup(aid):
    key = f"article:{aid}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    result = (
        db2()["articles"].find_one({"aid": aid}, {"_id": 0})
        or db1_or_standby()["articles"].find_one({"aid": aid}, {"_id": 0})
    )
    return _cache_set(key, result)

def safe_preview(text, n=220):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text[:n] + ("..." if len(text) > n else "")


def normalize_digits(text):
    digits = re.sub(r"\D", "", str(text or ""))
    return digits.lstrip("0") or (digits if digits else "")


def existing_image_candidates(article):
    candidates = []
    seen = set()

    aid_digits = normalize_digits(article.get("aid"))
    article_dir = ROOT / "db-generation" / "articles" / f"article{aid_digits}"

    for raw in parse_csv(article.get("image")):
        name = Path(str(raw).strip()).name
        p = article_dir / name
        if p.exists() and str(p) not in seen:
            candidates.append(p)
            seen.add(str(p))

    return candidates


def category_text_dirs(category):
    mapping = {
        "science": ["tech", "science"],
        "technology": ["tech"],
        "business": ["business"],
        "sport": ["sport"],
        "entertainment": ["entertainment"],
        "politics": ["politics"],
    }
    return mapping.get(str(category or "").lower(), [str(category or "").lower()])

def article_text_candidates(article):
    aid_digits = normalize_digits(article.get("aid"))
    candidates = []
    if aid_digits:
        padded = aid_digits.zfill(3)
        for sub in category_text_dirs(article.get("category")):
            candidates.append(TEXT_ROOT / sub / f"{padded}.txt")
            candidates.append(TEXT_ROOT / sub / f"{aid_digits}.txt")
    return candidates

def load_related_text(article):
    aid_digits = normalize_digits(article.get("aid"))
    article_dir = ROOT / "db-generation" / "articles" / f"article{aid_digits}"

    for raw in parse_csv(article.get("text")):
        name = Path(str(raw).strip()).name
        p = article_dir / name
        if p.exists():
            try:
                raw_text = p.read_text(errors="ignore").strip()
                if raw_text:
                    return {
                        "filename": name,
                        "source_path": str(p),
                        "content": raw_text,
                        "preview": safe_preview(raw_text, 500),
                    }
            except Exception:
                pass
    return None

def safe_count(coll, query=None):
    try:
        return coll.count_documents(query or {})
    except Exception:
        return 0

def _db3_collections():
    try:
        mongo3 = db3()
        return {
            "users":        safe_count(mongo3["users"]),
            "articles":     safe_count(mongo3["articles"]),
            "reads":        safe_count(mongo3["reads"]),
            "bereads":      safe_count(mongo3["bereads"]),
            "popular_rank": safe_count(mongo3["popular_rank"]),
        }
    except Exception:
        return {}

def _db4_collections():
    try:
        mongo4 = db4()
        return {
            "users": safe_count(mongo4["users"]),
            "articles": safe_count(mongo4["articles"]),
            "reads": safe_count(mongo4["reads"]),
            "bereads": safe_count(mongo4["bereads"]),
            "popular_rank": safe_count(mongo4["popular_rank"]),
        }
    except Exception:
        # If MONGO4_URI is not configured or node is down, treat as empty.
        return {}

EXPECTED_COUNTS = {
    "users": 10000,
    "articles": 10000,
    "reads": 1000000,
}

def load_status():
    d1, d2 = db1_or_standby(), db2()
    return {
        "users": {
            "expected": EXPECTED_COUNTS["users"],
            "db1": d1["users"].count_documents({}),
            "db2": d2["users"].count_documents({}),
        },
        "articles": {
            "expected": EXPECTED_COUNTS["articles"],
            "db1": d1["articles"].count_documents({}),
            "db2": d2["articles"].count_documents({}),
        },
        "reads": {
            "expected": EXPECTED_COUNTS["reads"],
            "db1": d1["reads"].count_documents({}),
            "db2": d2["reads"].count_documents({}),
        },
    }

def monitor_snapshot():
    mongo1 = db1_or_standby()
    mongo2 = db2()
    mongo4 = db4()
    statuses = node_status()   # live ping: "online" / "standby" / "offline"
    return [
        {
            "label": "MongoDB1",
            "status": statuses.get("MongoDB1", "offline"),
            "location_note": "Stores Beijing users, science articles replica, Beijing reads, science Be-Read replica, and daily popular rank.",
            "collections": {
                "users":        safe_count(mongo1["users"]),
                "articles":     safe_count(mongo1["articles"]),
                "reads":        safe_count(mongo1["reads"]),
                "bereads":      safe_count(mongo1["bereads"]),
                "popular_rank": safe_count(mongo1["popular_rank"]),
            },
            "managed_data": {
                "regions": {
                    "Beijing":   safe_count(mongo1["users"], {"region": "Beijing"}),
                    "Hong Kong": safe_count(mongo1["users"], {"region": "Hong Kong"}),
                },
                "article_categories": {
                    "science":    safe_count(mongo1["articles"], {"category": "science"}),
                    "technology": safe_count(mongo1["articles"], {"category": "technology"}),
                },
                                "popular_rank_granularity": {
                    "daily":   safe_count(mongo1["popular_rank"], {"temporalGranularity": "daily"}),
                    "weekly":  safe_count(mongo1["popular_rank"], {"temporalGranularity": "weekly"}),
                    "monthly": safe_count(mongo1["popular_rank"], {"temporalGranularity": "monthly"}),
                },
            },
        },
        {
            "label": "MongoDB2",
            "status": statuses.get("MongoDB2", "offline"),
            "location_note": "Stores Hong Kong users, science and technology articles, Hong Kong reads, science and technology Be-Read, and weekly/monthly popular rank.",
            "collections": {
                "users":        safe_count(mongo2["users"]),
                "articles":     safe_count(mongo2["articles"]),
                "reads":        safe_count(mongo2["reads"]),
                "bereads":      safe_count(mongo2["bereads"]),
                "popular_rank": safe_count(mongo2["popular_rank"]),
            },
            "managed_data": {
                "regions": {
                    "Beijing":   safe_count(mongo2["users"], {"region": "Beijing"}),
                    "Hong Kong": safe_count(mongo2["users"], {"region": "Hong Kong"}),
                },
                "article_categories": {
                    "science":    safe_count(mongo2["articles"], {"category": "science"}),
                    "technology": safe_count(mongo2["articles"], {"category": "technology"}),
                },
                "popular_rank_granularity": {
                    "daily":   safe_count(mongo2["popular_rank"], {"temporalGranularity": "daily"}),
                    "weekly":  safe_count(mongo2["popular_rank"], {"temporalGranularity": "weekly"}),
                    "monthly": safe_count(mongo2["popular_rank"], {"temporalGranularity": "monthly"}),
                },
            },
        },
        {
            "label": "MongoDB3 (Hot Standby)",
            "status": statuses.get("MongoDB3", "offline"),
            "location_note": "Hot standby for MongoDB1. Automatically takes over if DB1 goes offline. Mirrors: Beijing users, science articles, Beijing reads, science Be-Read, daily popular rank.",
            "collections": _db3_collections() if statuses.get("MongoDB3") != "offline" else {},
            "managed_data": {},
        },
        {
            "label": "MongoDB4 (Expansion node)",
            "status": statuses.get("MongoDB4", "offline"),
            "location_note": (
                "Reserved for future expansion. Can host new regions or "
                "categories when the data center scales out."
            ),
            "collections": _db4_collections()
            if statuses.get("MongoDB4") != "offline"
            else {},
            "managed_data": {},  # not assigned any shard yet
        },
    ]


def workload_summary():
    mongo1 = db1_or_standby()
    mongo2 = db2()

    return {
        "MongoDB1": {
            "read_records": safe_count(mongo1["reads"]),
            "beread_records": safe_count(mongo1["bereads"]),
            "article_records": safe_count(mongo1["articles"]),
            "user_records": safe_count(mongo1["users"]),
        },
        "MongoDB2": {
            "read_records": safe_count(mongo2["reads"]),
            "beread_records": safe_count(mongo2["bereads"]),
            "article_records": safe_count(mongo2["articles"]),
            "user_records": safe_count(mongo2["users"]),
        },
    }


def latest_ranks():
    cached = _cache_get("latest_ranks")
    if cached is not None:
        return cached

    docs = {
        "daily":   db1_or_standby()["popular_rank"].find_one({"temporalGranularity": "daily"},   {"_id": 0}),
        "weekly":  db2()["popular_rank"].find_one({"temporalGranularity": "weekly"},  {"_id": 0}),
        "monthly": db2()["popular_rank"].find_one({"temporalGranularity": "monthly"}, {"_id": 0}),
    }

    enriched = {}
    for granularity, doc in docs.items():
        rows = []
        if doc:
            for aid in doc.get("articleAidList", [])[:5]:
                art = article_lookup(aid)  # also cached
                if art:
                    aid_digits = normalize_digits(aid)
                    image_urls = [
                        f"/assets/image/{aid_digits}/{p.name}"
                        for p in existing_image_candidates(art)
                    ]
                    rows.append({
                        "aid":        aid,
                        "title":      art.get("title", "Untitled"),
                        "category":   art.get("category", "unknown"),
                        "authors":    art.get("authors", "Unknown"),
                        "abstract":   safe_preview(art.get("abstract", ""), 120),
                        "image_urls": image_urls,
                        "video_url":  existing_video(art),
                    })
        enriched[granularity] = rows

    return _cache_set("latest_ranks", enriched)


@app.route("/")
def home():
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 15
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "aid")

    query = {}
    if category:
        query["category"] = category
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"abstract": {"$regex": q, "$options": "i"}},
            {"authors": {"$regex": q, "$options": "i"}},
            {"keywords": {"$regex": q, "$options": "i"}},
        ]

    sort_map = {
        "aid": [("aid", 1)],
        "title": [("title", 1)],
        "newest": [("timestamp", -1)],
        "oldest": [("timestamp", 1)],
    }
    order = sort_map.get(sort, [("aid", 1)])

    total = db2()["articles"].count_documents(query)
    pages = max(math.ceil(total / per_page), 1)
    page = min(page, pages)

    cursor = (
        db2()["articles"]
        .find(query, {"_id": 0})
        .sort(order)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    articles = []
    for a in cursor:
        a["preview"] = safe_preview(a.get("abstract") or a.get("title"))
        a["local_images"] = existing_image_candidates(a)
        a["text_info"] = load_related_text(a)
        a["text_preview"] = a["text_info"]["preview"] if a["text_info"] else None
        a["video_url"]    = existing_video(a)
        articles.append(a)

    totals = {
        "articles": db2()["articles"].count_documents({}),
        "reads": db1_or_standby()["reads"].count_documents({}) + db2()["reads"].count_documents({}),
        "science": db2()["articles"].count_documents({"category": "science"}),
        "technology": db2()["articles"].count_documents({"category": "technology"}),
    }

    return render_template(
        "index.html",
        articles=articles,
        q=q,
        category=category,
        sort=sort,
        page=page,
        pages=pages,
        total=total,
        totals=totals,
        snapshot=monitor_snapshot(),
    )
    

def replica_consistency():
    try:
        d1, d2 = db1_or_standby(), db2()
        sci1 = d1["articles"].count_documents({"category": "science"})
        sci2 = d2["articles"].count_documents({"category": "science"})
        br1  = d1["bereads"].count_documents({})
        br2  = d2["bereads"].count_documents({})
        pr1  = d1["popular_rank"].count_documents({})
        pr2  = d2["popular_rank"].count_documents({})
        # Sample hash check: compare a single science article record between nodes
        sample1 = d1["articles"].find_one({"category": "science"}, {"_id": 0, "aid": 1, "title": 1})
        sample2 = d2["articles"].find_one(
            {"aid": sample1["aid"]}, {"_id": 0, "aid": 1, "title": 1}
        ) if sample1 else None
        record_match = (sample1 == sample2) if sample1 and sample2 else None
        try:
            d3 = db3()
            reads3  = safe_count(d3["reads"])
            reads1  = safe_count(db1_or_standby()["reads"])
            users3  = safe_count(d3["users"])
            users1  = safe_count(db1_or_standby()["users"])
            standby_sync = {
                "reads":  {"db1": reads1,  "db3": reads3,  "match": reads1 == reads3},
                "users":  {"db1": users1,  "db3": users3,  "match": users1 == users3},
            }
        except Exception:
            standby_sync = None
            
        return {
            "science_articles": {"db1": sci1, "db2": sci2, "match": sci1 == sci2},
            "bereads":          {"db1": br1,  "db2": br2},
            "popular_rank":     {"db1": pr1,  "db2": pr2},
            "sample_record":    {
                "aid":   (sample1 or {}).get("aid", "N/A"),
                "match": record_match,
            },
            "standby_sync":     standby_sync,
        }
    except Exception as e:
        
        return {"error": str(e)}

@app.route("/monitor")
def monitor():
    return render_template(
        "monitor.html",
        snapshot=monitor_snapshot(),
        ranks=latest_ranks(),
        consistency=replica_consistency(),
        workload=workload_summary(),
        load_status=load_status(),
        cache=cache_stats(), 
    )

@app.route("/assets/image/<aid>/<filename>")
def serve_image(aid, filename):
    article_dir = ROOT / "db-generation" / "articles" / f"article{aid}"
    return send_from_directory(article_dir, filename)

def existing_video(article) -> str | None:
    raw = article.get("video")
    if not raw or str(raw).strip() == "":
        return None
    aid_digits = normalize_digits(article.get("aid"))
    article_dir = ROOT / "db-generation" / "articles" / f"article{aid_digits}"
    name = Path(str(raw).strip()).name
    p = article_dir / name
    if p.exists():
        return f"/assets/image/{aid_digits}/{name}"
    return None

def user_lookup(uid: str) -> dict | None:
    return (
        db1_or_standby()["users"].find_one({"uid": uid}, {"_id": 0}) or
        db2()["users"].find_one({"uid": uid}, {"_id": 0})
    )
    
def beread_lookup(aid: str, category: str) -> dict | None:
    if category == "science":
        return (
            db1_or_standby()["bereads"].find_one({"aid": aid}, {"_id": 0}) or
            db2()["bereads"].find_one({"aid": aid}, {"_id": 0})
        )
    return db2()["bereads"].find_one({"aid": aid}, {"_id": 0})

@app.route("/users")
def users():
    q      = request.args.get("q", "").strip()
    region = request.args.get("region", "").strip()
    page   = max(int(request.args.get("page", 1)), 1)
    per_page = 20

    query = {}
    if q:
        query["$or"] = [
            {"name":  {"$regex": q, "$options": "i"}},
            {"uid":   {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]
    if region:
        query["region"] = region

    # Route to correct node; no region = merge both (up to per_page each)
    if region == "Beijing":
        results = list(db1_or_standby()["users"].find(query, {"_id": 0})
                       .skip((page - 1) * per_page).limit(per_page))
        total   = db1_or_standby()["users"].count_documents(query)
    elif region == "Hong Kong":
        results = list(db2()["users"].find(query, {"_id": 0})
                       .skip((page - 1) * per_page).limit(per_page))
        total   = db2()["users"].count_documents(query)
    else:
        half  = per_page // 2
        skip1 = max((page - 1) * half, 0)
        results = (
            list(db1_or_standby()["users"].find(query, {"_id": 0}).skip(skip1).limit(half)) +
            list(db2()["users"].find(query, {"_id": 0}).skip(skip1).limit(half))
        )
        total = (db1_or_standby()["users"].count_documents(query) +
                 db2()["users"].count_documents(query))

    pages = max(math.ceil(total / per_page), 1)
    return render_template(
        "users.html",
        users=results, q=q, region=region,
        page=page, pages=pages, total=total,
    )
    
@app.route("/user/<uid>/reads")
def user_reads(uid: str):
    user = user_lookup(uid)
    if not user:
        abort(404)

    # Reads are fragmented by user region — route to correct node
    node_region = user.get("region", "Hong Kong")
    reads_db    = db1_or_standby() if node_region == "Beijing" else db2()
    raw_reads   = list(reads_db["reads"].find({"uid": uid}, {"_id": 0}).limit(50))

    # Enrich each read record with article info (the join)
    enriched = []
    for r in raw_reads:
        art = article_lookup(r.get("aid", ""))
        enriched.append({
            **r,
            "article_title":    (art or {}).get("title",    "Unknown"),
            "article_category": (art or {}).get("category", "unknown"),
            "article_authors":  (art or {}).get("authors",  ""),
        })

    return render_template(
        "user_reads.html",
        user=user, reads=enriched,
        node_label="MongoDB1 (Beijing)" if node_region == "Beijing" else "MongoDB2 (Hong Kong)",
    )
    
@app.route("/article/<aid>")
def article_detail(aid: str):
    article = article_lookup(aid)
    if not article:
        abort(404)

    article["local_images"] = existing_image_candidates(article)
    article["text_info"]    = load_related_text(article)
    article["video_url"]    = existing_video(article)

    category = article.get("category", "technology")
    beread   = beread_lookup(aid, category)

    return render_template("article.html", article=article, beread=beread)


@app.template_filter("ts_fmt")
def ts_fmt(value, fmt="%B %d, %Y"):
    try:
        return datetime.fromtimestamp(int(value) / 1000, UTC).strftime(fmt)
    except Exception:
        return value or "—"

@app.template_filter("enumerate")
def jinja_enumerate(iterable, start=0):
    return list(enumerate(iterable, start=start))

def _which_db1_node() -> str:
    """Return label for whichever node is currently serving DB1 traffic."""
    try:
        MongoClient(os.getenv("MONGO1_URI"),
                    serverSelectionTimeoutMS=500).admin.command("ping")
        return "MongoDB1"
    except Exception:
        return "MongoDB3 (hot standby active)"

def run_queries_data() -> dict:
    statuses = node_status()
    db1_node = _which_db1_node()
    failover = "MongoDB3" in db1_node 

    # Query 1 & 2: Users by region
    users_beijing = list(db1_or_standby()["users"]
                         .find({"region": "Beijing"}).limit(5))
    users_hk      = list(db2()["users"]
                        .find({"region": "Hong Kong"}).limit(5))

    # Query 3 & 4: Articles by category
    articles_sci  = list(db2()["articles"].find({"category": "science"}).limit(5))
    articles_tech = list(db2()["articles"].find({"category": "technology"}).limit(5))

    # Query 5: Distributed join — user reads
    uid   = "0"
    user  = db1_or_standby()["users"].find_one({"uid": uid}) or db2()["users"].find_one({"uid": uid})
    reads_enriched = []
    reads_node     = "—"
    if user:
        region   = user.get("region", "Hong Kong")
        reads_db = db1_or_standby() if region == "Beijing" else db2()
        reads_node = db1_node if region == "Beijing" else "MongoDB2"
        for r in reads_db["reads"].find({"uid": uid}).limit(5):
            art = db2()["articles"].find_one({"aid": r.get("aid")}, {"title": 1, "category": 1})
            reads_enriched.append({
                **r,
                "title":    (art or {}).get("title", "?"),
                "category": (art or {}).get("category", "?"),
            })

    # Query 6: Top-5 popular
    ranks = {}
    for gran, source_db, node in [
        ("daily",   db1_or_standby(), db1_node),
        ("weekly",  db2(),            "MongoDB2"),
        ("monthly", db2(),            "MongoDB2"),
    ]:
        doc  = source_db["popular_rank"].find_one({"temporalGranularity": gran})
        rows = []
        if doc:
            for aid in doc.get("articleAidList", [])[:5]:
                art = db2()["articles"].find_one({"aid": aid}, {"title": 1, "category": 1})
                rows.append({
                    "aid":      aid,
                    "title":    (art or {}).get("title", "?"),
                    "category": (art or {}).get("category", "?"),
                })
        ranks[gran] = {"node": node, "rows": rows}

    return {
        "db1_node":       db1_node,
        "failover":       failover,
        "db1_status":     statuses.get("MongoDB1", "soffline"),   
        "db2_status":     statuses.get("MongoDB2", "offline"),   
        "db3_status":     statuses.get("MongoDB3", "offline"),   
        "db4_status":     statuses.get("MongoDB4", "offline"),  
        "users_beijing":  users_beijing,
        "users_hk":       users_hk,
        "articles_sci":   articles_sci,
        "articles_tech":  articles_tech,
        "user":           user,
        "reads_enriched": reads_enriched,
        "reads_node":     reads_node,
        "ranks":          ranks,
    }
    
@app.route("/queries")
def queries_page():
    return render_template("queries.html", **run_queries_data())


# ── write: record a read 

def _route_reads_db(region: str):
    """Return the correct reads node based on user region."""
    return db1_or_standby() if region == "Beijing" else db2()

def _beread_nodes(category: str):
    """Return list of DBs that hold Be-Read for this category."""
    if category == "science":
        return [
            (db1_or_standby(), "MongoDB1 (or MongoDB3 standby)"),
            (db2(),            "MongoDB2"),
        ]
    return [(db2(), "MongoDB2")]  

def insert_read(uid: str, aid: str, agree: str, comment: str,
                comment_text: str, share: str) -> dict:
    """
    Full distributed write:
      1. Insert into reads (fragmented by user region)
      2. Update bereads (replicated for science, DB2-only for tech)
    Returns a trace dict describing every node written.
    """
    # Resolve user + region
    user = (db1_or_standby()["users"].find_one({"uid": uid}, {"region": 1}) or
            db2()["users"].find_one({"uid": uid}, {"region": 1}))
    if not user:
        return {"ok": False, "error": f"User {uid} not found"}

    region = user.get("region", "Hong Kong")

    # Resolve article category
    article = db2()["articles"].find_one({"aid": aid}, {"category": 1})
    if not article:
        return {"ok": False, "error": f"Article {aid} not found"}
    category = article.get("category", "technology")

    # Build read record  (agreeOrNot/commentOrNot/shareOrNot stored as "1"/"0" strings)
    now_ms = int(time.time() * 1000)
    read_id = str(uuid.uuid4().int)[:12]
    read_doc = {
        "id":            read_id,
        "timestamp":     str(now_ms),
        "uid":           uid,
        "aid":           aid,
        "readTimeLength": "60",
        "agreeOrNot":    "1" if agree    == "1" else "0",
        "commentOrNot":  "1" if comment  == "1" else "0",
        "commentDetail": comment_text if comment == "1" else "",
        "shareOrNot":    "1" if share    == "1" else "0",
    }

    trace = {"ok": True, "uid": uid, "aid": aid, "region": region,
             "category": category, "writes": []}

    # ── Write 1: Insert into reads ──
    reads_db   = _route_reads_db(region)
    reads_node = "MongoDB1" if region == "Beijing" else "MongoDB2"
    reads_db["reads"].insert_one({**read_doc})
    trace["writes"].append({
        "node":       reads_node,
        "collection": "reads",
        "op":         "insert",
        "reason":     f"User region={region} → fragmented to {reads_node}",
    })

    # ── Write 2: Update bereads ──
    beread_update = {"$inc": {"readNum": 1}, "$push": {"readUidList": uid}}
    if agree == "1":
        beread_update["$inc"]["agreeNum"] = 1
        beread_update["$push"]["agreeUidList"] = uid
    if comment == "1":
        beread_update["$inc"]["commentNum"] = 1
        beread_update["$push"]["commentUidList"] = uid
    if share == "1":
        beread_update["$inc"]["shareNum"] = 1
        beread_update["$push"]["shareUidList"] = uid

    for br_db, node_label in _beread_nodes(category):
        br_db["bereads"].update_one({"aid": aid}, beread_update, upsert=True)
        trace["writes"].append({
            "node":       node_label,
            "collection": "bereads",
            "op":         "update ($inc readNum, push uid)",
            "reason":     f"Article category={category} → "
                        f"{'replicated to DB1+DB2' if category=='science' else 'DB2 only'}",
        })
    
    cache_clear()  # flush Redis after any write to ensure subsequent reads see latest data
    return trace


@app.route("/article/<aid>/read", methods=["POST"])
def record_read(aid: str):
    uid          = request.form.get("uid", "").strip()
    agree        = request.form.get("agree",   "0")
    comment      = request.form.get("comment", "0")
    comment_text = request.form.get("comment_text", "")
    share        = request.form.get("share",   "0")

    if not uid:
        return jsonify({"ok": False, "error": "uid is required"}), 400

    result = insert_read(uid, aid, agree, comment, comment_text, share)
    return jsonify(result)

        
@app.errorhandler(404)
def not_found(e):
    return "<h1>404 - Page not found</h1>", 404

if __name__ == "__main__":
    print("Starting Flask app on http://127.0.0.1:5001")
    app.run(debug=True, host="127.0.0.1", port=5001)