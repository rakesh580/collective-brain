#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Collective Brain — Start Monitoring Stack
# Usage:
#   ./start-monitoring.sh          # start Prometheus + Grafana + Jaeger
#   ./start-monitoring.sh stop     # stop and remove containers
#   ./start-monitoring.sh status   # show container status
# ─────────────────────────────────────────────────────────────────────────────
set -e

COMPOSE_FILE="docker-compose.observability.yml"
BACKEND_PORT="${CB_BACKEND_PORT:-8000}"

case "${1:-start}" in

  stop)
    echo "Stopping monitoring stack..."
    docker compose -f "$COMPOSE_FILE" down
    echo "Done."
    exit 0
    ;;

  status)
    docker compose -f "$COMPOSE_FILE" ps
    exit 0
    ;;

  start|*)
    ;;
esac

# ── Step 1: Ensure Docker daemon is running ──────────────────────────────────
if ! docker info > /dev/null 2>&1; then
  echo "Docker daemon is not running. Starting Docker Desktop..."
  open -a Docker
  echo -n "Waiting for Docker to start"
  for i in $(seq 1 30); do
    sleep 2
    if docker info > /dev/null 2>&1; then
      echo " ready."
      break
    fi
    echo -n "."
    if [ "$i" -eq 30 ]; then
      echo ""
      echo "ERROR: Docker did not start within 60 seconds."
      echo "Please open Docker Desktop manually, then run this script again."
      exit 1
    fi
  done
fi

# ── Step 2: Confirm backend is running and /metrics is reachable ─────────────
echo "Checking backend at http://localhost:${BACKEND_PORT}/metrics..."
if curl -s --max-time 3 "http://localhost:${BACKEND_PORT}/metrics" > /dev/null 2>&1; then
  echo "Backend /metrics: reachable ✓"
else
  echo ""
  echo "WARNING: Backend not reachable at http://localhost:${BACKEND_PORT}/metrics"
  echo "Start it first with:"
  echo "  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload"
  echo ""
  echo "Prometheus will keep retrying — starting stack anyway..."
fi

# ── Step 3: Start Prometheus + Grafana + Jaeger ──────────────────────────────
echo "Starting monitoring stack..."
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

# ── Step 4: Wait for services ────────────────────────────────────────────────
echo -n "Waiting for Grafana"
for i in $(seq 1 20); do
  sleep 2
  if curl -s --max-time 2 http://localhost:3001/api/health > /dev/null 2>&1; then
    echo " ready."
    break
  fi
  echo -n "."
done

echo -n "Waiting for Prometheus"
for i in $(seq 1 15); do
  sleep 2
  if curl -s --max-time 2 http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo " ready."
    break
  fi
  echo -n "."
done

# ── Step 5: Show status ───────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────────────"
echo " Monitoring stack is running:"
echo ""
echo "  Grafana:    http://localhost:3001  (admin / admin)"
echo "  Prometheus: http://localhost:9090"
echo "  Jaeger:     http://localhost:16686"
echo ""
echo "  To enable trace export from backend, add to backend/.env:"
echo "    CB_OTEL_ENDPOINT=http://localhost:4317"
echo ""
echo "  To stop: ./start-monitoring.sh stop"
echo "────────────────────────────────────────────────"
