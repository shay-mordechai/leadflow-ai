#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/deployer/app"
CONFIG_FILE="$APP_DIR/data-gate/envoy-nofilter.yaml"
CONTAINER_NAME="leadflow-data-gate-nofilter"
IMAGE_NAME="ghcr.io/shay-mordechai/leadflow-data-gate:latest"
CSV_OUTPUT="$APP_DIR/scripts/benchmark_rigorous.csv"
RAW_LOG="$APP_DIR/scripts/wrk_raw_outputs.log"

URL_DIRECT="http://127.0.0.1:8000"
URL_FILTER="http://127.0.0.1:10000"
URL_NOFILTER="http://127.0.0.1:10001"

export URL_DIRECT URL_FILTER URL_NOFILTER CSV_OUTPUT RAW_LOG

STOPPED_CONTAINERS=("leadflow-frontend" "leadflow-worker" "leadflow-beat" "leadflow-db" "leadflow-redis")

# -----------------------------------------------------------------------------
# 1. Cleanup & Full Production Restoration Routine on Exit
# -----------------------------------------------------------------------------
cleanup() {
    echo ""
    echo "=== Cleaning up benchmark resources & restoring production stack ==="
    podman rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

    # Restore CPU affinity of core containers back to all vCPUs (0-1)
    for c in leadflow-backend leadflow-data-gate; do
        if [ "$(podman inspect -f '{{.State.Running}}' "$c" 2>/dev/null)" = "true" ]; then
            PID=$(podman inspect "$c" --format '{{.State.Pid}}')
            podman unshare taskset -a -p -c 0-1 "$PID" >/dev/null 2>&1 || taskset -a -p -c 0-1 "$PID" >/dev/null 2>&1 || true
            echo "  -> Restored CPU affinity for $c (PID $PID) to cores [0-1]"
        fi
    done

    # Restart infrastructure services first (DB & Redis)
    echo "  -> Starting database and Redis containers..."
    podman start leadflow-db leadflow-redis >/dev/null 2>&1 || true
    sleep 2

    # Restart application workers and frontend
    echo "  -> Starting worker, beat, and frontend containers..."
    podman start leadflow-worker leadflow-beat leadflow-frontend >/dev/null 2>&1 || true

    echo "=== Current Container Status ==="
    podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}
trap cleanup EXIT INT TERM
podman rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

# -----------------------------------------------------------------------------
# 2. Sterilize Environment (Stop Non-Benchmark Containers for Zero Noise)
# -----------------------------------------------------------------------------
echo "=== Step 1: Sterilizing Execution Environment ==="
podman stop "${STOPPED_CONTAINERS[@]}" >/dev/null 2>&1 || true

for c in leadflow-backend leadflow-data-gate; do
    if [ "$(podman inspect -f '{{.State.Running}}' "$c" 2>/dev/null)" != "true" ]; then
        echo "ERROR: Required container '$c' is not running."
        exit 1
    fi
done

# -----------------------------------------------------------------------------
# 3. Detect Production Envoy Concurrency & Spawn Identical Baseline Envoy
# -----------------------------------------------------------------------------
echo "=== Step 2: Matching Envoy Concurrency & Spawning Baseline (Port 10001) ==="
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Baseline config file not found at $CONFIG_FILE"
    exit 1
fi

GATE_PID=$(podman inspect leadflow-data-gate --format '{{.State.Pid}}')
PROD_CONCURRENCY=$(ps -T -p "$GATE_PID" -o comm= 2>/dev/null | grep -c "wrk:worker" || true)
if [ "${PROD_CONCURRENCY:-0}" -le 0 ]; then
    PROD_CONCURRENCY=2
fi
echo "  -> Detected production Envoy (leadflow-data-gate) worker concurrency: $PROD_CONCURRENCY"

