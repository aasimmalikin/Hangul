#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-}}"
if [[ -z "$BASE_URL" ]]; then
  echo "usage: smoke_test.sh <base-url-or-alb-dns>" >&2
  exit 2
fi
[[ "$BASE_URL" =~ ^https?:// ]] || BASE_URL="http://$BASE_URL"

echo "→ health check"
code=$(curl -fsS -o /dev/null -w '%{http_code}' "$BASE_URL/healthz")
[[ "$code" == "200" ]] || { echo "healthz returned $code" >&2; exit 1; }
echo "  ok"

echo "→ ask"
resp=$(curl -fsS -X POST "$BASE_URL/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"does the pipeline work?"}')
echo "  $resp"
echo "$resp" | grep -q '"answer"' || { echo "no answer field in response" >&2; exit 1; }

echo "✓ smoke test passed"
