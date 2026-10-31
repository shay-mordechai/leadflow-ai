#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# שמירה על הרשאת sudo חמה כדי למנוע חלונות סיסמה באמצע הבדיקה
sudo -v

CONTAINER_NAME="leadflow-data-gate-nofilter"
IMAGE_NAME="ghcr.io/shay-mordechai/leadflow-data-gate:latest"
CONFIG_FILE="$PWD/../../data-gate/envoy-nofilter.yaml"

cleanup() {
    echo "=== Cleaning up ==="
    podman rm -f "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT
podman rm -f "$CONTAINER_NAME" 2>/dev/null || true

echo "=== Spawning Envoy Baseline container ==="
podman run --name "$CONTAINER_NAME" \
  --detach \
  --network leadflow-network \
  -p 127.0.0.1:10001:10000 \
  -v "$CONFIG_FILE":/etc/envoy/envoy.yaml:ro,Z \
  --entrypoint="" \
  "$IMAGE_NAME" \
  /usr/local/bin/envoy -c /etc/envoy/envoy.yaml --service-cluster proxy

echo "Waiting for baseline Envoy..."
for i in {1..20}; do
  if curl -s -X POST http://127.0.0.1:10001/bench/echo -H 'Content-Type: application/json' -d '{"ping":"pong"}' >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

URL_DIRECT=http://127.0.0.1:8000
URL_NOFILTER=http://127.0.0.1:10001
URL_FILTER=http://127.0.0.1:10000

# Warmup run (חימום חיבורים ומטמון - לא נספר בתוצאות)
echo "=== Warming up endpoints (5s each) ==="
for u in $URL_DIRECT $URL_NOFILTER $URL_FILTER; do
  ~/.local/bin/wrk -t2 -c10 -d5s -s "$PWD/post_medium.lua" "$u/bench/echo" >/dev/null 2>&1
done

RUNS=15
DUR=20s
echo "=== Starting Rigorous Benchmark ($RUNS runs, $DUR each) ==="
echo "run,direct_p50,nofilter_p50,filter_p50,delta_wasm_p50" > benchmark_rigorous.csv

to_ms() {
  awk -v v="$1" 'BEGIN{n=v+0; u=v; gsub(/[0-9.]+/,"",u); if(u=="us")n/=1000; else if(u=="s")n*=1000; printf "%.3f",n}';
}

for i in $(seq 1 $RUNS); do
  echo "--- Iteration $i/$RUNS ---"
  
  # הרצת direct
  out_d=$(~/.local/bin/wrk -t2 -c20 -d"$DUR" --latency -s "$PWD/post_medium.lua" "$URL_DIRECT/bench/echo")
  p50_d=$(to_ms "$(echo "$out_d" | awk '$1=="50%"{print $2}')")
  sleep 1
  
  # הרצת nofilter
  out_nf=$(~/.local/bin/wrk -t2 -c20 -d"$DUR" --latency -s "$PWD/post_medium.lua" "$URL_NOFILTER/bench/echo")
  p50_nf=$(to_ms "$(echo "$out_nf" | awk '$1=="50%"{print $2}')")
  sleep 1

  # הרצת filter
  out_f=$(~/.local/bin/wrk -t2 -c20 -d"$DUR" --latency -s "$PWD/post_medium.lua" "$URL_FILTER/bench/echo")
  p50_f=$(to_ms "$(echo "$out_f" | awk '$1=="50%"{print $2}')")
  sleep 1

  delta=$(awk -v f="$p50_f" -v nf="$p50_nf" 'BEGIN{printf "%.3f", f - nf}')
  echo "$i,$p50_d,$p50_nf,$p50_f,$delta" >> benchmark_rigorous.csv
  echo "    direct: ${p50_d}ms | nofilter: ${p50_nf}ms | filter: ${p50_f}ms | Delta (Wasm): ${delta}ms"
done

echo ""
echo "=== Statistical Analysis ==="
python3 - << 'PYEOF'
import csv
import statistics as stats

deltas = []
directs = []
nofilters = []
filters = []

with open("benchmark_rigorous.csv") as f:
    reader = csv.DictReader(f)
    for r in reader:
        directs.append(float(r["direct_p50"]))
        nofilters.append(float(r["nofilter_p50"]))
        filters.append(float(r["filter_p50"]))
        deltas.append(float(r["delta_wasm_p50"]))

def report(name, arr):
    print(f"{name:15} -> Median: {stats.median(arr):.2f}ms | Mean: {stats.mean(arr):.2f}ms | StdDev: {stats.stdev(arr):.2f}ms | Min: {min(arr):.2f}ms | Max: {max(arr):.2f}ms")

report("Direct (Backend)", directs)
report("Bare Envoy", nofilters)
report("Envoy + Wasm", filters)
report("Wasm Delta", deltas)

print("-" * 65)
if min(deltas) < 0 and max(deltas) > 0:
    print("Conclusion: Wasm overhead is strictly within run-to-run baseline jitter.")
else:
    print(f"Conclusion: Wasm introduces a stable overhead of ~{stats.median(deltas):.2f}ms.")
PYEOF