NET_NAME=$(podman inspect leadflow-backend --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' | head -n1)

podman run --name "$CONTAINER_NAME" \
    --detach \
    --network "$NET_NAME" \
    -p 127.0.0.1:10001:10000 \
    -v "$CONFIG_FILE":/etc/envoy/envoy.yaml:ro,Z \
    --entrypoint="" \
    "$IMAGE_NAME" \
    /usr/local/bin/envoy -c /etc/envoy/envoy.yaml --service-cluster proxy --concurrency "$PROD_CONCURRENCY" >/dev/null

echo "Waiting for baseline Envoy on port 10001..."
for i in {1..25}; do
    if curl -s -f -X POST "$URL_NOFILTER/bench/echo" \
        -H 'Content-Type: application/json' \
        -d '{"ping":"pong"}' >/dev/null 2>&1; then
        BASE_PID=$(podman inspect "$CONTAINER_NAME" --format '{{.State.Pid}}')
        BASE_CONC=$(ps -T -p "$BASE_PID" -o comm= 2>/dev/null | grep -c "wrk:worker" || true)
        echo "  -> Baseline Envoy online (worker concurrency: $BASE_CONC)."
        break
    fi
    if [ "$i" -eq 25 ]; then
        echo "ERROR: Baseline Envoy failed to initialize. Logs:"
        podman logs "$CONTAINER_NAME"
        exit 1
    fi
    sleep 0.5
done

# -----------------------------------------------------------------------------
# 4. Enforce Strict 2-Core CPU Pinning (Core 0: Client, Core 1: Servers)
# -----------------------------------------------------------------------------
echo "=== Step 3: Enforcing Strict 2-vCPU Hardware Isolation ==="
for c in leadflow-backend leadflow-data-gate "$CONTAINER_NAME"; do
    PID=$(podman inspect "$c" --format '{{.State.Pid}}')
    podman unshare taskset -a -p -c 1 "$PID" >/dev/null 2>&1 || taskset -a -p -c 1 "$PID" >/dev/null 2>&1
    AFFINITY=$(taskset -p "$PID" | awk -F': ' '{print $2}')
    echo "  -> Pinned $c (PID $PID) + child threads to Core mask: [$AFFINITY]"
done

# -----------------------------------------------------------------------------
# 5. Generate Multi-Size Lua Scripts (Small, Medium, Large, Huge >256KB)
# -----------------------------------------------------------------------------
echo "=== Step 4: Generating Benchmark Payloads ==="
python3 - << 'PYEOF'
import json

item = {
    "name": "Dana Cohen",
    "phone": "052-123-4567",
    "email": "dana@example.com",
    "status": "ok",
    "note": "call me tomorrow"
}

for name, count in [("small", 1), ("medium", 20), ("large", 100), ("huge", 2600)]:
    if count == 1:
        payload = item
    else:
        payload = {
            "customer_email": "start_boundary@example.com",
            "leads": [item] * count,
            "status": "ok",
            "refresh_token": "end_boundary_secret_token"
        }
    body = json.dumps(payload, separators=(",", ":"))
    lua_path = f"/home/deployer/app/scripts/post_{name}.lua"
    with open(lua_path, "w") as f:
        f.write('wrk.method = "POST"\n')
        f.write('wrk.headers["Content-Type"] = "application/json"\n')
        f.write(f'wrk.body = [==[{body}]==]\n')
    print(f"  -> Generated post_{name}.lua ({len(body)} bytes)")
PYEOF

# -----------------------------------------------------------------------------
# 6. Deep Outbound L7 Response Redaction & Integrity Verification Suite
# -----------------------------------------------------------------------------
echo ""
echo "=== Step 5: Running Outbound Response Redaction Verification Suite ==="
python3 - << 'PYEOF'
import json
import os
import urllib.request
import urllib.error

URL_DIRECT = os.environ["URL_DIRECT"]
URL_NOFILTER = os.environ["URL_NOFILTER"]
URL_FILTER = os.environ["URL_FILTER"]

def request_raw(url, path="/bench/echo", data_dict=None, method="POST"):
    raw_req = json.dumps(data_dict, separators=(",", ":")).encode("utf-8") if data_dict is not None else None
    headers = {"Content-Type": "application/json"} if raw_req is not None else {}
    req = urllib.request.Request(f"{url}{path}", data=raw_req, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw_bytes = resp.read()
            resp_headers = {k.lower(): v for k, v in resp.info().items()}
            return resp.status, raw_bytes, resp_headers
    except urllib.error.HTTPError as e:
        raw_bytes = e.read()
        resp_headers = {k.lower(): v for k, v in e.headers.items()}
        return e.code, raw_bytes, resp_headers

# Vector 1: Outbound Response Redaction, Header Stripping & Raw Byte Inspection
v1_payload = {
    "email": "audit_leak_check@example.com",
    "phone": "052-123-4567",
    "status": "ok",
    "safe_field": "preserve_this_string_12345"
}

for label, url in [("Direct Backend (8000)", URL_DIRECT), ("Bare Envoy (10001)", URL_NOFILTER)]:
    status, raw_bytes, hdrs = request_raw(url, "/bench/echo", v1_payload)
    body = json.loads(raw_bytes.decode("utf-8"))
    assert status == 200, f"{label} returned HTTP {status}"
    assert body.get("email") == "audit_leak_check@example.com", f"{label} altered email"
    assert hdrs.get("x-data-ttl") == "1", f"{label} missing x-data-ttl: 1 header"
    print(f"  [PASS] {label}: 200 OK (Unredacted response + x-data-ttl: 1 present)")

status, raw_bytes, hdrs = request_raw(URL_FILTER, "/bench/echo", v1_payload)
raw_text = raw_bytes.decode("utf-8")
body = json.loads(raw_text)
assert status == 200, f"Envoy+Wasm returned HTTP {status}"
assert hdrs.get("x-data-ttl") is None, "HEADER LEAK: x-data-ttl was not stripped by Wasm filter"
assert body.get("email") == "[REDACTED]", f"PII LEAK: email={body.get('email')}"
assert body.get("phone") == "[REDACTED]", f"PII LEAK: phone={body.get('phone')}"
assert body.get("safe_field") == "preserve_this_string_12345", "FALSE POSITIVE: safe_field modified"
assert "audit_leak_check@example.com" not in raw_text, "RAW BYTE LEAK: email found in raw stream"
assert "052-123-4567" not in raw_text, "RAW BYTE LEAK: phone found in raw stream"
print("  [PASS] Vector 1 (Outbound Redaction, x-data-ttl Stripping & Raw Byte Check): Verified")

# Vector 2: Architectural Scope Verification (Key-Name Matching vs Free-Text Value Scanning)
v2_payload = {
    "note": "unlisted_key_with_email_dana@example.com",
    "notes": "listed_key_with_email_dana@example.com",
    "status": "ok"
}
status, raw_bytes, _ = request_raw(URL_FILTER, "/bench/echo", v2_payload)
body = json.loads(raw_bytes.decode("utf-8"))
assert status == 200
assert body.get("notes") == "[REDACTED]", "Listed key 'notes' was not redacted"
assert body.get("note") == "unlisted_key_with_email_dana@example.com", "Unlisted key 'note' was unexpectedly altered"
print("  [PASS] Vector 2 (JSON Key-Scope Boundary: 'notes' redacted, unlisted 'note' preserved): Verified")

# Vector 3: Deep Nested Array & Bounded Recursion Limit (max_depth = 32)
deep_within = {"email": "depth_20_secret@example.com", "keep": "ok"}
for _ in range(20):
    deep_within = {"child": deep_within}

deep_beyond = {"email": "depth_36_beyond_limit@example.com"}
for _ in range(36):
    deep_beyond = {"child": deep_beyond}

v3_payload = {
    "leads": [{"id": i, "email": f"lead{i}@example.com", "role": "dev"} for i in range(20)],
    "within_depth_limit": deep_within,
    "beyond_depth_limit": deep_beyond
}
status, raw_bytes, _ = request_raw(URL_FILTER, "/bench/echo", v3_payload)
raw_text = raw_bytes.decode("utf-8")
assert status == 200, "Deep recursion payload failed"
assert "lead0@example.com" not in raw_text and "lead19@example.com" not in raw_text, "Nested array leak"
assert "depth_20_secret@example.com" not in raw_text, "Depth 20 PII was not redacted"
assert "depth_36_beyond_limit@example.com" in raw_text, "Depth 36 should bypass max_depth=32 safely"
print("  [PASS] Vector 3 (20-Lead Array & Bounded Recursion max_depth=32 Safety): Verified")

# Vector 4: Multi-Frame Large Outbound Response (>300KB, Commit 9b314f8 Buffer Accumulation)
filler_record = {
    "id": 100,
    "role": "backend_engineer",
    "department": "infrastructure_security_research",
    "description": "padding_block_" + ("X" * 90)
}
large_payload = {
    "customer_email": "ALPHA_START_CANARY_LEAK@example.com",
    "phone_number": "050-111-0001",
    "start_safe": "START_SAFE_MARKER",
    "first_half": [filler_record] * 1000,
    "mid_section": {
        "api_key": "BETA_MIDDLE_CANARY_SECRET_KEY_999",
        "customer_email": "BETA_MID_CANARY@example.com",
        "mid_safe": "MID_SAFE_MARKER"
    },
    "second_half": [filler_record] * 1000,
    "end_section": {
        "refresh_token": "GAMMA_END_CANARY_TOKEN_XYZ",
        "personal_whatsapp": "054-999-8888",
        "end_safe": "END_SAFE_MARKER"
    }
}

status, raw_bytes, _ = request_raw(URL_FILTER, "/bench/echo", large_payload)
raw_text = raw_bytes.decode("utf-8")
assert status == 200, f"Large >300KB response failed with status {status}"
assert len(raw_bytes) > 280000, f"Expected >280KB response, got {len(raw_bytes)} bytes"
for canary in [
    "ALPHA_START_CANARY_LEAK@example.com",
    "050-111-0001",
    "BETA_MIDDLE_CANARY_SECRET_KEY_999",
    "BETA_MID_CANARY@example.com",
    "GAMMA_END_CANARY_TOKEN_XYZ",
    "054-999-8888"
]:
    assert canary not in raw_text, f"MULTI-FRAME BUFFER LEAK: Canary '{canary}' survived in >300KB response!"

for safe_marker in ["START_SAFE_MARKER", "MID_SAFE_MARKER", "END_SAFE_MARKER"]:
    assert safe_marker in raw_text, f"DATA CORRUPTION: Safe marker '{safe_marker}' missing in >300KB response!"

print(f"  [PASS] Vector 4 (Multi-Frame {len(raw_bytes)//1024}KB Outbound Response Reassembly - Start/Mid/End PII): Verified")

# Vector 5: Production Middleware X-Data-TTL Route Check
status_fixed, raw_fixed, hdrs_fixed = request_raw(URL_FILTER, "/bench/fixed", None, method="GET")
if status_fixed == 200:
    assert hdrs_fixed.get("x-data-ttl") is None, "x-data-ttl leaked on GET /bench/fixed"
    print("  [PASS] Vector 5a (Pure Outbound GET /bench/fixed Redaction & Header Strip): Verified")

status_api_d, _, hdrs_api_d = request_raw(URL_DIRECT, "/api/v1/leads", None, method="GET")
status_api_f, _, hdrs_api_f = request_raw(URL_FILTER, "/api/v1/leads", None, method="GET")
if hdrs_api_d.get("x-data-ttl") == "1":
    assert hdrs_api_f.get("x-data-ttl") is None, "Middleware x-data-ttl leaked through Envoy on /api/v1/leads"
    print(f"  [PASS] Vector 5b (Production Middleware /api/v1/leads HTTP {status_api_f} x-data-ttl Intercept): Verified")
else:
    print(f"  [INFO] Vector 5b (/api/v1/leads returned HTTP {status_api_d} before TTL middleware tagging)")

print("=== All Outbound Security & Functional Checks Passed! ===")
PYEOF

# -----------------------------------------------------------------------------
# 7. Warmup Phase (Pinned to Core 0, Single Thread)
# -----------------------------------------------------------------------------
PAYLOAD="${PAYLOAD:-medium}"
LUA_FILE="$APP_DIR/scripts/post_${PAYLOAD}.lua"
RUNS="${RUNS:-30}"
DUR="${DUR:-20s}"
WRK_CONN="${WRK_CONN:-20}"

echo ""
echo "=== Step 6: Warming Up Connection Pools & Wasm VM (5s each) ==="
for u in "$URL_DIRECT" "$URL_NOFILTER" "$URL_FILTER"; do
    taskset -c 0 wrk -t1 -c"$WRK_CONN" -d5s -s "$LUA_FILE" "$u/bench/echo" >/dev/null 2>&1
done

# -----------------------------------------------------------------------------
# 8. Randomized Interleaved Benchmark Loop with Detailed Error & Raw Logging
# -----------------------------------------------------------------------------
echo ""
echo "=== Step 7: Running Randomized Interleaved Benchmark ==="
echo "  -> Payload: $PAYLOAD | Runs: $RUNS | Duration: $DUR | Connections: $WRK_CONN"
echo "  -> Full raw wrk logs saved to: $RAW_LOG"

echo "run,order_idx,cfg,p50_ms,p90_ms,p99_ms,rps,non2xx,sock_connect,sock_read,sock_write,sock_timeout,total_err,steal_pct" > "$CSV_OUTPUT"
: > "$RAW_LOG"

to_ms() {
    awk -v v="${1:-0}" 'BEGIN{
        n=v+0; u=v; gsub(/[0-9.]+/,"",u);
        if(u=="us") n/=1000;
        else if(u=="s") n*=1000;
        printf "%.3f", n
    }'
}

read_cpu_stat() {
    awk '/^cpu / {total=$2+$3+$4+$5+$6+$7+$8+$9; print total, $9}' /proc/stat
}

for i in $(seq 1 "$RUNS"); do
    # Randomize execution order on every iteration to eliminate ordering bias
    mapfile -t SHUFFLED_CFGS < <(printf "direct\nnofilter\nfilter\n" | shuf)
    ORDER_STR="${SHUFFLED_CFGS[0]} -> ${SHUFFLED_CFGS[1]} -> ${SHUFFLED_CFGS[2]}"
    echo "--- Iteration $i/$RUNS (Order: $ORDER_STR) ---"

    order_idx=0
    for cfg in "${SHUFFLED_CFGS[@]}"; do
        order_idx=$((order_idx + 1))
        case $cfg in
            direct)   u="$URL_DIRECT" ;;
            nofilter) u="$URL_NOFILTER" ;;
            filter)   u="$URL_FILTER" ;;
        esac

        read -r tot_start stl_start <<< "$(read_cpu_stat)"

        out=$(taskset -c 0 wrk -t1 -c"$WRK_CONN" -d"$DUR" --latency -s "$LUA_FILE" "$u/bench/echo")

        read -r tot_end stl_end <<< "$(read_cpu_stat)"

        {
            echo "=================================================================="
            echo "ITERATION $i | ORDER $order_idx | CFG: $cfg | TIME: $(date -Is)"
            echo "=================================================================="
            echo "$out"
            echo ""
        } >> "$RAW_LOG"

        steal_pct=$(awk -v ts="$tot_start" -v te="$tot_end" -v ss="$stl_start" -v se="$stl_end" \
            'BEGIN{dt=te-ts; ds=se-ss; if(dt>0) printf "%.2f", (ds/dt)*100; else print "0.00"}')

        p50=$(to_ms "$(echo "$out" | awk '$1=="50%"{print $2}')")
        p90=$(to_ms "$(echo "$out" | awk '$1=="90%"{print $2}')")
        p99=$(to_ms "$(echo "$out" | awk '$1=="99%"{print $2}')")
        rps=$(echo "$out" | awk '/Requests\/sec:/{print $2}')

        non2xx=$(echo "$out" | awk '/Non-2xx/{print $NF}')
        non2xx=${non2xx:-0}

        sock_line=$(echo "$out" | grep "Socket errors:" || true)
        if [ -n "$sock_line" ]; then
            s_conn=$(echo "$sock_line" | awk '{print $4}' | tr -d ',')
            s_read=$(echo "$sock_line" | awk '{print $6}' | tr -d ',')
            s_writ=$(echo "$sock_line" | awk '{print $8}' | tr -d ',')
            s_time=$(echo "$sock_line" | awk '{print $10}' | tr -d ',')
        else
            s_conn=0; s_read=0; s_writ=0; s_time=0
        fi

        total_err=$(( non2xx + s_conn + s_read + s_writ + s_time ))

        echo "$i,$order_idx,$cfg,$p50,$p90,$p99,$rps,$non2xx,$s_conn,$s_read,$s_writ,$s_time,$total_err,$steal_pct" >> "$CSV_OUTPUT"
        printf "  [%d] %-8s | p50: %6sms | p90: %6sms | p99: %7sms | RPS: %7s | 5xx/4xx: %d | Sock(c/r/w/t): %d/%d/%d/%d | Steal: %s%%\n" \
            "$order_idx" "$cfg" "$p50" "$p90" "$p99" "$rps" "$non2xx" "$s_conn" "$s_read" "$s_writ" "$s_time" "$steal_pct"

        if [ "$total_err" -gt 0 ]; then
            echo "    [WARN] Error detected on run $i ($cfg). Raw wrk output:"
            echo "$out" | sed 's/^/      | /'
        fi

        sleep 1
    done
