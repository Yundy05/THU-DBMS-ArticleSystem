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

echo "Waiting for mongo3..."
until docker exec mongo3 mongosh --quiet --eval "db.adminCommand({ ping: 1 }).ok" >/dev/null 2>&1; do
  sleep 2
done

# MongoDB4 is optional (expansion node) — wait only if the container exists
if docker ps --format '{{.Names}}' | grep -q '^mongo4$'; then
  echo "Waiting for mongo4 (expansion node)..."
  until docker exec mongo4 mongosh --quiet --eval "db.adminCommand({ ping: 1 }).ok" >/dev/null 2>&1; do
    sleep 2
  done
  echo "mongo4 is ready."
else
  echo "mongo4 not running — skipping (expansion node is optional)."
fi

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
python scripts/derive_beread.py

echo "Loading popular rankings..."
python scripts/derive_popular_rank.py

echo "Syncing DB1 → DB3 (hot standby)..."
python scripts/sync_standby.py --full

# Migrate to MongoDB4 only if the container is running
if docker ps --format '{{.Names}}' | grep -q '^mongo4$'; then
  echo "Migrating data to MongoDB4 (expansion node)..."
  python scripts/migrate_to_mongo4.py
else
  echo "Skipping MongoDB4 migration — container not running."
fi

echo "Bootstrap complete."
