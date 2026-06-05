# Usage: ./test_read_insert.sh <uid> <aid>
# Example: ./test_read_insert.sh 0 1000

set -e

USER_ID="$1"
ART_ID="$2"

if [ -z "$USER_ID" ] || [ -z "$ART_ID" ]; then
  echo "Usage: $0 <uid> <aid>"
  exit 1
fi

DB_NAME="${DB_NAME:-distrib_db}"          
BASE_URL="${BASE_URL:-http://127.0.0.1:5001}"

echo "=== Step 1: Trigger Record Read via Flask endpoint ==="
echo "uid = $USER_ID, aid = $ART_ID"
echo

RESP=$(curl -s -X POST "$BASE_URL/article/$ART_ID/read" \
  -d "uid=$USER_ID" \
  -d "agree=1" \
  -d "comment=0" \
  -d "comment_text=" \
  -d "share=0")

echo "Response JSON:"
echo "$RESP" | jq .
echo

echo "=== Step 2: Inspect reads in DB1 and DB3 (Beijing fragment) ==="
echo "--- mongo1 (if running) ---"
docker exec -i mongo1 mongosh --eval "
  const db = db.getSiblingDB('$DB_NAME');
  print('reads on mongo1 for uid=$USER_ID, aid=$ART_ID:');
  db.reads.find({ uid: '$USER_ID', aid: '$ART_ID' })
          .sort({ timestamp: -1 }).limit(3)
          .forEach(d => printjson(d));
" || echo "mongo1 not reachable"

echo
echo "--- mongo3 (hot standby) ---"
docker exec -it mongo3 mongosh --eval "
  const db = db.getSiblingDB('$DB_NAME');
  print('reads on mongo3 for uid=$USER_ID, aid=$ART_ID:');
  db.reads.find({ uid: '$USER_ID', aid: '$ART_ID' })
          .sort({ timestamp: -1 }).limit(3)
          .forEach(d => printjson(d));
" || echo "mongo3 not reachable"

echo
echo "=== Step 3: Inspect Be-Read in DB1/DB3 and DB2 ==="
echo "--- mongo1 (or DB3 during failover) ---"
docker exec -it mongo1 mongosh --eval "
  const db = db.getSiblingDB('$DB_NAME');
  print('bereads on mongo1 for aid=$ART_ID:');
  db.bereads.find(
    { aid: '$ART_ID' },
    { _id:0, aid:1, readNum:1, agreeNum:1, commentNum:1, shareNum:1 }
  ).forEach(d => printjson(d));
" || echo "mongo1 not reachable"

echo
echo "--- mongo3 (standby / failover copy) ---"
docker exec -it mongo3 mongosh --eval "
  const db = db.getSiblingDB('$DB_NAME');
  print('bereads on mongo3 for aid=$ART_ID:');
  db.bereads.find(
    { aid: '$ART_ID' },
    { _id:0, aid:1, readNum:1, agreeNum:1, commentNum:1, shareNum:1 }
  ).forEach(d => printjson(d));
" || echo "mongo3 not reachable"

echo
echo "--- mongo2 (replica / tech node) ---"
docker exec -it mongo2 mongosh --eval "
  const db = db.getSiblingDB('$DB_NAME');
  print('bereads on mongo2 for aid=$ART_ID:');
  db.bereads.find(
    { aid: '$ART_ID' },
    { _id:0, aid:1, readNum:1, agreeNum:1, commentNum:1, shareNum:1 }
  ).forEach(d => printjson(d));
" || echo "mongo2 not reachable"

echo
echo "=== Done ==="