done

# -----------------------------------------------------------------------------
# 9. Rigorous Statistical & Little's Law Evaluation (Paired Bootstrap 95% CI)
# -----------------------------------------------------------------------------
echo ""
echo "=== Step 8: Statistical & Systems Performance Report ==="
python3 - << 'PYEOF'
import csv
import math
import os
import random
import statistics as stats

csv_path = os.environ["CSV_OUTPUT"]
data = {"direct": {}, "nofilter": {}, "filter": {}}

with open(csv_path) as f:
    reader = csv.DictReader(f)
    for row in reader:
        run_id = int(row["run"])
        cfg = row["cfg"]
        data[cfg][run_id] = {
            "order": int(row["order_idx"]),
            "p50": float(row["p50_ms"]),
            "p90": float(row["p90_ms"]),
            "p99": float(row["p99_ms"]),
            "rps": float(row["rps"]),
            "non2xx": int(row["non2xx"]),
            "s_conn": int(row["sock_connect"]),
            "s_read": int(row["sock_read"]),
            "s_writ": int(row["sock_write"]),
            "s_time": int(row["sock_timeout"]),
            "err": int(row["total_err"]),
            "steal": float(row["steal_pct"]),
        }

runs = sorted(data["filter"].keys())
n_runs = len(runs)

