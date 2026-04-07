#!/usr/bin/env bash
# =============================================================================
# verify_contract.sh — LOCAL server OpenEnv contract smoke test
# =============================================================================
# Usage:
#   bash scripts/verify_contract.sh                  # starts server, tests, stops it
#   SERVER_RUNNING=1 bash scripts/verify_contract.sh # skip start (server already up)
#   PORT=8001 bash scripts/verify_contract.sh
# =============================================================================
set -euo pipefail

PORT="${PORT:-8000}"
BASE="http://localhost:${PORT}"
SERVER_RUNNING="${SERVER_RUNNING:-0}"
SERVER_PID=""
PASS=0
FAIL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  ✔ $1${NC}"; ((PASS++)); }
fail() { echo -e "${RED}  ✘ $1${NC}"; ((FAIL++)); }
info() { echo -e "${YELLOW}→ $1${NC}"; }

# ── helpers ──────────────────────────────────────────────────────────────────

require_key() {
  local label="$1" json="$2" key="$3"
  if echo "$json" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$key' in d, '$key missing'" 2>/dev/null; then
    ok "$label: key '$key' present"
  else
    fail "$label: key '$key' MISSING in response"
    echo "    Response was: $json"
  fi
}

require_type() {
  local label="$1" json="$2" key="$3" expected_type="$4"
  if echo "$json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
val = d.get('$key')
t = type(val).__name__
assert t == '$expected_type', f'Expected $expected_type, got {t} (value={val})'
" 2>/dev/null; then
    ok "$label: '$key' is $expected_type"
  else
    actual=$(echo "$json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(type(d.get('$key')).__name__)" 2>/dev/null || echo "parse-error")
    fail "$label: '$key' should be $expected_type, got '$actual'"
    echo "    Response was: $json"
  fi
}

require_nested_key() {
  local label="$1" json="$2" outer="$3" inner="$4"
  if echo "$json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert '$outer' in d, '$outer missing'
assert '$inner' in d['$outer'], '$inner missing in $outer'
" 2>/dev/null; then
    ok "$label: $outer.$inner present"
  else
    fail "$label: $outer.$inner MISSING"
    echo "    Response was: $json"
  fi
}

wait_for_server() {
  info "Waiting for server on $BASE …"
  for i in $(seq 1 20); do
    if curl -sf "$BASE/health" >/dev/null 2>&1; then
      ok "Server is up (attempt $i)"
      return 0
    fi
    sleep 1
  done
  fail "Server did not start within 20 seconds"
  return 1
}

# ── server lifecycle ──────────────────────────────────────────────────────────

if [[ "$SERVER_RUNNING" == "0" ]]; then
  info "Starting local server (uvicorn) …"
  # Must be run from repo root so examples/ is resolvable
  REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  cd "$REPO_ROOT"

  # Activate venv if present
  if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
  fi

  # Start server in background, redirect logs to /tmp/server.log
  cd bugtriage_env
  uvicorn server.app:app --host 0.0.0.0 --port "$PORT" > /tmp/bugtriage_server.log 2>&1 &
  SERVER_PID=$!
  cd ..

  # Ensure we kill the server on exit
  trap 'kill $SERVER_PID 2>/dev/null && echo "Server stopped."' EXIT

  wait_for_server || { cat /tmp/bugtriage_server.log; exit 1; }
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo " A) HEALTH ENDPOINT"
echo "═══════════════════════════════════════════════════════"

HEALTH=$(curl -sf "$BASE/health" || echo '{}')
info "GET /health → $HEALTH"
if echo "$HEALTH" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
  ok "/health returns valid JSON"
else
  fail "/health did not return valid JSON"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo " B) RESET ENDPOINT"
echo "═══════════════════════════════════════════════════════"

RESET=$(curl -sf -X POST "$BASE/reset" \
  -H "Content-Type: application/json" \
  -d '{}')
info "POST /reset response:"
echo "$RESET" | python3 -m json.tool 2>/dev/null || echo "$RESET"

