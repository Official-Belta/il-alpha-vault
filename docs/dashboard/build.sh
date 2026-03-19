#!/bin/bash
# Build dashboard: embed latest metrics.csv into index.html
# Usage: bash docs/dashboard/build.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CSV_FILE="$SCRIPT_DIR/../../keeper/metrics.csv"
TEMPLATE="$SCRIPT_DIR/index.html"
OUTPUT="$SCRIPT_DIR/dashboard.html"

if [ ! -f "$CSV_FILE" ]; then
  echo "No metrics.csv found at $CSV_FILE"
  exit 1
fi

CSV_CONTENT=$(cat "$CSV_FILE")

# Replace CSVDATA placeholder with actual CSV
sed "s|CSVDATA|$CSV_CONTENT|" "$TEMPLATE" > "$OUTPUT"

echo "Dashboard built: $OUTPUT ($(wc -l < "$CSV_FILE") data rows)"
