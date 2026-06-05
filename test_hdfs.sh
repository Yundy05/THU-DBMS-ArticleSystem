# test_hdfs.sh - Demonstrates MongoDB → HDFS export pipeline

set -e

echo "=== Starting HDFS services ==="
docker compose --profile hdfs up -d

# Wait an extra moment for namenode to exit safe mode
sleep 10

# Create base dir as root and make it world-writable
docker exec namenode hdfs dfs -mkdir -p /project/distrib_db
docker exec namenode hdfs dfs -chmod -R 777 /project/distrib_db
docker exec namenode hdfs dfs -chown -R hadoop /project/distrib_db
echo "HDFS directories ready."

echo "Waiting for HDFS namenode..."
until curl -s http://localhost:9870 > /dev/null 2>&1; do
  sleep 3
done
echo "HDFS namenode is ready."
echo

echo "=== Exporting sample (5000 docs per collection) ==="
python scripts/export_reads_to_hdfs.py --limit 5000
echo

echo "=== Verifying HDFS contents ==="
python scripts/export_reads_to_hdfs.py --list
echo

echo "=== HDFS Web UI ==="
echo "Open: http://localhost:9870/explorer.html#/project/distrib_db"
echo

echo "=== Raw file check via HDFS CLI ==="
docker exec namenode hdfs dfs -ls -R /project/distrib_db
echo

echo "=== Done ==="