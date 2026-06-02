from flask import Flask, render_template, request
import sys
sys.path.insert(0, ".")

from src.db.connections import get_mongo2

app = Flask(__name__)

@app.route("/")
def index():
    category = request.args.get("category")
    keyword = request.args.get("q", "").strip()

    db = get_mongo2()   # mongo2 has all articles
    query = {}

    if category:
        query["category"] = category
    if keyword:
        query["title"] = {"$regex": keyword, "$options": "i"}

    articles = list(
        db["articles"]
        .find(query, {"_id": 0})
        .limit(100)
    )

    return render_template("index.html", articles=articles, category=category, keyword=keyword)

@app.route("/article/<aid>")
def article_detail(aid):
    db = get_mongo2()
    article = db["articles"].find_one({"aid": aid}, {"_id": 0})
    return render_template("article.html", article=article)

if __name__ == "__main__":
    app.run(debug=True, port=5001)