# Exact two-tailed 95% t-critical lookup
t_table = {
    2: 12.706, 3: 4.303, 5: 2.776, 10: 2.262,
    15: 2.145, 20: 2.093, 25: 2.064, 30: 2.045,
    50: 2.009, 100: 1.984
}
t_val = t_table.get(n_runs, 2.045 if n_runs >= 25 else 2.145)

def summarize(arr):
    n = len(arr)
    med = stats.median(arr)
    mean = stats.mean(arr)
    sd = stats.stdev(arr) if n > 1 else 0.0
    ci95 = t_val * (sd / math.sqrt(n)) if n > 1 else 0.0
    s_arr = sorted(arr)
    q25 = s_arr[int(n * 0.25)]
    q75 = s_arr[int(n * 0.75)]
    iqr = q75 - q25
    return med, mean, sd, iqr, ci95, min(arr), max(arr)

def bootstrap_ci(deltas, iterations=10000, seed=42):
    rng = random.Random(seed)
    n = len(deltas)
    if n < 2:
        return (deltas[0], deltas[0]), (deltas[0], deltas[0])
    boot_medians = []
    boot_means = []
    for _ in range(iterations):
        sample = [deltas[rng.randrange(n)] for _ in range(n)]
        boot_medians.append(stats.median(sample))
        boot_means.append(stats.mean(sample))
    boot_medians.sort()
    boot_means.sort()
    lo_idx = int(0.025 * iterations)
    hi_idx = int(0.975 * iterations)
    return (boot_medians[lo_idx], boot_medians[hi_idx]), (boot_means[lo_idx], boot_means[hi_idx])

