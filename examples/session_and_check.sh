#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Numerisect API from curl. Every /api route except /api/session needs the token.
set -euo pipefail
BASE="${NUMERISECT_URL:-http://127.0.0.1:8765}"
JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT

curl --silent --cookie-jar "$JAR" "$BASE/api/session" > /dev/null
curl --silent --cookie "$JAR" \
  --header 'Content-Type: application/json' \
  --data '{"expression":"32416190071","mode":"proven"}' \
  "$BASE/api/primes/check"
echo
