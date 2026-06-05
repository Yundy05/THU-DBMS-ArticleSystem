# test_cache.sh - Demonstrates Redis caching benefit

BASE_URL="${BASE_URL:-http://127.0.0.1:5001}"
REDIS="docker exec redis redis-cli"

echo "=== Flushing Redis cache ==="
$REDIS flushdb
echo

echo "=== Request 1 (cache cold — expect MongoDB hit) ==="
time curl -s "$BASE_URL/monitor" > /dev/null
echo

echo "=== Redis state after first request ==="
echo "Keys cached:"
$REDIS dbsize
echo "Stats:"
$REDIS info stats | grep -E "keyspace_hits|keyspace_misses"
echo

echo "=== Request 2 (cache warm — expect Redis hit) ==="
time curl -s "$BASE_URL/monitor" > /dev/null
echo

echo "=== Redis state after second request ==="
echo "Keys cached:"
$REDIS dbsize
echo "Stats:"
$REDIS info stats | grep -E "keyspace_hits|keyspace_misses"
echo

echo "=== Cached keys ==="
$REDIS keys "*"
echo

echo "=== Done ==="
echo "Compare the two response times above."
echo "Hits should increase on the second request, misses should stay the same."