for metric, unit in [("p50", "ms"), ("p90", "ms"), ("p99", "ms"), ("rps", "req/s")]:
    print(f"\nMetric: {metric.upper()} ({unit}) [n={n_runs}, t={t_val:.3f}]")
    print("-" * 90)
    print(f"{'Configuration':<18} | {'Median':>9} | {'Mean':>9} | {'StdDev':>8} | {'IQR':>8} | {'95% CI(t)':>10} | {'Min/Max':>15}")
    print("-" * 90)
    for cfg, label in [("direct", "Direct (Backend)"), ("nofilter", "Bare Envoy"), ("filter", "Envoy + Wasm")]:
        vals = [data[cfg][r][metric] for r in runs]
        med, mean, sd, iqr, ci95, mn, mx = summarize(vals)
        print(f"{label:<18} | {med:>9.2f} | {mean:>9.2f} | {sd:>8.2f} | {iqr:>8.2f} | {'±'+f'{ci95:.2f}':>10} | {f'{mn:.1f}/{mx:.1f}':>15}")

# Paired per-iteration differences (Envoy+Wasm minus Bare Envoy)
p50_deltas = [data["filter"][r]["p50"] - data["nofilter"][r]["p50"] for r in runs]
p90_deltas = [data["filter"][r]["p90"] - data["nofilter"][r]["p90"] for r in runs]
p99_deltas = [data["filter"][r]["p99"] - data["nofilter"][r]["p99"] for r in runs]
rps_deltas = [data["filter"][r]["rps"] - data["nofilter"][r]["rps"] for r in runs]
rps_pct_deltas = [((data["filter"][r]["rps"] - data["nofilter"][r]["rps"]) / data["nofilter"][r]["rps"]) * 100.0 for r in runs]

