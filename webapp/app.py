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
    docs = {
        "daily": db1()["popular_rank"].find_one({"temporalGranularity": "daily"}, {"_id": 0}),
        "weekly": db2()["popular_rank"].find_one({"temporalGranularity": "weekly"}, {"_id": 0}),
        "monthly": db2()["popular_rank"].find_one({"temporalGranularity": "monthly"}, {"_id": 0}),
    }

    enriched = {}
    for granularity, doc in docs.items():
        rows = []
        if doc:
            for aid in doc.get("articleAidList", []):
                art = article_lookup(aid)
                if art:
                    rows.append({
                        "aid": aid,
                        "title": art.get("title", "Untitled"),
                        "category": art.get("category", "unknown"),
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
    
@app.route("/article/<aid>")
def article_detail(aid):
    article = article_lookup(aid)
    if not article:
        abort(404)

    article["local_images"] = existing_image_candidates(article)
    article["text_info"] = load_related_text(article)
    article["text_preview"] = article["text_info"]["preview"] if article["text_info"] else None

    beread = db1()["bereads"].find_one({"aid": aid}, {"_id": 0}) or db2()["bereads"].find_one({"aid": aid}, {"_id": 0})

    return render_template("article.html", article=article, beread=beread)


@app.route("/monitor")
def monitor():
    return render_template("monitor.html", snapshot=monitor_snapshot(), ranks=latest_ranks())


@app.route("/assets/image/<aid>/<filename>")
def serve_image(aid, filename):
    article_dir = ROOT / "db-generation" / "articles" / f"article{aid}"
    return send_from_directory(article_dir, filename)


@app.errorhandler(404)
def not_found(e):
    return "<h1>404 - Page not found</h1>", 404

if __name__ == "__main__":
    print("Starting Flask app on http://127.0.0.1:5001")
    app.run(debug=True, host="127.0.0.1", port=5001)