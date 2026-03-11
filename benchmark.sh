#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python"

NUM_REQUESTS="${1:-10}"
MIN_CHUNK="${2:-500}"
MAX_CHUNK="${3:-1000}"
TIMEOUT="${4:-120}"

PORT=1936

wait_for_server() {
    for _ in $(seq 1 20); do
        "$PYTHON" -c "import socket; s=socket.create_connection(('127.0.0.1', $PORT), timeout=1); s.close()" 2>/dev/null && return 0
        sleep 0.5
    done
    echo "ERROR: Server did not start." && return 1
}

kill_server() {
    [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null && kill -INT "$SERVER_PID" 2>/dev/null && wait "$SERVER_PID" 2>/dev/null || true
    [[ -n "${TEST_PID:-}" ]] && kill -0 "$TEST_PID" 2>/dev/null && kill "$TEST_PID" 2>/dev/null || true
}

run_benchmark() {
    local gil_value="$1" label="$2"
    export PYTHON_GIL="$gil_value"

    "$PYTHON" server.py &
    SERVER_PID=$!
    trap kill_server EXIT

    wait_for_server
    sleep 1

    local start_ts end_ts
    start_ts=$("$PYTHON" -c "import time; print(time.time())")

    "$PYTHON" test_load.py "$NUM_REQUESTS" --chunk-size "$MIN_CHUNK" "$MAX_CHUNK" 2>&1 | tail -2 &
    TEST_PID=$!

    local waited=0
    while kill -0 "$TEST_PID" 2>/dev/null; do
        sleep 1
        waited=$((waited + 1))
        if [[ $waited -ge $TIMEOUT ]]; then
            echo "  $label: TIMEOUT (>${TIMEOUT}s)"
            kill "$TEST_PID" 2>/dev/null || true
            kill_server
            trap - EXIT
            TEST_PID=""
            sleep 1
            ELAPSED="TIMEOUT"
            return
        fi
    done
    wait "$TEST_PID" 2>/dev/null || true
    TEST_PID=""

    end_ts=$("$PYTHON" -c "import time; print(time.time())")

    kill_server
    trap - EXIT
    sleep 1

    ELAPSED=$("$PYTHON" -c "print(round($end_ts - $start_ts, 3))")
    echo "  $label: ${ELAPSED}s"
}

echo "Benchmark: $NUM_REQUESTS requests, chunk $MIN_CHUNK-$MAX_CHUNK words (timeout: ${TIMEOUT}s)"
echo ""

run_benchmark 0 "No GIL"
NO_GIL_TIME="$ELAPSED"

run_benchmark 1 "With GIL"
GIL_TIME="$ELAPSED"

echo ""
if [[ "$NO_GIL_TIME" == "TIMEOUT" || "$GIL_TIME" == "TIMEOUT" ]]; then
    echo "  No GIL : $NO_GIL_TIME"
    echo "  With GIL : $GIL_TIME"
else
    SPEEDUP=$("$PYTHON" -c "print(f'{$GIL_TIME / $NO_GIL_TIME:.2f}x') if $NO_GIL_TIME > 0 else print('N/A')")
    echo "  No GIL : ${NO_GIL_TIME}s"
    echo "  With GIL : ${GIL_TIME}s"
    echo "  Speedup (GIL / No-GIL): $SPEEDUP"
fi
