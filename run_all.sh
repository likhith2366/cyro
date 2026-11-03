#!/usr/bin/env bash
# Runs every processing script in order. Outputs go to data/processed/ and output/samples/.
set -euo pipefail
cd "$(dirname "$0")/scripts"

python q1_q3_crz_entries.py
python q2_bt_crossings.py
python q4_speeds.py
python q5_q7_collisions.py
python q6_subway.py
python q6_citibike.py
python q8_summary.py

echo "Done. Sample tables for the report are in output/samples/"
