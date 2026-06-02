from flask import Flask, render_template, request, abort, send_from_directory
from pathlib import Path
import math
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from src.db.connections import get_mongo1, get_mongo2
except Exception as e:
    raise RuntimeError(
        "Could not import src.db.connections. Check your repo structure and connections.py"
    ) from e

app = Flask(__name__)
ROOT = Path(__file__).resolve().parents[1]

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

def find_local_images(article):
    items = []
    for name in parse_csv(article.get("image")):
        p = ROOT / "db-generation" / "image" / name
        if p.exists():
            items.append(name)
    return items

def safe_preview(text, n=220):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text[:n] + ("..." if len(text) > n else "")

def monitor_snapshot():
    result = []
    for label, db in [("MongoDB1", db1()), ("MongoDB2", db2())]:
        collections = {}
        for name in ["users", "articles", "reads", "bereads", "popular_rank"]:
            try:
                count = db[name].count_documents({})
            except Exception:
                count = 0
            collections[name] = count
        result.append({"label": label, "collections": collections})
    return result

def latest_ranks():
    docs = {}
    docs["daily"] = db1()["popular_rank"].find_one({"temporalGranularity": "daily"}, {"_id": 0})
    docs["weekly"] = db2()["popular_rank"].find_one({"temporalGranularity": "weekly"}, {"_id": 0})
    docs["monthly"] = db2()["popular_rank"].find_one({"temporalGranularity": "monthly"}, {"_id": 0})

    enriched = {}
    for k, doc in docs.items():
        rows = []
        if doc:
            for aid in doc.get("articleAidList", []):
                art = article_lookup(aid)
                if art:
                    rows.append({
                        "aid": aid,
                        "title": art.get("title", "Untitled"),
                        "category": art.get("category", "unknown")
                    })
        enriched[k] = rows
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
        a["local_images"] = find_local_images(a)
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

@app.route("/article/<aid>")
def article_detail(aid):
    article = article_lookup(aid)
    if not article:
        abort(404)

    article["local_images"] = find_local_images(article)
    beread = db1()["bereads"].find_one({"aid": aid}, {"_id": 0}) or db2()["bereads"].find_one({"aid": aid}, {"_id": 0})

    return render_template("article.html", article=article, beread=beread)

@app.route("/monitor")
def monitor():
    return render_template("monitor.html", snapshot=monitor_snapshot(), ranks=latest_ranks())

@app.route("/assets/image/<filename>")
def serve_image(filename):
    return send_from_directory(ROOT / "db-generation" / "image", filename)

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
    app.run(debug=True, port=5001)
