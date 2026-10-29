#!/usr/bin/env bash
set -e

# מעבר לתיקיית הבנצ'מרק בריפו
cd "$(dirname "$0")"

CONTAINER_NAME="leadflow-data-gate-nofilter"
IMAGE_NAME="ghcr.io/shay-mordechai/leadflow-data-gate:latest"
CONFIG_FILE="$PWD/../../data-gate/envoy-nofilter.yaml"

cleanup() {
    echo "=== Cleaning up benchmark containers ==="
    podman rm -f "$CONTAINER_NAME" 2>/dev/null || true
}

# ודא ניקוי במקרה של יציאה או שגיאה
trap cleanup EXIT

echo "=== Spawning temporary Envoy Baseline container (no-filter) ==="
podman run --name "$CONTAINER_NAME" \
  --detach \
  --network leadflow-network \
  -p 127.0.0.1:10001:10000 \
  -v "$CONFIG_FILE":/etc/envoy/envoy.yaml:ro,Z \
  --entrypoint="" \
  "$IMAGE_NAME" \
  /usr/local/bin/envoy -c /etc/envoy/envoy.yaml --service-cluster proxy

# המתנה קצרה לוודא שה-Envoy המדמה עלה בהצלחה
sleep 2

# 1. יצור סקריפטי Lua ל-Payloads בשלושה גדלים
cat << 'EOF' > gen_lua.py
import json, sys
name, n = sys.argv[1], int(sys.argv[2])
item = {"name": "Dana Cohen", "phone": "052-123-4567", "email": "dana@example.com", "note": "call me tomorrow"}
body = json.dumps({"leads": [item] * n})
open(f"post_{name}.lua", "w").write(
    'wrk.method = "POST"\n'
    'wrk.headers["Content-Type"] = "application/json"\n'
    'wrk.body = [==[' + body + ']==]\n')
print(f"Generated post_{name}.lua ({len(body)} bytes)")
EOF

python3 gen_lua.py small 1
python3 gen_lua.py medium 20
python3 gen_lua.py large 200

# 2. הגדרת כתובות הגישה
export URL_DIRECT=http://127.0.0.1:8000
export URL_FILTER=http://127.0.0.1:10000
export URL_NOFILTER=http://127.0.0.1:10001

# 3. בדיקת נכונות (Sanity Check)
echo "=== Running Sanity Check ==="
BODY='{"phone":"052-123-4567","email":"dana@example.com"}'
for u in $URL_DIRECT $URL_NOFILTER $URL_FILTER; do
  echo "== Checking $u"
  curl -s -X POST "$u/bench/echo" -H 'Content-Type: application/json' -d "$BODY"; echo
done

# 4. הרצת בנצ'מרק מדורג (5 ריצות לכל קונפיגורציה)
PAYLOAD=${PAYLOAD:-medium}; DUR=30s; RUNS=5
echo "=== Starting Benchmark (Payload: $PAYLOAD, Runs: $RUNS) ==="

echo "cfg,run,p50_ms,p99_ms,rps,non2xx" > results.csv
for i in $(seq $RUNS); do
  for cfg in direct nofilter filter; do
    case $cfg in
      direct) u=$URL_DIRECT;;
      nofilter) u=$URL_NOFILTER;;
      filter) u=$URL_FILTER;;
    esac
    
    out=$(podman run --rm --network host -v "$PWD/post_${PAYLOAD}.lua:/post.lua:ro,Z" \
      docker.io/williamyeh/wrk -t2 -c20 -d"$DUR" --latency -s /post.lua "$u/bench/echo")
      
    p50=$(echo "$out" | awk '$1=="50%"{print $2}')
    p99=$(echo "$out" | awk '$1=="99%"{print $2}')
    rps=$(echo "$out" | awk '/Requests\/sec/{print $2}')
    bad=$(echo "$out" | awk '/Non-2xx/{print $NF}')
    
    to_ms() {
      awk -v v="$1" 'BEGIN{n=v+0; u=v; gsub(/[0-9.]+/,"",u); if(u=="us")n/=1000; else if(u=="s")n*=1000; printf "%.3f",n}';
    }
    
    echo "$cfg,$i,$(to_ms $p50),$(to_ms $p99),$rps,${bad:-0}" >> results.csv
    sleep 3
  done
done

# 5. הצגת סיכום חציונים סופי
echo "=== Summary (Median across runs) ==="
for cfg in direct nofilter filter; do
  for col in 3 4 5; do
    name=$(echo "p50_ms p99_ms rps" | cut -d' ' -f$((col-2)))
    printf "%-9s %-7s " "$cfg" "$name"
    grep "^$cfg," results.csv | cut -d, -f$col | sort -n | awk '{a[NR]=$1} END{print a[int((NR+1)/2)]}'
  done
  echo ""
done