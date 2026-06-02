# load_articles.py

import sys, json
sys.path.insert(0, '.')

from src.db.router import route_article

def load_articles(filepath: str):
    counts = {"science": 0, "technology": 0}
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            article = json.loads(line)
            collections = route_article(article)
            for collection in collections:
                collection.update_one({"aid": article["aid"]}, {"$set": article}, upsert=True)
                category = article.get("category", "technology")
                counts[category] = counts.get(category,0) + 1
                
    print(f"Loaded {counts.get('science', 0)} science articles -> MongoDB1 + MongoDB2 (replicated)")
    print(f"Loaded {counts.get('technology', 0)} technology articles -> MongoDB2 only")    
    print(f"Loaded Successfully!")

    
if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "db-generation/article.dat"
    load_articles(path)
    
    