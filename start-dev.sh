#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# ─── Colors ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[start-dev]${NC} $*"; }
warn() { echo -e "${YELLOW}[start-dev]${NC} $*"; }
err()  { echo -e "${RED}[start-dev]${NC} $*"; }

# ─── Cleanup on exit ──────────────────────────────────────────────────────────
FRONTEND_PID=""
cleanup() {
  echo ""
  log "Shutting down..."
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    log "Stopping frontend (PID $FRONTEND_PID)..."
    kill "$FRONTEND_PID"
  fi
  log "Done. Backend containers are still running (use 'docker compose down' to stop them)."
}
trap cleanup EXIT INT TERM

# ─── 1. Check dependencies ────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  err "Docker not found. Please install Docker Desktop."
  exit 1
fi

if ! command -v npm &>/dev/null; then
  err "npm not found. Please install Node.js."
  exit 1
fi

# ─── 2. Start backend via Docker Compose ──────────────────────────────────────
log "Starting backend services (docker compose)..."
cd "$PROJECT_ROOT"
docker compose up -d --remove-orphans

log "Waiting for API to be ready..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health &>/dev/null || \
     curl -sf http://localhost:8000/docs  &>/dev/null || \
     curl -sf http://localhost:8000/      &>/dev/null; then
    log "API is ready at http://localhost:8000"
    break
  fi
  if [ "$i" -eq 30 ]; then
    warn "API health check timed out, but continuing anyway..."
  fi
  sleep 1
done

# ─── 3. Install frontend dependencies if needed ───────────────────────────────
cd "$FRONTEND_DIR"
if [ ! -d node_modules ]; then
  log "Installing frontend dependencies (npm install)..."
  npm install
fi

# ─── 4. Start frontend ────────────────────────────────────────────────────────
log "Starting frontend (Next.js dev server)..."
npm run dev &
FRONTEND_PID=$!

# ─── 5. Print summary ─────────────────────────────────────────────────────────
sleep 2
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Star Pulse - Dev Environment Ready${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Frontend UI   →  http://localhost:3000"
echo -e "  Backend API   →  http://localhost:8000"
echo -e "  API Docs      →  http://localhost:8000/docs"
echo -e "  RabbitMQ UI   →  http://localhost:15672"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Press Ctrl+C to stop the frontend (backend containers keep running)."
echo ""

# ─── 6. Wait for frontend to exit ────────────────────────────────────────────
wait "$FRONTEND_PID"
