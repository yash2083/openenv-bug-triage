#!/usr/bin/env bash
# =============================================================================
# verify_docker.sh — Docker build + run + contract smoke test
# =============================================================================
# Usage (from repo root):
#   bash scripts/verify_docker.sh
#   IMAGE_NAME=my-image PORT=8080 bash scripts/verify_docker.sh
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

IMAGE_NAME="${IMAGE_NAME:-antigravity-bugtriage}"
PORT="${PORT:-8000}"
CONTAINER_NAME="bugtriage-verify-$$"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  ✔ $1${NC}"; }
fail() { echo -e "${RED}  ✘ $1${NC}"; exit 1; }
info() { echo -e "${YELLOW}→ $1${NC}"; }

cleanup() {
  info "Stopping container $CONTAINER_NAME …"
  docker stop "$CONTAINER_NAME" 2>/dev/null || true
  docker rm "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT

# ── 1. Docker daemon check ────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo " 1. DOCKER DAEMON CHECK"
echo "═══════════════════════════════════════════════════════"
if docker info >/dev/null 2>&1; then
  ok "Docker daemon is running"
else
  fail "Docker daemon is NOT running. Start Docker Desktop and retry."
fi

# ── 2. Docker build ───────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo " 2. DOCKER BUILD"
echo "═══════════════════════════════════════════════════════"
info "Build context: $REPO_ROOT/bugtriage_env"
info "Dockerfile:    bugtriage_env/server/Dockerfile"
info "Image name:    $IMAGE_NAME"

# IMPORTANT: Build context is bugtriage_env/ not repo root.
# The Dockerfile does COPY . /app/env which copies from the build context.
# examples/ is at repo root, so we copy it into the build context first as a
# temporary workaround OR we use repo root as context with adjusted COPY.
#
# We use bugtriage_env/ as the primary context, then bind-mount examples/ at
# docker run time. For build, we use --build-context if BuildKit supports it.
# Simplest cross-platform approach: build from bugtriage_env/, copy examples
# alongside before building.

# Copy examples/ temporarily into bugtriage_env/ for build context
info "Copying examples/ into build context (bugtriage_env/examples_tmp/) …"
if [[ -d "$REPO_ROOT/examples" ]]; then
  cp -r "$REPO_ROOT/examples" "$REPO_ROOT/bugtriage_env/examples_tmp"
  COPIED_EXAMPLES=1
else
  COPIED_EXAMPLES=0
  info "No examples/ directory found at repo root — skipping copy"
fi

BUILD_EXIT=0
docker build \
  -f bugtriage_env/server/Dockerfile \
  -t "$IMAGE_NAME" \
  bugtriage_env/ 2>&1 | tee /tmp/docker_build.log || BUILD_EXIT=$?

# Clean up temporary copy
if [[ "$COPIED_EXAMPLES" == "1" ]]; then
  rm -rf "$REPO_ROOT/bugtriage_env/examples_tmp"
fi

if [[ $BUILD_EXIT -eq 0 ]]; then
  ok "docker build succeeded → $IMAGE_NAME"
else
  fail "docker build FAILED (exit $BUILD_EXIT). See /tmp/docker_build.log"
fi

# ── 3. Docker run ─────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo " 3. DOCKER RUN"
echo "═══════════════════════════════════════════════════════"
info "Starting container $CONTAINER_NAME on port $PORT …"

docker run -d \
  --name "$CONTAINER_NAME" \
  -p "${PORT}:8000" \
  -v "$REPO_ROOT/examples:/app/env/examples:ro" \
  "$IMAGE_NAME" > /tmp/container_id.txt

ok "Container started: $(cat /tmp/container_id.txt | head -c 12)"

# Wait for health
info "Waiting for container to become healthy …"
BASE="http://localhost:${PORT}"
READY=0
for i in $(seq 1 30); do
  if curl -sf "$BASE/health" >/dev/null 2>&1; then
    READY=1
    ok "Container healthy after ${i}s"
    break
  fi
  sleep 1
done

if [[ $READY -eq 0 ]]; then
  echo "--- Container logs ---"
  docker logs "$CONTAINER_NAME"
  fail "Container did not become healthy within 30 seconds"
fi

# ── 4. Contract checks inside container ──────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo " 4. CONTRACT CHECKS (in-container)"
echo "═══════════════════════════════════════════════════════"

check_key() {
  local label="$1" json="$2" key="$3"
  if echo "$json" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$key' in d" 2>/dev/null; then
    ok "$label: '$key' present"
  else
    echo -e "${RED}  ✘ $label: '$key' MISSING${NC}"
    echo "    Response: $json"
    return 1
  fi
}

# GET /health
HEALTH=$(curl -sf "$BASE/health")
info "GET /health → $HEALTH"
if echo "$HEALTH" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
  ok "/health returns valid JSON"
else
  fail "/health returned non-JSON: $HEALTH"
fi

# POST /reset
RESET=$(curl -sf -X POST "$BASE/reset" \
  -H "Content-Type: application/json" \
  -d '{}')
info "POST /reset → $(echo "$RESET" | python3 -m json.tool 2>/dev/null || echo $RESET)"

# Determine wrapper format
HAS_OBS=$(echo "$RESET" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if 'observation' in d else 'no')" 2>/dev/null)
if [[ "$HAS_OBS" == "yes" ]]; then
  OBS=$(echo "$RESET" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['observation']))")
else
  OBS="$RESET"
fi
check_key "reset observation" "$OBS" "issue_id"
check_key "reset observation" "$OBS" "step_count"
check_key "reset observation" "$OBS" "available_actions"
ok "reset response has required observation fields"

# POST /step
STEP=$(curl -sf -X POST "$BASE/step" \
  -H "Content-Type: application/json" \
  -d '{"action_type":"SetClassification","issue_type":"bug"}')
info "POST /step → $(echo "$STEP" | python3 -m json.tool 2>/dev/null || echo $STEP)"
check_key "step" "$STEP" "observation"
check_key "step" "$STEP" "reward"
check_key "step" "$STEP" "done"
check_key "step" "$STEP" "info"

# Verify reward is numeric
REWARD_OK=$(echo "$STEP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
r=d.get('reward')
assert isinstance(r, (int,float)), f'reward is {type(r)}'
print('ok')
" 2>/dev/null || echo "fail")
if [[ "$REWARD_OK" == "ok" ]]; then
  ok "step: reward is numeric float"
else
  echo -e "${RED}  ✘ step: reward is not numeric${NC}"
fi

# GET /state
STATE=$(curl -sf "$BASE/state")
check_key "state" "$STATE" "episode_id"
check_key "state" "$STATE" "step_count"

echo ""
echo "═══════════════════════════════════════════════════════"
echo " 5. DOCKER IMAGE SIZE"
echo "═══════════════════════════════════════════════════════"
SIZE=$(docker image inspect "$IMAGE_NAME" --format '{{.Size}}' 2>/dev/null || echo "unknown")
SIZE_MB=$(echo "$SIZE" | python3 -c "import sys; s=sys.stdin.read().strip(); print(f'{int(s)/1024/1024:.1f} MB')" 2>/dev/null || echo "$SIZE bytes")
info "Image size: $SIZE_MB"
ok "Build complete: $IMAGE_NAME ($SIZE_MB)"

echo ""
echo "═══════════════════════════════════════════════════════"
echo " ALL DOCKER CHECKS PASSED ✔"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Container will be stopped and removed on script exit."
echo "To keep it running: kill this script with Ctrl+C, then run:"
echo "  docker logs $CONTAINER_NAME"