p50_med_ci, p50_mean_ci = bootstrap_ci(p50_deltas)
p99_med_ci, p99_mean_ci = bootstrap_ci(p99_deltas)
rps_med_ci, rps_mean_ci = bootstrap_ci(rps_pct_deltas)

print("\n" + "=" * 90)
print("PAIRED DIFFERENCE ANALYSIS (Envoy + Wasm vs. Bare Envoy | 10,000 Bootstrap Resamples)")
print("=" * 90)
print(f"1. Paired p50 Delta : Median {stats.median(p50_deltas):+.2f} ms (95% Boot CI: [{p50_med_ci[0]:+.2f}, {p50_med_ci[1]:+.2f}] ms)")
print(f"                      Mean   {stats.mean(p50_deltas):+.2f} ms (95% Boot CI: [{p50_mean_ci[0]:+.2f}, {p50_mean_ci[1]:+.2f}] ms)")
print(f"2. Paired p99 Delta : Median {stats.median(p99_deltas):+.2f} ms (95% Boot CI: [{p99_med_ci[0]:+.2f}, {p99_med_ci[1]:+.2f}] ms)")
print(f"3. Paired RPS Delta : Median {stats.median(rps_pct_deltas):+.2f}%  (95% Boot CI: [{rps_med_ci[0]:+.2f}%, {rps_med_ci[1]:+.2f}%])")