# The OpenEnv HTTP server wraps the observation in a top-level key.
# Depending on openenv version, reset response may be:
#   { "observation": {...} }  OR  the observation dict directly.
# We detect which format we have:
HAS_OBS_WRAPPER=$(echo "$RESET" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if 'observation' in d else 'no')" 2>/dev/null || echo "no")

if [[ "$HAS_OBS_WRAPPER" == "yes" ]]; then
  OBS=$(echo "$RESET" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['observation']))")
  require_key "reset/observation" "$OBS" "issue_id"
  require_key "reset/observation" "$OBS" "title"
  require_key "reset/observation" "$OBS" "description"
  require_key "reset/observation" "$OBS" "step_count"
  require_key "reset/observation" "$OBS" "max_steps"
  require_key "reset/observation" "$OBS" "available_actions"
  require_type "reset/observation" "$OBS" "step_count" "int"
  require_type "reset/observation" "$OBS" "attachments_present" "bool"
  ok "reset wraps observation in 'observation' key (OpenEnv format)"
else
  # Flat format — observation fields at top level
  require_key "reset (flat)" "$RESET" "issue_id"
  require_key "reset (flat)" "$RESET" "title"
  require_key "reset (flat)" "$RESET" "step_count"
  ok "reset returns flat observation (check openenv version)"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo " C) STEP ENDPOINT"
echo "═══════════════════════════════════════════════════════"

# Step 1: SetClassification
STEP1=$(curl -sf -X POST "$BASE/step" \
  -H "Content-Type: application/json" \
  -d '{"action_type":"SetClassification","issue_type":"bug"}')
info "POST /step (SetClassification) response:"
echo "$STEP1" | python3 -m json.tool 2>/dev/null || echo "$STEP1"

require_key "step" "$STEP1" "observation"
require_key "step" "$STEP1" "reward"
require_key "step" "$STEP1" "done"
require_key "step" "$STEP1" "info"
require_type "step" "$STEP1" "reward" "float"
require_type "step" "$STEP1" "done" "bool"

INFO_TYPE=$(echo "$STEP1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(type(d.get('info')).__name__)" 2>/dev/null || echo "missing")
if [[ "$INFO_TYPE" == "dict" ]]; then ok "step: info is dict"; else fail "step: info should be dict, got $INFO_TYPE"; fi

# Step 2: SetSeverity
STEP2=$(curl -sf -X POST "$BASE/step" \
  -H "Content-Type: application/json" \
  -d '{"action_type":"SetSeverity","severity":"S2_minor"}')
require_key "step2" "$STEP2" "reward"
require_type "step2" "$STEP2" "reward" "float"
ok "step2 (SetSeverity) has numeric reward"

# Step 3: AssignComponent
STEP3=$(curl -sf -X POST "$BASE/step" \
  -H "Content-Type: application/json" \
  -d '{"action_type":"AssignComponent","component":"backend"}')
require_key "step3" "$STEP3" "reward"
ok "step3 (AssignComponent) accepted"

# Step 4: ProposeNextAction
STEP4=$(curl -sf -X POST "$BASE/step" \
  -H "Content-Type: application/json" \
  -d '{"action_type":"ProposeNextAction","next_action":"schedule_next_sprint"}')
require_key "step4" "$STEP4" "reward"
ok "step4 (ProposeNextAction) accepted"

# Step 5: SubmitTriage (terminal)
STEP5=$(curl -sf -X POST "$BASE/step" \
  -H "Content-Type: application/json" \
  -d '{
    "action_type":"SubmitTriage",
    "summary":"Cache invalidation bug after email update. Recommend scheduling a fix for next sprint.",
    "final_decision":{
      "issue_type":"bug",
      "severity":"S2_minor",
      "component":"backend",
      "next_action":"schedule_next_sprint"
    }
  }')
info "POST /step (SubmitTriage — terminal) response:"
echo "$STEP5" | python3 -m json.tool 2>/dev/null || echo "$STEP5"

