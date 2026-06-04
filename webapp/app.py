from flask import Flask, render_template, request, abort, send_from_directory
from pathlib import Path
import math
import re
import sys
from datetime import datetime, UTC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from src.db.connections import get_mongo1, get_mongo2
except Exception as e:
    raise RuntimeError(
        "Could not import src.db.connections. Check your repo structure and connections.py"
    ) from e

app = Flask(__name__)
ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "db-generation" / "image"
TEXT_ROOT = ROOT / "db-generation" / "bbc_news_texts"


def db1():
    return get_mongo1()


def db2():
    return get_mongo2()


def parse_csv(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(",") if v.strip()]


def article_lookup(aid):
    return db2()["articles"].find_one({"aid": aid}, {"_id": 0}) or db1()["articles"].find_one({"aid": aid}, {"_id": 0})


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


def monitor_snapshot():
    mongo1 = db1()
    mongo2 = db2()

    return [
        {
            "label": "MongoDB1",
            "status": "online",
            "location_note": "Stores Beijing users, science articles replica, Beijing reads, science Be-Read replica, and daily popular rank.",
            "collections": {
                "users": safe_count(mongo1["users"]),
                "articles": safe_count(mongo1["articles"]),
                "reads": safe_count(mongo1["reads"]),
                "bereads": safe_count(mongo1["bereads"]),
                "popular_rank": safe_count(mongo1["popular_rank"]),
            },
            "managed_data": {
                "regions": {
                    "Beijing": safe_count(mongo1["users"], {"region": "Beijing"}),
                    "Hong Kong": safe_count(mongo1["users"], {"region": "Hong Kong"}),
                },
                "article_categories": {
                    "science": safe_count(mongo1["articles"], {"category": "science"}),
                    "technology": safe_count(mongo1["articles"], {"category": "technology"}),
                },
                "popular_rank_granularity": {
                    "daily": safe_count(mongo1["popular_rank"], {"temporalGranularity": "daily"}),
                    "weekly": safe_count(mongo1["popular_rank"], {"temporalGranularity": "weekly"}),
                    "monthly": safe_count(mongo1["popular_rank"], {"temporalGranularity": "monthly"}),
                },
            },
        },
        {
            "label": "MongoDB2",
            "status": "online",
            "location_note": "Stores Hong Kong users, science and technology articles, Hong Kong reads, science and technology Be-Read, and weekly/monthly popular rank.",
            "collections": {
                "users": safe_count(mongo2["users"]),
                "articles": safe_count(mongo2["articles"]),
                "reads": safe_count(mongo2["reads"]),
                "bereads": safe_count(mongo2["bereads"]),
                "popular_rank": safe_count(mongo2["popular_rank"]),
            },
            "managed_data": {
                "regions": {
                    "Beijing": safe_count(mongo2["users"], {"region": "Beijing"}),
                    "Hong Kong": safe_count(mongo2["users"], {"region": "Hong Kong"}),
                },
                "article_categories": {
                    "science": safe_count(mongo2["articles"], {"category": "science"}),
                    "technology": safe_count(mongo2["articles"], {"category": "technology"}),
                },
                "popular_rank_granularity": {
                    "daily": safe_count(mongo2["popular_rank"], {"temporalGranularity": "daily"}),
                    "weekly": safe_count(mongo2["popular_rank"], {"temporalGranularity": "weekly"}),
                    "monthly": safe_count(mongo2["popular_rank"], {"temporalGranularity": "monthly"}),
                },
            },
        },
    ]


def workload_summary():
    mongo1 = db1()
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
    docs = {
        "daily":   db1()["popular_rank"].find_one({"temporalGranularity": "daily"},   {"_id": 0}),
        "weekly":  db2()["popular_rank"].find_one({"temporalGranularity": "weekly"},  {"_id": 0}),
        "monthly": db2()["popular_rank"].find_one({"temporalGranularity": "monthly"}, {"_id": 0}),
    }

    enriched = {}
    for granularity, doc in docs.items():
        rows = []
        if doc:
            for aid in doc.get("articleAidList", [])[:5]:
                art = article_lookup(aid)
                if art:
                    # ✅ Convert Path objects → URL strings for serve_image
                    aid_digits = normalize_digits(aid)
                    image_urls = []
                    for p in existing_image_candidates(art):
                        image_urls.append(f"/assets/image/{aid_digits}/{p.name}")

                    rows.append({
                        "aid":        aid,
                        "title":      art.get("title",    "Untitled"),
                        "category":   art.get("category", "unknown"),
                        "authors":    art.get("authors",  "Unknown"),
                        "abstract":   safe_preview(art.get("abstract", ""), 120),
                        "image_urls": image_urls,  
                        "video_url":  existing_video(art),
                    })
        enriched[granularity] = rows
    return enriched


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
        articles.append(a)

    totals = {
        "articles": db2()["articles"].count_documents({}),
        "reads": db1()["reads"].count_documents({}) + db2()["reads"].count_documents({}),
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
        d1, d2 = db1(), db2()
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
        return {
            "science_articles": {"db1": sci1, "db2": sci2, "match": sci1 == sci2},
            "bereads":          {"db1": br1,  "db2": br2},
            "popular_rank":     {"db1": pr1,  "db2": pr2},
            "sample_record":    {
                "aid":   (sample1 or {}).get("aid", "N/A"),
                "match": record_match,
            },
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
        db1()["users"].find_one({"uid": uid}, {"_id": 0}) or
        db2()["users"].find_one({"uid": uid}, {"_id": 0})
    )
    
def beread_lookup(aid: str, category: str) -> dict | None:
    if category == "science":
        return (
            db1()["bereads"].find_one({"aid": aid}, {"_id": 0}) or
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
        results = list(db1()["users"].find(query, {"_id": 0})
                       .skip((page - 1) * per_page).limit(per_page))
        total   = db1()["users"].count_documents(query)
    elif region == "Hong Kong":
        results = list(db2()["users"].find(query, {"_id": 0})
                       .skip((page - 1) * per_page).limit(per_page))
        total   = db2()["users"].count_documents(query)
    else:
        half  = per_page // 2
        skip1 = max((page - 1) * half, 0)
        results = (
            list(db1()["users"].find(query, {"_id": 0}).skip(skip1).limit(half)) +
            list(db2()["users"].find(query, {"_id": 0}).skip(skip1).limit(half))
        )
        total = (db1()["users"].count_documents(query) +
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
    reads_db    = db1() if node_region == "Beijing" else db2()
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

@app.errorhandler(404)
def not_found(e):
    return "<h1>404 - Page not found</h1>", 404

if __name__ == "__main__":
    print("Starting Flask app on http://127.0.0.1:5001")
    app.run(debug=True, host="127.0.0.1", port=5001)