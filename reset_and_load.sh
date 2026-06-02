set -e

echo "Resetting containers and volumes..."
docker compose down -v
docker compose up -d

echo "Waiting for mongo1..."
until docker exec mongo1 mongosh --quiet --eval "db.adminCommand({ ping: 1 }).ok" >/dev/null 2>&1; do
  sleep 2
done

echo "Waiting for mongo2..."
until docker exec mongo2 mongosh --quiet --eval "db.adminCommand({ ping: 1 }).ok" >/dev/null 2>&1; do
  sleep 2
done

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Initializing indexes..."
python scripts/init_db.py

echo "Loading users..."
python scripts/load_users.py db-generation/user.dat

echo "Loading articles..."
python scripts/load_articles.py

echo "Loading reads..."
python scripts/load_reads.py

echo "Reset and base load complete."