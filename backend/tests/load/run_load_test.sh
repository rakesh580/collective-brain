#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Collective Brain - Locust Load Test Runner
#
# Usage:
#   ./run_load_test.sh [HOST] [USERS] [DURATION_SECONDS] [SPAWN_RATE]
#
# Examples:
#   ./run_load_test.sh                                    # defaults
#   ./run_load_test.sh http://localhost:8000 50 60         # 50 users, 60s
#   ./run_load_test.sh https://staging.example.com 100 120 10
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

HOST="${1:-http://localhost:8000}"
USERS="${2:-50}"
DURATION="${3:-60}"
SPAWN_RATE="${4:-5}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCUSTFILE="${SCRIPT_DIR}/locustfile.py"
RESULTS_DIR="${SCRIPT_DIR}/results"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
CSV_PREFIX="${RESULTS_DIR}/${TIMESTAMP}"

# Ensure results directory exists
mkdir -p "${RESULTS_DIR}"

echo "======================================================================"
echo "  Collective Brain Load Test"
echo "======================================================================"
echo "  Host:        ${HOST}"
echo "  Users:       ${USERS}"
echo "  Spawn rate:  ${SPAWN_RATE} users/sec"
echo "  Duration:    ${DURATION}s"
echo "  Locustfile:  ${LOCUSTFILE}"
echo "  CSV output:  ${CSV_PREFIX}_*.csv"
echo "======================================================================"
echo ""

# Verify locust is installed
if ! command -v locust &>/dev/null; then
    echo "ERROR: locust is not installed."
    echo "  Install with: pip install locust"
    exit 1
fi

# Verify the target host is reachable
echo "Checking host connectivity..."
if ! curl -sf --max-time 5 "${HOST}/api/v1/health" >/dev/null 2>&1; then
    echo "WARNING: ${HOST}/api/v1/health did not respond. The server may not be running."
    echo "  Start it with: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"
    read -rp "Continue anyway? [y/N] " answer
    if [[ "${answer}" != "y" && "${answer}" != "Y" ]]; then
        exit 1
    fi
fi

echo ""
echo "Starting load test..."
echo ""

locust \
    -f "${LOCUSTFILE}" \
    --host "${HOST}" \
    --users "${USERS}" \
    --spawn-rate "${SPAWN_RATE}" \
    --run-time "${DURATION}s" \
    --headless \
    --csv "${CSV_PREFIX}" \
    --csv-full-history \
    --html "${RESULTS_DIR}/${TIMESTAMP}_report.html" \
    --print-stats \
    --only-summary

EXIT_CODE=$?

echo ""
echo "======================================================================"
echo "  Results saved to:"
echo "    CSV stats:     ${CSV_PREFIX}_stats.csv"
echo "    CSV history:   ${CSV_PREFIX}_stats_history.csv"
echo "    CSV failures:  ${CSV_PREFIX}_failures.csv"
echo "    HTML report:   ${RESULTS_DIR}/${TIMESTAMP}_report.html"
echo "======================================================================"

# Print a quick pass/fail summary based on error rate
if [[ -f "${CSV_PREFIX}_stats.csv" ]]; then
    echo ""
    echo "  Quick Summary (from CSV):"
    # The last row of _stats.csv is the "Aggregated" total
    TOTAL_LINE="$(tail -1 "${CSV_PREFIX}_stats.csv")"
    echo "    ${TOTAL_LINE}" | awk -F',' '{
        requests = $3;
        failures = $4;
        median   = $6;
        p95      = $9;
        p99      = $10;
        if (requests > 0) {
            err_pct = (failures / requests) * 100;
        } else {
            err_pct = 0;
        }
        printf "    Requests:  %s\n", requests;
        printf "    Failures:  %s (%.2f%%)\n", failures, err_pct;
        printf "    Median:    %sms\n", median;
        printf "    p95:       %sms\n", p95;
        printf "    p99:       %sms\n", p99;
        if (err_pct > 1) {
            printf "\n    RESULT: FAIL (error rate %.2f%% > 1%%)\n", err_pct;
        } else if (p95 > 1000) {
            printf "\n    RESULT: WARN (p95 %sms > 1000ms target)\n", p95;
        } else {
            printf "\n    RESULT: PASS\n";
        }
    }'
fi

exit ${EXIT_CODE}