require_key "SubmitTriage" "$STEP5" "done"
DONE_VAL=$(echo "$STEP5" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('done'))" 2>/dev/null || echo "false")
if [[ "$DONE_VAL" == "True" ]] || [[ "$DONE_VAL" == "true" ]]; then
  ok "SubmitTriage: done=true ✔"
else
  fail "SubmitTriage: expected done=true, got done=$DONE_VAL"
fi

# final_score must be in info when done=True
INFO_HAS_FINAL=$(echo "$STEP5" | python3 -c "
import sys, json
d = json.load(sys.stdin)
done = d.get('done', False)
if done:
    info = d.get('info', {})
    assert 'final_score' in info, 'final_score missing from info when done=True'
    fs = info['final_score']
    assert isinstance(fs, (int, float)), f'final_score must be numeric, got {type(fs)}'
    assert 0.0 <= fs <= 1.0, f'final_score out of range: {fs}'
    print(f'OK: final_score={fs}')
else:
    print('SKIP: not done yet')
" 2>/dev/null || echo "ERROR")

if echo "$INFO_HAS_FINAL" | grep -q "OK:"; then
  ok "final_score in info when done=True → $INFO_HAS_FINAL"
elif echo "$INFO_HAS_FINAL" | grep -q "SKIP:"; then
  info "Skipped final_score check (done=False)"
else
  fail "final_score check failed: $INFO_HAS_FINAL"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo " D) STATE ENDPOINT"
echo "═══════════════════════════════════════════════════════"

# Reset first for a clean state check
curl -sf -X POST "$BASE/reset" -H "Content-Type: application/json" -d '{}' > /dev/null
STATE=$(curl -sf "$BASE/state" || echo '{}')
info "GET /state → $(echo "$STATE" | python3 -m json.tool 2>/dev/null)"

require_key "state" "$STATE" "episode_id"
require_key "state" "$STATE" "step_count"

echo ""
echo "═══════════════════════════════════════════════════════"
echo " E) RESET CLEARS STATE (no carry-over)"
echo "═══════════════════════════════════════════════════════"

# Episode 1: reset → take a step
curl -sf -X POST "$BASE/reset" -H "Content-Type: application/json" -d '{}' > /dev/null
curl -sf -X POST "$BASE/step" -H "Content-Type: application/json" \
  -d '{"action_type":"SetClassification","issue_type":"bug"}' > /dev/null
STATE1=$(curl -sf "$BASE/state")
STEP1_CNT=$(echo "$STATE1" | python3 -c "import sys,json; print(json.load(sys.stdin).get('step_count',0))")
EPID1=$(echo "$STATE1" | python3 -c "import sys,json; print(json.load(sys.stdin).get('episode_id',''))")

# Episode 2: reset → check state
curl -sf -X POST "$BASE/reset" -H "Content-Type: application/json" -d '{}' > /dev/null
STATE2=$(curl -sf "$BASE/state")
STEP2_CNT=$(echo "$STATE2" | python3 -c "import sys,json; print(json.load(sys.stdin).get('step_count',0))")
EPID2=$(echo "$STATE2" | python3 -c "import sys,json; print(json.load(sys.stdin).get('episode_id',''))")

if [[ "$STEP2_CNT" == "0" ]]; then
  ok "Reset clears step_count (ep1 step=$STEP1_CNT → ep2 step=$STEP2_CNT)"
else
  fail "step_count NOT cleared after reset: got $STEP2_CNT (expected 0)"
fi

if [[ "$EPID1" != "$EPID2" ]]; then
  ok "New episode_id on reset ($EPID1 → $EPID2)"
else
  fail "episode_id did not change after reset! Both are: $EPID1"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo " SUMMARY"
echo "═══════════════════════════════════════════════════════"
TOTAL=$((PASS + FAIL))
echo -e "${GREEN}Passed: $PASS / $TOTAL${NC}"
if [[ $FAIL -gt 0 ]]; then
  echo -e "${RED}Failed: $FAIL / $TOTAL${NC}"
  echo ""
  echo "Check /tmp/bugtriage_server.log for server logs."
  exit 1
else
  echo -e "${GREEN}All checks passed! ✔${NC}"
fi