print("\n" + "-" * 90)
print("LITTLE'S LAW & CLOSED-LOOP SATURATION DYNAMICS (L = RPS * W)")
print("-" * 90)
for cfg, label in [("direct", "Direct (Backend)"), ("nofilter", "Bare Envoy"), ("filter", "Envoy + Wasm")]:
    med_rps = stats.median([data[cfg][r]["rps"] for r in runs])
    med_p50_s = stats.median([data[cfg][r]["p50"] for r in runs]) / 1000.0
    implied_c = med_rps * med_p50_s
    print(f"  {label:<18} -> Median RPS: {med_rps:6.1f} | Median p50: {med_p50_s*1000:6.2f} ms | Implied Active Queue (L): {implied_c:5.2f} conns")

print("\n" + "-" * 90)
print("ERROR & TELEMETRY BREAKDOWN BY CONFIGURATION")
print("-" * 90)
for cfg, label in [("direct", "Direct (Backend)"), ("nofilter", "Bare Envoy"), ("filter", "Envoy + Wasm")]:
    n2xx = sum(data[cfg][r]["non2xx"] for r in runs)
    sc = sum(data[cfg][r]["s_conn"] for r in runs)
    sr = sum(data[cfg][r]["s_read"] for r in runs)
    sw = sum(data[cfg][r]["s_writ"] for r in runs)
    st = sum(data[cfg][r]["s_time"] for r in runs)
    max_stl = max(data[cfg][r]["steal"] for r in runs)
    print(f"  {label:<18} -> Non-2xx: {n2xx} | Socket(connect={sc}, read={sr}, write={sw}, timeout={st}) | Max Steal: {max_stl:.2f}%")
print("=" * 90)
PYEOF
