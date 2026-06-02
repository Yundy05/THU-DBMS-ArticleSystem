set -e

echo "Starting MongoDB containers..."
docker compose up -d

echo "Waiting for mongo1..."
until docker exec mongo1 mongosh --quiet --eval "db.adminCommand({ ping: 1 }).ok" >/dev/null 2>&1; do
  sleep 2
done

echo "Waiting for mongo2..."
until docker exec mongo2 mongosh --quiet --eval "db.adminCommand({ ping: 1 }).ok" >/dev/null 2>&1; do
  sleep 2
done

echo "MongoDB containers are ready."

echo "Initializing indexes..."
python scripts/init_db.py

echo "Loading users..."
python scripts/load_users.py db-generation/user.dat

echo "Loading articles..."
python scripts/load_articles.py

echo "Loading reads..."
python scripts/load_reads.py

echo "Done loading base tables."

echo "Loading bereads..."
python scripts/load_reads.py

echo "Loading popular rankings..."
python scripts/derive_popular_rank.py
echo "Bootstrap complete."
